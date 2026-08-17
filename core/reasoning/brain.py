import json
import os
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