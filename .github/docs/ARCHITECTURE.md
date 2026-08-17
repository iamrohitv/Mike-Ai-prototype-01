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
|   +-- decision/
|
+-- memory/
|
+-- policies/
|
+-- tools/
|   +-- computer/
|   +-- git/
|   +-- github/
|   +-- email/
|   +-- calendar/
|
+-- interfaces/
|   +-- text/
|   +-- voice/
|   +-- phone/
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