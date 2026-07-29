# Super Dev Hazard — two-model, bounded self-editing

`start_super_dev_hazard.bat` is a HazardSable-only development profile. It is
not available in ordinary Sable, and it does not alter ordinary retrieval,
memory, Machinesoul, or Machinespirit semantics.

It uses two local coding models with distinct jobs:

| component | job | authority |
| --- | --- | --- |
| 14B planner/reviewer | selects a small, grounded improvement from the fixed unattended allowlist | no write authority |
| 7B patch worker | drafts one exact find/replace patch for that selected improvement | no write authority |
| trusted Python guard | validates, writes, tests, rolls back, and logs | the only component allowed to change a file |

The “two models together” wording is deliberately literal about the split:
they are two local processes. It does **not** mean their weights are merged,
or that one model can override the other’s limits.

## Starting it

1. Close other project editors and make a separate backup.
2. Run `start_super_dev_hazard.bat` and type the launch acknowledgement.
3. In the HazardSable window, type `super dev mode`.
4. On first use, choose and confirm an 8–32 digit Super Dev key at the masked
   prompt. Later sessions prompt for that same key. The key is never printed,
   logged, or committed; the machine stores only a PBKDF2 salted verifier at
   `assistant/.super_dev_passcode`.

Entering the mode starts one bounded session automatically. Use `super dev
status` to inspect the boundary or `exit super dev mode` to lock it early.

## What one session may do

The 14B sees a fixed inventory of the existing unattended-edit allowlist; it
does not see chat history, memories, web content, or a free-form user prompt.
The 7B gets only the selected file plus the precise change request and must
return one exact `find` / `replace` JSON patch. A session attempts at most one
accepted patch, capped at 40 changed lines.

Before a patch is retained, trusted code requires all of the following:

1. The 7B endpoint is authenticated and loopback-only.
2. The selected file is on the smaller autonomous allowlist.
3. The patch parses, fits exactly once, and stays within the line cap.
4. The capability boundary rejects added process, network, dynamic-code, and
   filesystem-write capability.
5. A timestamped backup and durable transaction marker exist before writing.
6. The fixed regression gate passes after the write.

Failure at any stage retains no patch: the backup is restored. A crash leaves
the transaction marker in place, and the next startup restores that one patch
before normal use resumes. Attempts and outcomes are appended to
`assistant/logs/super_dev_edits.log`.

## Deliberate non-capabilities

Super Dev cannot execute arbitrary shell commands, access external network
services, read or change credentials, modify model weights, modify its own
editing/authentication/UI guards, weaken tests, or push commits/releases to
GitHub. It is not a security sandbox, and passing tests is evidence rather
than proof; inspect the resulting diff and backup before relying on it.

The separate launcher keeps its temporary 7B API credential in the launcher
environment only and stops that worker when the HazardSable window exits.
