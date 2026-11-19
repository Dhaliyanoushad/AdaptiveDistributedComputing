import { useEffect, useState } from 'react'
import { fetchSnapshot, socketUrl } from './api'
import type { Snapshot } from './types'
export function useLiveDashboard() {
  const [data,setData]=useState<Snapshot|null>(null)
  const [connection,setConnection]=useState('Connecting')
  const [error,setError]=useState('')
  const [updated,setUpdated]=useState<Date|null>(null)
  useEffect(()=>{
    let disposed=false, socket:WebSocket|undefined, poll:ReturnType<typeof setTimeout>|undefined, retry:ReturnType<typeof setTimeout>|undefined
    let attempt=0, connected=false, fetching=false
    const accept=(snapshot:Snapshot)=>{if(!disposed){setData(snapshot);setUpdated(new Date());setError('')}}
    const refresh=async()=>{
      if(disposed||fetching)return
      fetching=true
      try{accept(await fetchSnapshot())}catch(e){if(!disposed)setError(e instanceof Error?e.message:'Master unavailable')}
      finally{fetching=false}
    }
    const pollNext=()=>{ if(disposed||connected)return; poll=setTimeout(async()=>{await refresh();pollNext()},5000) }
    const fallback=()=>{if(disposed)return;connected=false;setConnection('Polling fallback');if(poll===undefined)pollNext()}
    const connect=()=>{
      if(disposed)return
      try{socket=new WebSocket(socketUrl)}catch{fallback();retry=setTimeout(connect,Math.min(30000,1000*2**Math.min(attempt++,5)));return}
      const current=socket
      socket.onopen=()=>{if(disposed||socket!==current)return;connected=true;attempt=0;clearTimeout(poll);poll=undefined;setConnection('Live connection');void refresh()}
      socket.onmessage=event=>{if(disposed||socket!==current)return;try{const message=JSON.parse(event.data);if(message.type==='snapshot'&&Array.isArray(message.data?.workers)&&Array.isArray(message.data?.tasks)&&message.data?.scheduler)accept(message.data)}catch{setError('Invalid live update; refreshing from Master');void refresh()}}
      socket.onerror=()=>{current.close()}
      socket.onclose=()=>{if(disposed||socket!==current)return;fallback();retry=setTimeout(connect,Math.min(30000,1000*2**Math.min(attempt++,5)))}
    }
    void refresh();fallback();connect()
    return()=>{disposed=true;clearTimeout(poll);clearTimeout(retry);if(socket){socket.onclose=null;socket.onerror=null;socket.close()}}
  },[])
  return {data,connection,error,updated}
}
