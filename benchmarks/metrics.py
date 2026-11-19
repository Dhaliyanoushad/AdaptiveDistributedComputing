"""Measurement definitions and conservative comparison validity."""
from datetime import datetime
import math
import statistics


def seconds(start, end):
    if not start or not end:
        return None
    try:
        value = (datetime.fromisoformat(end.replace('Z','+00:00'))-datetime.fromisoformat(start.replace('Z','+00:00'))).total_seconds()
        return value if math.isfinite(value) and value>=0 else None
    except (ValueError,TypeError):
        return None


def task_metrics(task):
    history = task.get('attempt_history',[])
    return {'task_id':task['task_id'],'status':task['status'],'worker_id':task.get('assigned_worker'),
        'attempts':task.get('attempt_count',0),'retries':max(0,task.get('attempt_count',0)-1),
        'initial_queue_seconds':seconds(task.get('created_at'),history[0].get('assigned_at') if history else None),
        'end_to_end_seconds':seconds(task.get('created_at'),task.get('completed_at')),
        'attempts_observed':[{'attempt':a.get('attempt'),'worker_id':a.get('worker_id'),
            'assigned_to_start_seconds':seconds(a.get('assigned_at'),a.get('started_at')),
            'retry_queue_seconds':seconds(history[index-1].get('finished_at'),a.get('assigned_at')) if index else None,
            'execution_and_transfer_seconds':a.get('duration_seconds'), 'reason':a.get('reason'),'outcome':a.get('outcome')}
            for index,a in enumerate(history)]}


def summarize_tasks(tasks, expected_count, elapsed):
    successful = sum(task['status']=='completed' for task in tasks)
    failed = sum(task['status']=='failed' for task in tasks)
    retried = sum(task.get('attempt_count',0)>1 for task in tasks)
    return {'expected':expected_count,'observed':len(tasks),'successful':successful,'failed':failed,'retried_tasks':retried,
        'retry_attempts':sum(max(0,task.get('attempt_count',0)-1) for task in tasks),
        'unfinished':sum(task['status'] not in {'completed','failed'} for task in tasks),
        'elapsed_seconds':elapsed if math.isfinite(elapsed) and elapsed>0 else None,
        'throughput_images_per_second':successful/elapsed if math.isfinite(elapsed) and elapsed>0 else None}


def statistics_for(values):
    values = [value for value in values if value is not None and math.isfinite(value)]
    return {'n':len(values),'mean':statistics.mean(values) if values else None,'median':statistics.median(values) if values else None,
            'stdev':statistics.stdev(values) if len(values)>1 else None}


def aggregate(records):
    groups = {}
    for record in records:
        key = (record['comparison_key'],record['mode'],tuple(record['worker_ids']))
        group = groups.setdefault(key,{'comparison_key':key[0],'mode':key[1],'worker_ids':list(key[2]),'trials':[]})
        if not record['warmup']:
            group['trials'].append(record)
    results = []
    for group in groups.values():
        trials = group.pop('trials')
        valid = [trial for trial in trials if trial['valid']]
        results.append({**group,'total_trials':len(trials),'invalid_trials':len(trials)-len(valid),
            'elapsed':statistics_for([trial['metrics']['elapsed_seconds'] for trial in valid]),
            'throughput':statistics_for([trial['metrics']['throughput_images_per_second'] for trial in valid])})
    for result in results:
        baselines = [g for g in results if g['comparison_key']==result['comparison_key'] and g['mode']=='single']
        baseline = baselines[0] if len(baselines)==1 else None
        usable = baseline and not baseline['invalid_trials'] and not result['invalid_trials'] and baseline['total_trials']>=3 and result['total_trials']>=3
        compatible = baseline and baseline['worker_ids'][0] in result['worker_ids']
        # Require the same distributed worker set when both distributed modes exist.
        peers = [g for g in results if g['comparison_key']==result['comparison_key'] and g['mode'] in {'static','adaptive'}]
        same_workers = all(g['worker_ids']==result['worker_ids'] for g in peers) if result['mode']!='single' else True
        elapsed = result['elapsed']['mean']
        speedup = baseline['elapsed']['mean']/elapsed if usable and compatible and same_workers and elapsed and elapsed>0 else None
        result.update(speedup=speedup,efficiency=speedup/len(result['worker_ids']) if speedup is not None else None,
            comparison_note='Valid matched comparison' if speedup is not None else 'Unavailable: need >=3 valid matched trials, one baseline, stable worker sets and no invalid trials')
    return results
