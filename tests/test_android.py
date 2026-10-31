import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch, Mock
from handset.android import AndroidBridge, make_server, session_args


class SessionTests(unittest.TestCase):
    def test_audio_modes(self):
        phone = session_args('scrcpy', 'phone', 'phone', 'light', False, 29)
        self.assertIn('--no-audio', phone)
        pc = session_args('scrcpy', 'phone', 'pc', 'balanced', True, 30)
        self.assertIn('--require-audio', pc)
        self.assertIn('--turn-screen-off', pc)
        self.assertNotIn('--audio-dup', pc)
        self.assertIn('--audio-dup', session_args('scrcpy', 'phone', 'both', 'sharp', False, 33))

    def test_unsupported_audio_rejected(self):
        for audio, sdk in [('both', 32), ('pc', 29)]:
            with self.assertRaises(ValueError):
                session_args('scrcpy', 'phone', audio, 'light', False, sdk)
        with self.assertRaises(ValueError):
            session_args('scrcpy', 'phone', 'invalid', 'light', False, 33)

    def test_unauthorized_device_cannot_start(self):
        bridge = AndroidBridge('adb', 'scrcpy')
        with patch.object(bridge, 'status', return_value={'devices': [{'serial': 'x', 'state': 'unauthorized'}]}):
            with self.assertRaises(ValueError):
                bridge.start({'serial': 'x'})

    def test_invalid_restart_keeps_existing_session(self):
        bridge = AndroidBridge('adb', 'scrcpy')
        process = Mock()
        process.poll.return_value = None
        bridge.process = process
        with patch.object(bridge, 'status', return_value={'devices': [{'serial': 'x', 'state': 'device'}]}), patch.object(bridge, 'run_adb', return_value='29'):
            with self.assertRaises(ValueError):
                bridge.start({'serial': 'x', 'audio': 'both'})
        process.terminate.assert_not_called()

    def test_unknown_action_does_not_run_adb(self):
        bridge = AndroidBridge('adb', 'scrcpy')
        bridge.process = Mock()
        bridge.process.poll.return_value = None
        bridge.serial = 'x'
        with patch.object(bridge, 'run_adb') as adb:
            with self.assertRaises(ValueError):
                bridge.action({'action': 'arbitrary shell command'})
            adb.assert_not_called()


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Mock()
        self.bridge.status.return_value = {'running': False, 'devices': []}
        self.server = make_server(self.bridge)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_ui_has_token_and_no_iphone_runtime(self):
        with urllib.request.urlopen(self.url) as response:
            html = response.read().decode()
            self.assertNotIn('__ANDROID_TOKEN__', html)
            self.assertNotIn('src="/app.js', html)
            self.assertIn('/android.js', html)

    def test_post_without_token_is_rejected(self):
        request = urllib.request.Request(self.url + '/api/android/start', data=b'{}', method='POST')
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 403)
        self.bridge.start.assert_not_called()

    def test_wrong_host_is_rejected(self):
        request = urllib.request.Request(self.url, headers={'Host': 'attacker.example'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 403)

    def test_authenticated_request(self):
        with urllib.request.urlopen(self.url) as response:
            html = response.read().decode()
        token = html.split('name="android-link-token" content="')[1].split('"')[0]
        self.bridge.start.return_value = {'message': 'started'}
        request = urllib.request.Request(self.url + '/api/android/start', data=b'{"serial":"x"}',
            headers={'X-Android-Link-Token': token, 'Content-Type': 'application/json', 'Origin': self.url}, method='POST')
        with urllib.request.urlopen(request) as response:
            self.assertEqual(json.load(response), {'message': 'started'})
        self.bridge.start.assert_called_once_with({'serial': 'x'})


if __name__ == '__main__':
    unittest.main()
