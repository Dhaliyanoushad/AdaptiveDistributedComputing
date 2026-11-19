"""Assignment header propagation and transient/permanent processing reports."""
import unittest
from unittest.mock import Mock, patch
import requests
import test_worker

worker = test_worker.worker


class WorkerAssignmentTests(unittest.TestCase):
    def tearDown(self):
        worker.SESSION_TOKEN = worker.ASSIGNMENT_TOKEN = None

    def test_assignment_header_on_start_and_completion(self):
        worker.SESSION_TOKEN = 'session'
        task = {'task_id':'task','operation':'dummy','payload':{}}
        replies = [Mock(status_code=200,json=Mock(return_value={'task':task,'assignment_token':'generation'})),
                   Mock(status_code=200),Mock(status_code=200),KeyboardInterrupt()]
        with patch.object(worker.requests,'post',side_effect=replies) as post, patch.object(worker.time,'sleep'):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_worker('http://master','a',1,0)
        for index in [1,2]:
            self.assertEqual(post.call_args_list[index].kwargs['headers'],{'X-Worker-Session':'session','X-Task-Assignment':'generation'})
        self.assertNotIn('X-Task-Assignment',post.call_args_list[3].kwargs['headers'])

    def test_network_processing_failure_is_retryable(self):
        task = {'task_id':'image','operation':'grayscale','payload':{'parameters':{}}}
        replies = [Mock(status_code=200,json=Mock(return_value={'task':task,'assignment_token':'generation'})),
                   Mock(status_code=200),Mock(status_code=200),KeyboardInterrupt()]
        with patch.object(worker.requests,'post',side_effect=replies) as post, \
                patch.object(worker,'execute_image',side_effect=requests.Timeout('download timeout')):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_worker('http://master','a',1,0)
        self.assertTrue(post.call_args_list[2].kwargs['json']['retryable'])

    def test_validation_processing_failure_is_permanent(self):
        task = {'task_id':'image','operation':'grayscale','payload':{'parameters':{}}}
        replies = [Mock(status_code=200,json=Mock(return_value={'task':task})),Mock(status_code=200),Mock(status_code=200),KeyboardInterrupt()]
        with patch.object(worker.requests,'post',side_effect=replies) as post, \
                patch.object(worker,'execute_image',side_effect=ValueError('invalid image')):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_worker('http://master','a',1,0)
        self.assertFalse(post.call_args_list[2].kwargs['json']['retryable'])

    def test_poll_network_failure_stops_instead_of_duplicate_claim(self):
        with patch.object(worker.requests,'post',side_effect=requests.ConnectionError('offline')) as post:
            with self.assertRaises(requests.ConnectionError):
                worker.run_worker('http://master','a',1,0)
        self.assertEqual(post.call_count,1)
