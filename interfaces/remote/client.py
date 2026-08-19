import json
import sys
import urllib.request


def chat(message, key, base="http://127.0.0.1:8877"):
    body = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/chat", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["reply"]


def status(key, base="http://127.0.0.1:8877"):
    req = urllib.request.Request(
        f"{base}/api/status",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def briefing(key, base="http://127.0.0.1:8877"):
    req = urllib.request.Request(
        f"{base}/api/briefing",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["briefing"]


def history(key, limit=30, base="http://127.0.0.1:8877"):
    req = urllib.request.Request(
        f"{base}/api/history?limit={limit}",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["history"]


def tools(key, base="http://127.0.0.1:8877"):
    req = urllib.request.Request(
        f"{base}/api/tools",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["tools"]


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "mike-remote-dev-key"
    message = sys.argv[2] if len(sys.argv) > 2 else "system status"
    print(chat(message, key))