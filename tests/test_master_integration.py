"""Final contracts joining UI, registration, polling and documented routes."""
import json
import unittest

from master.main import create_app
import test_master_images


class FinalContractTests(unittest.IsolatedAsyncioTestCase):
    raw=test_master_images.ImageHTTPTests.raw

    def setUp(self):self.app=create_app()

    async def test_worker_id_with_encoded_path_separator_can_poll(self):
        body=json.dumps({'worker_id':'laptop/A','hostname':'laptop'}).encode()
        status,_,headers=await self.raw('POST','/workers/register',body,extra_headers={b'x-worker-protocol':b'session-v1'})
        self.assertEqual(status,201)
        token=dict(headers)[b'x-worker-session']
        status,_,_=await self.raw('POST','/workers/laptop/A/next-task',extra_headers={b'x-worker-session':token})
        self.assertEqual(status,200)
        status,body,_=await self.raw('GET','/workers/laptop/A')
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['worker_id'],'laptop/A')

    async def test_frontend_and_benchmark_routes_exist(self):
        schema=self.app.openapi()
        expected={'/workers':{'get'},'/tasks':{'get','post'},'/scheduler':{'get'},'/images/tasks':{'post'},
                  '/tasks/{task_id}/attempts':{'get'},'/tasks/{task_id}/result':{'get','post'},
                  '/tasks/{task_id}/result/download':{'get'},'/tasks/{task_id}/input':{'get'}}
        for route,methods in expected.items():
            self.assertTrue(methods.issubset(schema['paths'][route]))

    async def test_modern_task_and_image_headers_documented(self):
        schema=self.app.openapi()
        for route,method in [('/tasks/{task_id}/start','post'),('/tasks/{task_id}/complete','post'),
            ('/tasks/{task_id}/fail','post'),('/tasks/{task_id}/input','get'),('/tasks/{task_id}/result','post')]:
            headers={item['name'].lower() for item in schema['paths'][route][method]['parameters'] if item['in']=='header'}
            self.assertTrue({'x-worker-session','x-task-assignment'}.issubset(headers))

    async def test_public_snapshot_schema_does_not_include_private_headers(self):
        for path in ['/health','/workers','/tasks','/scheduler']:
            status,data,_=await self.raw('GET',path)
            self.assertEqual(status,200)
            self.assertNotIn(b'X-Worker-Session',data)
            self.assertNotIn(b'assignment_token',data)
