# Security policy

Status: security policy for the researchB release tree, reviewed 2026-07-28.

TORMENT_NEXUS is experimental software, not a hardened security product. The
project still treats authentication bypasses, unexpected data disclosure,
unauthorized file changes, and unsafe packaging as defects worth reporting
responsibly.

## Supported versions

Security work is focused on:

- the latest published GitHub beta release; and
- the current default development branch when the issue still reproduces.

Older beta archives and private experimental branches may not receive fixes.
A version being in scope does not create a service-level or response-time
guarantee.

## Reporting a vulnerability

Prefer GitHub’s private vulnerability-reporting or Security Advisory flow:

[Privately report a security vulnerability](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/security/advisories/new)

If private reporting is unavailable, open a minimal public issue asking the
maintainer to establish private contact. Do not include exploit details,
secrets, private data, or a working proof of concept in that issue.

Include:

- release name, commit, launch profile, and whether the tree was modified;
- Windows version and relevant hardware;
- expected and observed boundary;
- the smallest synthetic reproduction;
- whether networking, developer mode, self-maintenance, agent API,
  escalation, or hardware features were enabled;
- likely impact and whether any real data or credentials were exposed;
- a safe way for the maintainer to confirm the fix.

Never attach conversation history, memories, embedding caches, activity logs,
keys, tokens, passcodes, pairing information, or a full environment dump.

## Security issues in scope

Examples include:

- bypassing a Python-enforced file or command authority boundary;
- an edit or hardware action occurring without the documented confirmation
  or opt-in;
- the loopback model or agent API accepting unauthenticated requests;
- binding a supposedly local service to a non-loopback interface;
- path traversal, archive injection, unsafe extraction, or release inclusion
  of denied private files;
- credentials appearing in prompts, logs, process listings, release assets,
  or error output contrary to the documented design;
- a custom endpoint receiving more context than the feature promises;
- command, search-result, model-output, or prompt injection that produces a
  real boundary violation;
- malicious or corrupt model input causing code execution or an unexpected
  read/write outside the selected model file;
- dependency or binary provenance that materially changes the release threat
  model.

Incorrect, offensive, harmful, or bizarre language-model text is normally a
safety or quality issue rather than a software vulnerability. It becomes a
security issue when it crosses an enforced authority boundary, exposes data,
or triggers an action that the operator did not authorize. See `SAFETY.md`
for the broader model-output disclosure.

## Current trust boundaries

### Windows process permissions

The application runs with the permissions of the account that launched it.
Its editing guards and passcodes are application controls, not an OS sandbox.
Do not run it as Administrator. Use a separate test copy for autonomous or
unfamiliar model experiments.

### Local HTTP services

The default language-model server binds to loopback port 8080 and the
embedding server to loopback port 8082. They use a generated bearer key. The
optional agent API binds to `127.0.0.1:8099`, checks the Host header, and
requires its own token.

Loopback protects against ordinary remote connections; it does not protect
against another process running as the same Windows user. A browser page,
malware, debugger, backup agent, or local client that obtains a bearer token
may use the corresponding service.

The key files are local plaintext. The code requests restrictive file modes,
but Windows account access remains the practical boundary.

### Custom and cloud endpoints

A custom model endpoint can receive complete prompts and context. A custom
embedding endpoint can receive private memory, history, and query text.
Cloud escalation sends the exact command argument to the selected provider.

Use HTTPS and a trusted hostname. Never reuse a valuable provider key with a
third-party compatible endpoint. Provider retention and security are outside
this repository’s control.

### Models and native runtimes

GGUF and ONNX artifacts are processed by native libraries. Hash verification
detects a byte mismatch; it does not prove that a model is benign or that its
parser is free of vulnerabilities.

Use the inventory in `MODELS.md`, keep llama.cpp and inference dependencies
within a reviewed version set, and test unknown models under a low-privilege
account. Do not publish or install a replacement merely because its filename
looks familiar.

### Self-editing

Normal proposals, maintenance sessions, and autonomous startup profiles do
not have the same human-review guarantees. Back up the tree, inspect diffs
and logs, and verify rollback paths before enabling any automatic cycle.

An application rule limiting files or diff size reduces scope. It does not
guarantee semantic correctness or prevent the Windows account from changing
other files by some unrelated code path.

### Hardware and radio

USB, Bluetooth, LoRa, radar, and Wi-Fi experiments add device, firmware,
radio, and physical-world boundaries. Test only hardware and networks you own
or are authorized to use. Treat pairing data and mesh channel credentials as
secrets. Do not connect experimental sensing to safety-critical decisions.

## Release integrity

Official release assets should provide:

- exact filenames, byte sizes, and SHA-256 checksums;
- the source commit and test result;
- a model/provenance manifest;
- all required third-party notices;
- a statement of known safety, privacy, and licensing limitations.

Verify checksums after download and before first execution. A checksum should
be obtained from a channel independent of the downloaded archive when
possible.

The release process must exclude personal runtime files, tokens, memories,
history, activity logs, caches, private music, and recovery copies. A failure
of those deny rules is a security and privacy issue.

## Coordinated disclosure

Please allow the maintainer a reasonable opportunity to reproduce and fix a
reported boundary failure before publishing exploit details. Avoid accessing
data that is not yours, persistence, destructive testing, denial of service,
or tests against systems without authorization.

There is currently no bug-bounty program and no promise of payment. Good-faith
reports will be evaluated on their technical evidence and impact.
