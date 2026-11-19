import type { Snapshot, Task, Attempt } from './types'
const configured = (import.meta.env.VITE_MASTER_URL || 'http://127.0.0.1:8000').replace(/\/$/,'')
const parsed = new URL(configured)
if (!['http:','https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash) throw new Error('VITE_MASTER_URL must be an HTTP(S) base URL without credentials, query or fragment')
export const API_URL = configured
export const socketUrl = `${configured.replace(/^http/,'ws')}/ws/dashboard`
export async function request<T>(path:string, options:RequestInit = {}):Promise<T> {
  const timeout = new AbortController()
  const timer = setTimeout(()=>timeout.abort(),30000)
  const signal = options.signal || timeout.signal
  try {
    const response = await fetch(`${API_URL}${path}`,{...options,signal,credentials:'omit'})
    if (!response.ok) {
      let detail = ''
      try { const data = await response.json(); detail = typeof data.detail === 'string' ? data.detail : 'Request validation failed' } catch { /* retain HTTP status */ }
      throw new Error(`HTTP ${response.status}${detail ? `: ${detail}` : ''}`)
    }
    return await response.json() as T
  } finally { clearTimeout(timer) }
}
export async function fetchSnapshot():Promise<Snapshot> {
  const [workers,tasks,scheduler] = await Promise.all([request<Snapshot['workers']>('/workers'),request<Task[]>('/tasks'),request<Snapshot['scheduler']>('/scheduler')])
  return {workers,tasks,scheduler}
}
export const fetchAttempts = (id:string) => request<Attempt[]>(`/tasks/${encodeURIComponent(id)}/attempts`)
export const resultUrl = (id:string,download=false) => `${API_URL}/tasks/${encodeURIComponent(id)}/result${download?'/download':''}`
export function uploadImages(files:File[],operation:string,params:Record<string,number>) {
  const body = new FormData()
  files.forEach(file=>body.append('files',file))
  body.append('operation',operation);body.append('params',JSON.stringify(params))
  return request<Task[]>('/images/tasks',{method:'POST',body})
}
