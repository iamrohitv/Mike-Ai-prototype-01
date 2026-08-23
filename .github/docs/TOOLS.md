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

## Implemented Tools

| Tool | Level | What it does |
|---|---|---|
| `note` | GREEN | Remember facts from conversation |
| `task` | GREEN | Add / list / complete tasks |
| `file` | GREEN | Read a text file and preview it |
| `file_ops` | YELLOW* | Create / read / write / append / replace / delete files & folders (natural language) |
| `launch` | GREEN | Open a file in an app, URL in browser, folder in Explorer |
| `open_app` | GREEN | Launch installed apps by name (notepad, vscode, chrome...) |
| `contacts` | YELLOW | Save numbers/emails under names; list contacts |
| `whatsapp` | YELLOW* | Send WhatsApp messages via WhatsApp Web (verbatim or brain-drafted) |
| `email` | YELLOW* | Send Gmail via app password (verbatim or brain-composed subject+body) |
| `calculator` | GREEN | Safe AST arithmetic ("what is 12 * (8 + 4) / 3") |
| `project` | YELLOW | Inspect git status and branch |
| `system` | GREEN | Report OS, disk, host info |
| `terminal` | YELLOW* | Run commands; read-only auto, risky require approval |
| `git` | YELLOW* | Status, log, diff, pull, commit, push (mutating requires approval) |
| `screenshot` | GREEN | Capture the screen to `config/screenshots/` |
| `opencode` | YELLOW | Route coding tasks to the opencode CLI via local bridge (:8765) |

`*` Mutating operations (write, delete, send, commit, push, install,
shutdown) escalate to ORANGE and require Rohit to say "approve"
(or "deny"). GREEN runs automatically; YELLOW runs and logs.

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

## File Operations

Natural-language file management (OneDrive Desktop auto-detected first).

    create file notes.txt                          -> Mike ASKS where
    desktop                                        -> completes on Desktop
    create a python file of calculator app on desktop  -> calculator app.py
    make a markdown file named ideas on desktop         -> ideas.md
    write hello to notes.txt on desktop            # overwrite (approval)
    append another line to notes.txt on desktop
    replace old with new in notes.txt on desktop   # approval
    delete file junk.txt / delete folder tmp       # approval

- Spoken types become extensions: python/py, markdown/md, json, csv, html,
  js, java, sql, yaml, bat, ps1 — never part of the filename.
- No location given for create/write? Mike asks; answer with `desktop`,
  `documents`, `downloads`, an `<X> drive`, or a full path.

## App & Web Launcher

    open main.py in vscode        # any file in any known app
    browse to github.com          # default browser
    open https://x.com in chrome
    open folder C:\Projects
    launch notepad                # or: open notepad / start spotify

Known apps: notepad, calc, paint, cmd, powershell, explorer, settings,
task manager, chrome, firefox, edge, vscode, discord, spotify, steam,
outlook, teams, zoom, slack, whatsapp, telegram. Files resolve from cwd,
Desktop, Documents and Downloads automatically.

## Contacts Manager

    save number 9876543210 as mom        # +91 assumed for bare numbers
    save contact boss boss@corp.com
    add email officialvermarohit14@gmail.com as rohit
    append number 9999888877 as rahul    # same as save/add
    show contacts

Saved instantly to `config/contacts.json` (gitignored) and usable by
WhatsApp + email tools immediately — no restart. Sources merge in this
priority: contacts.json > contacts.vcf (Google export).

## WhatsApp Messaging

Send messages from your own WhatsApp account via WhatsApp Web (pywhatkit).

Setup (once):
1. Log into `web.whatsapp.com` in your default browser (scan QR, stay signed in).
2. Give Mike contacts — say `save number ... as ...` lines (above), drop a
   Google Contacts vCard export at `config/contacts.vcf`, or hand-write
   `config/contacts.json`.

Usage:

    send message to rahul saying on my way           # verbatim
    whatsapp mom calling you in five minutes          # verbatim
    send hi to rhit                                   # typo? Mike confirms:
                                                      # "Closest contact is
                                                      # 'rohit' (...). yes/no"
    whatsapp rahul wishing him happy birthday          # brain composes
    whatsapp rohit in hinglish good night wishes       # drafted in Hinglish
    send msg to +919812545678 saying hi                # raw number works too

Rules:
- `saying ...` = word-for-word. Intent phrasing = brain drafts it and shows
  exactly what was sent.
- Typo-tier name matches ask `yes / no` before sending.
- Brain offline => nothing is sent; Mike reports it in chat instead.
- `MIKE_WHATSAPP_DRYRUN=1` (config/.env) previews without sending.

## Email Messaging

Gmail via app password (SMTP_SSL :465). Setup once:

    # config/.env
    MIKE_EMAIL_ADDRESS=you@gmail.com
    MIKE_EMAIL_APP_PASSWORD=<16-char app password>

(Google Account -> Security -> 2-Step Verification -> App passwords.)

Usage:

    email rahul about project update saying here is the file
    send mail from me to a@b.com saying quick line          # verbatim body
    draft an email to rahul apologizing for the delay        # brain writes
                                                             # SUBJECT+BODY
    send mail to rohit ... his email address is a@b.com      # address found
    send him the mail about the offer                        # pronoun reuse
    email mom in hindi wishing good night                    # Hindi draft

Rules mirror WhatsApp: composed mails always show subject+body after
sending, sign off as **Rohit** (never placeholders), fail-safe on brain
errors, `MIKE_EMAIL_DRYRUN=1` previews. If mails land in spam, mark them
"Not spam" once — Gmail learns fast.

## Multilingual Drafting

Both messengers draft in any language:

- Explicit: append `in hindi`, `in hinglish`, `in tamil`, `in spanish`...
- Implicit: matches the language of your instruction (Hinglish instruction
  -> Hinglish message)
- Default: English.

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