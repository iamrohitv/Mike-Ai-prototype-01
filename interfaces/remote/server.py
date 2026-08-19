import hashlib
import hmac
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interfaces.text.cli import Mike

_INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text(
    encoding="utf-8"
)

_mike = None
_mike_lock = threading.RLock()
_token = os.environ.get("MIKE_REMOTE_KEY", "")

_MAX_FAILED = 5
_LOCKOUT_SECONDS = 60
_failed_attempts = {}
_failed_lock = threading.Lock()


def _lockout_state(ip):
    with _failed_lock:
        entry = _failed_attempts.get(ip, (0, 0))
        now = time.time()
        count, window_start = entry
        if now - window_start >= _LOCKOUT_SECONDS:
            entry = (0, now)
            _failed_attempts[ip] = entry
            count = 0
        if count >= _MAX_FAILED:
            return _LOCKOUT_SECONDS - int(now - window_start)
        return 0


def _record_failed(ip):
    with _failed_lock:
        now = time.time()
        count, window_start = _failed_attempts.get(ip, (0, 0))
        if now - window_start >= _LOCKOUT_SECONDS:
            count, window_start = 0, now
        _failed_attempts[ip] = (count + 1, window_start)


def get_mike():
    global _mike
    with _mike_lock:
        if _mike is None:
            _mike = Mike()
            _mike.memory.register_device("this-device", kind="pc")
        return _mike


def _authorized(auth_header):
    if not _token:
        return False
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    provided = auth_header[len("Bearer "):].strip()
    return hmac.compare_digest(provided, _token)


class Handler(BaseHTTPRequestHandler):
    def _client_ip(self):
        return self.client_address[0] if self.client_address else "unknown"

    def _record_auth_failure(self):
        _record_failed(self._client_ip())

    def _is_locked_out(self):
        return _lockout_state(self._client_ip()) > 0

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self._is_locked_out():
            self._send(429, {"error": "too many failed attempts, try again later"})
            return
        if self.path == "/" or self.path == "/index.html":
            body = _INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/health":
            self._send(200, {"status": "ok", "brain": bool(get_mike())})
            return
        if not _authorized(self.headers.get("Authorization")):
            self._record_auth_failure()
            self._send(401, {"error": "unauthorized"})
            return
        if self.path == "/api/status":
            mike = get_mike()
            self._send(200, {
                "status": "ok",
                "pending_tasks": len(mike.memory.recent_pending_tasks(limit=100)),
                "briefing": mike.briefings.short(),
                "devices": mike.memory.list_devices(),
            })
            return
        if self.path == "/api/briefing":
            mike = get_mike()
            self._send(200, {"briefing": mike.briefings.build()})
            return
        if self.path == "/api/sync/pull":
            mike = get_mike()
            with _mike_lock:
                payload = mike.memory.sync_changes()
            self._send(200, payload)
            return
        if self.path.split("?")[0] == "/api/history":
            mike = get_mike()
            with _mike_lock:
                limit = 30
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                if query.get("limit"):
                    try:
                        limit = int(query["limit"][0])
                    except ValueError:
                        limit = 30
                history = mike.context.recent_talk(limit=limit)
            self._send(200, {"history": history})
            return
        if self.path == "/api/tools":
            mike = get_mike()
            tools = [
                {"name": t.name, "description": t.description}
                for t in mike.tools
            ]
            self._send(200, {"tools": tools})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self._is_locked_out():
            self._send(429, {"error": "too many failed attempts, try again later"})
            return
        if not _authorized(self.headers.get("Authorization")):
            self._record_auth_failure()
            self._send(401, {"error": "unauthorized"})
            return
        if self.path == "/api/sync/push":
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                with _mike_lock:
                    mike = get_mike()
                    count = mike.memory.apply_sync(payload, "remote-device")
                self._send(200, {"applied": count})
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"error": str(exc)})
            return
        if self.path != "/api/chat":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            message = payload.get("message", "")
            with _mike_lock:
                mike = get_mike()
                mike.events.emit("phone.command", {"message": message})
                reply = mike.handle(message)
                mike.events.emit("phone.reply", {"reply": reply})
            self._send(200, {"reply": reply})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": str(exc)})

    def log_message(self, fmt, *args):
        pass


def _lan_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


def serve_background(mike=None, port=8877):
    global _mike
    if _mike is None:
        _mike = mike
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    ip = _lan_ip()
    return server, thread, f"http://{ip}:{port}"


def main():
    global _token
    if not _token:
        _token = sys.argv[2] if len(sys.argv) > 2 else "mike-remote-dev-key"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8877
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Mike remote interface on port {port} (key required).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()