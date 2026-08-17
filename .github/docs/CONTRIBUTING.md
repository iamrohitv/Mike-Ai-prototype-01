# MIKE — CONTRIBUTING

## Scope

Mike is a proprietary, privately developed personal AI system.
The repository is private. Mike is NOT an open-source project.

## Development AI Behavior

When working on Mike:

1. Respect the vision.
2. Do not flatten ambitious ideas into generic chatbot features.
3. Translate ideas into engineering systems.
4. Point out technical limitations honestly.
5. Separate current capabilities from future possibilities.
6. Never pretend something is implemented when it is not.
7. Prefer modular architecture.
8. Prefer reversible changes.
9. Protect secrets.
10. Test before declaring success.
11. Explain important architectural decisions.
12. Challenge bad technical decisions when necessary.
13. Do not blindly agree.
14. Give practical alternatives.
15. Keep the long-term architecture in mind while building small pieces.

## Turning Ideas into Systems

The primary bottleneck is turning ideas into frameworks.

```
IDEA
  -> REQUIREMENTS
  -> ARCHITECTURE
  -> MODULES
  -> INTERFACES
  -> IMPLEMENTATION
  -> TESTING
  -> DEPLOYMENT
  -> ITERATION
```

When given an idea, do not immediately write random code. First
determine:

- What problem is being solved?
- Desired behavior?
- Constraints?
- Required components?
- Minimum viable implementation?
- Interfaces?
- Security risks?
- Success criteria?

Then implement.

## Commit Convention

Use Conventional Commits:

- `feat:` — new feature
- `fix:` — bug fix
- `chore:` — maintenance, tooling, setup
- `docs:` — documentation
- `refactor:` — code change without behavior change
- `test:` — tests
- `style:` — formatting, non-functional
- `build:` — build system
- `perf:` — performance

## Security

Never commit API keys, passwords, tokens, private credentials,
private certificates, or personal secrets. Use environment variables
and secret management. See SECURITY.md.