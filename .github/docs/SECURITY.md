# MIKE — SECURITY

Security is foundational.

## Never Commit

- API keys
- Passwords
- Tokens
- Private credentials
- Private certificates
- Personal secrets
- Personal contact data (`config/contacts.json`, `config/contacts.vcf`
  are gitignored)

## Use

- Environment variables
- Secret managers
- Encryption
- Access control
- Authentication
- Authorization
- Audit logs
- Sandboxing
- Network isolation
- Rate limits
- Backups
- Key rotation

## Design Assumptions

Mike should be designed assuming that:

- Tools can fail
- Accounts can be compromised
- AI reasoning can be wrong

## Access vs Authority

`ACCESS != AUTHORITY`

Mike may have broad access while having different permission levels
for different actions.

See POLICIES.md for the authority model.

## Financial Safety

Mike should NOT have unlimited access to Rohit's primary finances.

Example dedicated operating account:

- Starting balance: Rs. 5,000
- Warning threshold: Rs. 3,000

The limited account reduces the blast radius of mistakes or compromised
automation.

## Digital Continuity

Mike should not be tied permanently to one computer.

```
MIKE =
    Identity
    + Software
    + Memory
    + Policies
    + Tools
    + Configuration
```

Use backups, version control, recovery systems, redundancy, encryption
and persistent memory so Mike is recoverable on replacement hardware.

## Public / Private Model

Mike is PUBLICLY KNOWN, PRIVATELY OWNED, PROPRIETARY.

- Public: name, identity, capabilities, demonstrations, public presence.
- Private: source code, private architecture, memory, credentials,
  infrastructure, proprietary methods.

Source code belongs in Rohit's private repository.