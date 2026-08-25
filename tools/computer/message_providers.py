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


def _real_edge_user_data():
    """Path to the real Microsoft Edge 'User Data' dir, or None."""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    p = Path(local) / "Microsoft" / "Edge" / "User Data"
    return p if p.is_dir() else None


def _use_real_edge_profile():
    """True when Rohit wants Mike on his actual Edge login."""
    return os.environ.get("MIKE_WA_USE_REAL_EDGE", "").strip() == "1"


def _edge_profile_dir():
    """Which Edge profile holds WhatsApp ('Default', 'Profile 1', ...)."""
    return os.environ.get("MIKE_WA_EDGE_PROFILE", "").strip() or "Default"


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
_ROW_SELECTOR = "#pane-side div[role='row'], #pane-side div[aria-label*='Chat list'] def"


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
    """Fetch unread WhatsApp Web messages.

    Tries Microsoft Edge first; falls back to Chrome if Edge is not available.
    Uses a dedicated browser profile directory at ``config/wa_profile`` so
    the user only needs to scan the QR code once.
    """
    try:
        from selenium import webdriver
    except ImportError:
        return {"ok": False, "items": [],
                "note": "selenium missing - pip install selenium"}

    # ---- pick a browser ----------------------------------------------------
    edge_options = None
    chrome_options = None
    using_real_edge = _use_real_edge_profile() and _real_edge_user_data()

    if using_real_edge:
        user_data = str(_real_edge_user_data())
        profile_dir = _edge_profile_dir()
    else:
        WA_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        user_data = str(WA_PROFILE_DIR)
        profile_dir = "Default"

    # 1) Try Edge
    try:
        from selenium.webdriver.edge.options import Options as EdgeOptions
        edge_options = EdgeOptions()
        edge_options.add_argument(f"--user-data-dir={user_data}")
        edge_options.add_argument(f"--profile-directory={profile_dir}")
        edge_options.add_argument("--log-level=3")
        edge_options.add_argument("--no-first-run")
        edge_options.add_argument("--disable-notifications")
    except Exception:  # noqa: BLE001
        edge_options = None

    # 2) Try Chrome (dedicated profile only - never touch real Chrome data)
    try:
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        chrome_options = ChromeOptions()
        chrome_options.add_argument(f"--user-data-dir={user_data}")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-notifications")
    except Exception:  # noqa: BLE001
        chrome_options = None

    # 3) Fallback order: Edge > Chrome
    selected_options = edge_options or chrome_options
    if not selected_options:
        return {"ok": False, "items": [],
                "note": "no supported browser (edge/chrome) selenium options found"}

    # ---- launch the browser ------------------------------------------------
    driver = None
    try:
        if edge_options is not None:
            from selenium.webdriver.edge.service import Service as EdgeService
            # Try common edge driver locations
            edge_driver_path = None
            for candidate in [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedgedriver.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedgedriver.exe",
                None,  # let selenium find it on PATH
            ]:
                if candidate and os.path.exists(candidate):
                    edge_driver_path = candidate
                    break
            if edge_driver_path:
                driver = webdriver.Edge(service=EdgeService(edge_driver_path),
                                        options=edge_options)
            else:
                driver = webdriver.Edge(options=edge_options)
        else:
            from selenium.webdriver.chrome.service import Service as ChromeService
            chrome_driver_path = None
            for candidate in [
                r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
                r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
                None,
            ]:
                if candidate and os.path.exists(candidate):
                    chrome_driver_path = candidate
                    break
            if chrome_driver_path:
                driver = webdriver.Chrome(service=ChromeService(chrome_driver_path),
                                          options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)

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
        raw = str(exc)
        msgt = raw.splitlines()[0][:90] if raw else "unknown"
        lowered = (raw + type(exc).__name__).lower()
        if "user data directory is already in use" in lowered or \
                "devtoolsactiveport" in lowered or "only one instance" in lowered:
            note = ("whatsapp: Microsoft Edge is open right now - close all "
                    "Edge windows and ask again")
        elif "timeout" in lowered:
            if using_real_edge:
                note = ("whatsapp: the selected Edge profile ('"
                        + _edge_profile_dir() + "') isn't logged into "
                        "WhatsApp - set MIKE_WA_EDGE_PROFILE to the other "
                        "profile in config/.env, or open WhatsApp once there")
            else:
                note = ("first time? a browser is asking you to scan the QR "
                        "with your phone - do it once, then retry")
        else:
            note = msgt
        return {"ok": False, "items": [], "note": f"whatsapp: {note}"}
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:  # noqa: BLE001
            pass


def list_edge_profiles():
    """Return [(profile_dir_name, account_name)] from Edge's Local State."""
    base = _real_edge_user_data()
    if not base:
        return []
    try:
        import json
        with open(base / "Local State", "r", encoding="utf-8") as f:
            state = json.load(f)
        cache = state.get("profile", {}).get("info_cache", {})
        out = []
        for dirname, info in cache.items():
            name = (info.get("name") or info.get("user_name")
                    or dirname).strip()
            email = (info.get("user_name") or "").strip()
            label = f"{name} <{email}>" if email else name
            out.append((dirname, label))
        return out
    except Exception:  # noqa: BLE001
        return []


if __name__ == "__main__":
    print("Edge profiles found:")
    found = list_edge_profiles()
    if not found:
        print("  (none - or Edge not installed at the default location)")
    for dirname, label in found:
        marker = ("  <- current MIKE_WA_EDGE_PROFILE"
                  if dirname == _edge_profile_dir() else "")
        print(f"  {dirname}: {label}{marker}")
    print("\nTo use your real logged-in WhatsApp profile, set in config/.env:")
    print("  MIKE_WA_USE_REAL_EDGE=1")
    print("  MIKE_WA_EDGE_PROFILE=<dir name from above>")