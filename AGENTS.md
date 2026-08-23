# AGENTS.md

Standing rules for AI coding agents working in this repo (Mike).

## Hard rules

- **No live messaging during tests.** Never send real WhatsApp/SMS/email
  messages while verifying code. Exceptions Rohit pre-approved (23 Aug):
  WhatsApp to **rohit (+919049923832)** and email to
  **officialvermarohit14@gmail.com** are allowed for testing without asking
  again. Anything else: ask him which number/address first and wait for his
  explicit go-ahead. Prefer `MIKE_WHATSAPP_DRYRUN=1` /
  `MIKE_EMAIL_DRYRUN=1` or unit-level mocks.
- **Commit/push only when Rohit says so.** He decides when work is ready;
  never push proactively.
- **Secrets stay out of git.** `config/.env` (brain keys, `MIKE_REMOTE_KEY`,
  `MIKE_EMAIL_APP_PASSWORD`) is gitignored - never commit it or echo its
  values.

## Project quick facts

- Personal AI assistant for Windows; entry: `python -m interfaces.desktop.app`
- Tests: `python -m unittest discover -s tests`
- Docs: `.github/docs/TOOLS.md`, `.github/docs/AUTOSTART.md`
