# Contributing

Thank you for helping make TORMENT_NEXUS more understandable, inspectable,
private, and useful.

The project values local ownership, reversible changes, measured performance,
honest negative results, explicit authority boundaries, and documentation
that distinguishes working features from experiments.

## Read the project boundaries first

Before contributing, read:

- `SAFETY.md`
- `PRIVACY.md`
- `SECURITY.md`
- `MODELS.md`
- `THIRD_PARTY_NOTICES.md`
- `RIGHTS.md`

There is no project-wide license or published contribution agreement yet.
Discuss a substantial code contribution with the maintainer before investing
significant work. Opening a pull request does not automatically grant the
project or other users permission to reuse it.

## Good first contributions

- A minimal bug reproduction using synthetic data.
- A regression test for a confirmed behavior.
- Documentation corrections with exact file or command references.
- Accessibility and first-run clarity improvements.
- Measurements that label hardware, model, settings, and sample size.
- Privacy, packaging, provenance, and license inventory corrections.
- Small performance changes with before-and-after measurements.

Broad rewrites, new autonomous authority, new network destinations, model
replacements, and hardware capture features should begin with an issue and a
written threat/privacy analysis.

## Protect private data

Do not submit:

- conversations, memories, embedding caches, or activity logs;
- API keys, bearer tokens, passcodes, pairing PINs, environment dumps, or
  authenticated URLs;
- personal music, voice recordings, private filenames, full user paths, or
  message previews;
- generated recovery files or backups that may contain earlier private
  state.

Use invented names, synthetic conversations, temporary directories, and
redacted logs. If a report may expose a security boundary or someone else’s
data, follow the private process in `SECURITY.md`.

## Do not add model weights or opaque binaries in a pull request

Model and binary additions require a provenance review before they enter the
tree. Provide, in text:

- exact upstream URL and revision;
- original filename and local filename;
- exact byte size and SHA-256;
- model card and derivation chain;
- license and required attribution;
- intended role and authority;
- known behavior, bias, safety, privacy, and hardware limitations.

Do not assume that a base model’s license covers an abliterated, fine-tuned,
converted, or quantized derivative. Do not copy a file into the repository
while its redistribution terms are unresolved.

## Change process

1. Keep each change focused on one explainable outcome.
2. Preserve unrelated work in a dirty tree.
3. Add or update regression coverage for behavior changes.
4. Keep secrets and personal runtime files out of test fixtures.
5. Run `setup\test_assistant.bat` on Windows.
6. Report the exact tests run and any untested hardware or platform.
7. Describe privacy, network, authority, compatibility, and migration impact.
8. Include rollback instructions for a persistent-data or self-editing
   change.

Tests should fail for the old behavior and pass for the new behavior. A test
that only checks a status message is not enough when the feature writes to
disk, crosses a network, or survives restart.

## Documentation standards

Use plain language and label a feature as one of:

- **Implemented and verified**
- **Experimental**
- **Planned**
- **Failed or archived**

Do not describe a measurement plan as a supported capability. State when
hardware has not been assembled or tested. Distinguish radar motion estimates
from sight, LoRa communication from sensing, application guardrails from an
OS sandbox, and semantic embedding vectors from visual vector graphics.

Safety warnings should be factual and specific, not sensational. Do not claim
that abliterated models always comply or never refuse.

## AI-assisted contributions

AI assistance is permitted, but the human contributor remains responsible
for every submitted line.

- Disclose material AI assistance in the pull request.
- Read and test generated code.
- Check licenses and provenance instead of trusting generated claims.
- Do not paste private project data into a cloud model without authorization.
- Reject generated dependencies, URLs, APIs, and security claims that were
  not independently verified.

## Commit and pull-request description

A useful pull request explains:

- the problem and observed evidence;
- the smallest implemented change;
- tests and measurements;
- data written, retained, deleted, or transmitted;
- new dependencies or model artifacts;
- user-visible warnings or migration steps;
- known limitations and remaining work.

The maintainer may decline a technically sound change that expands authority,
surveillance, legal uncertainty, or maintenance burden beyond the project’s
goals.

## Conduct

Be patient, concrete, and respectful. Discuss design and evidence rather than
the person presenting them. Do not use project issues to solicit harmful
model output, publish exploits before coordination, or expose another
person’s data.
