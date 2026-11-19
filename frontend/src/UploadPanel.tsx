import { useRef, useState, type FormEvent } from 'react';
import { uploadImages } from './api';
export const operations = {
    grayscale: 'Grayscale',
    resize: 'Resize',
    gaussian_blur: 'Gaussian Blur',
    edge_detection: 'Edge Detection',
};
const descriptions: Record<string, string> = {
    grayscale: 'Convert each image to shades of gray.',
    resize: 'Change each image to the width and height you choose.',
    gaussian_blur: 'Soften detail using an odd-sized Gaussian kernel.',
    edge_detection: 'Find image edges using low and high thresholds.',
};
interface Parameters {
    width: number;
    height: number;
    kernel_size: number;
    threshold1: number;
    threshold2: number;
}
function operationParameters(operation: string, values: Parameters): Record<string, number> {
    if (operation === 'resize')
        return { width: values.width, height: values.height };
    if (operation === 'gaussian_blur')
        return { kernel_size: values.kernel_size };
    if (operation === 'edge_detection')
        return { threshold1: values.threshold1, threshold2: values.threshold2 };
    return {};
}
export function validateSelection(files: File[], operation: string, params: Record<string, number>): string {
    if (!files.length || files.length > 20)
        return 'Select between 1 and 20 images.';
    if (files.some(file => !/^image\/(png|jpeg)$/.test(file.type) || !/\.(png|jpe?g)$/i.test(file.name)))
        return 'Only JPG and PNG images are supported.';
    if (files.some(file => file.size === 0 || file.size > 10 * 1024 * 1024))
        return 'Each image must be nonempty and at most 10 MiB.';
    if (!(operation in operations))
        return 'Select a supported operation.';
    if (Object.values(params).some(value => !Number.isInteger(value)))
        return 'Parameters must be whole numbers.';
    if (operation === 'resize' && (!(params.width >= 1 && params.width <= 4096 && params.height >= 1 && params.height <= 4096) || params.width * params.height > 16000000))
        return 'Resize dimensions must be 1–4096 with at most 16 million pixels.';
    if (operation === 'gaussian_blur' && (!(params.kernel_size >= 1 && params.kernel_size <= 99) || params.kernel_size % 2 === 0))
        return 'Kernel size must be odd and between 1 and 99.';
    if (operation === 'edge_detection' && (!(params.threshold1 >= 0 && params.threshold2 <= 255) || params.threshold1 > params.threshold2))
        return 'Edge thresholds must be 0–255, in ascending order.';
    return '';
}
async function validateDimensions(files: File[]): Promise<void> {
    for (const file of files) {
        const url = URL.createObjectURL(file);
        try {
            await new Promise<void>((resolve, reject) => {
                const image = new Image();
                image.onload = () => {
                    if (image.width > 4096 || image.height > 4096 || image.width * image.height > 16000000) {
                        reject(new Error('Images must be at most 4096 pixels per side and 16 million pixels.'));
                    }
                    else {
                        resolve();
                    }
                };
                image.onerror = () => reject(new Error('An image could not be decoded.'));
                image.src = url;
            });
        }
        finally {
            URL.revokeObjectURL(url);
        }
    }
}
export function UploadPanel({ onTrack }: {
    onTrack: (id: string) => void;
}) {
    const [files, setFiles] = useState<File[]>([]);
    const [operation, setOperation] = useState('grayscale');
    const [values, setValues] = useState({ width: 640, height: 480, kernel_size: 5, threshold1: 100, threshold2: 200 });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [created, setCreated] = useState<string[]>([]);
    const input = useRef<HTMLInputElement>(null);
    const params = operationParameters(operation, values);
    const parameterField = (key: keyof typeof values, label: string, min: number, max: number) => <label>{label}<input type="number" required min={min} max={max} value={values[key]} onChange={e => setValues({ ...values, [key]: Number(e.target.value) })}/>
      </label>;
    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError('');
        setCreated([]);
        const problem = validateSelection(files, operation, params);
        if (problem) {
            setError(problem);
            return;
        }
        setBusy(true);
        try {
            await validateDimensions(files);
            const tasks = await uploadImages(files, operation, params);
            setCreated(tasks.map(task => task.task_id));
            setFiles([]);
            if (input.current)
                input.current.value = '';
        }
        catch (problem) {
            setError(problem instanceof Error ? problem.message : 'Upload failed');
        }
        finally {
            setBusy(false);
        }
    }
    return <section className="panel" id="upload">
      <div className="section-heading">
      <div>
      <p className="eyebrow">IMAGE PIPELINE</p>
      <h2>Process Images</h2>
      </div>
      <span className="tag">JPG / PNG</span>
      </div>
      <p className="muted">1. Select JPG or PNG images. 2. Choose an operation. 3. Submit and track one Task per image.</p>
    <form onSubmit={handleSubmit} aria-busy={busy}>
      <label className="dropzone">Choose images<input ref={input} aria-label="Image files" type="file" multiple accept="image/png,image/jpeg" disabled={busy} onChange={e => setFiles(Array.from(e.target.files || []))}/>
      <span>{files.length ? `${files.length} selected · ${(files.reduce((sum, file) => sum + file.size, 0) / 1048576).toFixed(1)} MiB` : 'Up to 20 images · 10 MiB each · 4096 px per side'}</span>
      </label>
      <div className="form-grid">
      <label>Operation<select value={operation} disabled={busy} onChange={e => setOperation(e.target.value)}>{Object.entries(operations).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      </label>
      {operation === 'resize' && <>{parameterField('width', 'Width (pixels)', 1, 4096)}{parameterField('height', 'Height (pixels)', 1, 4096)}</>}
      {operation === 'gaussian_blur' && parameterField('kernel_size', 'Kernel size (odd)', 1, 99)}
      {operation === 'edge_detection' && <>{parameterField('threshold1', 'Low threshold', 0, 255)}{parameterField('threshold2', 'High threshold', 0, 255)}</>}</div>
      <p className="muted" aria-live="polite">{descriptions[operation]}</p>
      <button className="primary" disabled={busy}>{busy ? 'Validating and uploading…' : 'Submit image tasks'}</button>
    </form>
    {busy && <p aria-live="polite">Validating and uploading images. Task IDs appear after the Master accepts the batch.</p>}
    {error && <p role="alert" className="error">{error}</p>}{created.length > 0 && <div role="status" className="success">{created.length} tasks submitted. Processing is queued, not necessarily complete.<ul>{created.map(id => <li key={id}>
      <button className="text-button" onClick={() => onTrack(id)}>Track {id}</button>
      </li>)}</ul>
      </div>}
  </section>;
}
