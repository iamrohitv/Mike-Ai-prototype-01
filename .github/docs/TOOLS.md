# MIKE — TOOLS

## Tool Architecture

Mike should not hard-code every external capability into the reasoning
system. Use modular tools/interfaces.

```
Mike Core
  |
  +-- filesystem
  +-- terminal
  +-- Git
  +-- GitHub
  +-- email
  +-- calendar
  +-- browser
  +-- server
  +-- phone
  +-- finance
  +-- robotics
```

Each tool should define:

- What it can do
- Inputs
- Permissions
- Risks
- Confirmation level
- Results

## Authorization

Every tool gets explicit permissions. Access does not automatically
mean unlimited authority (`ACCESS != AUTHORITY`).

See POLICIES.md for the authority model.

## Implemented Tools (V0.2)

| Tool | Level | What it does |
|---|---|---|
| `note` | GREEN | Remember facts from conversation |
| `task` | GREEN | Add / list / complete tasks |
| `file` | GREEN | Read a text file and preview it |
| `project` | YELLOW | Inspect git status and branch |
| `system` | GREEN | Report OS, disk, host info |
| `terminal` | YELLOW* | Run commands; read-only auto, risky require approval |
| `git` | YELLOW* | Status, log, diff, pull, commit, push (mutating requires approval) |
| `screenshot` | GREEN | Capture the screen to `config/screenshots/` |

`*` Mutating operations (commit, push, delete, install, shutdown) are
classified ORANGE and require Rohit to say "approve" (or "deny").

Approval flow:
1. Mike asks "Say 'approve' to allow it, or 'deny' to cancel."
2. Rohit says `approve` or `deny`.
3. Mike executes and verifies, or cancels, logging the decision.

## Tool Routing

`Brain.select_tool` asks the brain to pick the best tool from the
registry. If the brain is offline, a local keyword router
(`_fallback_route`) matches the request against per-tool keyword sets
so common commands still work without network access.

## Phone Control (V0.5)

The desktop app starts a token-authenticated remote HTTP server on port
8877 in the background. On your phone (same WiFi):

1. Open `http://<pc-ip>:8877` — the JARVIS-styled mobile page loads.
2. Enter `MIKE_REMOTE_KEY` once (saved in the browser).
3. Tap the mic and speak, or type a command (briefing / status / tasks /
   compact chips included).
4. Mike processes the command on the PC and replies as text + spoken voice.

One-time setup (run PowerShell as admin):

    python -m interfaces.remote.firewall enable

Manage the rule later:

    python -m interfaces.remote.firewall disable

### Remote from anywhere (V0.6 — Tailscale)

The same phone page works from any city using [Tailscale](https://tailscale.com)
(free) — a private WireGuard mesh between your PC and phone. Your PC is never
exposed to the public internet.

1. PC: install `winget install Tailscale.Tailscale`, open it, sign in with your
   Google/Microsoft/GitHub account. It auto-runs as a Windows service.
2. Phone: install the Tailscale app from the Play Store / App Store, sign in
   with the SAME account, toggle it ON.
3. Open `http://<pc-name>.ts.net:8877` (the stable tailnet address) on the
   phone from any network — same login page, same `MIKE_REMOTE_KEY`.

When Mike's desktop app starts it prints both URLs in the chat panel:

- `phone (wifi): http://<lan-ip>:8877` — home network
- `phone (anywhere): http://<pc-name>.ts.net:8877` — from anywhere

Ask Mike `remote link` anytime to see the current URLs. The PC must be on and
awake for either link to work. No firewall rule is needed for Tailscale (it
makes an outbound connection).

### Autostart & manual start

Everything that auto-starts with Mike (phone server, opencode bridge,
autostart registry key, Tailscale) plus standalone manual commands is
documented in [AUTOSTART.md](AUTOSTART.md).

## WhatsApp Messaging

Send messages from your own WhatsApp account via WhatsApp Web (pywhatkit).

Setup (once):
1. Log into `web.whatsapp.com` in your default browser (scan QR, stay signed in).
2. Give Mike your contacts — either:
   - **Google Contacts export** (recommended): go to contacts.google.com ->
     Export -> Google CSV or vCard -> save the `.vcf` as
     `config/contacts.vcf`. Mike parses names + numbers automatically
     (prefers mobile numbers), or
   - **Manual file**: create `config/contacts.json`:
     `{ "mom": "+919876543210", "rahul": "+919812345678" }`

Usage:

    send message to rahul saying on my way          # verbatim - sends exactly
    whatsapp mom calling you in five minutes        # verbatim
    whatsapp rahul wishing him happy birthday       # Mike composes the message
    tell dad through whatsapp apologizing for delay # composed by the brain
    send msg to +919812345678 saying hi             # raw number works too

Name matching is fuzzy: first name ("rahul"), full name ("rahul sharma"),
or exact key all resolve. Re-export the vcf anytime to refresh.

When you give intent instead of exact words, Mike drafts the message with
his brain and replies showing what he sent: `Sent to rahul (+91...):
"Happy birthday! ..."`. Use "saying ..." whenever you want word-for-word.
Messages fire immediately on your command - no confirmation step.

## Development Tools (V0.2)

Potential tools: filesystem, terminal, git, GitHub, browser, code
editor interfaces, testing systems, local development environment.

Workflow:
Understand -> Inspect -> Plan -> Execute -> Test -> Verify -> Report.

Example:
Rohit: "Mike, commit this."

Mike inspects changes, understands modifications, generates an
appropriate conventional commit, commits, verifies, and reports.

Later: push, pull request, review, CI analysis, issue management.
All actions remain subject to authorization policies.