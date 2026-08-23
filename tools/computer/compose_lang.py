"""Language handling for composed messages (WhatsApp / email)."""

import re

LANGS = (
    "hindi|hinglish|english|marathi|tamil|telugu|bengali|gujarati|"
    "kannada|malayalam|punjabi|urdu|spanish|french|german|italian|"
    "portuguese|arabic|russian|japanese|korean|chinese|mandarin"
)
LANG_RE = re.compile(r"\bin\s+(" + LANGS + r")\b", re.I)


def extract_language(text):
    """Explicit override like '... in hinglish'. Returns lowercase name|None."""
    m = LANG_RE.search(text or "")
    return m.group(1).lower() if m else None


def language_directive(explicit_lang=None):
    """Prompt fragment controlling draft language. English is the default."""
    if explicit_lang:
        if explicit_lang == "english":
            return "Write the message in English."
        return (
            f"IMPORTANT: Write the entire message in {explicit_lang.upper()} "
            "- natural native phrasing (for Hinglish: roman-script "
            "Hindi-English mix exactly like people text). Never output "
            "English for this one."
        )
    return (
        "Language: match the language/style of the instruction itself - "
        "if it is Hinglish or Hindi, write the message that same way; "
        "otherwise use English."
    )