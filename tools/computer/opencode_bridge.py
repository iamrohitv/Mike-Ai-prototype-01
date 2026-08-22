#!/usr/bin/env python3
"""
Mike → opencode bridge
Mike writes commands to a queue file, this daemon picks them up and runs opencode CLI.
"""

import os
import time
import json
import subprocess
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

QUEUE_FILE = Path(os.path.expanduser("~")) / ".mike_opencode_queue"
RESPONSE_FILE = Path(os.path.expanduser("~")) / ".mike_opencode_response"
WORKING_DIR = Path(r"E:\code-2026\mike-AI")


def run_opencode(prompt: str) -> str:
    """Run opencode CLI with the given prompt."""
    # Use full path to opencode.cmd on Windows
    opencode_cmd = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm", "opencode.cmd")
    
    try:
        result = subprocess.run(
            [opencode_cmd, "run", prompt],
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            shell=True,
            encoding='utf-8',
            errors='replace',
        )
        if result.returncode == 0:
            return result.stdout.strip() or "Done."
        else:
            return f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120s."
    except FileNotFoundError:
        return "Error: 'opencode' not found in PATH."
    except Exception as exc:
        return f"Error: {exc}"


def process_queue():
    """Process commands from the queue file."""
    while True:
        try:
            if QUEUE_FILE.exists():
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                cmd = data.get("command", "")
                cmd_id = data.get("id", "")
                
                if cmd:
                    print(f"[Bridge] Processing: {cmd[:60]}...")
                    result = run_opencode(cmd)
                    
                    # Write response
                    response = {
                        "id": cmd_id,
                        "command": cmd,
                        "result": result,
                        "timestamp": time.time(),
                    }
                    with open(RESPONSE_FILE, "w", encoding="utf-8") as f:
                        json.dump(response, f)
                    
                    # Clear queue
                    QUEUE_FILE.unlink()
                    print(f"[Bridge] Completed: {cmd_id}")
        except json.JSONDecodeError:
            pass
        except Exception as exc:
            print(f"[Bridge] Error: {exc}")
        
        time.sleep(1)


class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP endpoint for Mike to POST commands."""
    
    def do_POST(self):
        if self.path == "/bridge/command":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                data = json.loads(body)
                cmd = data.get("command", "")
                cmd_id = data.get("id", f"cmd_{int(time.time())}")
                
                if not cmd:
                    self._send_json({"error": "Missing 'command'"}, 400)
                    return
                
                # Queue the command
                with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"id": cmd_id, "command": cmd}, f)
                
                # Wait for response (poll)
                for _ in range(120):  # 120s timeout
                    if RESPONSE_FILE.exists():
                        with open(RESPONSE_FILE, "r", encoding="utf-8") as f:
                            response = json.load(f)
                        if response.get("id") == cmd_id:
                            RESPONSE_FILE.unlink(missing_ok=True)
                            self._send_json(response)
                            return
                    time.sleep(1)
                
                self._send_json({"error": "Timeout"}, 504)
                
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, 400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_GET(self):
        if self.path == "/bridge/health":
            self._send_json({"status": "ok", "queue_exists": QUEUE_FILE.exists()})
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
    
    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_http_server(port=8765):
    server = HTTPServer(("127.0.0.1", port), BridgeHandler)
    print(f"[Bridge] HTTP server on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    # Start queue processor in background
    queue_thread = threading.Thread(target=process_queue, daemon=True)
    queue_thread.start()
    
    # Start HTTP server
    start_http_server()