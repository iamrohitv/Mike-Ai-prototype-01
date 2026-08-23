# Mike — Autostart & Connection Guide

Everything that starts automatically with Mike, plus how to run each piece
manually when you need to.

---

## What Auto-Starts

| Component | Trigger | Port / Location |
|---|---|---|
| **Mike desktop app** | Windows boot (registry Run key, starts hidden in tray) | — |
| **Phone remote server** | Inside desktop app at launch | `0.0.0.0:8877` |
| **opencode bridge** | Inside desktop app at launch | `127.0.0.1:8765` |
| **Tailscale** | Windows service (always on after sign-in) | tailnet |

You only ever launch one thing: **Mike**. Everything else comes up with it.

---

## 1. Mike Desktop App

### Autostart (already enabled)
Runs at Windows login, minimized to tray. Registry Run key points to:

```
pythonw -m interfaces.desktop.app --hidden
```

### Manual start
```powershell
cd E:\code-2026\mike-AI
pythonw -m interfaces.desktop.app          # visible window
pythonw -m interfaces.desktop.app --hidden # hidden to tray
```
Or double-click **MIKE.lnk** on your Desktop.

### Enable / disable autostart
```powershell
python -m interfaces.desktop.autostart enable
python -m interfaces.desktop.autostart disable
```

### Quit completely
Tray icon → **Quit** (shuts down remote server + bridge too).

---

## 2. Phone Remote Server (:8877)

Auto-starts inside the desktop app. The chat panel shows both links at launch:

```
— phone (wifi): http://<lan-ip>:8877 —
— phone (anywhere): http://<pc-name>.tailXXXX.ts.net:8877 —
```

### Connect from phone
1. **Same WiFi:** open `http://<lan-ip>:8877` in any browser.
2. **Anywhere (Tailscale):** turn Tailscale ON on the phone, open the
   `ts.net` link from any network (4G/5G included).
3. Enter `MIKE_REMOTE_KEY` once (from `config/.env`) — saved in the browser.

### One-time setup checklist
```powershell
# Tailscale on PC + phone, same account:
winget install Tailscale.Tailscale     # PC; then sign in
# Phone: install Tailscale from Play Store / App Store, same account, toggle ON

# Firewall rule for LAN access (run PowerShell as admin):
python -m interfaces.remote.firewall enable
```

### Standalone manual start (without desktop app)
```powershell
python -m interfaces.remote.server 8877
```

### Ask Mike
```
"remote link"   → Mike replies with both URLs
```

> PC must be ON and awake for either link to work.

---

## 3. opencode Bridge (:8765)

Lets you hand coding tasks to the opencode agent through Mike:

```
You:  "opencode create a rest api in flask"
Mike: "Created app.py with two routes. Run it with: python app.py"
```

### Auto-start
Starts inside the desktop app. Chat panel confirms:
```
— opencode bridge: ready on :8765 — say 'opencode <task>' —
```

### Manual standalone start
```powershell
cd E:\code-2026\mike-AI
python tools/computer/opencode_bridge.py        # default port 8765
python tools/computer/opencode_bridge.py 9000   # custom port
```

### Health check
```powershell
curl http://127.0.0.1:8765/bridge/health
# {"status": "ok", "queue_exists": false}
```

### Direct API use (no Mike)
```powershell
curl -X POST http://127.0.0.1:8765/bridge/command `
  -H "Content-Type: application/json" `
  -d '{"command": "create a hello world script", "id": "test1"}'
```

### Prerequisite
```powershell
npm install -g @opencode-ai/cli-windows-x64
opencode --version   # should print a version
```

Tasks run inside `E:\code-2026\mike-AI` (the repo root).

---

## 4. Tailscale Service

Installed once; runs as a Windows service forever after sign-in.

```powershell
winget install Tailscale.Tailscale
tailscale status    # verify: BackendState "Running"
```

Phone: install the app, sign into the **same account**, toggle ON.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Phone page unreachable on WiFi | Firewall: `python -m interfaces.remote.firewall enable` (admin) |
| Phone unreachable away from home | Tailscale OFF on phone → toggle it ON |
| Bridge line says "offline" | Start manually: `python tools/computer/opencode_bridge.py`, or check `opencode --version` |
| `"Error: 'opencode' not found"` | Install CLI: `npm install -g @opencode-ai/cli-windows-x64` |
| Port already in use | A bridge/server is already running — that's fine, it reuses it |
| Nothing responds at all | PC asleep — wake it; Mike must be running (check tray icon) |
| Wrong Desktop folder used | Mike auto-detects `OneDrive\Desktop` first, falls back to `Desktop` |
