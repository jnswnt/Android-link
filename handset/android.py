"""Android Link: local UI + ADB/scrcpy adapter; independent of iPhone services."""
import argparse
import json
import secrets
import shutil
import subprocess
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WEB = Path(__file__).parent / 'web'
KEYS = {'back': 4, 'home': 3, 'recent': 187, 'volume-up': 24, 'volume-down': 25, 'power': 26}


def session_args(scrcpy, serial, audio, quality, screen_off, sdk):
    if audio not in ('phone', 'pc', 'both'):
        raise ValueError('Tujuan audio tidak valid.')
    if quality not in ('light', 'balanced', 'sharp'):
        raise ValueError('Kualitas tidak valid.')
    if audio == 'pc' and sdk < 30:
        raise ValueError('Audio ke PC memerlukan Android 11 atau lebih baru.')
    if audio == 'both' and sdk < 33:
        raise ValueError('Audio HP + PC memerlukan Android 13 atau lebih baru.')
    presets = {'light': (720, 30, '2M'), 'balanced': (1080, 60, '6M'), 'sharp': (1920, 60, '10M')}
    size, fps, bitrate = presets[quality]
    args = [scrcpy, '--serial', serial, '--window-title=Android Link — Mirror',
            f'--max-size={size}', f'--max-fps={fps}', f'--video-bit-rate={bitrate}']
    args += ['--no-audio'] if audio == 'phone' else ['--require-audio']
    if audio == 'both':
        args += ['--audio-dup']
    if screen_off:
        args += ['--turn-screen-off']
    return args


class AndroidBridge:
    def __init__(self, adb=None, scrcpy=None, output=None):
        self.adb = adb or shutil.which('adb')
        self.scrcpy = scrcpy or shutil.which('scrcpy')
        self.output = Path(output or Path.home() / 'Pictures' / 'Android Link')
        self.process = None
        self.serial = None
        self.settings = None
        self.lock = threading.RLock()
        self.log_path = None

    def run_adb(self, *args, binary=False):
        if not self.adb:
            raise ValueError('ADB belum ditemukan. Tambahkan platform-tools ke PATH atau gunakan --adb.')
        result = subprocess.run([self.adb, *args], capture_output=True, timeout=15)
        if result.returncode:
            raise ValueError(result.stderr.decode(errors='replace').strip() or 'Perintah ADB gagal.')
        return result.stdout if binary else result.stdout.decode(errors='replace').strip()

    def status(self):
        with self.lock:
            running = self.process is not None and self.process.poll() is None
            devices = []
            error = None
            if self.adb:
                try:
                    for line in self.run_adb('devices', '-l').splitlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 2:
                            model = next((p[6:] for p in parts[2:] if p.startswith('model:')), parts[0])
                            devices.append({'serial': parts[0], 'state': parts[1], 'name': model.replace('_', ' ')})
                except (ValueError, subprocess.TimeoutExpired) as exc:
                    error = str(exc)
            diagnostic = ''
            if self.process is not None and not running and self.process.returncode:
                diagnostic = 'scrcpy berhenti. Periksa log sesi.'
                if self.log_path and self.log_path.exists():
                    diagnostic = self.log_path.read_text(errors='replace')[-3000:]
            return {'adb': bool(self.adb), 'scrcpy': bool(self.scrcpy), 'devices': devices,
                    'running': running, 'serial': self.serial, 'settings': self.settings,
                    'error': error, 'diagnostic': diagnostic}

    def stop(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
            self.serial = None
            self.settings = None

    def start(self, data):
        with self.lock:
            if not self.scrcpy:
                raise ValueError('scrcpy belum ditemukan. Tambahkan ke PATH atau gunakan --scrcpy.')
            serial = str(data.get('serial', ''))
            ready = [d['serial'] for d in self.status()['devices'] if d['state'] == 'device']
            if serial not in ready:
                raise ValueError('Pilih perangkat berstatus device; izinkan USB debugging di HP.')
            sdk = int(self.run_adb('-s', serial, 'shell', 'getprop', 'ro.build.version.sdk'))
            audio, quality = data.get('audio', 'phone'), data.get('quality', 'light')
            args = session_args(self.scrcpy, serial, audio, quality, bool(data.get('screenOff')), sdk)
            self.output.mkdir(parents=True, exist_ok=True)
            self.stop()
            self.log_path = self.output / 'scrcpy-session.log'
            with self.log_path.open('wb') as log:
                self.process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
            self.serial = serial
            self.settings = {'audio': audio, 'quality': quality, 'screenOff': bool(data.get('screenOff'))}
            return {'message': 'Sesi dimulai di jendela scrcpy. Status audio tersedia setelah sesi berjalan.'}

    def action(self, data):
        with self.lock:
            if not self.process or self.process.poll() is not None or not self.serial:
                raise ValueError('Mulai sesi mirroring terlebih dahulu.')
            action = data.get('action')
            if action in KEYS:
                self.run_adb('-s', self.serial, 'shell', 'input', 'keyevent', str(KEYS[action]))
                return {'message': 'Perintah dikirim ke HP.'}
            if action == 'screenshot':
                image = self.run_adb('-s', self.serial, 'exec-out', 'screencap', '-p', binary=True)
                if not image.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Perangkat tidak mengirim screenshot PNG yang valid.')
                path = self.output / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.png')
                path.write_bytes(image)
                return {'message': f'Screenshot disimpan: {path}'}
            raise ValueError('Kontrol tidak dikenal.')


def make_server(bridge):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, mime='application/json'):
            raw = json.dumps(body).encode() if mime == 'application/json' else body
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {'error': 'Host ditolak.'})
            path = urlparse(self.path).path
            if path == '/api/android/status':
                return self.reply(200, bridge.status())
            assets = {'/': ('android.html', 'text/html; charset=utf-8'),
                      '/android.js': ('android.js', 'text/javascript; charset=utf-8'),
                      '/android.css': ('android.css', 'text/css'), '/app.css': ('app.css', 'text/css'),
                      '/logo.svg': ('logo.svg', 'image/svg+xml')}
            if path not in assets:
                return self.reply(404, {'error': 'Tidak ditemukan.'})
            name, mime = assets[path]
            content = (WEB / name).read_bytes()
            if name == 'android.html':
                content = content.replace(b'__ANDROID_TOKEN__', token.encode())
            self.reply(200, content, mime)

        def do_POST(self):
            origin = self.headers.get('Origin')
            expected_origin = f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or self.headers.get('X-Android-Link-Token') != token or (origin and origin != expected_origin):
                return self.reply(403, {'error': 'Sesi tidak diizinkan.'})
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 4096:
                    raise ValueError('Ukuran permintaan tidak valid.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Permintaan harus berupa objek JSON.')
                path = urlparse(self.path).path
                if path == '/api/android/start':
                    result = bridge.start(data)
                elif path == '/api/android/stop':
                    bridge.stop()
                    result = {'message': 'Sesi dihentikan.'}
                elif path == '/api/android/action':
                    result = bridge.action(data)
                else:
                    return self.reply(404, {'error': 'Tidak ditemukan.'})
                self.reply(200, result)
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                self.reply(400, {'error': str(exc)})

        def log_message(self, *_):
            pass

    return ThreadingHTTPServer(('127.0.0.1', 0), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', help='Path lengkap adb.exe')
    parser.add_argument('--scrcpy', help='Path lengkap scrcpy.exe')
    parser.add_argument('--browser', action='store_true', help='Buka melalui browser, tanpa pywebview')
    args = parser.parse_args()
    bridge = AndroidBridge(args.adb, args.scrcpy)
    server = make_server(bridge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        if args.browser:
            webbrowser.open(url)
            print(f'Android Link: {url}\nTekan Ctrl+C untuk keluar.')
            threading.Event().wait()
        else:
            try:
                import webview
            except ImportError:
                raise SystemExit('Pasang pywebview: pip install pywebview, atau gunakan --browser.')
            webview.create_window('Android Link', url, width=920, height=760, min_size=(560, 540))
            webview.start()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
