class Event:
    def __init__(self, kind, payload=None):
        self.kind = kind
        self.payload = payload or {}


class EventBus:
    def __init__(self):
        self._subscribers = []

    def subscribe(self, fn):
        self._subscribers.append(fn)

    def emit(self, kind, payload=None):
        event = Event(kind, payload)
        for fn in self._subscribers:
            fn(event)