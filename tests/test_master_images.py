import json
import asyncio
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.parse import urlsplit

from PIL import Image
from master.main import create_app
import test_master


def picture(size=(48, 32), mode='RGB'):
    buffer = BytesIO()
    Image.new(mode, size, 100).save(buffer, format='PNG')
    return buffer.getvalue()


def multipart(fields, files):
    boundary = 'test-image-boundary'
    chunks = []
    for name, value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, filename, data, mime in files:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + data + b'\r\n')
    return b''.join(chunks) + f'--{boundary}--\r\n'.encode(), f'multipart/form-data; boundary={boundary}'


class ImageHTTPTests(unittest.IsolatedAsyncioTestCase):
    request = test_master.MasterTests.request
    register = test_master.MasterTests.register

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = create_app(input_dir=self.root/'in', output_dir=self.root/'out')

    async def raw(self, method, url, body=b'', content_type='application/json', extra_headers=None):
        parts = urlsplit(url)
        sent = []
        delivered = False
        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            await asyncio.Future()
        async def send(message):
            sent.append(message)
        await self.app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                        'method': method, 'scheme': 'http', 'path': parts.path, 'root_path': '',
                        'query_string': parts.query.encode(),
                        'headers': [(b'content-type', content_type.encode())] + list((extra_headers or {}).items()),
                        'client': ('127.0.0.1', 1), 'server': ('test', 80)}, receive, send)
        start = next(m for m in sent if m['type'] == 'http.response.start')
        return start['status'], b''.join(m.get('body', b'') for m in sent if m['type'] == 'http.response.body'), start['headers']

    async def upload(self, operation='grayscale', params=None, files=None):
        body, mime = multipart({'operation': operation, 'params': json.dumps(params or {})},
                               files if files is not None else [('files', 'image.png', picture(), 'image/png')])
        status, data, _ = await self.raw('POST', '/images/tasks', body, mime)
        return status, json.loads(data)

    async def post(self, path, body):
        return await self.request('POST', path, json.dumps(body).encode())

    async def result(self, task, data, worker='a'):
        body, mime = multipart({'worker_id': worker}, [('file', 'result.png', data, 'image/png')])
        status, response, _ = await self.raw('POST', f"/tasks/{task['task_id']}/result", body, mime)
        return status, json.loads(response)

    async def ready(self, task):
        await self.post('/workers/a/next-task', {})
        await self.post(f"/tasks/{task['task_id']}/start", {'worker_id': 'a'})

    async def test_complete_http_roundtrips_all_operations(self):
        await self.register({'worker_id': 'a', 'hostname': 'test'})
        worker_python = Path(__file__).resolve().parents[1]/'worker/.venv/Scripts/python.exe'
        for operation, params in [('grayscale', {}), ('resize', {'width': 12, 'height': 8}),
                                  ('gaussian_blur', {'kernel_size': 3}), ('edge_detection', {})]:
            with self.subTest(operation=operation):
                status, tasks = await self.upload(operation, params)
                self.assertEqual(status, 201)
                task = tasks[0]
                self.assertNotIn('path', str(task))
                await self.ready(task)
                url = f"/tasks/{task['task_id']}"
                status, image_bytes, _ = await self.raw('GET', url+'/input?worker_id=a')
                self.assertEqual(status, 200)
                # A separate worker interpreter receives bytes, not a shared file path.
                code = 'import sys,json; from worker.image_processing import process_image; sys.stdout.buffer.write(process_image(sys.stdin.buffer.read(),sys.argv[1],json.loads(sys.argv[2])))'
                processed = subprocess.run([str(worker_python), '-c', code, operation, json.dumps(params)],
                                           input=image_bytes, capture_output=True, timeout=30, check=True).stdout
                status, completed = await self.result(task, processed)
                self.assertEqual((status, completed['status']), (200, 'completed'))
                self.assertEqual(await self.result(task, processed), (200, completed))
                for suffix in ['/result', '/result/download']:
                    status, result, headers = await self.raw('GET', url+suffix)
                    self.assertEqual((status, result), (200, processed))
                    if suffix.endswith('download'):
                        self.assertTrue(any(k == b'content-disposition' and b'attachment' in v for k,v in headers))

    async def test_batch_atomicity_and_safe_names(self):
        status, _ = await self.upload(files=[('files', 'good.png', picture(), 'image/png'),
                                           ('files', 'bad.png', b'bad', 'image/png')])
        self.assertEqual(status, 422)
        self.assertEqual((await self.request('GET', '/tasks'))[1], [])
        self.assertFalse(list(self.root.rglob('*.img')))
        status, tasks = await self.upload(files=[('files', '../../escape.png', picture(), 'image/png')]*2)
        self.assertEqual((status, len(tasks)), (201, 2))
        names = list((self.root/'in').iterdir())
        self.assertEqual(len({p.name for p in names}), 2)
        self.assertFalse((self.root/'escape.png').exists())

    async def test_invalid_uploads_and_parameters(self):
        for operation, params in [('resize', {}), ('resize', {'width': 0, 'height': 10}),
                                  ('gaussian_blur', {'kernel_size': 4}), ('edge_detection', {'threshold1': 200, 'threshold2': 10}),
                                  ('grayscale', {'unexpected': 1}), ('unknown', {})]:
            self.assertEqual((await self.upload(operation, params))[0], 422)
        self.assertEqual((await self.upload(files=[('files','x.txt', picture(),'text/plain')]))[0], 415)
        self.assertEqual((await self.upload(files=[('files','x.png', picture((4097,1)), 'image/png')]))[0], 422)
        self.assertEqual((await self.upload(files=[('files','x.png', b'x'*(10*1024*1024+1), 'image/png')]))[0], 413)

    async def test_ownership_status_validation_and_completion_bypass(self):
        await self.register({'worker_id': 'a', 'hostname': 'a'})
        await self.register({'worker_id': 'b', 'hostname': 'b'})
        task = (await self.upload())[1][0]
        url = f"/tasks/{task['task_id']}"
        self.assertEqual((await self.raw('GET', url+'/input?worker_id=b'))[0], 409)
        self.assertEqual((await self.raw('GET', url+'/result'))[0], 404)
        self.assertEqual((await self.result(task, picture(mode='L')))[0], 409)
        await self.ready(task)
        self.assertEqual((await self.post(url+'/complete', {'worker_id':'a'}))[0], 409)
        self.assertEqual((await self.result(task, picture(mode='L'), 'b'))[0], 409)
        self.assertEqual((await self.result(task, b'bad'))[0], 422)
        self.assertEqual((await self.result(task, picture((1,1), 'L')))[0], 422)
        self.assertEqual((await self.result(task, picture()))[0], 422)
        self.assertEqual((await self.request('GET',url))[1]['status'], 'running')
        self.assertEqual((await self.result(task, picture(mode='L')))[0], 200)
        self.assertEqual((await self.result(task, picture(mode='L')+b'extra'))[0], 409)

    async def test_image_failure_and_unknown_task(self):
        await self.register({'worker_id':'a','hostname':'a'})
        task = (await self.upload())[1][0]
        await self.ready(task)
        self.assertEqual((await self.post(f"/tasks/{task['task_id']}/fail", {'worker_id':'a','error':'decode failed'}))[1]['status'], 'failed')
        self.assertEqual((await self.result(task, picture(mode='L')))[0], 409)
        self.assertEqual((await self.raw('GET','/tasks/unknown/result'))[0], 404)
