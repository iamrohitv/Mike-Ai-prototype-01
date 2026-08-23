#!/usr/bin/env python3
"""
Mike -> opencode bridge.

Mike's OpencodeBridgeTool POSTs coding tasks to the local HTTP endpoint;
the bridge queues them and runs the opencode CLI, returning the result.

Auto-started by the desktop app via start_background(); can also be run
standalone:  python tools/computer/opencode_bridge.py [port]
"""

import json
import os
import subprocess
import threading
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

QUEUE_FILE = Path(os.path.expanduser("~")) / ".mike_opencode_queue"
RESPONSE_DIR = Path(os.path.expanduser("~")) / ".mike_opencode_responses"
WORKING_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 8765

SUBPROCESS_TIMEOUT = 600   # opencode can be slow on big tasks
POLL_TIMEOUT = 620         # bridge waits for the result
BUSY_CODE = "busy"


def _response_file(cmd_id):
    RESPONSE_DIR.mkdir(exist_ok=True)
    safe = "".join(c for c in str(cmd_id) if c.isalnum() or c in "-_") or "cmd"
    return RESPONSE_DIR / f"{safe}.json"


def _opencode_cmd():
    """Full path to the opencode CLI on Windows; falls back to bare name."""
    candidate = os.path.join(
        os.path.expanduser("~"), "AppData", "Roaming", "npm", "opencode.cmd"
    )
    return candidate if os.path.exists(candidate) else "opencode"


def run_opencode(prompt: str) -> str:
    """Run opencode CLI with the given prompt."""
    try:
        result = subprocess.run(
            [_opencode_cmd(), "run", prompt],
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            shell=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return result.stdout.strip() or "Done."
        return f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return (
            f"Error: opencode timed out after {SUBPROCESS_TIMEOUT} seconds. "
            "Try a smaller task."
        )
    except FileNotFoundError:
        return "Error: 'opencode' not found. Install with: npm install -g @opencode-ai/cli-windows-x64"
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"


def process_queue(stop_event=None):
    """Process commands from the queue file until stopped."""
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            if QUEUE_FILE.exists():
                data = {}
                try:
                    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    QUEUE_FILE.unlink(missing_ok=True)
                    data = {}

                cmd = data.get("command", "")
                cmd_id = data.get("id", "")

                if cmd:
                    result = run_opencode(cmd)
                    response = {
                        "id": cmd_id,
                        "command": cmd,
                        "result": result,
                        "timestamp": time.time(),
                    }
                    with open(_response_file(cmd_id), "w", encoding="utf-8") as f:
                        json.dump(response, f)
                    QUEUE_FILE.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass

        time.sleep(1)


class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP endpoint for Mike to POST commands."""

    def do_POST(self):
        if self.path != "/bridge/command":
            self._send_json({"error": "Not found"}, 404)
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(body)
            cmd = data.get("command", "")
            cmd_id = data.get("id", f"cmd_{int(time.time())}")

            if not cmd:
                self._send_json({"error": "Missing 'command'"}, 400)
                return

            if QUEUE_FILE.exists():
                self._send_json(
                    {"status": BUSY_CODE,
                     "error": "A task is already running; try again shortly."},
                    202,
                )
                return

            tmp = QUEUE_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"id": cmd_id, "command": cmd}, f)
            tmp.replace(QUEUE_FILE)

            rfile = _response_file(cmd_id)
            deadline = time.time() + POLL_TIMEOUT
            while time.time() < deadline:
                if rfile.exists():
                    with open(rfile, "r", encoding="utf-8") as f:
                        response = json.load(f)
                    rfile.unlink(missing_ok=True)
                    self._send_json(response)
                    return
                time.sleep(1)

            self._send_json(
                {"error": f"Timeout after {POLL_TIMEOUT}s — task may still finish later."},
                504,
            )

        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, 500)

    def do_GET(self):
        if self.path == "/bridge/health":
            self._send_json({"status": "ok", "queue_exists": QUEUE_FILE.exists()})
        else:
            self._send_json({"error": "Not found"}, 404)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def bridge_alive(port=DEFAULT_PORT, timeout=1):
    """True when a bridge is already serving on this port."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/bridge/health", timeout=timeout
        ) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def start_background(port=DEFAULT_PORT):
    """Start bridge threads inside this process. Returns (server, thread) or
    (None, None) when a bridge is already running on the port."""
    if bridge_alive(port):
        return None, None
    server = HTTPServer(("127.0.0.1", port), BridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    threading.Thread(target=process_queue, daemon=True).start()
    return server, thread


def main():
    port = DEFAULT_PORT
    import sys

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    if bridge_alive(port):
        print(f"[Bridge] already running on port {port}.")
        return
    queue_thread = threading.Thread(target=process_queue, daemon=True)
    queue_thread.start()
    server = HTTPServer(("127.0.0.1", port), BridgeHandler)
    print(f"[Bridge] http://127.0.0.1:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()