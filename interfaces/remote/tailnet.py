import json
import os
import subprocess
from pathlib import Path

_CANDIDATE_BINS = [
    r"C:\Program Files\Tailscale\tailscale.exe",
    str(Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Tailscale" / "tailscale.exe"),
    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tailscale" / "tailscale.exe"),
    "/usr/bin/tailscale",
    "/usr/local/bin/tailscale",
    "tailscale",
]


def _find_bin():
    for candidate in _CANDIDATE_BINS:
        if candidate == "tailscale":
            from shutil import which
            if which("tailscale"):
                return "tailscale"
            continue
        if os.path.exists(candidate):
            return candidate
    return None


def _run(bin_path, *args, timeout=3):
    try:
        proc = subprocess.run(
            [bin_path, *args],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            return None
        return proc.stdout
    except Exception:  # noqa: BLE001
        return None


def tailscale_available():
    return _find_bin() is not None


def tailnet_status():
    """Return tailnet info dict or None when Tailscale is missing/off."""
    bin_path = _find_bin()
    if not bin_path:
        return None
    out = _run(bin_path, "status", "--json")
    if not out:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        return None
    if data.get("BackendState") != "Running":
        return None
    self_node = data.get("Self") or {}
    tailnet = data.get("CurrentTailnet") or {}
    return {
        "hostname": self_node.get("HostName", ""),
        "dns_name": (self_node.get("DNSName") or "").rstrip("."),
        "magic_dns": bool(tailnet.get("MagicDNSEnabled", False)),
        "ip": (self_node.get("TailscaleIPs") or [None])[0],
        "online": bool(self_node.get("Online", False)),
        "tailnet": tailnet.get("Name", ""),
    }


def tailnet_url(port=8877):
    """Stable URL for reaching this machine from anywhere: http://<name>.ts.net:port"""
    info = tailnet_status()
    if not info or not info.get("online"):
        return None
    host = info["dns_name"] if info.get("magic_dns") and info.get("dns_name") else info.get("ip")
    if not host:
        return None
    return f"http://{host}:{port}"