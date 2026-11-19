"""Synthetic API observations are tests, never reported as performance trials."""
import csv
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import requests

from PIL import Image
from benchmarks.workload import generate, inspect_workload
from benchmarks.runner import run_trial, verify_topology, validate_parameters, HTTPClient, main
from benchmarks.metrics import aggregate, summarize_tasks, seconds, statistics_for
from benchmarks.report import build_report


def png(mode='L',size=(16,12)):
    stream = BytesIO();Image.new(mode,size,100).save(stream,format='PNG');return stream.getvalue()


class FakeClient:
    def __init__(self,workers=('a',),mode='static'):
        self.configuration = {'mode':mode,'max_attempts':3}
        self.workers = [{'worker_id':key,'hostname':key,'status':'online','last_seen':'2026-11-19T00:00:00Z',
                         'cpu_percent':10,'ram_percent':20,'available_ram_mb':1024} for key in workers]
        self.tasks = []
        self.outcome = 'completed'
        self.attempts = 1
        self.duplicate = False

    def get(self,path):
        if path=='/scheduler':return {'configuration':self.configuration}
        if path=='/workers':return self.workers
        if path=='/tasks':return self.tasks
        raise AssertionError(path)

    def upload(self,directory,items,operation,params):
        tasks = []
        for item in items:
            key = 'same' if self.duplicate else f'task-{len(self.tasks)+len(tasks)}'
            history = [{'attempt':a+1,'worker_id':self.workers[0]['worker_id'],
                'assigned_at':'2026-11-19T00:00:01Z','started_at':'2026-11-19T00:00:02Z',
                'finished_at':'2026-11-19T00:00:03Z','duration_seconds':1,
                'outcome':'completed' if a==self.attempts-1 else 'retry','reason':'test'} for a in range(self.attempts)]
            tasks.append({'task_id':key,'operation':operation,'status':self.outcome,'assigned_worker':self.workers[0]['worker_id'],
                'created_at':'2026-11-19T00:00:00Z','completed_at':'2026-11-19T00:00:03Z' if self.outcome=='completed' else None,
                'attempt_count':self.attempts,'attempt_history':history})
        self.tasks.extend(tasks)
        return tasks

    def result(self,task_id):return png()


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = generate(self.root/'inputs',count=2,width=16,height=12)
        self.tick = 0.0
        self.environment = {'experiment_id':'test-fixture-only','network':'mocked API', 'workers':{
            key:{'physical_device':key,'hostname':key,'cpu':'fixture','ram_mb':1024,'python':'test','opencv':'test'} for key in ['a','b']}}

    def clock(self):
        self.tick += .01
        return self.tick

    def run_case(self,client=None,**kwargs):
        return run_trial(client or FakeClient(),self.root/'inputs',self.manifest,mode=kwargs.pop('mode','single'),
            workers=kwargs.pop('workers',['a']),operation='grayscale',params={},environment=self.environment,
            clock=kwargs.pop('clock',self.clock),sleep=lambda _:None,output_dir=self.root/'results',**kwargs)

    def test_workload_reproducible(self):
        other = generate(self.root/'same',count=2,width=16,height=12)
        different = generate(self.root/'different',seed=43,count=2,width=16,height=12)
        self.assertEqual(self.manifest['workload_id'],other['workload_id'])
        self.assertNotEqual(self.manifest['workload_id'],different['workload_id'])
        self.assertIn('Synthetic',self.manifest['provenance'])

    def test_generator_never_overwrites(self):
        with self.assertRaises(ValueError):generate(self.root/'inputs')
        with self.assertRaises(ValueError):generate(self.root/'bad',width=5000)

    def test_workload_inspection_no_images(self):
        (self.root/'empty').mkdir()
        with self.assertRaises(ValueError):inspect_workload(self.root/'empty')

    def test_run_id_and_task_correlation(self):
        first = self.run_case();second = self.run_case()
        self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertTrue(first['valid'])
        self.assertEqual(len(first['task_inputs']),2)
        self.assertEqual(first['metrics']['successful'],2)
        self.assertEqual(first['executing_worker_ids'],['a'])

    def test_static_and_adaptive_configuration(self):
        for mode in ['static','adaptive']:
            record = self.run_case(FakeClient(('a','b'),mode),mode=mode,workers=['a','b'])
            self.assertTrue(record['valid'])
        with self.assertRaises(ValueError):self.run_case(FakeClient(mode='adaptive'))

    def test_worker_count_and_topology_validation(self):
        with self.assertRaises(ValueError):self.run_case(workers=['a','b'])
        with self.assertRaises(ValueError):self.run_case(mode='static')
        with self.assertRaises(ValueError):verify_topology(FakeClient().workers,['b'])

    def test_unrelated_pending_rejected_before_submission(self):
        client = FakeClient();client.tasks=[{'task_id':'unrelated','status':'pending'}]
        with self.assertRaises(ValueError):self.run_case(client)
        self.assertEqual(len(client.tasks),1)

    def test_failed_run_retained_invalid(self):
        client = FakeClient();client.outcome='failed'
        record = self.run_case(client)
        self.assertFalse(record['valid']);self.assertEqual(record['metrics']['failed'],2)
        self.assertTrue((self.root/'results'/record['run_id']/'run.json').exists())

    def test_timeout_preserves_partial_without_deleting_server_work(self):
        client = FakeClient();client.outcome='running'
        record = self.run_case(client,timeout=.2)
        self.assertEqual(record['status'],'partial')
        self.assertTrue(any('deadline' in issue for issue in record['issues']))
        self.assertEqual(len(client.tasks),2)

    def test_cancel_retains_observations(self):
        client = FakeClient()
        def cancelled(task_id):raise KeyboardInterrupt()
        client.result=cancelled
        record = self.run_case(client)
        self.assertEqual(record['status'],'cancelled');self.assertFalse(record['valid'])

    def test_retries_count_and_invalidate_clean_comparison(self):
        client = FakeClient();client.attempts=2
        record = self.run_case(client)
        self.assertEqual(record['metrics']['retried_tasks'],2)
        self.assertEqual(record['metrics']['retry_attempts'],2)
        self.assertFalse(record['valid'])

    def test_duplicate_upload_ids_rejected(self):
        client = FakeClient();client.duplicate=True
        record = self.run_case(client)
        self.assertFalse(record['valid'])
        self.assertTrue(any('correlation' in issue for issue in record['issues']))

    def test_wrong_result_dimensions_invalid(self):
        client = FakeClient();client.result=lambda _:png(size=(1,1))
        self.assertFalse(self.run_case(client)['valid'])

    def test_missing_and_zero_duration_metrics(self):
        self.assertIsNone(summarize_tasks([],1,0)['throughput_images_per_second'])
        self.assertIsNone(seconds(None,'invalid'))
        self.assertEqual(statistics_for([]),{'n':0,'mean':None,'median':None,'stdev':None})
        self.assertEqual(statistics_for([1,2,3])['stdev'],1)

    def test_speedup_efficiency_and_failed_trial_handling(self):
        baseline=self.run_case()
        records=[]
        for mode,elapsed,workers in [('single',4,['a']),('static',2,['a','b']),('adaptive',1,['a','b'])]:
            for index in range(3):
                record={**baseline,'mode':mode,'run_id':f'{mode}-{index}','worker_ids':workers,
                        'metrics':{**baseline['metrics'],'elapsed_seconds':elapsed,'throughput_images_per_second':2/elapsed}}
                records.append(record)
        groups=aggregate(records)
        adaptive=next(g for g in groups if g['mode']=='adaptive')
        self.assertEqual((adaptive['speedup'],adaptive['efficiency']),(4,2))
        records[-1]['valid']=False
        self.assertIsNone(next(g for g in aggregate(records) if g['mode']=='adaptive')['speedup'])

    def test_different_comparison_groups_not_mixed(self):
        baseline=self.run_case()
        distributed={**baseline,'mode':'static','worker_ids':['a','b'],'comparison_key':'different'}
        self.assertTrue(all(g['speedup'] is None for g in aggregate([baseline,distributed])))

    def test_warmups_excluded_from_statistics(self):
        baseline=self.run_case(warmup=True)
        self.assertEqual(aggregate([baseline])[0]['elapsed']['n'],0)

    def test_csv_json_svg_exports(self):
        record=self.run_case()
        groups=build_report(self.root/'results',self.root/'report')
        with (self.root/'report/trials.csv').open(newline='',encoding='utf-8') as source:
            rows=list(csv.DictReader(source))
        self.assertEqual(rows[0]['run_id'],record['run_id'])
        self.assertEqual(json.loads((self.root/'report/summary.json').read_text())['groups'],groups)
        self.assertIn('<svg',(self.root/'report/elapsed.svg').read_text())
        self.assertIn('No valid measurements',(self.root/'report/speedup.svg').read_text())
        with self.assertRaises(ValueError):build_report(self.root/'results',self.root/'report')

    def test_parameter_and_url_validation(self):
        self.assertEqual(validate_parameters('gaussian_blur',{}),{'kernel_size':5})
        for operation,params in [('resize',{}),('edge_detection',{'threshold1':200,'threshold2':10}),('gaussian_blur',{'kernel_size':4})]:
            with self.assertRaises(ValueError):validate_parameters(operation,params)
        with self.assertRaises(ValueError):HTTPClient('http://user:secret@host')

    def test_mid_trial_topology_change_retained_invalid(self):
        client = FakeClient()
        original = client.upload
        def upload(*args):
            tasks=original(*args)
            client.workers[0]['status']='offline'
            return tasks
        client.upload=upload
        record=self.run_case(client)
        self.assertFalse(record['valid'])
        self.assertIn('Expected online workers',record['issues'][0])

    def test_uncertain_submission_network_failure_is_partial(self):
        client=FakeClient()
        client.upload=Mock(side_effect=requests.ConnectionError('test network error'))
        record=self.run_case(client)
        self.assertEqual(record['status'],'partial')
        self.assertEqual(record['task_ids'],[])
        self.assertTrue(record['issues'])

    def test_http_upload_uses_real_pipeline_fields_and_bytes(self):
        client=HTTPClient('http://master')
        response=Mock();response.json.return_value=[]
        def post(url,**kwargs):
            self.assertEqual(url,'http://master/images/tasks')
            self.assertEqual(kwargs['data'],{'operation':'grayscale','params':'{}'})
            self.assertEqual(kwargs['files'][0][0],'files')
            self.assertEqual(kwargs['files'][0][1][1].read(),(self.root/'inputs'/self.manifest['images'][0]['filename']).read_bytes())
            return response
        with patch('benchmarks.runner.requests.post',side_effect=post):
            client.upload(self.root/'inputs',self.manifest['images'][:1],'grayscale',{})

    def test_http_deadline_and_environment_validation(self):
        client=HTTPClient('http://master');client.set_deadline(-1)
        with self.assertRaises(TimeoutError):client.request_timeout()
        self.environment['workers']['a']['cpu']='REPLACE'
        with self.assertRaises(ValueError):self.run_case()

    def test_cli_refuses_changed_saved_manifest_before_network_submission(self):
        path=self.root/'inputs'/self.manifest['images'][0]['filename']
        path.write_bytes(png(mode='RGB'))
        argv=['benchmark','--mode','single','--workers','a','--workload',str(self.root/'inputs'),
              '--environment',str(self.root/'unused.json')]
        with patch('sys.argv',argv),patch('benchmarks.runner.requests.post') as post:
            with self.assertRaises(SystemExit) as result:
                main()
        self.assertEqual(result.exception.code,1)
        post.assert_not_called()
