import { useState } from 'react'
import { API_URL } from './api'
import { useLiveDashboard } from './useLiveDashboard'
import { UploadPanel } from './UploadPanel'
import { ResultCard, SchedulingPanel, StatusBadge, TaskDetail, WorkerCard } from './DashboardPanels'
import type { Task } from './types'
import { countTasks, formatDate, operationLabel, schedulingLabel, taskStatuses } from './ui'

export { ResultCard, StatusBadge, WorkerCard } from './DashboardPanels'

const navigation = {
  Overview: 'Dashboard',
  'Image processing': 'Process Images',
  Workers: 'Workers', Tasks: 'Tasks', Results: 'Results', Scheduling: 'Scheduling',
}
type View = keyof typeof navigation

function TaskTable({ tasks, onSelect }: { tasks: Task[]; onSelect: (id: string) => void }) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Task registry table">
      <table>
        <thead>
          <tr>{['Task', 'Operation', 'Status', 'Worker', 'Attempts', 'Created', 'Completed'].map(label => <th key={label}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {tasks.map(task => (
            <tr key={task.task_id}>
              <td><button className="text-button mono" onClick={() => onSelect(task.task_id)}>{task.task_id}</button></td>
              <td>{operationLabel(task.operation)}</td>
              <td><StatusBadge status={task.status} /></td>
              <td>{task.assigned_worker || 'Unassigned'}</td>
              <td>{task.attempt_count}</td>
              <td>{formatDate(task.created_at)}</td>
              <td>{formatDate(task.completed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function App() {
  const { data, connection, error, updated } = useLiveDashboard()
  const [view, setView] = useState<View>('Overview')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [selected, setSelected] = useState<string | null>(null)
  const workers = data?.workers || []
  const tasks = data?.tasks || []
  const counts = countTasks(tasks)
  const completed = tasks.filter(task => task.status === 'completed' && task.operation !== 'dummy')
  const filtered = tasks.filter(task => {
    const matchesStatus = filter === 'all' || task.status === filter
    const searchableText = `${task.task_id} ${task.operation} ${task.assigned_worker || ''}`
    return matchesStatus && searchableText.toLowerCase().includes(search.toLowerCase())
  })
  const current = tasks.find(task => task.task_id === selected)
  const stats = [
    ['Registered workers', workers.length, `${workers.filter(w => w.status === 'online').length} online · ${workers.filter(w => w.status === 'offline').length} offline`],
    ['Total tasks', tasks.length, `${counts.pending} pending · ${counts.assigned} assigned`],
    ['Running', counts.running, 'Actively executing'],
    ['Completed', counts.completed, `${counts.failed} failed`],
  ]

  function navigate(name: View) {
    setView(name)
    setSelected(null)
  }
  function trackTask(id: string) {
    setSelected(id)
    setView('Tasks')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" onClick={() => navigate('Overview')}>
          <span className="brand-icon">A</span>
          <span>ADAPTIVE<small>DISTRIBUTED COMPUTING</small></span>
        </a>
        <p className="sidebar-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {(Object.keys(navigation) as View[]).map(name => (
            <button key={name} aria-current={view === name ? 'page' : undefined}
              className={view === name ? 'active' : ''} onClick={() => navigate(name)}>
              {navigation[name]}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <p>Master and Worker monitoring</p>
          <span>Academic project · Local deployment</span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>Framework / <strong>{navigation[view]}</strong></span>
          <span className="connection">{connection}</span>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">DISTRIBUTED COMPUTING FRAMEWORK</p>
              <h1>{navigation[view]}</h1>
              <p className="muted">{view === 'Overview' ? 'Upload images, monitor Workers and track Tasks.' : 'Live state from your FastAPI Master.'}</p>
            </div>
            <div className="update-note">
              {updated ? `Updated ${updated.toLocaleTimeString()}` : 'Awaiting Master'}
              <span>{data ? schedulingLabel(data.scheduler.configuration.mode) : 'No data yet'}</span>
            </div>
          </div>
          {error && (
            <div role="alert" className="error">
              Master connection: {error}. {data ? 'Showing the last received snapshot.' : 'No live statistics available.'}
            </div>
          )}
          {!data ? (
            <section className="panel empty" role="status">
              {error ? 'Cannot load Master data. Check the API URL and CORS settings.' : 'Connecting to the Master and loading cluster state…'}
            </section>
          ) : (
            <>
              {view === 'Overview' && (
                <>
                  <div className="stat-grid">
                    {stats.map(([label, value, note]) => (
                      <article className="stat-card" key={label}><p>{label}</p><strong>{value}</strong><span>{note}</span></article>
                    ))}
                  </div>
                  <div className="overview-grid">
                    <UploadPanel onTrack={trackTask} />
                    <section className="panel">
                      <p className="eyebrow">WORKLOAD STATUS</p>
                      <h2>Task status</h2>
                      <div className="progress-stack" aria-label="Task status distribution">
                        {Object.entries(counts).map(([status, count]) => (
                          <div key={status} className={status} style={{ flex: count || 0 }} title={`${status}: ${count}`} />
                        ))}
                      </div>
                      <div className="status-list">
                        {Object.entries(counts).map(([status, count]) => <div key={status}><StatusBadge status={status} /><strong>{count}</strong></div>)}
                      </div>
                      <p className="muted">Task state comes from the Master. Retries retain the original task ID.</p>
                    </section>
                  </div>
                  <section className="panel">
                    <div className="section-heading"><h2>Recent task activity</h2><button onClick={() => navigate('Tasks')}>View all tasks</button></div>
                    {tasks.length === 0 ? <p className="empty">No task activity yet. Submit your first image batch.</p> : (
                      <div className="activity-list">
                        {tasks.slice(-5).reverse().map(task => (
                          <button key={task.task_id} onClick={() => trackTask(task.task_id)}>
                            <StatusBadge status={task.status} />
                            <span>{operationLabel(task.operation)}<small className="mono">{task.task_id}</small></span>
                            <span>{task.attempt_count} attempts</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </section>
                </>
              )}
              {view === 'Image processing' && <UploadPanel onTrack={trackTask} />}
              {view === 'Workers' && (
                <>
                  <div className="section-heading"><h2>Registered Workers</h2><span>{workers.length} workers</span></div>
                  {workers.length === 0 ? <section className="panel empty">No workers registered. Start a worker process to join this Master.</section> : (
                    <div className="worker-grid">
                      {workers.map(worker => (
                        <WorkerCard key={worker.worker_id} worker={worker} maxAge={data.scheduler.configuration.metrics_max_age}
                          activeTasks={data.scheduler.workers[worker.worker_id]?.load} />
                      ))}
                    </div>
                  )}
                </>
              )}
              {view === 'Tasks' && (
                <>
                  <section className="panel">
                    <div className="section-heading"><h2>Task registry</h2><span>{filtered.length} of {tasks.length}</span></div>
                    <div className="filters">
                      <label>Search tasks<input type="search" placeholder="Task ID, operation or worker" value={search} onChange={e => setSearch(e.target.value)} /></label>
                      <label>Status<select value={filter} onChange={e => setFilter(e.target.value)}>
                        <option value="all">All statuses</option>
                        {taskStatuses.map(status => <option key={status} value={status}>{status}</option>)}
                      </select></label>
                    </div>
                    <TaskTable tasks={filtered} onSelect={setSelected} />
                    {filtered.length === 0 && <p className="empty">{tasks.length ? 'No tasks match these filters.' : 'No tasks submitted yet.'}</p>}
                  </section>
                  {current && <TaskDetail task={current} onClose={() => setSelected(null)} />}
                  {selected && !current && <p role="status">Waiting for submitted task {selected} to appear in the next snapshot.</p>}
                </>
              )}
              {view === 'Results' && (
                <>
                  <div className="section-heading"><h2>Completed image outputs</h2><span>{completed.length} results</span></div>
                  <p className="muted">Originals are restricted to the assigned worker by the existing API. This gallery displays completed outputs only.</p>
                  {completed.length === 0 ? <section className="panel empty">No completed image results yet. Pending, failed and dummy tasks do not have downloadable images.</section> : (
                    <div className="results-grid">{completed.map(task => <ResultCard key={task.task_id} task={task} />)}</div>
                  )}
                </>
              )}
              {view === 'Scheduling' && <SchedulingPanel scheduler={data.scheduler} tasks={tasks} />}
            </>
          )}
          <footer>Adaptive Distributed Computing Framework <span>Master: {API_URL}</span></footer>
        </div>
      </main>
    </div>
  )
}
