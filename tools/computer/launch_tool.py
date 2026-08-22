import os
import subprocess
import urllib.parse

from policies.engine import Level
from tools.base import Tool
from tools.computer.open_app_tool import KNOWN_APPS as OPEN_APP_KNOWN_APPS


LAUNCH_APPS = {
    **OPEN_APP_KNOWN_APPS,
    "vscode": "code.exe",
    "code": "code.exe",
    "vs code": "code.exe",
    "visual studio code": "code.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "browser": "msedge.exe",
}


BROWSERS = {"chrome", "firefox", "edge", "browser"}

COMMON_SITES = {
    "youtube": "https://youtube.com",
    "google": "https://google.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit": "https://reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "facebook": "https://facebook.com",
    "instagram": "https://instagram.com",
    "linkedin": "https://linkedin.com",
    "gmail": "https://gmail.com",
    "outlook": "https://outlook.com",
    "drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "netflix": "https://netflix.com",
    "spotify": "https://spotify.com",
    "amazon": "https://amazon.com",
    "wikipedia": "https://wikipedia.org",
}


class LaunchTool(Tool):
    name = "launch"
    description = "open a file in an app, open a URL in a browser, or open a folder in Explorer"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "open ",
                "launch ",
                "start ",
                "browse ",
            ]
        )

    def run(self, request):
        lowered = request.lower().strip()

        for trigger in ("open ", "launch ", "start ", "browse "):
            if lowered.startswith(trigger):
                target = lowered[len(trigger):].strip()
                break
        else:
            target = lowered

        if not target:
            return "What would you like me to open?"

        if target.startswith("to "):
            target = target[3:].strip()

        # strip common prefixes
        for prefix in ("folder ", "directory ", "dir "):
            if target.startswith(prefix):
                target = target[len(prefix):].strip()
                break

        if " in " in target:
            return self._handle_open_with(target)
        if self._is_url(target):
            return self._open_url(target)
        if os.path.isdir(target):
            return self._open_folder(target)
        if os.path.isfile(target):
            return self._open_file_default(target)
        if target in LAUNCH_APPS:
            return self._launch_app(target)
        return f"I don't know how to open '{target}'. Try a file path, folder, URL, or known app."

    def _is_url(self, text):
        # Don't treat file paths with extensions as URLs
        if os.path.exists(text):
            return False
        return text.startswith(("http://", "https://", "www.")) or (
            "." in text and " " not in text and not os.path.exists(text)
        ) or text.lower() in COMMON_SITES

    def _handle_open_with(self, target):
        parts = target.split(" in ", 1)
        file_or_url = parts[0].strip()
        app_name = parts[1].strip().lower()

        resolved_path = self._resolve_file_path(file_or_url)
        if os.path.isfile(resolved_path):
            return self._open_file_with_app(resolved_path, app_name)
        if os.path.isdir(resolved_path):
            return self._open_folder_in_explorer(resolved_path)
        # Fallback to URL handling
        if self._is_url(file_or_url):
            return self._open_url_in_browser(file_or_url, app_name)
        return f"Could not find '{file_or_url}' to open with {app_name}."

    def _open_url(self, url):
        url = url.strip()
        if url.lower() in COMMON_SITES:
            url = COMMON_SITES[url.lower()]
        elif not url.startswith(("http://", "https://")):
            url = "https://" + url
        return self._launch_url(url)

    def _open_url_in_browser(self, url, browser_name):
        url = url.strip()
        if url.lower() in COMMON_SITES:
            url = COMMON_SITES[url.lower()]
        elif not url.startswith(("http://", "https://")):
            url = "https://" + url
        return self._launch_url(url)

    def _resolve_browser(self, name):
        if name in BROWSERS:
            return LAUNCH_APPS.get(name, "msedge.exe")
        return LAUNCH_APPS.get(name, "msedge.exe")

    def _launch_url(self, url):
        try:
            subprocess.Popen(["start", "", url], shell=True)
            return f"Opening {url}..."
        except Exception as exc:
            return f"Failed to open URL: {exc}"

    def _resolve_file_path(self, file_path):
        if os.path.isabs(file_path) and os.path.isfile(file_path):
            return file_path
        if os.path.isfile(file_path):
            return os.path.abspath(file_path)
        # check common locations
        home = os.path.expanduser("~")
        for base in (os.path.join(home, "OneDrive", "Desktop"), os.path.join(home, "Desktop"), os.path.join(home, "Documents"), os.path.join(home, "Downloads")):
            full = os.path.join(base, file_path)
            if os.path.isfile(full):
                return full
        return file_path

    def _open_file_with_app(self, file_path, app_name):
        file_path = self._resolve_file_path(file_path)
        app_exe = LAUNCH_APPS.get(app_name)
        if not app_exe:
            return f"I don't know the app '{app_name}'. Try vscode, notepad, chrome, etc."
        try:
            subprocess.Popen([app_exe, file_path], shell=False)
            return f"Opening {file_path} in {app_name}..."
        except Exception as exc:
            return f"Failed to open {file_path} in {app_name}: {exc}"

    def _open_file_default(self, file_path):
        try:
            os.startfile(file_path)
            return f"Opening {file_path} with default app..."
        except Exception as exc:
            return f"Failed to open {file_path}: {exc}"

    def _open_folder(self, folder_path):
        try:
            subprocess.Popen(["explorer.exe", folder_path], shell=False)
            return f"Opening folder {folder_path} in Explorer..."
        except Exception as exc:
            return f"Failed to open folder: {exc}"

    def _open_folder_in_explorer(self, folder_path):
        return self._open_folder(folder_path)

    def _launch_app(self, app_name):
        app_exe = LAUNCH_APPS.get(app_name)
        if not app_exe:
            return f"I don't know the app '{app_name}'."
        try:
            subprocess.Popen(app_exe, shell=isinstance(app_exe, str))
            return f"Launching {app_name}..."
        except Exception as exc:
            return f"Failed to launch {app_name}: {exc}"

    def verify(self, result):
        if "Opening" in result or "Launching" in result:
            return "verified: launched"
        if "Failed" in result or "don't know" in result or "Could not find" in result:
            return "failed"
        return "completed"