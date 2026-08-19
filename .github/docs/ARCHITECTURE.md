# MIKE — ARCHITECTURE

Mike is built incrementally, not as one final monolithic system.
Every version must produce a real, testable improvement.

## Design Principles

- Working systems over demonstrations
- Modular architecture
- Clear interfaces
- Testability
- Security
- Observability
- Replaceable components
- Incremental development

## Core Components (V0.1)

| Module | Responsibility |
|---|---|
| Identity | Persistent identity and personality |
| Mood Reader | User state detection (business / normal / low-tired) |
| Tone Engine | Adaptive formal/informal response, warm + motivating when low |
| Uncertainty / Guessing | Labeled guesses, honest about missing context |
| Reasoning | Natural-language understanding and reasoning (hybrid brain) |
| Context Manager | Conversation and task context |
| Memory | Persistent memory — holds everything, sharp recall |
| Planner | Basic planning |
| Policy Engine | Policy enforcement, authority levels |
| Logger | Event/action logging |

## V0.2+ Components

| Module | Responsibility |
|---|---|
| Tools (computer/) | Terminal, git, filesystem, notes, tasks, system health, screenshot |
| Awareness | Scheduler, monitors (disk/repo/server/tasks/routine/reminders/metrics/health), initiative engine |
| Guardian | Normal / unusual / emergency classification, check-ins and escalation, scheduled health checks |
| Operations | Autonomous routine reporting (daily report, project report, task triage, compact) |
| Perception | Sensor hub for system/screen/camera readings (robotics body) |
| Remote interface | Token-authenticated phone/remote API for status, briefing, chat, sync, history, tools |
| Distributed sync | Device registry and memory/conversation push/pull across devices |
| Memory | Sharp recall: TF-IDF-lite weighting, biword (phrase) matching, auto-tags, compaction |

## Memory Recall

`MemoryStore.recall` ranks active memories by:
- TF-IDF-lite weighting — rare query words outrank common ones.
- Biword (adjacent phrase) matches score +1.5 each.
- Auto-extracted tags match score +2.0 each.

Every `remember()` auto-extracts the top significant keywords as tags
(`recall_by_tag`), and `compact` folds old conversation lines into a
summary memory while pruning raw history (via `prune_conversations`).

## Hybrid Brain

Mike uses BOTH a local brain and a global one.

- Local first: private, free, fast.
- Global when needed: harder questions, more capability.
- Any knowledge retrieved from the global brain is persisted into
  Mike's private memory, so future lookups come from his own brain
  before going external again.

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

## Repository Structure

```
mike/
|
+-- core/
|   +-- reasoning/
|   +-- planning/
|   +-- identity/
|   +-- mood/
|   +-- tone/
|   +-- context/
|
+-- memory/
|   +-- store.py
|   +-- sync.py
|
+-- policies/
|
+-- tools/
|   +-- computer/
|       +-- note / task / file / project / terminal / git / system
|
+-- awareness/
|   +-- scheduler.py
|   +-- monitors.py
|   +-- initiative.py
|   +-- briefing.py
|
+-- guardian/
|
+-- operations/
|   +-- reports.py
|
+-- perception/
|   +-- sensors.py
|
+-- interfaces/
|   +-- text/
|   +-- desktop/
|   +-- remote/
|
+-- monitoring/
|
+-- security/
|
+-- events/
|
+-- tests/
|
+-- docs/
|
+-- config/
|
+-- logs/
```

## Event System

Mike is event-driven. Events include:

- `email.received`
- `client.requested_revision`
- `server.health_changed`
- `project.deadline_near`
- `payment.received`
- `calendar.changed`
- `device.offline`
- `operating_balance.low`

Each event can trigger: Ignore, Log, Queue, Notify, Call, Act.

## Planning System

Plans have preconditions, steps, dependencies, expected results,
failure handling, and verification.

## Verification

Mike should not assume tool success means task success.

Update dependency -> Test -> Health check -> Verify service
-> Confirm expected behavior -> Report

## Observability

Maintain action logs, tool calls, errors, decisions, policy decisions,
external events, and verification results using structured audit
information.

```
ACTION:      Update dependency X
REASON:      Approved routine maintenance policy
RESULT:      Successful
VERIFICATION: Tests passed / service healthy
```

## Interface Independence

Interfaces (text, voice, phone, EV, robot, hologram) are bodies for ONE
Mike Core. The intelligence always remains in the core.