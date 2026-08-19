from core.mood.mood import detect_mood
from core.tone.tone import build_system_prompt
from core.identity.identity import DEFAULT_SYSTEM_PROMPT

RECALL_PHRASES = [
    "what was i working on",
    "what was i doing",
    "what am i working on",
    "what are we working on",
    "what were we working on",
    "remind me what i was working on",
    "where did i leave off",
    "where did we leave off",
    "what should i do next",
    "what's pending",
    "whats pending",
    "what is pending",
    "what's on my plate",
]

CLEAR_PHRASES = [
    "clear memory",
    "clear my memory",
    "forget that",
    "forget about",
    "forget it",
    "don't mention",
    "do not mention",
    "don't bring that up",
    "do not bring that up",
    "stop mentioning",
    "stop talking about",
    "remove that from memory",
    "erase that",
    "wipe that",
]

PEEK_PHRASES = [
    "what did i ask you to forget",
    "show me the corner",
    "archived memories",
    "what's in the corner",
    "show me what you forgot",
]


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

    def is_recall_request(self, text):
        lowered = (text or "").lower()
        return any(phrase in lowered for phrase in RECALL_PHRASES)

    def is_clear_request(self, text):
        lowered = (text or "").lower()
        return any(phrase in lowered for phrase in CLEAR_PHRASES)

    def is_peek_request(self, text):
        lowered = (text or "").lower()
        return any(phrase in lowered for phrase in PEEK_PHRASES)

    def relevant_memory(self, query, limit=6):
        return self.memory.recall(query=query, limit=limit)

    def recall_context(self):
        recent_mem = self.memory.recent_memories(limit=6)
        tasks = self.memory.recent_pending_tasks(limit=5)
        recent_talk = self.memory.recent_conversation(limit=8)
        archived = [m["content"].lower() for m in self.memory.archived_memories(limit=50)]

        def suppressed(content):
            lowered = content.lower()
            return any(a in lowered for a in archived if a)

        parts = []
        if recent_mem:
            parts.append("Recent things I've remembered:")
            for m in recent_mem:
                parts.append(f"- {m['content']}")
        if tasks:
            parts.append("Pending tasks:")
            for t in tasks:
                parts.append(f"- (task {t['id']}) {t['title']}")
        if recent_talk:
            lines = []
            for role, content in recent_talk:
                if suppressed(content):
                    continue
                who = "Rohit" if role == "user" else "Mike"
                lines.append(f"{who}: {content}")
            if lines:
                parts.append("Recent conversation:\n" + "\n".join(lines))
        return "\n\n".join(parts)

    def relevant_context(self, text, limit=6):
        if self.is_recall_request(text):
            return self.recall_context()
        return self.relevant_memory(text, limit=limit)

    def recent_talk(self, limit=8):
        return self.memory.recent_conversation(limit=limit)

    def unsuppressed_talk(self, limit=8):
        recent_talk = self.memory.recent_conversation(limit=limit)
        archived = [m["content"].lower() for m in self.memory.archived_memories(limit=50)]

        def suppressed(content):
            lowered = content.lower()
            return any(a in lowered for a in archived if a)

        return [
            (role, content)
            for role, content in recent_talk
            if not suppressed(content)
        ]