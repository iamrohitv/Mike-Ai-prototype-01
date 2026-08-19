from datetime import datetime, timezone


class InitiativeEngine:
    def __init__(self, event_bus, memory, policies, brain=None):
        self.event_bus = event_bus
        self.memory = memory
        self.policies = policies
        self.brain = brain
        self.thresholds = {"act": 7, "notify": 4}

    def evaluate(self, kind, payload):
        relevance = self._relevance(kind, payload)
        importance = self._importance(kind, payload)
        urgency = self._urgency(kind, payload)
        score = relevance + importance + urgency
        decision = "wait"
        if score >= self.thresholds["act"]:
            decision = "act"
        elif score >= self.thresholds["notify"]:
            decision = "notify"
        self.event_bus.emit(
            "initiative.evaluated",
            {"kind": kind, "score": score, "decision": decision},
        )
        return {"kind": kind, "score": score, "decision": decision}

    def _relevance(self, kind, payload):
        kind_low = kind.lower()
        if "disk" in kind_low:
            return 3
        if "repo" in kind_low:
            return 3
        if "server" in kind_low:
            return 3
        if "tasks" in kind_low:
            return 2
        return 1

    def _importance(self, kind, payload):
        payload = payload or {}
        if "error" in payload:
            return 4
        if "count" in payload and payload.get("count", 0) > 10:
            return 4
        if "used_percent" in payload and payload.get("used_percent", 0) > 95:
            return 4
        return 2

    def _urgency(self, kind, payload):
        if "error" in (payload or {}):
            return 3
        if "server" in kind.lower():
            return 2
        return 1

    def should_notify(self, kind, payload):
        return self.evaluate(kind, payload)["decision"] in ("act", "notify")

    def act(self, decision):
        if decision["decision"] != "act":
            return None
        self.memory.add_task(
            f"follow up on {decision['kind']} (score {decision['score']})"
        )
        self.event_bus.emit(
            "initiative.action", {"task": f"follow up on {decision['kind']}"}
        )
        return f"added follow-up task for {decision['kind']}"