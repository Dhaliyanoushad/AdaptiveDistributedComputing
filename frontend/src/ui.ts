/** Display helpers only: backend values and request schemas stay unchanged. */
import type { Status } from './types';
export const taskStatuses: Status[] = ['pending', 'assigned', 'running', 'completed', 'failed'];
export const statusHelp: Record<Status, string> = {
    pending: 'Waiting for an available Worker.',
    assigned: 'Assigned to a Worker. Processing has not started yet.',
    running: 'The Worker has started processing this task.',
    completed: 'The Master accepted the completed result.',
    failed: 'The task failed. Check the error and attempt history.',
};
export function formatDate(value: string | null | undefined): string {
    return value ? new Date(value).toLocaleString() : '—';
}
export function operationLabel(value: string): string {
    const names: Record<string, string> = {
        dummy: 'Dummy task', grayscale: 'Grayscale', resize: 'Resize',
        gaussian_blur: 'Gaussian Blur', edge_detection: 'Edge Detection',
    };
    return names[value] ?? value.replaceAll('_', ' ');
}
export function schedulingLabel(mode: string): string {
    return mode === 'adaptive' ? 'Adaptive Scheduling' : 'Static Scheduling';
}
export function countTasks(tasks: {
    status: Status;
}[]): Record<Status, number> {
    const counts: Record<Status, number> = { pending: 0, assigned: 0, running: 0, completed: 0, failed: 0 };
    for (const task of tasks)
        counts[task.status] += 1;
    return counts;
}
export function attemptExplanation(outcome: string, reason?: string): string {
    if (outcome === 'retry') {
        return reason === 'heartbeat_timeout'
            ? 'The Worker stopped sending heartbeats. A retry was requested; check the latest attempt for progress.'
            : 'This attempt ended and a retry was requested. Check the latest attempt for progress.';
    }
    if (outcome === 'completed')
        return 'This attempt completed successfully.';
    if (outcome === 'failed')
        return 'This attempt failed. No further retry is recorded for this attempt.';
    if (outcome === 'running')
        return 'Processing started on this Worker.';
    return 'The task was assigned to this Worker.';
}
