"""Providers that fetch new messages for the messages tool.

Each provider returns a dict:
    {"ok": bool, "items": [..], "note": str}

items are (title, detail) tuples ready for display.
"""

import email
import imaplib
import os
import re
from email.header import decode_header
from pathlib import Path

from security.paths import get_config_path

WA_PROFILE_DIR = Path(get_config_path()) / "wa_profile"
WA_URL = "https://web.whatsapp.com"


# --------------------------------------------------------------------- #
# Gmail
# --------------------------------------------------------------------- #
def _decode(raw):
    if not raw:
        return ""
    out = ""
    for text, enc in decode_header(raw):
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", "replace")
        else:
            out += text
    return out


def _email_account():
    return (
        os.environ.get("MIKE_EMAIL_ADDRESS", "").strip(),
        os.environ.get("MIKE_EMAIL_APP_PASSWORD", "").strip(),
    )


def fetch_unread_emails(limit=6):
    addr, pw = _email_account()
    if not addr or not pw:
        return {"ok": False, "items": [],
                "note": "email not configured (config/.env)"}
    try:
        m = imaplib.IMAP4_SSL("imap.gmail.com")
        m.login(addr, pw)
        m.select("INBOX", readonly=True)
        _, data = m.search(None, "(UNSEEN)")
        ids = data[0].split()
        items = []
        for mid in reversed(ids[-limit:]):
            _, md = m.fetch(
                mid,
                "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])",
            )
            msg = email.message_from_bytes(md[0][1])
            sender = _decode(msg.get("From"))
            name = re.split(r"<", sender)[0].strip().strip('"') or sender
            subj = _decode(msg.get("Subject")) or "(no subject)"
            when = (msg.get("Date") or "")[:16]
            items.append((name[:28], f"{subj}  [{when}]"))
        m.logout()
        return {"ok": True, "items": items,
                "note": f"{len(ids)} unread mail(s)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "items": [], "note": f"gmail error: {exc}"}


# --------------------------------------------------------------------- #
# WhatsApp Web (selenium, dedicated profile - scan QR once)
# --------------------------------------------------------------------- #
_BADGE_SELECTORS = [
    "span[aria-label]",
    "[data-testid='icon-unread-count']",
]
_ROW_SELECTOR = "#pane-side div[role='row'], #pane-side div[aria-label*='Chat list'] div"


def _digits(text):
    mm = re.search(r"\d+", text or "")
    return int(mm.group()) if mm else 1


def parse_chat_rows(rows):
    """Best-effort extraction of unread chats from whatsapp web rows."""
    chats = []
    for row in rows:
        try:
            count = None
            for sel in _BADGE_SELECTORS:
                for span in row.find_elements("css selector", sel):
                    label = (span.get_attribute("aria-label")
                             or span.text or "").strip()
                    if re.fullmatch(r"\d+", label) and int(label) > 0:
                        count = int(label)
                        break
                if count:
                    break
            if not count:
                continue
            name = "?"
            for cand in row.find_elements(
                    "css selector", "span[title], div[title], strong"):
                t = (cand.get_attribute("title") or cand.text or "").strip()
                if t and len(t) > 1 and not t.isdigit():
                    name = t
                    break
            preview = ""
            try:
                previews = row.find_elements(
                    "css selector", "span[dir='ltr'], span[dir='auto']")
                texts = [p.text.strip() for p in previews if p.text.strip()]
                if len(texts) >= 2:
                    preview = texts[-1][:60]
            except Exception:  # noqa: BLE001
                pass
            chats.append((name[:26], count, preview))
        except Exception:  # noqa: BLE001
            continue
    return chats


def fetch_whatsapp_unreads(wait_seconds=25):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        return {"ok": False, "items": [],
                "note": "selenium missing - pip install selenium"}

    WA_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    opts = Options()
    opts.add_argument(f"--user-data-dir={WA_PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--log-level=3")
    opts.add_argument("--no-first-run")
    opts.add_argument("--disable-notifications")
    driver = None
    try:
        driver = webdriver.Chrome(options=opts)
        driver.set_window_size(1200, 900)
        driver.get(WA_URL)

        # logged in? pane-side appears; otherwise QR -> user must scan once
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        def pane(drv):
            return drv.find_elements(By.CSS_SELECTOR, "#pane-side")

        WebDriverWait(driver, wait_seconds).until(lambda d: pane(d))
        rows = driver.find_elements(By.CSS_SELECTOR, _ROW_SELECTOR)
        chats = parse_chat_rows(rows)
        note = f"{len(chats)} chat(s) with unreads"
        if not chats:
            note += " (or selectors missed - open whatsapp to verify)"
        return {"ok": True, "items":
                [(n, f"{c} new | {p}" if p else f"{c} new")
                 for n, c, p in chats],
                "note": note}
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).splitlines()[0][:90] if str(exc) else "unknown"
        qr_hint = ("first time? a Chrome window is asking you to scan the QR "
                   "with your phone - do it once, then retry"
                   if "TimeoutException" in type(exc).__name__ or
                   "timeout" in msg.lower() else msg)
        return {"ok": False, "items": [], "note": f"whatsapp: {qr_hint}"}
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:  # noqa: BLE001
            pass