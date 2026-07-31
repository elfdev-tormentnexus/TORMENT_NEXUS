# Public derivative of the private Research C collector artifacts

Transformation: `researchc-public-derivative-1`, built by
`handoffs/researchc_open_threads_tools/publish_evidence.py`.

Four artifacts from the 120-call rate/distortion run and its six-call
preflight could not be committed as written. This directory is what can be.
Everything here is generated; regenerate it with:

```bash
python handoffs/researchc_open_threads_tools/publish_evidence.py --check
```

## What was private, and why

| Private original | Why it stays out of Git |
|---|---|
| `preflight_prompts.json` | the exact runtime system prompt, twice, carrying installation-local chosen-name state |
| `rate_distortion/rate_distortion_stable_messages.json` | the same runtime prompt as the frozen stable prefix |
| `rate_distortion/rate_distortion_spec.json` | absolute host paths to the interpreter, the director binary, and the model |
| `rate_distortion/rate_distortion_rows.jsonl` | the same binding record, with those paths, repeated on all 120 rows |

All four are listed in `.gitignore` by exact path and are retained locally.
`PUBLIC_DERIVATIVE_MANIFEST.json` holds a SHA-256 commitment to each one, so a
reviewer with the private file can prove it is the file these numbers came
from, without the file being published.

## What the transformation did

Nothing was recomputed, reordered, regraded, or rounded. Verified
independently: all 120 rows preserve every field byte-for-byte except the
binding, and no measurement, grading, task, or timing field differs.

- The identical binding record repeated on 120 rows was replaced by
  `bindings_sha256` pointing at one consolidated record in
  `public_binding.json`. Rows shrank from 786 KB to 464 KB purely by
  de-duplication.
- That consolidated record keeps basenames, roles, PIDs, parent PIDs, loopback
  ports, the model's size, the llama.cpp revision and build info, and every
  cryptographic hash. It drops the four absolute paths and the model alias,
  which llama.cpp defaults to the model path.
- Prompt text is withheld rather than redacted. `publish_evidence.py` slides
  an 80-character window over every withheld string and fails the build if any
  run of it appears in any public artifact, so a partial copy fails too.

Withholding the prompt costs no reproducibility. The stable messages are the
production persona plus a fixed style demonstration; they contain no
experimental content. The controlled source index and all 28 questions are
already published in full in `rate_distortion_queries.json`,
`rate_distortion_manifests.json`, and the rows. For the preflight, the entire
manipulation was one substituted directory aggregate —
`assistant/ui 3f 4,353L` became `assistant/ui 3f 7,731L` — and both values are
public repository facts, reproduced in `public_preflight_prompts.json`.

## Two corrections carried into this derivative

1. The private originals recorded
   `assistant_mode.independently_verified = true`. That overstates the check.
   Hazard mode was **operator-reported**. What was independently verified is
   process topology: PIDs, executable and command-line hashes, the unpooled
   helper on 8084, and the absence of a listener on 8099. None of those
   establishes which UI mode was selected.
2. The collector-era `server_bundle_sha256`
   `2cfd58b8b4a2e9a1081cab1168877dfa6598f0c430c6970afbd41a37f08f96ab`
   omitted `mtmd.dll`. The launcher, main implementation libraries, model,
   repository, prompt, and sampler were still bound, but that value must not
   be described as a complete CPU dependency-closure digest.

## What this derivative is not

It does not revalidate under the original collector digests, and no collector
should be pointed at it. `spec_sha256`, `stable_artifact_sha256`, and the row
binding digests commit to the private originals. Those digests are preserved
here as commitments, not as claims that these files reproduce them.
