"""Contact resolution for messaging tools.

Sources, merged in priority order (later overrides earlier):
  1. config/contacts.vcf   - Google Contacts export (Export -> vCard)
  2. config/contacts.json  - manual overrides {"mom": "+91..."}

resolve("rahul") -> "+919876543210" or None.
Raw numbers ("+91 98765 43210") pass through unchanged.
"""

import difflib
import json
import os
import re
import quopri

from security.paths import get_config_path

_PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{6,}$")


def _vcf_path():
    return os.path.join(get_config_path(), "contacts.vcf")


def _json_path():
    return os.path.join(get_config_path(), "contacts.json")


def _decode_value(value):
    """Decode a vCard value, handling quoted-printable UTF-8."""
    value = value.strip()
    if value.upper().startswith("=?UTF-8?"):
        try:
            parts = re.findall(r"=\?UTF-8\?([QBQq])\?(.*?)\?=", value, re.I)
            decoded = "".join(
                quopri.decodestring(part.encode("ascii")).decode("utf-8")
                for _, part in parts
            )
            if decoded:
                return decoded
        except Exception:  # noqa: BLE001
            pass
    return value


def _normalize_number(raw):
    digits = re.sub(r"[\s\-()]", "", raw)
    return digits


def _normalize_name(name):
    return re.sub(r"\s+", " ", name).strip().lower()


def parse_vcf(path):
    """Parse a vCard file into {normalized_name: normalized_number}."""
    contacts = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return contacts

    for block in re.findall(
        r"BEGIN:VCARD(.*?)END:VCARD", content, re.S | re.I
    ):
        lines = [
            l.strip() for l in block.replace("\r\n", "\n").split("\n") if l.strip()
        ]
        # unfold folded lines (continuation lines start with space/tab)
        unfolded = []
        for line in lines:
            if line[:1] in (" ", "\t") and unfolded:
                unfolded[-1] += line[1:]
            else:
                unfolded.append(line)

        name = ""
        phones = []
        preferred = []
        for line in unfolded:
            upper = line.upper()
            if upper.startswith("FN:") and not name:
                name = _decode_value(line[3:])
            elif upper.startswith("TEL"):
                value = line.split(":", 1)[-1]
                if not value:
                    continue
                number = _normalize_number(value)
                if len(re.sub(r"\D", "", number)) < 7:
                    continue
                phones.append(number)
                type_part = line.split(":", 1)[0].upper()
                if "CELL" in type_part or "MOBILE" in type_part:
                    preferred.append(number)

        if name and phones:
            number = preferred[0] if preferred else phones[0]
            contacts[_normalize_name(name)] = number
    return contacts


def load_json_contacts(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        _normalize_name(k): _normalize_number(str(v))
        for k, v in data.items()
        if str(v).strip()
    }


def load_contacts():
    """Merged contact book: vcf first, json overrides."""
    contacts = parse_vcf(_vcf_path())
    contacts.update(load_json_contacts(_json_path()))
    return contacts


def is_raw_number(text):
    return bool(_PHONE_RE.match(text.strip()))


def _score(query, candidate):
    q = query.strip()
    c = candidate.strip()
    if not q or not c:
        return 0
    if q == c:
        return 100
    c_tokens = c.split()
    if len(q.split()) == 1 and c_tokens and q == c_tokens[0]:
        return 90  # first-name hit
    if q in c or c in q:
        return 60
    q_tokens = set(q.split())
    c_tokens_set = set(c_tokens)
    if q_tokens and q_tokens.issubset(c_tokens_set):
        return 50
    return 0


def resolve(name, contacts=None):
    """Fuzzy-resolve a contact name to a phone number, or None."""
    number, _key, _fuzzy = resolve_detailed(name, contacts)
    return number


def resolve_detailed(name, contacts=None):
    """Resolve returning (number|None, matched_key|None, fuzzy_bool).

    fuzzy_bool=True means a close-but-not-certain match (typo like
    'rhit' -> 'rohit'); callers should confirm before sending.
    """
    text = name.strip()
    if is_raw_number(text):
        return _normalize_number(text), None, False
    query = _normalize_name(text)
    if not query:
        return None, None, False
    if contacts is None:
        contacts = load_contacts()
    if not contacts:
        return None, None, False
    if query in contacts:
        return contacts[query], query, False
    best_key, best_score = None, 0
    for key in contacts:
        s = _score(query, key)
        if s > best_score:
            best_key, best_score = key, s
    if best_key and best_score >= 90:
        return contacts[best_key], best_key, False
    # typo-tier: difflib similarity ('rhit' -> 'rohit sharma' ~ 0.67)
    close = difflib.get_close_matches(query, list(contacts), n=1, cutoff=0.6)
    if close:
        return contacts[close[0]], close[0], True
    return None, None, False