from enum import Enum


class Level(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class PolicyEngine:
    def __init__(self):
        self.rules = {}

    def allow(self, action, level):
        self.rules[action] = level

    def level_for(self, action):
        return self.rules.get(action, Level.RED)

    def may_execute(self, action):
        return self.level_for(action) in (Level.GREEN, Level.YELLOW)