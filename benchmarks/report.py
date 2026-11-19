"""CSV, Markdown and standalone SVG graphs from saved observations only."""
import argparse
import csv
from html import escape
import json
from pathlib import Path

from benchmarks.metrics import aggregate


def write_csv(path, rows, fields):
    with path.open('w',newline='',encoding='utf-8') as output:
        writer = csv.DictWriter(output,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def bar_chart(path, title, values, unit):
    values = [(str(label),float(value)) for label,value in values if value is not None]
    width,height = 1000,max(240,100+len(values)*45)
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title,quote=True)}">',
        '<rect width="100%" height="100%" fill="white"/>',f'<text x="24" y="32" font-family="sans-serif" font-size="20">{escape(title)}</text>']
    maximum = max([value for _,value in values],default=1) or 1
    if not values:
        pieces.append('<text x="24" y="90" font-family="sans-serif">No valid measurements available</text>')
    for index,(label,value) in enumerate(values):
        y = 70+index*45
        pieces += [f'<text x="20" y="{y+17}" font-family="sans-serif" font-size="12">{escape(label[:48])}</text>',
                   f'<rect x="385" y="{y}" width="{value/maximum*450}" height="25" fill="#0f766e"/>',
                   f'<text x="850" y="{y+17}" font-family="sans-serif" font-size="12">{value:.4g} {escape(unit)}</text>']
    pieces.append('</svg>')
    path.write_text(''.join(pieces),encoding='utf-8')


def utilization_chart(path, records):
    pieces = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500" role="img" aria-label="Worker utilization over client observation time">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="20" y="28" font-size="20" font-family="sans-serif">CPU/RAM samples over time (recorded runs)</text>',
        '<path d="M65 60V380H950" stroke="black" fill="none"/>',
        '<text x="15" y="65" font-family="sans-serif">100%</text><text x="25" y="380" font-family="sans-serif">0%</text>',
        '<text x="400" y="475" font-family="sans-serif">Client monotonic seconds since trial start</text>']
    observations = [(r,o) for r in records if not r['warmup'] for o in r.get('observations',[])]
    maximum = max([o['elapsed_seconds'] for _,o in observations],default=1) or 1
    colors = ['#0f766e','#2563eb','#b45309','#be185d','#7c3aed']
    series = {}
    for record,observation in observations:
        for worker in observation['workers']:
            for field in ['cpu_percent','ram_percent']:
                value = worker.get(field)
                if value is not None:
                    series.setdefault((record['run_id'],worker['worker_id'],field),[]).append((observation['elapsed_seconds'],value))
    for index,(key,points) in enumerate(series.items()):
        color = colors[index%len(colors)]
        encoded = ' '.join(f'{65+x/maximum*885:.2f},{380-y/100*320:.2f}' for x,y in points)
        pieces.append(f'<polyline points="{encoded}" stroke="{color}" stroke-dasharray="{"6 3" if key[2]=="ram_percent" else "none"}" fill="none"><title>{escape(" / ".join(key))}</title></polyline>')
    pieces.append(f'<text x="65" y="405" font-family="sans-serif">0</text><text x="900" y="405" font-family="sans-serif">{maximum:.2f}s</text>')
    pieces.append('<text x="65" y="435" font-family="sans-serif">Solid: CPU; dashed: RAM. Hover a series for run/worker/metric. Samples are last-reported values.</text>')
    if not series:
        pieces.append('<text x="100" y="150" font-family="sans-serif">No resource samples available</text>')
    pieces.append('</svg>')
    path.write_text(''.join(pieces),encoding='utf-8')


def build_report(source: Path, output: Path):
    if output.exists():
        raise ValueError('Choose a new report directory to preserve previous reports')
    records = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(source.glob('*/run.json'))]
    ids = [record['run_id'] for record in records]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate run IDs in source results')
    groups = aggregate(records)
    output.mkdir(parents=True)
    (output/'summary.json').write_text(json.dumps({'runs':records,'groups':groups},indent=2,allow_nan=False),encoding='utf-8')
    rows = [{**record,**record['metrics'],'issues':'; '.join(record['issues']),'worker_ids':','.join(record['worker_ids'])} for record in records]
    write_csv(output/'trials.csv',rows,['run_id','workload_id','comparison_key','mode','warmup','valid','status','worker_ids','participating_worker_count','elapsed_seconds','successful','failed','unfinished','retried_tasks','retry_attempts','throughput_images_per_second','issues'])
    write_csv(output/'tasks.csv',[{'run_id':r['run_id'],**task} for r in records for task in r.get('per_task_metrics',[])],
        ['run_id','task_id','status','worker_id','attempts','retries','initial_queue_seconds','end_to_end_seconds'])
    samples = [{'run_id':r['run_id'],'warmup':r['warmup'],'elapsed_seconds':o['elapsed_seconds'],**worker} for r in records for o in r.get('observations',[]) for worker in o['workers']]
    write_csv(output/'resources.csv',samples,['run_id','warmup','elapsed_seconds','worker_id','hostname','status','last_seen','cpu_percent','ram_percent','available_ram_mb'])
    label = lambda g:f"{g['comparison_key'][:6]} {g['mode']} ({len(g['worker_ids'])} workers)"
    for filename,title,key,unit in [('elapsed.svg','Mean batch completion time by mode','elapsed','s'),('throughput.svg','Mean completed image throughput by mode','throughput','images/s')]:
        bar_chart(output/filename,title,[(label(g),g[key]['mean']) for g in groups],unit)
    bar_chart(output/'speedup.svg','Speedup — valid matched comparisons only',[(label(g),g['speedup']) for g in groups],'×')
    bar_chart(output/'efficiency.svg','Efficiency — speedup / allocated eligible workers',[(label(g),g['efficiency']) for g in groups],'')
    distribution = {}
    for record in records:
        if record['warmup']:
            continue
        for task in record.get('tasks',[]):
            worker = task.get('assigned_worker') or 'unassigned'
            key = f"{record['run_id'][:8]} {record['mode']} {worker}"
            distribution[key] = distribution.get(key,0)+int(task['status']=='completed')
    bar_chart(output/'distribution.svg','Successfully completed images by final worker',list(distribution.items()),'images')
    utilization_chart(output/'resources.svg',records)
    lines = ['# Benchmark report','',f'{len(records)} actual saved trial records; warmups retained in JSON/CSV but excluded from statistics.',
        '', '| Group / mode | Trials / invalid | Mean s | Median s | Sample SD s | Images/s | Speedup | Efficiency |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for group in groups:
        number = lambda value:'N/A' if value is None else f'{value:.5g}'
        lines.append('| '+' | '.join([label(group),f"{group['total_trials']} / {group['invalid_trials']}",
            number(group['elapsed']['mean']),number(group['elapsed']['median']),number(group['elapsed']['stdev']),
            number(group['throughput']['mean']),number(group['speedup']),number(group['efficiency'])])+' |')
    lines += ['', 'Failed/partial/cancelled trials are retained in trials.csv and raw JSON, not silently removed. Means use valid trials; any invalid measured trial prevents a speedup/efficiency comparison for its group.',
        'At least three valid matched trials per mode and one unambiguous single-device baseline are required for comparison.',
        'SVGs use only recorded measurements. A blank/N/A comparison is not evidence of zero performance. No superiority conclusion is generated automatically.',
        'Worker resources are sampled last-reported whole-host metrics, not per-process CPU or isolated worker-only timing. See docs/phase7.md for boundaries.']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return groups


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('benchmarks/results'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    build_report(args.source,args.output)
