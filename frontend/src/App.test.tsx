import {render,screen,fireEvent,waitFor,within} from '@testing-library/react'
import {beforeEach,describe,it,expect,vi} from 'vitest'
import App,{ResultCard,WorkerCard} from './App'
import {snapshotFixture,taskFixture} from './fixtures'
import {useLiveDashboard} from './useLiveDashboard'
import {fetchAttempts} from './api'
vi.mock('./useLiveDashboard',()=>({useLiveDashboard:vi.fn()}))
vi.mock('./api',()=>({API_URL:'http://master',fetchAttempts:vi.fn(),resultUrl:(id:string,download=false)=>`http://master/tasks/${id}/result${download?'/download':''}`,uploadImages:vi.fn()}))
beforeEach(()=>{vi.mocked(useLiveDashboard).mockReturnValue({data:snapshotFixture,connection:'Live connection',error:'',updated:new Date()});vi.mocked(fetchAttempts).mockResolvedValue(taskFixture.attempt_history)})
describe('public dashboard',()=>{
 it('renders actual overview counts and current mode',()=>{render(<App/>);expect(screen.getByText('Registered workers')).toBeInTheDocument();expect(screen.getByText('1 online · 0 offline')).toBeInTheDocument();expect(screen.getByText('Adaptive Scheduling')).toBeInTheDocument()})
 it('shows honest loading with no invented statistics',()=>{vi.mocked(useLiveDashboard).mockReturnValue({data:null,connection:'Connecting',error:'',updated:null});render(<App/>);expect(screen.getByRole('status')).toHaveTextContent('loading cluster state');expect(screen.queryByText('Registered workers')).not.toBeInTheDocument()})
 it('shows initial error and retains last snapshot on later error',()=>{vi.mocked(useLiveDashboard).mockReturnValue({data:snapshotFixture,connection:'Polling fallback',error:'HTTP 500',updated:new Date()});render(<App/>);expect(screen.getByRole('alert')).toHaveTextContent('last received snapshot')})
 it('shows empty worker and result states',()=>{vi.mocked(useLiveDashboard).mockReturnValue({data:{...snapshotFixture,workers:[],tasks:[]},connection:'Live connection',error:'',updated:new Date()});render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Workers'}));expect(screen.getByText(/No workers registered/)).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'Results'}));expect(screen.getByText(/No completed image results/)).toBeInTheDocument()})
 it('filters tasks by search and status',()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Tasks'}));expect(screen.getByRole('table')).toHaveTextContent('task-1');fireEvent.change(screen.getByLabelText('Status'),{target:{value:'failed'}});expect(screen.getByText('No tasks match these filters.')).toBeInTheDocument();fireEvent.change(screen.getByLabelText('Status'),{target:{value:'all'}});fireEvent.change(screen.getByLabelText('Search tasks'),{target:{value:'not-found'}});expect(screen.queryByRole('button',{name:'task-1'})).not.toBeInTheDocument()})
 it('loads task attempts and retry reasons',async()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Tasks'}));fireEvent.click(screen.getByRole('button',{name:'task-1'}));expect(await screen.findByText('Attempt 1 · worker-old')).toBeInTheDocument();await waitFor(()=>expect(fetchAttempts).toHaveBeenCalledWith('task-1'));expect(screen.getByText(/retry · heartbeat_timeout/)).toBeInTheDocument()})
 it('shows history errors without dropping the task snapshot',async()=>{vi.mocked(fetchAttempts).mockRejectedValue(new Error('HTTP 500'));render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Tasks'}));fireEvent.click(screen.getByRole('button',{name:'task-1'}));expect(await screen.findByRole('alert')).toHaveTextContent('History refresh failed');expect(screen.getByText('Attempt 1 · worker-old')).toBeInTheDocument()})
 it('shows recorded recovery and read-only scheduling',()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Scheduling'}));expect(screen.getByText(/dashboard cannot change it/)).toBeInTheDocument();expect(screen.getByText(/attempt 1 · worker-old · heartbeat_timeout/)).toBeInTheDocument();expect(screen.queryByRole('button',{name:/switch mode/i})).not.toBeInTheDocument()})
 it('shows nullable and stale worker metrics honestly',()=>{render(<WorkerCard worker={{...snapshotFixture.workers[0],status:'offline',cpu_percent:null}}/>);expect(screen.getByText('Unavailable')).toBeInTheDocument();expect(screen.getByText(/Stale metrics/)).toBeInTheDocument();expect(screen.getByRole('progressbar',{name:'worker-1 RAM utilization'})).toHaveAttribute('value','40')})
 it('links results only to HTTP result endpoints',()=>{render(<ResultCard task={{...taskFixture,status:'completed'}}/>);expect(screen.getByRole('link',{name:'Download PNG'})).toHaveAttribute('href','http://master/tasks/task-1/result/download');fireEvent.error(screen.getByRole('img'));expect(screen.getByText(/Result unavailable/)).toBeInTheDocument()})
 it('renders all distinct task states',()=>{const statuses=['pending','assigned','running','completed','failed'] as const;vi.mocked(useLiveDashboard).mockReturnValue({data:{...snapshotFixture,tasks:statuses.map(status=>({...taskFixture,task_id:status,status}))},connection:'Live connection',error:'',updated:new Date()});render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Tasks'}));statuses.forEach(status=>expect(within(screen.getByRole('table')).getAllByText(status).length).toBeGreaterThan(0))})
 it('updates task ownership and attempts after reassignment',async()=>{const {rerender}=render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Tasks'}));fireEvent.click(screen.getByRole('button',{name:'task-1'}));await waitFor(()=>expect(fetchAttempts).toHaveBeenCalledWith('task-1'));vi.mocked(useLiveDashboard).mockReturnValue({data:{...snapshotFixture,tasks:[{...taskFixture,assigned_worker:'worker-2',attempt_count:3,status:'assigned'}]},connection:'Live connection',error:'',updated:new Date()});rerender(<App/>);expect(within(screen.getByRole('table')).getByText('worker-2')).toBeInTheDocument();expect(screen.getByLabelText('Task details')).toHaveTextContent('3 attempts')})
})

it('preserves all six navigation destinations with clearer labels', () => {
 render(<App />)
 const nav = screen.getByRole('navigation', {name: 'Main navigation'})
 expect(within(nav).getAllByRole('button')).toHaveLength(6)
 for (const name of ['Dashboard', 'Process Images', 'Workers', 'Tasks', 'Results', 'Scheduling']) {
  fireEvent.click(within(nav).getByRole('button', {name}))
  expect(screen.getByRole('heading', {level: 1, name})).toBeInTheDocument()
  expect(within(nav).getByRole('button', {name})).toHaveAttribute('aria-current', 'page')
 }
})
it('shows real Worker load, hostname and heartbeat labels', () => {
 render(<App />)
 fireEvent.click(screen.getByRole('button', {name: 'Workers'}))
 expect(screen.getByText(`Hostname: ${snapshotFixture.workers[0].hostname}`)).toBeInTheDocument()
 expect(screen.getByText(/Last Heartbeat:/)).toBeInTheDocument()
 expect(screen.getByText(/Available RAM:/)).toHaveTextContent('MiB')
 expect(screen.getByText(/Active Tasks:/)).toHaveTextContent(String(snapshotFixture.scheduler.workers['worker-1'].load))
})
it('does not invent an active task count when Worker load is absent', () => {
 render(<WorkerCard worker={snapshotFixture.workers[0]} />)
 expect(screen.getByText(/Active Tasks:/)).toHaveTextContent('Not reported')
})
it('explains recorded retry without claiming a successful reassignment', async () => {
 render(<App />)
 fireEvent.click(screen.getByRole('button', {name: 'Tasks'}))
 fireEvent.click(screen.getByRole('button', {name: 'task-1'}))
 expect(await screen.findByText(/A retry was requested; check the latest attempt/)).toBeInTheDocument()
 expect(screen.getByLabelText('Task details')).toHaveTextContent('The Worker has started processing this task.')
})
it('explains both scheduler modes without adding a runtime toggle', () => {
 const {unmount} = render(<App />)
 fireEvent.click(screen.getByRole('button', {name: 'Scheduling'}))
 expect(screen.getByText('Tasks are assigned based on Worker resources and current workload.')).toBeInTheDocument()
 expect(screen.getByText(/score also uses processing history/)).toBeInTheDocument()
 unmount()
 vi.mocked(useLiveDashboard).mockReturnValue({data: {...snapshotFixture, scheduler: {...snapshotFixture.scheduler, configuration: {...snapshotFixture.scheduler.configuration, mode: 'static'}}}, connection: 'Live connection', error: '', updated: new Date()})
 render(<App />)
 fireEvent.click(screen.getByRole('button', {name: 'Scheduling'}))
 expect(screen.getByText('Tasks are assigned to available Workers in order.')).toBeInTheDocument()
 expect(screen.getByText(/dashboard cannot change it/)).toBeInTheDocument()
})
it('explains standalone benchmark reports and formula meanings without data', () => {
 render(<App />)
 fireEvent.click(screen.getByRole('button', {name: 'Scheduling'}))
 const reports = screen.getByLabelText('Benchmark reports')
 expect(reports).toHaveTextContent('Single-device, Static distributed and Adaptive distributed')
 expect(reports).toHaveTextContent('CSV, JSON, Markdown and SVG')
 expect(reports).toHaveTextContent('Single-device time divided by distributed time.')
 expect(reports).toHaveTextContent('Speedup divided by the allocated Worker count.')
 expect(reports).toHaveTextContent('Adaptive Scheduling is not guaranteed to be faster.')
 expect(reports).toHaveTextContent('No experimental results are loaded here.')
})
