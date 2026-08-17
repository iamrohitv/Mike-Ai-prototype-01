import os

from security.paths import get_config_path


def ensure_env_template():
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