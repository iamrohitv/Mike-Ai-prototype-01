from core.mood.mood import detect_mood
from core.tone.tone import build_system_prompt
from core.identity.identity import DEFAULT_SYSTEM_PROMPT


class ConversationContext:
    def __init__(self, memory):
        self.memory = memory

    def add_user(self, text):
        self.memory.add_conversation("user", text)

    def add_mike(self, text):
        self.memory.add_conversation("mike", text)

    def current_mood(self):
        recent = self.memory.recent_conversation(limit=1)
        if recent:
            return detect_mood(recent[-1][1])
        return None

    def system_prompt(self):
        mood = self.current_mood()
        return build_system_prompt(DEFAULT_SYSTEM_PROMPT, mood)

    def relevant_memory(self, query, limit=6):
        return self.memory.recall(query=query, limit=limit)

    def recent_talk(self, limit=8):
        return self.memory.recent_conversation(limit=limit)