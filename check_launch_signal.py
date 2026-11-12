"""Startup counter sends one fixed request without local credentials."""

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import app


received = []
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        received.append((self.path, self.headers.get("User-Agent", "")))
        self.send_response(204)
        self.end_headers()
    def log_message(self, *_):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
old_url, old_config = app.LAUNCH_SIGNAL_URL, app.CONFIG
try:
    with tempfile.TemporaryDirectory() as temp:
        app.CONFIG = Path(temp) / "config.json"
        settings = dict(app.DEFAULTS, api_key="private-test-key")
        app.CONFIG.write_text(json.dumps(settings), encoding="utf-8")
        app.LAUNCH_SIGNAL_URL = f"http://127.0.0.1:{server.server_port}/?source=chaoxing-chapter-helper&event=launch"
        app.send_launch_signal()
        assert len(received) == 1
        assert "private-test-key" not in str(received)
        settings["usage_ping"] = False
        app.CONFIG.write_text(json.dumps(settings), encoding="utf-8")
        app.send_launch_signal()
        assert len(received) == 1
        print("Startup counter check passed")
finally:
    app.LAUNCH_SIGNAL_URL, app.CONFIG = old_url, old_config
    server.shutdown()
