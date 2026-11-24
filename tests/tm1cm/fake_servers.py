"""Small HTTP servers that answer as TM1 and Cognos do where logging in is concerned, for tests that
don't need a real TM1."""
import base64
import http.server
import json
import threading
import time

VERSION = '11.8.02300.1'
CLIENT_CAM_URI = 'http://cognos:9300/bi/v1/disp'


class FakeTm1:
    """TM1 in its own security (``Basic``) or CAM (``CAMNamespace``, ``CAMPassport``): logs in the
    one Authorization it accepts, and answers the requests tm1cm makes on connecting."""

    def __init__(self, accept, cam=False):
        server = self
        self.accept = accept
        self.cam = cam
        self.logins = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def _send(self, status, body=b'', headers=()):
                self.send_response(status)
                for name, value in headers:
                    self.send_header(name, value)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _challenge(self):
                if server.cam:
                    return [('WWW-Authenticate', f'CAMPassport {CLIENT_CAM_URI}'), ('WWW-Authenticate', 'CAMNamespace')]
                return [('WWW-Authenticate', 'Basic realm="TM1"')]

            def do_GET(self):
                if self.path.startswith('/api/v1/ActiveSession'):
                    authorization = self.headers.get('Authorization')
                    server.logins.append(authorization)
                    if authorization == server.accept:
                        headers = [('Set-Cookie', 'TM1SessionId=s1; Path=/api/; HttpOnly'), ('Content-Type', 'application/json')]
                        self._send(200, json.dumps({'ID': 7}).encode(), headers)
                    else:
                        self._send(401, headers=self._challenge())
                    return
                if 'TM1SessionId=s1' not in (self.headers.get('Cookie') or ''):
                    self._send(401, headers=self._challenge())
                    return
                if self.path.startswith('/api/v1/Server'):
                    self._send(200, json.dumps({'ProductVersion': VERSION}).encode(), [('Content-Type', 'application/json')])
                elif self.path.startswith('/api/v1/Configuration/ProductVersion'):
                    self._send(200, VERSION.encode(), [('Content-Type', 'text/plain')])
                else:
                    self._send(404, json.dumps({'error': {'code': '278', 'message': 'Not found'}}).encode(),
                               [('Content-Type', 'application/json')])

            def do_POST(self):
                self._send(204)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.root = f'http://127.0.0.1:{self.httpd.server_port}'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def basic(user, password):
    return 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()


def cam(user, password, namespace):
    return 'CAMNamespace ' + base64.b64encode(f'{user}:{password}:{namespace}'.encode()).decode()


class LoginServer:
    """Cognos's browser login: sets cam_passport (HttpOnly, as Cognos does) after a 'sign-in'
    redirect, and a decoy cookie. With ``needs_user``, sends the browser to a provider's page on
    another host (localhost rather than 127.0.0.1) that never comes back, as a provider does when
    it needs the user."""

    def __init__(self, delay=0.0, needs_user=False):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/bi/'):
                    self.send_response(302)
                    if server.needs_user:
                        self.send_header('Location', f'http://localhost:{server.httpd.server_port}/provider/login')
                    else:
                        self.send_header('Location', '/signed-in')
                    self.send_header('Set-Cookie', 'other=decoy; Path=/')
                    self.end_headers()
                    return
                if self.path.startswith('/provider/'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<form>Sign in</form>')
                    return
                time.sleep(server.delay)
                self.send_response(200)
                self.send_header('Set-Cookie', 'cam_passport=MTsxMDE6passport; Path=/; HttpOnly')
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<p>Signed in</p>')

            def log_message(self, *args):
                pass

        self.delay = delay
        self.needs_user = needs_user
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.httpd.server_port}/bi/'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
