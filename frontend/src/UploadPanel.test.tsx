import {render,screen,fireEvent,waitFor} from '@testing-library/react'
import {beforeEach,it,expect,vi} from 'vitest'
import {UploadPanel,validateSelection} from './UploadPanel'
import {uploadImages} from './api'
import {taskFixture} from './fixtures'
vi.mock('./api',()=>({uploadImages:vi.fn()}))
beforeEach(()=>{
 vi.stubGlobal('Image',class {width=48;height=32;onload:(()=>void)|null=null;set src(_value:string){queueMicrotask(()=>this.onload?.())}})
 URL.createObjectURL=vi.fn(()=> 'blob:fixture');URL.revokeObjectURL=vi.fn()
 vi.mocked(uploadImages).mockResolvedValue([taskFixture])
})
it('validates file count, types, empty files and byte limits',()=>{
 expect(validateSelection([],'grayscale',{})).toContain('1 and 20')
 expect(validateSelection([new File(['x'],'x.txt',{type:'text/plain'})],'grayscale',{})).toContain('JPG and PNG')
 expect(validateSelection([new File([],'x.png',{type:'image/png'})],'grayscale',{})).toContain('nonempty')
 const file=new File(['x'],'x.png',{type:'image/png'});Object.defineProperty(file,'size',{value:10485761});expect(validateSelection([file],'grayscale',{})).toContain('10 MiB')
 expect(validateSelection(Array(21).fill(file),'grayscale',{})).toContain('1 and 20')
})
it('validates operation-specific parameters',()=>{
 const files=[new File(['x'],'x.png',{type:'image/png'})]
 expect(validateSelection(files,'resize',{width:0,height:4})).toContain('Resize')
 expect(validateSelection(files,'gaussian_blur',{kernel_size:4})).toContain('odd')
 expect(validateSelection(files,'edge_detection',{threshold1:200,threshold2:10})).toContain('ascending')
 expect(validateSelection(files,'edge_detection',{threshold1:100,threshold2:200})).toBe('')
})
it('exposes fields for the selected operation',()=>{render(<UploadPanel onTrack={vi.fn()}/>);fireEvent.change(screen.getByLabelText('Operation'),{target:{value:'resize'}});expect(screen.getByLabelText('Width (pixels)')).toBeInTheDocument();fireEvent.change(screen.getByLabelText('Operation'),{target:{value:'gaussian_blur'}});expect(screen.getByLabelText('Kernel size (odd)')).toHaveValue(5);fireEvent.change(screen.getByLabelText('Operation'),{target:{value:'edge_detection'}});expect(screen.getByLabelText('Low threshold')).toHaveValue(100);expect(screen.getByLabelText('High threshold')).toHaveValue(200)})
it('submits real files and tracks returned tasks without claiming completion',async()=>{
 const track=vi.fn();render(<UploadPanel onTrack={track}/>);const file=new File(['png'],'x.png',{type:'image/png'});fireEvent.change(screen.getByLabelText('Image files'),{target:{files:[file]}});fireEvent.click(screen.getByRole('button',{name:'Submit image tasks'}));expect(await screen.findByRole('status')).toHaveTextContent('not necessarily complete');expect(uploadImages).toHaveBeenCalledWith([file],'grayscale',{});fireEvent.click(screen.getByRole('button',{name:'Track task-1'}));expect(track).toHaveBeenCalledWith('task-1');expect(URL.revokeObjectURL).toHaveBeenCalled()
})
it('shows API upload errors',async()=>{vi.mocked(uploadImages).mockRejectedValue(new Error('HTTP 422: Invalid image'));render(<UploadPanel onTrack={vi.fn()}/>);fireEvent.change(screen.getByLabelText('Image files'),{target:{files:[new File(['x'],'x.png',{type:'image/png'})]}});fireEvent.click(screen.getByRole('button',{name:'Submit image tasks'}));expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 422')})
it('prevents an empty submission',async()=>{render(<UploadPanel onTrack={vi.fn()}/>);fireEvent.click(screen.getByRole('button',{name:'Submit image tasks'}));await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Select between'));expect(uploadImages).not.toHaveBeenCalled()})
it('rejects decoded dimensions beyond backend limits',async()=>{vi.stubGlobal('Image',class {width=4097;height=1;onload:(()=>void)|null=null;set src(_value:string){queueMicrotask(()=>this.onload?.())}});render(<UploadPanel onTrack={vi.fn()}/>);fireEvent.change(screen.getByLabelText('Image files'),{target:{files:[new File(['x'],'x.png',{type:'image/png'})]}});fireEvent.click(screen.getByRole('button',{name:'Submit image tasks'}));expect(await screen.findByRole('alert')).toHaveTextContent('4096 pixels');expect(uploadImages).not.toHaveBeenCalled()})

it('shows beginner instructions and descriptions for all four existing operations', () => {
 render(<UploadPanel onTrack={vi.fn()} />)
 expect(screen.getByText(/1. Select JPG or PNG images/)).toBeInTheDocument()
 expect(screen.getByText('Convert each image to shades of gray.')).toBeInTheDocument()
 for (const [operation, description] of [
  ['resize', 'Change each image to the width and height you choose.'],
  ['gaussian_blur', 'Soften detail using an odd-sized Gaussian kernel.'],
  ['edge_detection', 'Find image edges using low and high thresholds.'],
 ]) {
  fireEvent.change(screen.getByLabelText('Operation'), {target: {value: operation}})
  expect(screen.getByText(description)).toBeInTheDocument()
 }
 expect(screen.queryByLabelText('Width (pixels)')).not.toBeInTheDocument()
 expect(screen.queryByLabelText('Kernel size (odd)')).not.toBeInTheDocument()
})
it('shows submission activity and preserves resize parameter schema', async () => {
 let finish!: (value: typeof taskFixture[]) => void
 vi.mocked(uploadImages).mockReturnValue(new Promise(resolve => {finish = resolve}))
 render(<UploadPanel onTrack={vi.fn()} />)
 const file = new File(['png'], 'x.png', {type: 'image/png'})
 fireEvent.change(screen.getByLabelText('Image files'), {target: {files: [file]}})
 fireEvent.change(screen.getByLabelText('Operation'), {target: {value: 'resize'}})
 fireEvent.click(screen.getByRole('button', {name: 'Submit image tasks'}))
 await waitFor(() => expect(uploadImages).toHaveBeenCalledWith([file], 'resize', {width: 640, height: 480}))
 expect(screen.getByText(/Task IDs appear after the Master accepts/)).toBeInTheDocument()
 expect(screen.getByRole('button', {name: 'Validating and uploading…'})).toBeDisabled()
 finish([taskFixture])
 await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('not necessarily complete'))
})
