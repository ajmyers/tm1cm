"""The fake servers themselves: stopping one leaves none of its threads running."""

import socket
import threading
import time
import urllib.request

from tests.tm1cm.fake_servers import LoginServer


def request_threads():
    return [t for t in threading.enumerate() if 'process_request_thread' in t.name]


def test_stopping_ends_a_request_held_up_by_its_delay():
    # As when the browser is killed mid-sign-in: the request is still waiting out its delay
    server = LoginServer(delay=30)
    signed_in = server.url.replace('/bi/', '/signed-in')
    client = threading.Thread(target=lambda: urllib.request.urlopen(signed_in, timeout=60).read(), daemon=True)
    client.start()
    deadline = time.monotonic() + 5
    while not request_threads() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert request_threads()
    started = time.monotonic()
    server.stop()
    assert time.monotonic() - started < 5
    assert not request_threads()


def test_stopping_doesnt_wait_long_on_a_connection_that_sends_nothing():
    # Chrome opens connections ahead of need (preconnect) and may never send a request on them
    server = LoginServer()
    idle = socket.create_connection(('127.0.0.1', server.httpd.server_port))
    try:
        time.sleep(0.2)
        started = time.monotonic()
        server.stop()
        assert time.monotonic() - started < 10
        assert not request_threads()
    finally:
        idle.close()
