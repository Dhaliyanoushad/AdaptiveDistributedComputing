"""Run isolated real image batches against a separately configured Master."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import platform
import time
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image
import psutil
import requests

from benchmarks.workload import inspect_workload, fingerprint
from benchmarks.metrics import summarize_tasks, task_metrics


def validate_parameters(operation, params):
    if operation not in {'grayscale','resize','gaussian_blur','edge_detection'} or not isinstance(params,dict):
        raise ValueError('Operation must be supported and parameters must be a JSON object')
    allowed = {'grayscale':{},'resize':{'width':(1,4096),'height':(1,4096)},
               'gaussian_blur':{'kernel_size':(1,99)},'edge_detection':{'threshold1':(0,255),'threshold2':(0,255)}}[operation]
    values = ({'kernel_size':5} if operation=='gaussian_blur' else {'threshold1':100,'threshold2':200} if operation=='edge_detection' else {}) | params
    if set(values)!=set(allowed):
        raise ValueError('Missing or unknown operation parameters')
    for key,(low,high) in allowed.items():
        if type(values[key]) is not int or not low<=values[key]<=high:
            raise ValueError(f'Invalid {key}')
    if operation=='resize' and values['width']*values['height']>16000000 or operation=='gaussian_blur' and values['kernel_size']%2==0 or operation=='edge_detection' and values['threshold1']>values['threshold2']:
        raise ValueError('Invalid operation parameters')
    return values


class HTTPClient:
    def __init__(self, base_url):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Master URL must be HTTP(S), without credentials/query/fragment')
        self.url = base_url.rstrip('/')
        self.deadline = None

    def set_deadline(self, value):
        self.deadline = value

    def request_timeout(self, read_seconds=10):
        remaining = self.deadline-time.monotonic() if self.deadline is not None else read_seconds
        if remaining<=0:
            raise TimeoutError('Benchmark HTTP deadline exceeded')
        return min(3,remaining),min(read_seconds,remaining)

    def get(self, path):
        response = requests.get(self.url+path,timeout=self.request_timeout())
        response.raise_for_status()
        return response.json()

    def upload(self, directory, items, operation, params):
        with ExitStack() as stack:
            files = [('files',(item['filename'],stack.enter_context((directory/item['filename']).open('rb')),
                        'image/png' if item['filename'].lower().endswith('.png') else 'image/jpeg')) for item in items]
            response = requests.post(self.url+'/images/tasks',files=files,data={'operation':operation,'params':json.dumps(params)},timeout=self.request_timeout(30))
            response.raise_for_status()
            return response.json()

    def result(self, task_id):
        with requests.get(self.url+f'/tasks/{task_id}/result/download',timeout=self.request_timeout(),stream=True) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(65536):
                self.request_timeout()
                data.extend(chunk)
                if len(data)>10*1024*1024:
                    raise ValueError('Result exceeds image byte limit')
            return bytes(data)


def verify_topology(workers, expected):
    online = {worker['worker_id'] for worker in workers if worker['status']=='online'}
    if online!=set(expected):
        raise ValueError(f'Expected online workers {sorted(expected)}, observed {sorted(online)}')


def run_trial(client, directory, manifest, *, mode, workers, operation, params, environment,
              timeout=300, warmup=False, clock=time.monotonic, sleep=time.sleep, poll_interval=1, output_dir=Path('benchmarks/results')):
    if hasattr(client,'set_deadline'):
        client.set_deadline(None)
    if mode not in {'single','static','adaptive'} or not workers or len(set(workers))!=len(workers) or (mode=='single' and len(workers)!=1) or (mode!='single' and len(workers)<2):
        raise ValueError('single requires one unique worker; distributed modes require at least two')
    if not math.isfinite(timeout) or timeout<=0 or not math.isfinite(poll_interval) or poll_interval<=0:
        raise ValueError('Timeout and poll interval must be finite and positive')
    params = validate_parameters(operation,params)
    if not isinstance(environment,dict) or not environment.get('experiment_id') or not environment.get('network') or not all(environment.get('workers',{}).get(key) for key in workers):
        raise ValueError('Environment requires experiment_id, network and hardware entries for every expected worker')
    configuration = client.get('/scheduler')['configuration']
    if configuration['mode']!=('static' if mode=='single' else mode):
        raise ValueError('Master scheduler mode does not match; restart a separate isolated Master')
    initial_workers = client.get('/workers')
    verify_topology(initial_workers,workers)
    if 'REPLACE' in json.dumps(environment):
        raise ValueError('Replace all environment template placeholders with actual observations')
    for worker_id in workers:
        hardware = environment['workers'][worker_id]
        if not isinstance(hardware,dict) or not all(hardware.get(key) for key in ['physical_device','hostname','cpu','ram_mb','python','opencv']):
            raise ValueError(f'Incomplete hardware metadata for {worker_id}')
        if type(hardware['ram_mb']) not in {int,float} or not math.isfinite(hardware['ram_mb']) or hardware['ram_mb']<=0:
            raise ValueError('Hardware ram_mb must be a positive finite number')
        if hardware['hostname']!=next(worker['hostname'] for worker in initial_workers if worker['worker_id']==worker_id):
            raise ValueError('Declared hardware hostname does not match registered worker')
    before = client.get('/tasks')
    if any(task['status'] not in {'completed','failed'} for task in before):
        raise ValueError('Isolation failure: unrelated unfinished tasks exist')
    baseline_ids = {task['task_id'] for task in before}
    run_id = str(uuid4())
    target = output_dir/run_id
    target.mkdir(parents=True,exist_ok=False)
    comparison_config = {key:value for key,value in configuration.items() if key!='mode'}
    record = {'schema_version':1,'run_id':run_id,'workload_id':manifest['workload_id'],'mode':mode,'warmup':warmup,
        'worker_ids':sorted(workers),'participating_worker_count':len(workers),'operation':operation,'parameters':params,
        'workload':manifest,'scheduler_configuration':configuration,'environment':environment,
        'client_environment':{'platform':platform.platform(),'python':platform.python_version(),'logical_cpu_count':psutil.cpu_count(),
            'ram_bytes':psutil.virtual_memory().total},
        'comparison_key':fingerprint({'workload':manifest['workload_id'],'operation':operation,'params':params,'environment':environment,
            'scheduler':comparison_config,'poll_interval':poll_interval,'timeout':timeout}),
        'measurement_settings':{'poll_interval':poll_interval,'timeout':timeout},'preexisting_task_ids':sorted(baseline_ids),
        'started_at':datetime.now(timezone.utc).isoformat(),'status':'running','valid':False,'issues':[],
        'task_ids':[],'task_inputs':{},'observations':[],'results':{},'tasks':[]}
    started = clock()
    if hasattr(client,'set_deadline'):
        client.set_deadline(started+timeout)
    def observe():
        tasks = client.get('/tasks')
        current_workers = client.get('/workers')
        record['observations'].append({'elapsed_seconds':clock()-started,'observed_at':datetime.now(timezone.utc).isoformat(),
            'workers':current_workers,'tasks':tasks})
        tracked = {task['task_id']:task for task in tasks if task['task_id'] in set(record['task_ids'])}
        record['tasks'] = list(tracked.values())
        if any(a.get('worker_id') not in workers for task in tracked.values() for a in task.get('attempt_history',[])):
            raise ValueError('An unexpected worker received a benchmark task')
        if {task['task_id'] for task in tasks}-baseline_ids-set(record['task_ids']):
            raise ValueError('Isolation failure: unexpected new tasks')
        if baseline_ids-{task['task_id'] for task in tasks}:
            raise ValueError('Master state reset or existing tasks disappeared')
        verify_topology(current_workers,workers)
        for worker in current_workers:
            previous = next((item for item in initial_workers if item['worker_id']==worker['worker_id']),None)
            if previous and previous['hostname']!=worker['hostname']:
                raise ValueError('Worker hostname changed during trial')
        if client.get('/scheduler')['configuration']!=configuration:
            raise ValueError('Scheduler configuration changed during trial')
        return tracked
    try:
        for offset in range(0,len(manifest['images']),20):
            if clock()-started>=timeout:
                raise TimeoutError('Benchmark deadline exceeded during submission')
            items = manifest['images'][offset:offset+20]
            # Recheck bytes immediately before each upload.
            for item in items:
                if hashlib.sha256((directory/item['filename']).read_bytes()).hexdigest()!=item['sha256']:
                    raise ValueError('Workload changed after manifest inspection')
            submitted = client.upload(directory,items,operation,params)
            ids = [task['task_id'] for task in submitted]
            if len(ids)!=len(items) or len(set(ids))!=len(ids) or set(ids)&(baseline_ids|set(record['task_ids'])):
                raise ValueError('Upload response has duplicate/mismatched task correlation')
            record['task_ids'].extend(ids)
            record['task_inputs'].update({key:item for key,item in zip(ids,items,strict=True)})
            observe()
        while True:
            tracked = observe()
            if len(tracked)!=len(record['task_ids']):
                raise ValueError('Expected benchmark task is missing')
            if all(task['status'] in {'completed','failed'} for task in tracked.values()):
                break
            if clock()-started>=timeout:
                raise TimeoutError('Benchmark deadline exceeded while waiting for tasks')
            sleep(min(poll_interval,max(0,timeout-(clock()-started))))
        # Batch completion boundary excludes client result downloads.
        record['batch_elapsed_seconds'] = clock()-started
        record['batch_ended_at'] = datetime.now(timezone.utc).isoformat()
        for task_id,task in tracked.items():
            if task['status']!='completed':
                continue
            if clock()-started>=timeout:
                raise TimeoutError('Deadline exceeded while validating outputs')
            data = client.result(task_id)
            source = record['task_inputs'][task_id]
            expected = (params['width'],params['height']) if operation=='resize' else (source['width'],source['height'])
            with Image.open(BytesIO(data)) as image:
                if image.format!='PNG' or image.size!=expected or (operation in {'grayscale','edge_detection'} and image.mode!='L'):
                    raise ValueError('Result format/dimensions/mode mismatch')
                image.verify()
            record['results'][task_id] = {'input_sha256':source['sha256'],'output_sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
        observe()
        if clock()-started>=timeout:
            raise TimeoutError('Deadline exceeded during final result validation')
        record['status'] = 'complete'
    except KeyboardInterrupt:
        record['status'] = 'cancelled'
        record['issues'].append('Client cancelled; server tasks were not deleted/cancelled')
    except (requests.RequestException,ValueError,OSError,KeyError,TypeError) as exc:
        record['status'] = 'partial'
        record['issues'].append(f'{type(exc).__name__}: {exc}; server tasks may still be active')
    finally:
        if hasattr(client,'set_deadline'):
            client.set_deadline(None)
        record['ended_at'] = datetime.now(timezone.utc).isoformat()
        record['client_total_seconds'] = clock()-started
        elapsed = record.get('batch_elapsed_seconds',record['client_total_seconds'])
        record['metrics'] = summarize_tasks(record['tasks'],len(manifest['images']),elapsed)
        record['per_task_metrics'] = [task_metrics(task) for task in record['tasks']]
        record['executing_worker_ids'] = sorted({a['worker_id'] for task in record['tasks'] for a in task.get('attempt_history',[]) if a.get('worker_id')})
        metric = record['metrics']
        record['valid'] = (record['status']=='complete' and metric['successful']==len(manifest['images']) and not metric['retried_tasks']
            and metric['elapsed_seconds'] is not None and len(record['results'])==len(manifest['images']))
        if not record['valid'] and not record['issues']:
            record['issues'].append('Run failed success criteria, included retries, or has nonpositive duration')
        (target/'run.json').write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--master-url',default='http://127.0.0.1:8000')
    parser.add_argument('--mode',choices=['single','static','adaptive'],required=True)
    parser.add_argument('--workers',required=True,help='Comma-separated exact expected online IDs')
    parser.add_argument('--workload',type=Path,required=True)
    parser.add_argument('--operation',choices=['grayscale','resize','gaussian_blur','edge_detection'],default='grayscale')
    parser.add_argument('--params',default='{}',help='Operation parameter JSON')
    parser.add_argument('--environment',type=Path,required=True,help='User-recorded experiment/hardware/network JSON')
    parser.add_argument('--trials',type=int,default=3);parser.add_argument('--warmups',type=int,default=1)
    parser.add_argument('--timeout',type=float,default=300);parser.add_argument('--poll-interval',type=float,default=1)
    parser.add_argument('--output',type=Path,default=Path('benchmarks/results'))
    args = parser.parse_args()
    try:
        if args.trials<1 or args.warmups<0:
            raise ValueError('Trials must be positive; warmups nonnegative')
        client = HTTPClient(args.master_url)
        manifest = inspect_workload(args.workload)
        if (args.workload/'manifest.json').exists():
            provenance = json.loads((args.workload/'manifest.json').read_text(encoding='utf-8'))
            if provenance.get('workload_id')!=manifest['workload_id']:
                raise ValueError('Workload differs from its saved manifest; prepare a new labeled workload')
            manifest.update({key:provenance[key] for key in ['seed','profile','provenance'] if key in provenance})
        environment = json.loads(args.environment.read_text(encoding='utf-8'))
        if not isinstance(environment,dict):
            raise ValueError('Environment JSON must be an object')
        environment = {**environment,'protocol':{'warmups':args.warmups,'measured_trials':args.trials}}
        params = json.loads(args.params)
        workers = [value.strip() for value in args.workers.split(',') if value.strip()]
        for index in range(args.warmups+args.trials):
            record = run_trial(client,args.workload,manifest,mode=args.mode,workers=workers,operation=args.operation,params=params,
                environment=environment,timeout=args.timeout,warmup=index<args.warmups,output_dir=args.output,poll_interval=args.poll_interval)
            print(json.dumps({'run_id':record['run_id'],'status':record['status'],'valid':record['valid'],'warmup':record['warmup'],'metrics':record['metrics']}))
            if not record['valid']:
                parser.exit(1,'Trial invalid/partial; retained observations. Resolve isolation before another trial.\n')
    except (ValueError,OSError,requests.RequestException) as exc:
        parser.exit(1,f'{exc}\n')


if __name__=='__main__':
    main()
