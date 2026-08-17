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