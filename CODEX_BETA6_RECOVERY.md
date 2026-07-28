# TORMENT NEXUS Beta 6 — Codex Recovery Note

Updated: 2026-07-28  
Workspace: `C:\Users\evely\Documents\AI_Project`

## Owner intent

- Finish and publish a complete Beta 6, including the intended abliterated-model path.
- Do not silently remove capabilities to make the release easier to explain.
- Use unusually clear onboarding, safety disclosure, model provenance, licensing notes, and install warnings so inexperienced users cannot mistake the project for a conventional assistant.
- Ship the main Windows release and model payloads as multiple GitHub-sized archives, as with the prior beta.
- Keep the sensing workstream active, pending the ordered HLK-LD2450 mmWave hardware.

## Current blockers

1. **Disk space is the immediate packaging blocker.**
   - The last reliable check showed roughly 9.5 GiB free on `C:`.
   - Do not delete old artifacts without fresh, explicit owner approval.
   - Previously identified optional cleanup targets:
     - `dist\TORMENT_NEXUS.zip` plus its six root `.partNN` files: about 23.0 GiB
     - `dist\_beta3_archive`: about 8.8 GiB
     - `dist\releases\v0.2.0-beta.1`: about 8.8 GiB
     - `dist\superseded`: about 2.9 GiB
   - Potential recovery: about 43.5 GiB.
   - Preserve `dist\modelpacks`, source files, and model files unless the owner explicitly says otherwise.

2. **Git metadata is read-only in the current execution environment.**
   - Branch creation previously failed on `.git`.
   - Current branch at the last check: `beta-5.1-guardrail-and-latency`
   - Current HEAD at the last check: `1abc836`
   - Intended new branch name: `codex/beta-6-release`

3. **GitHub authentication is not usable.**
   - `gh auth status` reported an invalid token.
   - Commit/push/release publication therefore has not occurred.

4. **The official privacy-safe packager intentionally includes only Git-tracked assistant files.**
   - New Beta 6 files must be committed before an official archive is built.
   - Do not weaken this rule just to package an uncommitted tree.

## Implemented Beta 6 work

### Semantic memory and agent bridge

- Local BGE embedding server, cache, semantic memory retrieval, history recall, `/ask`, and live vector-panel wiring.
- Conservative automatic retrieval thresholds and ambiguity margins.
- Explicit semantic search remains available without automatic-injection thresholds.
- Loopback-only embedding endpoint, model identity validation, finite-vector checks, cache locking, and cache purge support.
- Remote escalation remains opt-in and uses stateless requests.
- OpenAI escalation default was updated to `gpt-5.6-sol`.

### Offline practical knowledge library

- Built-in reference cards plus user imports.
- SQLite FTS lexical search and local semantic search.
- Text, JSON, PDF, DOCX, and EPUB parsing with strict size/archive safeguards.
- Unicode-aware search, hostile-control-character stripping, bounded prompt serialization, and role-boundary protection.
- Imported material is treated as untrusted reference data at user priority, never as a system instruction.
- Automatic retrieval rejects generic low-evidence matches.
- Event-driven indexing worker, retry behavior, status/health reporting, embedding backlog handling, and exact-scan limits.
- Synchronous library removal from live source/FTS/vector rows, followed by best-effort database compaction.
- Documentation clearly states that removal is not forensic erasure from backups, filesystem snapshots, or SSD history.

### Safety and onboarding

- First run requires typing exactly `I UNDERSTAND`.
- Voice, activity logging, cloud escalation, autonomy, and sensing start off by default.
- README, install guidance, project goals, research goals, privacy, rights, model provenance, third-party notices, release notes, and release checklist were substantially rewritten.
- Public language explicitly distinguishes experimental/abliterated models from ordinary assistants.

### Sensing

- Wi-Fi sensing failure and limitations are documented.
- Sensing work is active again, pending new hardware.
- Selected primary experiment: HLK-LD2450 24 GHz FMCW trajectory radar over 5 V UART at 256000 baud.
- T-Deck/LoRa is useful as a transport or remote reporting node, not as a camera-free spatial “sight” sensor by itself.

### Release/model packaging

- `tools/package_release.py` is versioned and privacy-hardened.
- `tools/package_model_pack.py` creates a versioned five-part 14B model pack with manifest, checksums, README, safe installer, free-space checks, overwrite checks, and reparse/symlink protections.
- The main packager refuses knowledge-directory/database overlap with release inputs.
- `assistant/` is selected from Git-tracked files only; runtime/vendor payload directories remain recursive by design.

### Model and license documentation

- 14B SHA-256 and provenance were matched exactly to the Hugging Face artifact.
- BGE SHA-256 provenance was corrected to the exact CompendiumLabs conversion.
- The 4B model remains included, with the uploader’s missing license declaration disclosed instead of concealed.
- Added:
  - `LICENSES\AGPL-3.0.txt`
  - `LICENSES\LLAMA_CPP_MIT.txt`
  - `LICENSES\BGE_SMALL_EN_V1.5_NOTICE.txt`
  - `LICENSES\SILERO_VAD_MIT.txt`
- Updated `MODELS.md`, `THIRD_PARTY_NOTICES.md`, and `RIGHTS.md`.

## Verification state

- Last complete suite before the final Silero-license/include edits:
  - **606 tests passed**
  - **2 expected symlink-related skips**
- Latest focused knowledge suite:
  - **24 tests passed**
  - **1 expected symlink-related skip**
- Focused release/model/prompt tests passed after their corresponding changes.
- A full final suite still must be run after the latest documentation/license edits.

## Immediate source-cleanliness issue

`git diff --check` currently reports apparent trailing whitespace throughout added sections of:

`assistant\core\config.py`

Inspection found:

- 838 CRLF line endings
- 29 bare LF line endings
- no actual spaces or tabs at line ends
- no `CR CR LF` sequences

This is almost certainly a **mixed-line-ending diff artifact**, not genuine trailing spaces. Normalize only this file to one newline convention, preserving UTF-8 and content, then rerun `git diff --check`. Treat this as a mechanical formatting operation and inspect the diff afterward.

## Safest continuation order

1. Recheck free space after the owner’s cleanup.
2. Normalize `assistant\core\config.py` line endings and inspect its diff.
3. From the workspace root, run:

   ```powershell
   python -m compileall -q assistant tools
   python assistant\run_regressions.py
   git diff --check
   ```

4. Review `git status --short` without staging.
5. Confirm that private runtime knowledge, caches, secrets, user history, and handoff/recovery notes are excluded from release packaging.
6. Obtain writable Git metadata and valid GitHub authentication.
7. Create/switch to `codex/beta-6-release`.
8. Commit the reviewed source so the privacy-safe tracked-file packager can include the new assistant files.
9. Build and verify the exact versioned main Beta 6 archive.
10. Build and verify the versioned five-part 14B model pack.
11. Extract into a disposable directory and run the documented smoke test.
12. Rebuild from the clean committed tree if the smoke test modifies anything.
13. Create a GitHub prerelease, upload all parts, compare published sizes and hashes, then publish only after verification.
14. Insert final test counts and archive checksums into the release notes.

## Important boundaries

- Do not claim Beta 6 is released, committed, pushed, or packaged until each action actually succeeds.
- Do not package untracked assistant code by broadening the packager.
- Do not publish secrets, user-imported knowledge, memory/history, caches, logs, or local configuration.
- Do not delete legacy release artifacts or models without explicit approval naming the targets.
- Do not describe Hugging Face availability as proof of redistribution rights; preserve the intended release while stating exact provenance and unresolved licensing facts.
- Do not confuse the UI’s visual vector panel with semantic embedding vectors; they are separate systems.

