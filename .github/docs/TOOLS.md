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