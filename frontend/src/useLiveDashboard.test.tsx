import {act,renderHook} from '@testing-library/react'
import {afterEach,beforeEach,it,expect,vi} from 'vitest'
import {useLiveDashboard} from './useLiveDashboard'
import {fetchSnapshot} from './api'
import {snapshotFixture} from './fixtures'
vi.mock('./api',()=>({fetchSnapshot:vi.fn(),socketUrl:'ws://master/ws/dashboard'}))
class FakeSocket {
 static instances:FakeSocket[]=[]
 onopen:(()=>void)|null=null;onmessage:((e:{data:string})=>void)|null=null;onerror:(()=>void)|null=null;onclose:(()=>void)|null=null
 close=vi.fn(()=>this.onclose?.())
 constructor(_url:string){FakeSocket.instances.push(this)}
}
beforeEach(()=>{vi.useFakeTimers();FakeSocket.instances=[];vi.stubGlobal('WebSocket',FakeSocket);vi.mocked(fetchSnapshot).mockResolvedValue(snapshotFixture)})
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals()})
it('loads public state and accepts live snapshots',async()=>{const {result}=renderHook(()=>useLiveDashboard());await act(async()=>{});act(()=>FakeSocket.instances[0].onopen?.());await act(async()=>{});act(()=>FakeSocket.instances[0].onmessage?.({data:JSON.stringify({type:'snapshot',data:{...snapshotFixture,tasks:[]}})}));expect(result.current.connection).toBe('Live connection');expect(result.current.data?.tasks).toEqual([])})
it('polls every five seconds without a live socket',async()=>{renderHook(()=>useLiveDashboard());await act(async()=>{});expect(fetchSnapshot).toHaveBeenCalledTimes(1);await act(async()=>{await vi.advanceTimersByTimeAsync(5000)});expect(fetchSnapshot).toHaveBeenCalledTimes(2)})
it('reconnects with backoff and refreshes on recovery',async()=>{const {result}=renderHook(()=>useLiveDashboard());await act(async()=>{});act(()=>FakeSocket.instances[0].onclose?.());await act(async()=>{await vi.advanceTimersByTimeAsync(1000)});expect(FakeSocket.instances).toHaveLength(2);act(()=>FakeSocket.instances[1].onopen?.());await act(async()=>{});expect(result.current.connection).toBe('Live connection');expect(fetchSnapshot).toHaveBeenCalledTimes(2)})
it('retains existing data and reports polling failures',async()=>{const {result}=renderHook(()=>useLiveDashboard());await act(async()=>{});vi.mocked(fetchSnapshot).mockRejectedValue(new Error('network unavailable'));await act(async()=>{await vi.advanceTimersByTimeAsync(5000)});expect(result.current.error).toBe('network unavailable');expect(result.current.data).toEqual(snapshotFixture)})
it('refreshes after malformed events',async()=>{renderHook(()=>useLiveDashboard());await act(async()=>{});act(()=>FakeSocket.instances[0].onmessage?.({data:'invalid-json'}));await act(async()=>{});expect(fetchSnapshot).toHaveBeenCalledTimes(2)})
it('cleans up timers and subscriptions on unmount',async()=>{const {unmount}=renderHook(()=>useLiveDashboard());await act(async()=>{});unmount();expect(FakeSocket.instances[0].close).toHaveBeenCalledOnce();await act(async()=>{await vi.advanceTimersByTimeAsync(30000)});expect(fetchSnapshot).toHaveBeenCalledTimes(1);expect(FakeSocket.instances).toHaveLength(1)})
it('ignores updates from superseded socket connections',async()=>{const {result}=renderHook(()=>useLiveDashboard());await act(async()=>{});const old=FakeSocket.instances[0];act(()=>old.onclose?.());await act(async()=>{await vi.advanceTimersByTimeAsync(1000)});act(()=>old.onmessage?.({data:JSON.stringify({type:'snapshot',data:{...snapshotFixture,tasks:[]}})}));expect(result.current.data?.tasks).toHaveLength(1)})
