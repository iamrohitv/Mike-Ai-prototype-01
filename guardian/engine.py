from enum import Enum


class GuardianLevel(Enum):
    NORMAL = "normal"
    UNUSUAL = "unusual"
    EMERGENCY = "emergency"


class GuardianEngine:
    def __init__(self, event_bus, memory, emergency_policy=None):
        self.event_bus = event_bus
        self.memory = memory
        self.emergency_policy = emergency_policy or {
            "level": "emergency",
            "actions": ["notify-owner", "log"],
        }
        self.checkins = []

    def evaluate(self, kind, payload):
        payload = payload or {}
        level = self._classify(kind, payload)
        if level is GuardianLevel.EMERGENCY:
            self._escalate(kind, payload)
        elif level is GuardianLevel.UNUSUAL:
            self._check_in(kind, payload)
        self.event_bus.emit(
            "guardian.evaluated",
            {"kind": kind, "level": level.value},
        )
        return level

    def _classify(self, kind, payload):
        kind_low = kind.lower()
        if "error" in payload:
            error = (payload.get("error") or "").lower()
            if any(marker in error for marker in ["disk full", "out of memory", "no space"]):
                return GuardianLevel.EMERGENCY
            return GuardianLevel.UNUSUAL
        if "used_percent" in payload:
            pct = payload.get("used_percent", 0)
            if pct >= 98:
                return GuardianLevel.EMERGENCY
            if pct >= 90:
                return GuardianLevel.UNUSUAL
        if "server" in kind_low:
            return GuardianLevel.UNUSUAL
        return GuardianLevel.NORMAL

    def _check_in(self, kind, payload):
        record = {
            "kind": kind,
            "level": "unusual",
            "payload": payload,
            "ts": self.memory._now(),
        }
        self.checkins.append(record)
        self.memory.add_task(f"check in: {kind} showed an unusual signal")
        self.event_bus.emit(
            "guardian.checkin",
            {"kind": kind, "detail": payload},
        )
        self.memory.log_action(
            action="guardian_checkin",
            reason=kind,
            result=str(payload),
            verification="unusual signal",
        )

    def _escalate(self, kind, payload):
        self.memory.log_action(
            action="guardian_emergency",
            reason=kind,
            result=str(payload),
            verification="emergency escalated",
        )
        self.event_bus.emit(
            "guardian.emergency",
            {"kind": kind, "detail": payload, "policy": self.emergency_policy},
        )
        self.memory.add_task(
            f"EMERGENCY follow-up: {kind}"
        )

    def recent_checkins(self, limit=10):
        return self.checkins[-limit:]