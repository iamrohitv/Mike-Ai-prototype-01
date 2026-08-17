from enum import Enum


class Mood(Enum):
    BUSINESS = "business"
    NORMAL = "normal"
    LOW = "low"


LOW_INDICATORS = [
    "i'm tired",
    "i am tired",
    "exhausted",
    "not feeling",
    "don't feel like",
    "do not feel like",
    "low",
    "down",
    "stressed",
    "overwhelmed",
    "hopeless",
    "no energy",
    "can't focus",
    "cannot focus",
    "give up",
    "tired of",
    "so done",
    "meh",
    "whatever",
    "idk",
    "i don't know anymore",
    "not in the mood",
]

BUSINESS_INDICATORS = [
    "urgent",
    "deadline",
    "client",
    "invoice",
    "budget",
    "meeting",
    "commit",
    "deploy",
    "production",
    "contract",
    "agreement",
    "quote",
    "project status",
    "sprint",
    "roadmap",
]


def detect_mood(text, short_threshold=12):
    lowered = (text or "").lower().strip()

    for indicator in LOW_INDICATORS:
        if indicator in lowered:
            return Mood.LOW

    short = len(lowered) <= short_threshold and len(text or "") > 0
    if short:
        return Mood.NORMAL

    for indicator in BUSINESS_INDICATORS:
        if indicator in lowered:
            return Mood.BUSINESS

    if text and text.endswith(("!", "?")) and len(text) < 40:
        return Mood.NORMAL

    return Mood.NORMAL