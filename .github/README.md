# MIKE — Rohit's Personal AI Counterpart

Mike is a Windows-native personal AI assistant with a JARVIS-style desktop
HUD, voice I/O, long-term memory, and hands on the machine: files, apps,
browser, WhatsApp, email, and a coding agent (opencode).

```
python -m interfaces.desktop.app        # launch (visible)
python -m interfaces.desktop.app --hidden  # launch to tray
python -m unittest discover -s tests    # test suite
```

---

## What Mike Can Do

| Area | Examples |
|---|---|
| **Voice + chat** | "hey mike" wake word, text box, phone page; replies mirror your language (Hinglish in -> Hinglish out) |
| **Files** | `create a python file of calculator app on desktop` -> `calculator app.py`; read/write/append/replace/delete; asks for a destination when you don't give one |
| **Launch** | `open main.py in vscode`, `browse to github.com`, `launch notepad` |
| **Contacts** | `save number 9876543210 as mom`, `add email a@b.com as boss`, `show contacts` |
| **WhatsApp** | `send message to rohit saying hi`, or intent: `whatsapp rahul wishing him happy birthday` -> brain drafts it — in any language (`in hinglish`, `in hindi`) |
| **Email** | `email rahul about update saying done`, or composed: `draft an email apologizing...` (Gmail app password) |
| **Coding agent** | `opencode create a rest api` — routed to opencode CLI via local bridge |
| **Memory** | recalls past context, archives to "the corner", daily briefings |
| **Awareness** | disk/battery/task monitors, reminders, initiative engine, guardian |

## Architecture Map

```
interfaces/       desktop HUD app (tkinter), phone web UI, remote server
core/             brain routing (local+global LLM), context, tone, identity
tools/computer/   file ops, launchers, whatsapp, email, opencode bridge...
awareness/        scheduler + monitors (disk, tasks, reminders, metrics)
operations/       reports (daily report, task triage, routines)
policies/         approval engine (GREEN/YELLOW/ORANGE levels)
memory/           sqlite store - memories, tasks, actions, devices
events/           thread-safe event bus wiring everything together
config/           .env (secrets, gitignored), contacts.json/vcf (personal)
security/         env loading, path helpers
tests/            unittest suite (`python -m unittest discover -s tests`)
```

## Docs

- [TOOLS.md](TOOLS.md) — every tool, trigger phrases, setup (WhatsApp,
  email, phone control, Tailscale)
- [AUTOSTART.md](AUTOSTART.md) — what auto-starts with Mike, manual start
  commands, troubleshooting

## Quick Links

- Phone from anywhere: Tailscale address shown at startup (`remote link`)
- opencode bridge: auto-starts on :8765; health at `/bridge/health`
- Secrets live in `config/.env` (gitignored) — never commit them
- Personal contacts in `config/contacts.json` / `contacts.vcf` (gitignored)

## Safety Rules

1. Risky file ops (overwrite/delete) ask for approval; GREEN ops run free.
2. Messaging tools never send when the drafting brain fails — they report
   in chat instead.
3. `MIKE_WHATSAPP_DRYRUN=1` / `MIKE_EMAIL_DRYRUN=1` preview messages
   without sending.
