import os
import shutil
import subprocess

from awareness.scheduler import Monitor


class DiskMonitor(Monitor):
    name = "disk"
    interval = 600

    def __init__(self, event_bus, path=None, threshold_percent=90):
        super().__init__(event_bus)
        self.path = path or os.getcwd()
        self.threshold = threshold_percent

    def check(self):
        usage = shutil.disk_usage(self.path)
        pct = usage.used / usage.total * 100
        if pct >= self.threshold:
            return {
                "path": self.path,
                "used_percent": round(pct, 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
            }
        return None


class RepoMonitor(Monitor):
    name = "repo"
    interval = 900

    def __init__(self, event_bus, path=None):
        super().__init__(event_bus)
        self.path = path or os.getcwd()

    def check(self):
        try:
            proc = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if not lines:
            return None
        return {"path": self.path, "changes": lines[:20], "count": len(lines)}


class ServerMonitor(Monitor):
    name = "server"
    interval = 300

    def __init__(self, event_bus, url):
        super().__init__(event_bus)
        self.url = url

    def check(self):
        import urllib.request

        try:
            with urllib.request.urlopen(self.url, timeout=10) as resp:
                return {"url": self.url, "status": resp.status}
        except Exception as exc:  # noqa: BLE001
            return {"url": self.url, "error": str(exc)}


class TaskMonitor(Monitor):
    name = "tasks"
    interval = 1800

    def __init__(self, event_bus, memory, threshold=5):
        super().__init__(event_bus)
        self.memory = memory
        self.threshold = threshold

    def check(self):
        pending = self.memory.recent_pending_tasks(limit=100)
        if len(pending) >= self.threshold:
            return {"pending": len(pending), "oldest": pending[-1]["title"]}
        return None


class RoutineMonitor(Monitor):
    name = "routine"
    interval = 21600

    def __init__(self, event_bus, runner):
        super().__init__(event_bus)
        self.runner = runner

    def check(self):
        results = self.runner.run(name="daily_report")
        if results:
            return {"report": results[0].splitlines()[0]}
        return None


class ReminderMonitor(Monitor):
    name = "reminders"
    interval = 60

    def __init__(self, event_bus, memory):
        super().__init__(event_bus)
        self.memory = memory

    def check(self):
        due = self.memory.due_reminders()
        if not due:
            return None
        titles = [r["title"] for r in due]
        for r in due:
            self.memory.mark_reminder_done(r["id"])
            self.memory.add_task(f"reminder: {r['title']}")
        return {"due": titles}


class MetricMonitor(Monitor):
    name = "metrics"
    interval = 600

    def __init__(self, event_bus, memory):
        super().__init__(event_bus)
        self.memory = memory

    def check(self):
        pending = self.memory.recent_pending_tasks(limit=100)
        actions = self.memory.recent_actions(limit=50)
        self.memory.record_metric("pending_tasks", len(pending))
        self.memory.record_metric("recent_actions", len(actions))
        return {
            "pending_tasks": len(pending),
            "recent_actions": len(actions),
        }


class HealthMonitor(Monitor):
    name = "health"
    interval = 900

    def __init__(self, event_bus, guardian):
        super().__init__(event_bus)
        self.guardian = guardian

    def check(self):
        payload = {}
        try:
            import psutil
            payload["cpu_percent"] = psutil.cpu_percent(interval=1)
            payload["mem_percent"] = psutil.virtual_memory().percent
            try:
                payload["disk_percent"] = psutil.disk_usage(os.getcwd()).percent
            except (OSError, PermissionError):
                payload["disk_percent"] = None
            battery = psutil.sensors_battery()
            if battery is not None:
                payload["battery_percent"] = battery.percent
                payload["battery_plugged"] = battery.power_plugged
        except ImportError:
            return None
        if payload.get("mem_percent", 0) >= 98 or (payload.get("disk_percent") or 0) >= 98:
            self.guardian.evaluate("system.health", payload)
            return {"level": "emergency", "payload": payload}
        if payload.get("mem_percent", 0) >= 90 or (payload.get("disk_percent") or 0) >= 90:
            self.guardian.evaluate("system.health", payload)
            return {"level": "unusual", "payload": payload}
        return None