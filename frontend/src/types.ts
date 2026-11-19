export type Status = 'pending'|'assigned'|'running'|'completed'|'failed'
export interface Worker {worker_id:string;hostname:string;status:'online'|'offline';last_seen:string;cpu_percent:number|null;ram_percent:number|null;available_ram_mb:number|null}
export interface Attempt {attempt:number;worker_id:string;outcome:string;reason?:string;assignment_reason?:string;assigned_at:string;finished_at?:string|null;mode?:string;score?:number|null}
export interface Task {task_id:string;operation:string;status:Status;assigned_worker:string|null;attempt_count:number;created_at:string;completed_at:string|null;error:string|null;attempt_history:Attempt[]}
export interface Scheduler {configuration:{mode:'static'|'adaptive';metrics_max_age:number;max_attempts:number;[key:string]:string|number};pending_count:number;workers:Record<string,{load:number;fairness_skips:number;completed_samples:number;mean_completion_seconds:number|null}>}
export interface Snapshot {workers:Worker[];tasks:Task[];scheduler:Scheduler}
