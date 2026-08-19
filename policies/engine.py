from enum import Enum


class Level(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class PolicyEngine:
    def __init__(self):
        self.rules = {}
        self.pending_approvals = {}
        self.approved = {}

    def allow(self, action, level):
        self.rules[action] = level

    def level_for(self, action):
        return self.rules.get(action, Level.RED)

    def may_execute(self, action):
        return self.level_for(action) in (Level.GREEN, Level.YELLOW)

    def needs_approval(self, action):
        return self.level_for(action) is Level.ORANGE

    def require_approval(self, action, payload):
        self.pending_approvals[action] = payload

    def approve(self, action):
        self.pending_approvals.pop(action, None)
        self.approved[action] = True

    def deny(self, action):
        self.pending_approvals.pop(action, None)
        self.approved.pop(action, None)

    def is_approved(self, action):
        return self.approved.get(action, False)