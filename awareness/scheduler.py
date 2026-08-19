import threading
import time
from datetime import datetime, timezone


class Monitor:
    name = "base"
    interval = 300

    def __init__(self, event_bus):
        self.event_bus = event_bus

    def check(self):
        raise NotImplementedError

    def run_check(self):
        try:
            result = self.check()
            if result:
                self.event_bus.emit(f"monitor.{self.name}", result)
            return result
        except Exception as exc:  # noqa: BLE001
            self.event_bus.emit(
                f"monitor.{self.name}.error", {"error": str(exc)}
            )
            return None


class Scheduler:
    def __init__(self, event_bus, monitors=None):
        self.event_bus = event_bus
        self.monitors = monitors or []
        self._stop = threading.Event()
        self._thread = None

    def add_monitor(self, monitor):
        self.monitors.append(monitor)

    def start(self):
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            now = datetime.now(timezone.utc).timestamp()
            for monitor in self.monitors:
                if self._stop.is_set():
                    return
                try:
                    monitor.run_check()
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.2)
            self._stop.wait(min(m.interval for m in self.monitors) if self.monitors else 300)


class DailyBriefing(Monitor):
    name = "briefing"
    interval = 3600

    def check(self):
        hour = datetime.now().hour
        payload = {"due": hour == 8}
        self.event_bus.emit("briefing.check", payload)
        return payload