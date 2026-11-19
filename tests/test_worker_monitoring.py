import threading
import unittest
from unittest.mock import Mock, patch

import requests
from worker.monitoring import collect_metrics, HeartbeatSender
import test_worker


class ResourceMonitoringTests(unittest.TestCase):
    def test_metric_values_and_nonblocking_cpu_sample(self):
        with patch('worker.monitoring.psutil.cpu_percent',return_value=12.5) as cpu, \
                patch('worker.monitoring.psutil.virtual_memory',return_value=Mock(percent=50,available=1048576)):
            self.assertEqual(collect_metrics(),{'cpu_percent':12.5,'ram_percent':50.0,'available_ram_mb':1.0})
            cpu.assert_called_once_with(interval=None)

    def test_collection_errors_return_null_independently(self):
        with patch('worker.monitoring.psutil.cpu_percent',side_effect=OSError()), \
                patch('worker.monitoring.psutil.virtual_memory',return_value=Mock(percent=30,available=0)):
            values = collect_metrics()
            self.assertIsNone(values['cpu_percent'])
            self.assertEqual(values['ram_percent'],30)
        with patch('worker.monitoring.psutil.cpu_percent',return_value=20), \
                patch('worker.monitoring.psutil.virtual_memory',side_effect=OSError()):
            self.assertIsNone(collect_metrics()['available_ram_mb'])

    def test_invalid_samples_are_null(self):
        with patch('worker.monitoring.psutil.cpu_percent',return_value=float('nan')), \
                patch('worker.monitoring.psutil.virtual_memory',return_value=Mock(percent=101,available=-1)):
            self.assertEqual(collect_metrics(),{'cpu_percent':None,'ram_percent':None,'available_ram_mb':None})

    def test_heartbeat_request_identity_timestamp_metrics_and_timeout(self):
        sender = HeartbeatSender('http://master','a','secret')
        with patch('worker.monitoring.requests.post',return_value=Mock(status_code=200)) as post:
            sender.send_once()
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs['headers'],{'X-Worker-Session':'secret'})
        self.assertEqual(kwargs['timeout'],(2,2))
        self.assertEqual(kwargs['json']['worker_id'],'a')
        self.assertIn('timestamp',kwargs['json'])

    def test_periodic_failures_do_not_busy_spin(self):
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.side_effect = [False,True]
        sender = HeartbeatSender('http://master','a','secret',stop=stop)
        with patch.object(sender,'send_once',side_effect=[requests.Timeout(),None]) as send:
            sender.run()
        self.assertEqual(send.call_count,2)
        self.assertEqual([c.args for c in stop.wait.call_args_list],[(3,),(3,)])

    def test_heartbeats_continue_while_processing_is_blocked(self):
        sent = threading.Event()
        release_image = threading.Event()
        image_started = threading.Event()
        def processing():
            image_started.set()
            release_image.wait(2)
        image = threading.Thread(target=processing)
        sender = HeartbeatSender('http://master','a','secret',interval=.01)
        try:
            image.start()
            self.assertTrue(image_started.wait(1))
            with patch.object(sender,'send_once',side_effect=lambda:sent.set()), sender:
                self.assertTrue(sent.wait(1))
                self.assertTrue(image.is_alive())
            self.assertFalse(sender.thread.is_alive())
        finally:
            release_image.set()
            image.join(2)

    def test_rejected_heartbeat_is_reported(self):
        sender = HeartbeatSender('http://master','a','secret')
        with patch('worker.monitoring.requests.post',return_value=Mock(status_code=401)), self.assertRaises(ValueError):
            sender.send_once()

    def test_main_starts_stops_heartbeat_and_sends_session_header(self):
        worker = test_worker.worker
        reply = Mock(status_code=201, headers={'X-Worker-Session':'private'})
        try:
            with patch.dict(worker.os.environ,{},clear=True), \
                    patch.object(worker.requests,'post',return_value=reply) as post, \
                    patch('worker.monitoring.HeartbeatSender') as sender, \
                    patch.object(worker,'run_worker',side_effect=KeyboardInterrupt()):
                self.assertEqual(worker.main(),0)
                sender.assert_called_once()
                sender.return_value.__enter__.assert_called_once()
                sender.return_value.__exit__.assert_called_once()
                self.assertEqual(worker.session_headers(),{'headers':{'X-Worker-Session':'private'}})
                reply.status_code = 200
                worker.post_update('http://master/tasks/id/start',{'worker_id':'a'})
                self.assertEqual(post.call_args.kwargs['headers'],{'X-Worker-Session':'private'})
        finally:
            worker.SESSION_TOKEN = None

    def test_main_rejects_invalid_heartbeat_configuration(self):
        worker = test_worker.worker
        for key in ['HEARTBEAT_INTERVAL','HEARTBEAT_HTTP_TIMEOUT']:
            for value in ['0','-1','nan','inf','bad']:
                with self.subTest(key=key,value=value), patch.dict(worker.os.environ,{key:value}), \
                        patch.object(worker.requests,'post') as post:
                    self.assertEqual(worker.main(),1)
                    post.assert_not_called()
