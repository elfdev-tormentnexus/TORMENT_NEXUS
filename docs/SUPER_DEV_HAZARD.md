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
4. On first use, choose and confirm a Super Dev key at the masked prompt — 8–32
   digits, or 7–32 characters if it includes a letter. Later sessions prompt
   for that same key. The key is never printed,
   logged, or committed; the machine stores only a PBKDF2 salted verifier at
   `assistant/.super_dev_passcode`.

Entering the mode starts one bounded session automatically. Use `super dev
status` to inspect the boundary or `exit super dev mode` to lock it early.

## What one session may do

The 14B sees a fixed inventory of the existing unattended-edit allowlist; it
does not see chat history, memories, web content, or a free-form user prompt.
The 7B gets only the selected file plus the precise change request and must
return one exact `find` / `replace` JSON patch, capped at 40 changed lines.

A session is unattended and runs a **loop** over that single-patch
transaction. It is a loop rather than a batch: the planner re-runs after every
accepted patch, because the tree it planned against has changed, and each
patch clears the full gate list below on its own before the next one is
attempted.

**The session is bounded by time, not by a patch count.** There is no cap on
how many patches one activation may retain — the point of the mode is to get
through a night's work, and capping the count caps the value while capping the
time caps the exposure. The window is six hours by default and six hours at
most: `TORMENT_NEXUS_SUPER_DEV_SESSION_SECONDS` accepts 60 to 21600, so
raising it cannot extend a session past the ceiling.

Read the bound as *no new patch starts after the window closes*, not *the
process dies at six hours*. A patch already inside its regression gate is
allowed to finish, because interrupting the gate is what strands a
transaction marker. Overrun is bounded by one gate run.

The session stops when the window closes, when the planner errors or offers
nothing it has not already tried, when no untried candidate survives the
gates, or when a patch reports success without having written anything.

Two rules make the loop safe to leave running overnight. A candidate the gates
rejected is never retried within the same session, so a planner that keeps
proposing the same refused change cannot spend the window grinding against it.
And progress is verified against an internal write counter rather than a
returned success flag — the counter moves only after a real write clears the
regression gate, so a success that is secretly a no-op halts the session
instead of looping for six hours. The bonus self-heal batch in
`autonomous_engine.run_observed_serial()` guards itself the same way.

Before a patch is retained, trusted code requires all of the following:

1. The 7B endpoint is authenticated and loopback-only.
2. The selected file is on the smaller autonomous allowlist.
3. The patch parses, fits exactly once, and stays within the line cap.
4. The capability boundary rejects added process, network, dynamic-code, and
   filesystem-write capability.
5. A timestamped backup and durable transaction marker exist before writing.
6. The fixed regression gate passes after the write.

Failure at any stage retains no patch: the backup is restored, and the session
moves on to the next candidate rather than stopping.

At most one patch is ever in flight, because the transaction marker is written
before the write and cleared once the regression gate passes. So a crash mid-
session still leaves exactly one patch to undo, and the next startup restores
that one before normal use resumes. Patches the session already retained stay
applied — each had passed the gate on its own — so recovery is not a
session-wide rollback. If you want the whole session reverted, use the
per-patch backups the edit guard kept.

Session start, every attempt, and the reason the session stopped are appended
to `assistant/logs/super_dev_edits.log`.

## Deliberate non-capabilities

Super Dev cannot execute arbitrary shell commands, access external network
services, read or change credentials, modify model weights, modify its own
editing/authentication/UI guards, weaken tests, or push commits/releases to
GitHub. It is not a security sandbox, and passing tests is evidence rather
than proof; inspect the resulting diff and backup before relying on it.

The separate launcher keeps its temporary 7B API credential in the launcher
environment only and stops that worker when the HazardSable window exits.
