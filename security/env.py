import os

from security.paths import get_config_path


def load_env_file():
    env_path = os.path.join(get_config_path(), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and os.environ.get(key) is None:
                    os.environ[key] = value


def ensure_env_template():
    load_env_file()
    template = os.path.join(get_config_path(), ".env.example")
    if not os.path.exists(template):
        with open(template, "w", encoding="utf-8") as f:
            f.write(
                "# Mike hybrid brain configuration\n"
                "# Local brain (default)\n"
                "MIKE_LOCAL_URL=http://localhost:11434/v1/chat/completions\n"
                "MIKE_LOCAL_MODEL=\n"
                "# Global brain (used when local is unreachable)\n"
                "MIKE_GLOBAL_URL=\n"
                "MIKE_GLOBAL_KEY=\n"
                "MIKE_GLOBAL_MODEL=\n"
            )