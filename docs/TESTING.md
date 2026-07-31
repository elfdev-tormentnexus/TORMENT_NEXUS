# Testing researchC

Testing is part of the safety boundary, but it is not a safety certification.
Passing tests can show that an application rule behaves as coded; it cannot
prove that an abliterated model is truthful, unbiased, lawful, secure, or
appropriate for a high-stakes use.

Run the automated suite from a source checkout:

```powershell
.\setup\test_assistant.bat
```

Review the complete result. Do not publish a fixed test count: it changes as
the project evolves. A release candidate should have zero failures and no
unexpected skipped safety-boundary tests.

## Clean-state first-launch test

Use a disposable copy without personal data.

1. Confirm no acknowledgement state exists.
2. Launch and verify that the disclosure appears before model loading,
   microphone access, activity sampling, listeners, or network-capable
   subsystems.
3. Enter anything except the exact `I UNDERSTAND`; verify the application
   exits without starting them.
4. Launch again, enter the exact text, and verify acknowledgement is recorded.
5. Relaunch and verify the disclosure is not repeated.
6. Confirm the ordinary session begins in text mode with activity awareness
   off.

Do not use a real memory folder, API key, or imported manual for this test.

## Privacy-default test

- Confirm no microphone is opened before `audio mode`.
- Confirm `activity on` persists the opt-in and begins sampling.
- Confirm `activity forget` deletes current observations without changing the
  enabled state.
- Confirm `activity off` stops sampling, persists off, and deletes
  `assistant\memory\activity_log.jsonl`.
- Restart and confirm activity remains off.
- Confirm optional agent, escalation, autonomous editing, and sensing paths
  remain disabled without their explicit settings.

Review [Privacy](../PRIVACY.md) before testing with real documents or
activity.

## Conversation and semantic retrieval

Test both positive and negative cases:

- exact terms, filenames, identifiers, and word-overlap memories remain
  reliable;
- greetings and acknowledgements do not trigger semantic retrieval;
- automatic zero-word-overlap memory contributes at most one item and only
  at cosine `>= 0.55` with a `>= 0.06` margin over the runner-up;
- ambiguous or unrelated queries return no semantic memory;
- explicit memory search ranks candidates by cosine rather than silently
  mixing recency or confidence;
- earlier-conversation recall runs only for clear recall intent, returns at
  most one item, and requires cosine `>= 0.60` plus a `>= 0.06` margin;
- a long persisted exchange preserves both its beginning and end around the
  visible clipping marker;
- stopping the embedding server leaves lexical behavior working.

The bundled BGE model is deliberately evaluated with project-selected mean
pooling. Upstream examples commonly use CLS pooling, so any embedding-model
or runtime change requires fresh measurements rather than inherited
thresholds. See [Semantic retrieval](SEMANTIC_AND_AGENT_BRIDGES.md).

## Offline knowledge

In a disposable library:

1. Check that the eight built-in practical-reference cards are present.
2. Import representative `.txt`, `.md`, `.rst`, `.html`, `.json`, `.csv`,
   text PDF, `.epub`, and `.docx` files.
3. Confirm imports are copied to the private shelf and indexed locally.
4. Verify automatic context requires a lexical match.
5. Verify embeddings only rerank those automatic lexical hits.
6. Verify explicit `library search` can return a semantic-only result and
   labels it `semantic-candidate`.
7. Verify an unrelated query returns no confident answer.
8. Import an image-only PDF and confirm the documentation accurately warns
   that OCR is required.
9. Remove and rebuild sources in developer mode; verify no stale extracted
   text remains.

Use synthetic documents. Imported files, the SQLite index, extracted text,
and vectors are private runtime data and must not enter a release.

## Voice, media, and interface

- Start in text mode and verify `audio mode`, `text mode`, and `voice status`.
- Verify speech recognition, cancellation, and spoken replies on an ordinary
  Windows account.
- Play local MP3, WAV, FLAC, and OGG files and verify the visualizer remains
  responsive.
- Confirm local-song startup does not produce an unwanted spoken
  confirmation.
- Exercise long-output pagination and cancellation.
- Confirm no feature silently enables activity sampling or networking.

### Research C endpoint-recovery matrix

Automated tests simulate endpoint loss, cleanup `S_FALSE`, default-device
re-enumeration, same-frame playback recovery, recovery cancellation, and power
guard release. Before publishing the hardware claim, run all four cases on a
non-Administrator Windows account:

1. automatic display sleep and wake;
2. manual lock and unlock;
3. switch the default output while a local track is playing; and
4. disconnect and reconnect the active HDMI/DisplayPort audio device.

For every case, record whether playback resumes at the same position, whether
the visualizer resumes, the visible explanation, and capture/reader/player
thread counts before and after. A manual Stop or Play must cancel the old
recovery loop.

## Research C measurement acceptance

- Run repair and memory calls with top-two measurement and with
  `TORMENT_NEXUS_RESEARCHC_LOGPROBS=off`; existing decisions must be identical.
- Confirm `assistant/logs/research_c.jsonl` contains no prompt, reply, source,
  memory, API key, or arbitrary outcome/timing text.
- Bind director and worker rows to separate exact model SHA-256 values and
  record the llama-server revision.
- Fit and holdout files must be different. The report must refuse unbound rows
  unless an operator explicitly selects exploratory `--allow-unbound`.
- Report false refusals beside compute avoided. Do not install a threshold from
  the release-candidate probe transcripts; they are grounding probes, not the
  labelled repair/memory dataset.
- Use paired McNemar for grounded/ungrounded binary outcomes. Use a
  predeclared SPRT only within one fixed Bernoulli stratum; do not pool prompts
  with different success probabilities as though they were independent
  repeats.

## Agent-interface tests

With the interface disabled, confirm `127.0.0.1:8099` is unavailable. Then
enable it only in a disposable session and test:

- bearer authentication and Host-header rejection;
- `/health`, `/state`, `/entropy`, `/files/editable`;
- `/memory/search` and `/knowledge/search`, including result labels;
- `/ask` answer length, busy/cancel behavior, and human-session priority;
- `/ask` receives stable persona/core-memory context but not the live chat,
  does not append conversation history, and does not extract memory;
- every call produces metadata-only audit output;
- no route binds outside loopback or edits project state.

Never include the token or returned private text in test logs. See
[Agent interface](AGENT_INTERFACE.md).

## Connected and hardware tests

Network and hardware tests require explicit consent and separate test data.

- Verify search announces and uses only the configured backend.
- Verify escalation sends exactly the explicit question and no history,
  memory, persona, or system prompt.
- Verify a custom model or embedding URL is treated as remote and receives
  only the intended data.
- Test T-Deck/LoRa only on authorized channels and regions.
- Treat the failed AX211 Wi-Fi proxy as an archived negative result.
- Test the planned LD2450 only as a motion/trajectory sensor, never as
  identity, camera-like sight, or proof of occupancy.

## Release-package acceptance

Before publishing any researchC asset:

- build from the intended clean commit and record it in the manifest;
- render the machinesoul APNG cut maps and record the exact plans the owner
  approved;
- verify every capsule, decoded vector segment, and directly reconstructed
  file against its recorded hash;
- verify the exact asset names, decompiler, manifest capsule, and reassembler
  capsule;
- inventory the bundled model/runtime versions and compare hashes with
  [Models](../MODELS.md);
- confirm the full-model warning appears before download/install directions;
- verify the reconstructed tree contains no keys, tokens, passcodes,
  acknowledgements,
  activity-consent state, conversation history, memories, embedding cache,
  imported library, SQLite knowledge index, activity log, personal music,
  logs, recovery material, or local paths;
- decompile and reconstruct on a clean Windows account, run setup, and repeat
  the clean-state first-launch test;
- inspect [Third-party notices](../THIRD_PARTY_NOTICES.md) and
  [Rights and reuse](../RIGHTS.md) before redistribution.

## Reporting results

Record the commit, Windows build, CPU/RAM, launch profile, exact input,
expected result, actual result, and whether optional services were enabled.
Use synthetic content and redact personal paths. A security or privacy
boundary failure follows [Security](../SECURITY.md); ordinary failures follow
[Contributing](../CONTRIBUTING.md).
