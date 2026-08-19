import threading


class Event:
    def __init__(self, kind, payload=None):
        self.kind = kind
        self.payload = payload or {}


class EventBus:
    def __init__(self):
        self._subscribers = []
        self._lock = threading.Lock()

    def subscribe(self, fn):
        with self._lock:
            self._subscribers.append(fn)

    def emit(self, kind, payload=None):
        event = Event(kind, payload)
        with self._lock:
            subscribers = list(self._subscribers)
        for fn in subscribers:
            try:
                fn(event)
            except Exception:  # noqa: BLE001
                pass