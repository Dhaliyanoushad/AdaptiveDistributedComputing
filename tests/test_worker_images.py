import unittest
from unittest.mock import Mock, patch
import cv2
import numpy as np

from worker.image_processing import process_image
import test_worker


class ImageOperationTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((32, 48, 3), dtype=np.uint8)
        self.image[8:24, 12:36] = (20, 120, 240)
        self.data = cv2.imencode('.png', self.image)[1].tobytes()

    def check_operation(self, operation, params, expected):
        output = process_image(self.data, operation, params)
        actual = cv2.imdecode(np.frombuffer(output, np.uint8), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(actual, expected)

    def test_grayscale(self):
        self.check_operation('grayscale', {}, cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY))

    def test_resize(self):
        self.check_operation('resize', {'width': 12, 'height': 8}, cv2.resize(self.image, (12, 8), interpolation=cv2.INTER_AREA))

    def test_gaussian_blur(self):
        self.check_operation('gaussian_blur', {'kernel_size': 5}, cv2.GaussianBlur(self.image, (5, 5), 0))

    def test_edge_detection(self):
        self.check_operation('edge_detection', {}, cv2.Canny(cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY), 100, 200))

    def test_jpeg_input(self):
        data = cv2.imencode('.jpg', self.image)[1].tobytes()
        self.assertTrue(process_image(data, 'grayscale', {}).startswith(b'\x89PNG'))

    def test_invalid_images_and_parameters(self):
        for data, op, params in [(b'bad', 'grayscale', {}), (self.data, 'unknown', {}),
                                 (self.data, 'resize', {'width': 0, 'height': 1}),
                                 (self.data, 'gaussian_blur', {'kernel_size': 2}),
                                 (self.data, 'edge_detection', {'threshold1': 250, 'threshold2': 1})]:
            with self.subTest(operation=op), self.assertRaises((ValueError, OSError)):
                process_image(data, op, params)

    def test_worker_downloads_and_uploads_bytes(self):
        response = Mock(status_code=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [self.data]
        with patch.object(test_worker.worker.requests, 'get', return_value=response) as get, \
                patch.object(test_worker.worker.requests, 'post', return_value=Mock(status_code=200)) as post:
            test_worker.worker.execute_image('http://master', {
                'task_id': 'image-1', 'operation': 'grayscale', 'payload': {'parameters': {}}}, 'a')
        self.assertEqual(get.call_args.kwargs['params'], {'worker_id': 'a'})
        self.assertEqual(get.call_args.kwargs['timeout'], (3.05, 10))
        uploaded = post.call_args.kwargs['files']['file'][1]
        self.assertEqual(uploaded, process_image(self.data, 'grayscale', {}))
        self.assertEqual(post.call_args.kwargs['data'], {'worker_id': 'a'})

    def test_processing_failure_reports_failed_task(self):
        task = {'task_id':'image-1', 'operation':'grayscale', 'payload': {'parameters':{}}}
        replies = [Mock(status_code=200, json=Mock(return_value={'task':task})),
                   Mock(status_code=200), Mock(status_code=200), KeyboardInterrupt()]
        with patch.object(test_worker.worker.requests, 'post', side_effect=replies) as post, \
                patch.object(test_worker.worker, 'execute_image', side_effect=ValueError('decode failed')):
            with self.assertRaises(KeyboardInterrupt):
                test_worker.worker.run_worker('http://master', 'a', 1, 0)
        self.assertTrue(post.call_args_list[2].args[0].endswith('/fail'))
        self.assertEqual(post.call_args_list[2].kwargs['json']['error'], 'decode failed')
