import json
import os
import re
import urllib.error
import urllib.request


class Brain:
    def __init__(self, memory, config=None):
        self.memory = memory
        self.config = config or {}
        self.local_url = self.config.get("local_url") or os.environ.get(
            "MIKE_LOCAL_URL", "http://localhost:11434/v1/chat/completions"
        )
        self.local_model = self.config.get("local_model") or os.environ.get(
            "MIKE_LOCAL_MODEL", ""
        )
        self.global_url = self.config.get("global_url") or os.environ.get(
            "MIKE_GLOBAL_URL", ""
        )
        self.global_key = self.config.get("global_key") or os.environ.get(
            "MIKE_GLOBAL_KEY", ""
        )
        self.global_model = self.config.get("global_model") or os.environ.get(
            "MIKE_GLOBAL_MODEL", ""
        )

    def _post(self, url, payload, headers=None):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers=headers or {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body

    def _extract(self, body):
        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            try:
                return body["response"].strip()
            except (KeyError, TypeError):
                raise ValueError("unrecognized provider response")

    def _ask_local(self, messages):
        if not self.local_url:
            return None
        if self.local_model:
            model = self.local_model
        else:
            model = self.config.get("local_model_default") or os.environ.get(
                "MIKE_LOCAL_MODEL", "mike-local"
            )
        try:
            body = self._post(
                self.local_url,
                {"model": model, "messages": messages, "stream": False},
            )
            return self._extract(body)
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def _ask_global(self, messages):
        if not (self.global_url and self.global_key):
            return None
        try:
            body = self._post(
                self.global_url,
                {"model": self.global_model, "messages": messages},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.global_key}",
                },
            )
            return self._extract(body)
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def reason(self, system_prompt, user_input, context=None):
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append(
                {"role": "system", "content": f"Relevant context:\n{context}"}
            )
        messages.append({"role": "user", "content": user_input})

        cached = self.memory.find_cached_knowledge(user_input)
        if cached and cached.get("origin") == "global":
            return f"{cached['answer']}\n\n(sourced from my private memory)"

        answer = self._ask_local(messages)
        source = "local"
        if answer is None:
            answer = self._ask_global(messages)
            source = "global"
            if answer is not None:
                self.memory.cache_knowledge(user_input, answer, origin="global")

        if answer is None:
            return (
                "I don't have context on this, so I'm guessing: I can't reach "
                "my brain right now. I could reason better if my local brain is "
                "running or a global key is configured."
            )
        return f"{answer}\n\n(brain: {source})"

    def select_tool(self, user_input, tools):
        catalog = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in tools
        )
        prompt = (
            "You are a tool router for a personal AI assistant. "
            "Decide which single tool best fits the user's request.\n"
            f"Available tools:\n{catalog}\n\n"
            "Reply with ONLY the tool name if one fits, otherwise reply with the "
            "single word: none."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input},
        ]
        answer = self._ask_local(messages)
        if answer is None:
            answer = self._ask_global(messages)
        if answer:
            choice = answer.strip().lower()
            for tool in tools:
                if tool.name in choice:
                    return tool
        return self._fallback_route(user_input, tools)

    def _fallback_route(self, user_input, tools):
        lowered = (user_input or "").lower()
        keywords = {
            "terminal": ["command", "run", "terminal", "execute", "ls", "dir", "echo"],
            "git": ["git", "commit", "push", "pull", "stage", "branch"],
            "file": ["file", "read", "open", "path"],
            "task": ["task", "todo", "pending", "remind"],
            "note": ["remember", "note", "recall"],
            "project": ["project", "repo", "status", "inspect"],
            "system": ["system", "disk", "battery", "health", "storage", "free space", "machine"],
            "screenshot": ["screenshot", "screen", "capture"],
        }
        best = None
        best_score = 0
        for tool in tools:
            hits = sum(1 for k in keywords.get(tool.name, []) if k in lowered)
            if hits > best_score:
                best_score = hits
                best = tool
        if best and best_score >= 2:
            return best
        return None

    def target_memories(self, user_input, memories):
        if not memories:
            return []
        catalog = "\n".join(
            f"ID {m['id']}: {m['content']}" for m in memories
        )
        prompt = (
            "Rohit wants to forget/clear some memories. Here are his current "
            "active memories, each with an ID.\n"
            f"{catalog}\n\n"
            "Decide which memories he is referring to. Reply with ONLY the "
            "IDs, comma-separated. If he is clearing everything or being "
            "vague about clearing memory, reply with ALL the IDs. If nothing "
            "clearly matches, reply with the single word: none."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input},
        ]
        answer = self._ask_local(messages)
        if answer is None:
            answer = self._ask_global(messages)
        if not answer:
            return []
        ids = []
        for token in re.findall(r"\d+", answer):
            try:
                parsed = int(token)
            except ValueError:
                continue
            if any(m["id"] == parsed for m in memories):
                ids.append(parsed)
        return list(dict.fromkeys(ids))