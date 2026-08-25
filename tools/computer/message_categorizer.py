"""Auto-categorize unread messages into: work, friends, company, personal, other.

Uses signals:
- Email domain patterns
- Sender name matching against contacts.json categories
- Subject keyword matching
- WhatsApp contact name matching
Defaults to 'personal' / 'other' when unsure.
"""

from pathlib import Path
import re

from security.paths import get_config_path

CONTACTS_JSON = Path(get_config_path()) / "contacts.json"


def _load_contacts():
    """Load contacts.json; return dict mapping normalized name -> {value, category}."""
    try:
        from tools.computer.contacts import load_contacts
        raw = load_contacts()
        # backward compat: simple {"name": "value"} or enhanced {"name": {"value": "...", "category": "..."}}
        result = {}
        for name, value in raw.items():
            if isinstance(value, dict):
                result[_normalize_name(name)] = value.get("category", "personal")
            else:
                result[_normalize_name(name)] = "personal"
        return result
    except Exception:
        return {}


_CONTACT_CATEGORIES = None  # lazily loaded


def _get_contact_categories():
    global _CONTACT_CATEGORIES
    if _CONTACT_CATEGORIES is None:
        _CONTACT_CATEGORIES = _load_contacts()
    return _CONTACT_CATEGORIES


def _normalize_name(name):
    """Normalize a name for dict-key lookup."""
    return re.sub(r"\s+", " ", name or "").strip().lower()


def _email_domain(email):
    """Extract domain from email address."""
    if not email:
        return ""
    m = re.search(r"@([^@\s]+)", email)
    return m.group(1).lower() if m else ""


def _has_keyword(text, keywords):
    """Check if any keyword appears in text (case-insensitive)."""
    if not text:
        return False
    tl = text.lower()
    return any(kw.lower() in tl for kw in keywords)


def categorize_message(sender, subject, is_whatsapp=False, contact_name=None):
    """Categorize a single message into work/friends/company/personal/other.

    Signals (in priority order):
    1. WhatsApp contact's explicit category (from contacts.json)
    2. Email domain patterns
    3. Subject keyword matches
    4. Sender name matching contacts categories
    5. Default: personal / other
    """
    # 1. WhatsApp contact category
    if is_whatsapp and contact_name:
        cats = _get_contact_categories()
        cnorm = _normalize_name(contact_name)
        if ncat := cats.get(cnorm):
            return ncat

# 2. Email domain patterns (only for non-WhatsApp)
    if not is_whatsapp and sender:
        domain = _email_domain(sender)
        if not domain:
            # No domain (e.g. raw number); treat as personal
            pass
        else:
            # Personal free domains first (most specific)
            personal_domains = {"gmail.com", "yahoo.com", "outlook.com",
                               "hotmail.com", "protonmail.com",
                               "aol.com", "icloud.com"}
            if domain in personal_domains:
                return "personal"

            # Company domains
            company_domains = {"apple.com", "google.com", "microsoft.com",
                              "amazon.com", "meta.com",
                              "x.com", "twitter.com", "linkedin.com",
                              "netflix.com", "spotify.com", "dropbox.com",
                              "slack.com", "teams.microsoft.com",
                              "github.com", "gitlab.com", "bitbucket.org"}
            if domain in company_domains:
                return "company"

            # Likely work corporate domain (any other .com/.co/.net etc.)
            # but only if it looks like a corporate domain (has dots, not just a name)
            # Default to "work" for unknown domains that aren't personal
            return "work"

    # 3. Subject keyword matches
    if subject:
        work_kw = ["collaboration", "meeting", "project", "invoice", "approval",
                  "budget", "RFP", "tender", "contract", "deliverable"]
        friends_kw = ["party", "dinner", "catch up", "hang out", "weekend",
                     "birthday", "celebration", "outing", "drinks"]
        if _has_keyword(subject, work_kw):
            return "work"
        if _has_keyword(subject, friends_kw):
            return "friends"

    # 4. Sender name matching against contacts categories
    cats = _get_contact_categories()
    if sender:
        cnorm = _normalize_name(sender)
        if ncat := cats.get(cnorm):
            return ncat

    # 5. Default
    # If WhatsApp contact with no category -> other; else personal
    if is_whatsapp:
        return "other"
    return "personal"


def categorize_items(items, is_whatsapp=False, subject_getter=None):
    """Categorize a list of (name_or_sender, detail) items.

    items: list of (title, detail) tuples
    subject_getter: optional callable(detail) -> subject string, or None
    """
    cats_count = {"work": 0, "friends": 0, "company": 0, "personal": 0, "other": 0}
    cat_items = {"work": [], "friends": [], "company": [], "personal": [], "other": []}

    for title, detail in items:
        # Determine category
        if is_whatsapp:
            # For WhatsApp, contact name is first element, detail is "N new | preview"
            contact_name = title
            # Extract preview from detail if present
            subject = None
            if subject_getter:
                subject = subject_getter(detail)
            cat = categorize_message(None, subject, is_whatsapp=True, contact_name=contact_name)
        else:
            # For Gmail: title is sender, detail is "subject [date]"
            sender = title
            subject = None
            if subject_getter:
                subject = subject_getter(detail)
            elif "[" in detail:
                # Parse "subject [date]"
                m = re.match(r"(.+?)\s+\[", detail)
                if m:
                    subject = m.group(1).strip()
            cat = categorize_message(sender, subject, is_whatsapp=False)

        cats_count[cat] += 1
        cats_count.setdefault(cat, 0)
        cats_count[cat] = cats_count.get(cat, 0) + 1  # ensure increment
        # Actually let me redo this more cleanly below

    # Redo cleanly:
    cats_count = {"work": 0, "friends": 0, "company": 0, "personal": 0, "other": 0}
    cat_items = {"work": [], "friends": [], "company": [], "personal": [], "other": []}

    for item in items:
        if is_whatsapp:
            title, detail = item
            contact_name = title
            subject = None
            if subject_getter:
                subject = subject_getter(detail)
            cat = categorize_message(None, subject, is_whatsapp=True, contact_name=contact_name)
        else:
            title, detail = item
            sender = title
            subject = None
            if subject_getter:
                subject = subject_getter(detail)
            elif "[" in detail:
                m = re.match(r"(.+?)\s+\[", detail)
                if m:
                    subject = m.group(1).strip()
            cat = categorize_message(sender, subject, is_whatsapp=False)

        cats_count[cat] = cats_count.get(cat, 0) + 1
        cat_items[cat].append(item)

    return cats_count, cat_items