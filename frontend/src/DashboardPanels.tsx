import { useEffect, useState } from 'react';
import { fetchAttempts, resultUrl } from './api';
import type { Attempt, Scheduler, Task, Worker } from './types';
import { attemptExplanation, formatDate, operationLabel, schedulingLabel, statusHelp } from './ui';
export function StatusBadge({ status }: {
    status: string;
}) {
    // Keep the original value for CSS and API terminology.
    return <span className={`badge ${status}`}>{status}</span>;
}
export function WorkerCard({ worker, maxAge = 8, activeTasks }: {
    worker: Worker;
    maxAge?: number;
    activeTasks?: number;
}) {
    const stale = worker.status === 'offline' || Date.now() - Date.parse(worker.last_seen) > maxAge * 1000;
    return (<article className="worker-card">
      <div className="section-heading"><h3>{worker.worker_id}</h3><StatusBadge status={worker.status}/></div>
      <p className="muted">Hostname: {worker.hostname}</p>
      <div className="meter-row">
        {(['cpu_percent', 'ram_percent'] as const).map(key => {
            const label = key === 'cpu_percent' ? 'CPU' : 'RAM';
            const value = worker[key];
            return (<div key={key}>
              <div className="meter-label"><span>{label}</span><strong>{value === null ? 'Unavailable' : `${value.toFixed(1)}%`}</strong></div>
              <progress max="100" value={value ?? 0} aria-label={`${worker.worker_id} ${label} utilization`}/>
            </div>);
        })}
      </div>
      <p>Available RAM: <strong>{worker.available_ram_mb === null ? 'Unavailable' : `${worker.available_ram_mb.toFixed(0)} MiB`}</strong></p>
      <p>Active Tasks: <strong>{activeTasks ?? 'Not reported'}</strong></p>
      <p className="metadata">Last Heartbeat: {formatDate(worker.last_seen)}</p>
      {stale && <p className="warning">Stale metrics · last reported values, not current usage</p>}
    </article>);
}
export function ResultCard({ task }: {
    task: Task;
}) {
    const [missing, setMissing] = useState(false);
    return (<article className="result-card">
      {missing
            ? <div className="preview empty">Result unavailable. The Master may have restarted. Check the task before downloading again.</div>
            : <img loading="lazy" src={resultUrl(task.task_id)} alt={`${operationLabel(task.operation)} result for ${task.task_id}`} onError={() => setMissing(true)}/>}
      <div className="result-caption">
        <strong>{operationLabel(task.operation)}</strong>
        <p className="mono metadata">{task.task_id}</p>
        <div className="actions">
          <a href={resultUrl(task.task_id)} target="_blank" rel="noreferrer">Preview</a>
          <a href={resultUrl(task.task_id, true)}>Download PNG</a>
        </div>
      </div>
    </article>);
}
export function TaskDetail({ task, onClose }: {
    task: Task;
    onClose: () => void;
}) {
    const [attempts, setAttempts] = useState<Attempt[]>(task.attempt_history);
    const [error, setError] = useState('');
    useEffect(() => {
        let disposed = false;
        setAttempts(task.attempt_history);
        setError('');
        fetchAttempts(task.task_id)
            .then(history => {
                if (!disposed) setAttempts(history);
            })
            .catch(problem => {
                if (!disposed) setError(problem.message);
            });
        return () => { disposed = true; };
    }, [task.task_id, task.attempt_count, task.status]);
    return (<section className="panel detail" aria-label="Task details">
      <div className="section-heading"><h2>Task details</h2><button onClick={onClose}>Close details</button></div>
      <p className="mono break-all">{task.task_id}</p>
      <p><StatusBadge status={task.status}/> {operationLabel(task.operation)} · Worker {task.assigned_worker || 'Unassigned'} · {task.attempt_count} attempts</p>
      <p>{statusHelp[task.status]}</p>
      {task.error && <p className="error">Task error: {task.error}</p>}
      <p className="muted">Created {formatDate(task.created_at)} · Completed {formatDate(task.completed_at)}</p>
      <h3>Assignment & retry history</h3>
      {error && <p role="alert" className="error">History refresh failed: {error}. Showing the last task history. Check the Master connection.</p>}
      {attempts.length === 0 ? <p>No assignments yet.</p> : (<ol className="timeline">
          {attempts.map(attempt => (<li key={attempt.attempt}>
              <strong>Attempt {attempt.attempt} · {attempt.worker_id}</strong>
              <p>{attemptExplanation(attempt.outcome, attempt.reason)}</p>
              <p className="metadata">{attempt.outcome} · {attempt.reason || attempt.assignment_reason || 'No recorded reason'}</p>
              <span className="metadata">
                {formatDate(attempt.assigned_at)} · {attempt.mode ? schedulingLabel(attempt.mode) : '—'}
                {attempt.score != null ? ` · score ${attempt.score.toFixed(3)}` : ''}
              </span>
            </li>))}
        </ol>)}
      {task.status === 'completed' && task.operation !== 'dummy' && <a href={resultUrl(task.task_id, true)}>Download result</a>}
    </section>);
}
export function BenchmarkHelp() {
    return (<section className="panel" aria-label="Benchmark reports">
      <h2>Benchmark reports</h2>
      <p>Compare Single-device, Static distributed and Adaptive distributed runs with the existing benchmark scripts.</p>
      <p className="muted">Reports are saved files, not dashboard API data. Open the generated CSV, JSON, Markdown and SVG reports from your benchmark output folder.</p>
      <dl className="config-grid">
        <div><dt>Throughput</dt><dd>Completed images per second.</dd></div>
        <div><dt>Speedup</dt><dd>Single-device time divided by distributed time.</dd></div>
        <div><dt>Efficiency</dt><dd>Speedup divided by the allocated Worker count.</dd></div>
      </dl>
      <p className="muted">Execution time, Worker utilization, metadata and failed or partial trials remain in the reports. Compare matching workloads and valid repeated trials. Adaptive Scheduling is not guaranteed to be faster.</p>
      <p className="metadata">Report command help: <code>scripts\benchmark_report.cmd --help</code>. No experimental results are loaded here.</p>
    </section>);
}
export function SchedulingPanel({ scheduler, tasks }: {
    scheduler: Scheduler;
    tasks: Task[];
}) {
    const recoveryEvents = tasks.flatMap(task => task.attempt_history
        .filter(attempt => attempt.outcome === 'retry' || attempt.reason === 'heartbeat_timeout')
        .map(attempt => ({ taskId: task.task_id, attempt })));
    return (<>
      <section className="panel">
        <p className="eyebrow">SCHEDULING</p>
        <h2>{schedulingLabel(scheduler.configuration.mode)}</h2>
        <p>{scheduler.configuration.mode === 'adaptive'
            ? 'Tasks are assigned based on Worker resources and current workload.'
            : 'Tasks are assigned to available Workers in order.'}</p>
        <p className="muted">Mode is set at Master startup; this dashboard cannot change it. Busy or offline Workers do not receive new tasks.</p>
        {scheduler.configuration.mode === 'adaptive' && <p className="muted">The score also uses processing history. Fairness gives eligible Workers a turn; missing or stale metrics use the configured fallback.</p>}
        <details open>
          <summary>Technical details: scheduler configuration</summary>
          <dl className="config-grid">{Object.entries(scheduler.configuration).map(([key, value]) => (<div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{String(value)}</dd></div>))}</dl>
        </details>
      </section>
      <section className="panel">
        <h2>Worker task load</h2>
        {Object.keys(scheduler.workers).length === 0 ? <p>No Worker assignment information yet.</p> : (<div className="config-grid">{Object.entries(scheduler.workers).map(([id, worker]) => (<div key={id}>
              <h3>{id}</h3>
              <p>{worker.load} active Tasks · {worker.fairness_skips} fairness skips</p>
              <p>{worker.completed_samples} successful samples · {worker.mean_completion_seconds === null ? 'No timing history' : `${worker.mean_completion_seconds.toFixed(2)}s observed mean`}</p>
            </div>))}</div>)}
      </section>
      <section className="panel">
        <h2>Recorded retries and timeouts</h2>
        <p className="muted">These are recorded attempt outcomes. Check the latest task status to see whether a retry started or finished.</p>
        {recoveryEvents.length === 0 ? <p>No recorded retries or timeout attempts.</p> : recoveryEvents.map(({ taskId, attempt }) => (<div key={`${taskId}-${attempt.attempt}`} className="event">
            <p><strong>{taskId}</strong> · attempt {attempt.attempt} · {attempt.worker_id} · {attempt.reason} · {formatDate(attempt.finished_at)}</p>
            <p className="muted">{attemptExplanation(attempt.outcome, attempt.reason)}</p>
          </div>))}
      </section>
      <BenchmarkHelp />
    </>);
}
