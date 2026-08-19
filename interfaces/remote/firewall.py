import subprocess
import sys


def firewall_rule_exists(name="Mike Remote (8877)"):
    try:
        proc = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode == 0 and name in proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def enable_firewall(port=8877, name="Mike Remote (8877)"):
    if firewall_rule_exists(name):
        return f"Firewall rule '{name}' already exists."
    try:
        proc = subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={name}",
                "dir=in",
                "action=allow",
                f"protocol=TCP",
                f"localport={port}",
                "profile=private",
            ],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Could not run netsh: {exc}"
    if proc.returncode == 0:
        return f"Firewall opened port {port} for private networks."
    return f"Firewall rule failed: {proc.stderr.strip() or proc.stdout.strip()}"


def disable_firewall(name="Mike Remote (8877)"):
    if not firewall_rule_exists(name):
        return f"Firewall rule '{name}' does not exist."
    try:
        proc = subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Could not run netsh: {exc}"
    if proc.returncode == 0:
        return f"Firewall rule '{name}' removed."
    return f"Firewall rule removal failed: {proc.stderr.strip() or proc.stdout.strip()}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "enable"
    if action == "enable":
        print(enable_firewall())
    elif action == "disable":
        print(disable_firewall())
    else:
        print("usage: python -m interfaces.remote.firewall [enable|disable]")