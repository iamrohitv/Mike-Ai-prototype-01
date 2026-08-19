import json
import urllib.error
import urllib.request


class SyncEngine:
    def __init__(self, memory, device_name, remote_base=None, remote_key=None):
        self.memory = memory
        self.device_name = device_name
        self.remote_base = remote_base
        self.remote_key = remote_key

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.remote_key:
            headers["Authorization"] = f"Bearer {self.remote_key}"
        return headers

    def push(self, since_ts=None):
        if not self.remote_base:
            return None
        payload = self.memory.sync_changes(since_ts=since_ts)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.remote_base}/api/sync/push",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def pull(self):
        if not self.remote_base:
            return None
        req = urllib.request.Request(
            f"{self.remote_base}/api/sync/pull",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                return self.memory.apply_sync(payload, self.device_name)
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def sync(self, since_ts=None):
        pushed = self.push(since_ts=since_ts)
        pulled = self.pull()
        return {"pushed": pushed, "pulled": pulled}