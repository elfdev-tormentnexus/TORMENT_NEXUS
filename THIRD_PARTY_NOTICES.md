# Third-party notices and provenance ledger

Status: evidence-based notice inventory for `researchA`, reviewed
2026-07-28.

TORMENT_NEXUS includes or can package third-party runtimes, model weights,
voice assets, and installed Python dependencies. Those materials remain
subject to their own terms. Nothing in `RIGHTS.md` or the absence of a
project-wide license overrides a third party’s license.

This ledger records terms supported by metadata currently present in the
workspace or by the identified upstream artifact page. It also names gaps
that remain in the model-bearing release the owner chose to publish. Shipping
an artifact is not presented as evidence that its terms are complete or that
redistribution permission has been established. This is not legal advice.

## Confirmed or declared terms

### llama.cpp

- **Component:** compiled `llama.cpp` executables and libraries used for GGUF
  inference and embeddings.
- **Local evidence:** `llama.cpp/LICENSE`
- **Packaged notice:** `LICENSES/LLAMA_CPP_MIT.txt`
- **Upstream:** [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)
- **License:** MIT
- **Attribution:** Copyright (c) 2023-2026 The ggml authors.

The full Windows package carries the dedicated MIT notice beside the other
release notices.

### BAAI BGE small English v1.5 and CompendiumLabs GGUF conversion

- **Component:** `models/embedding/bge-small-en-v1.5-q8_0.gguf`
- **Base:** [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5)
- **Exact conversion artifact:**
  [CompendiumLabs/bge-small-en-v1.5-gguf](https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf)
- **Exact identity:** `36,806,944` bytes and SHA-256
  `EC38E8DA142596BAA913124AE50550DE284B6916BF59577EF2F0CB9660C2F514`
  match the repository's Q8_0 file at observed revision
  `d32f8c040ea3b516330eeb75b72bcc2d3a780ab7`.
- **Declared license:** MIT
- **Packaged notice:** `LICENSES/BGE_SMALL_EN_V1.5_NOTICE.txt`

The similarly named ggml-org Q8_0 conversion has different bytes and is not
listed as this artifact's source.

### Moonshine tiny English speech model

- **Component:**
  `models/voice/sherpa-onnx-moonshine-tiny-en-int8/`
- **Local evidence:** the same directory contains `LICENSE` and `README.md`.
- **Upstream:** [Moonshine](https://github.com/moonshine-ai/moonshine)
- **License recorded locally:** MIT
- **Attribution recorded locally:** Copyright (c) 2024 Useful Sensors.

The included license notice must remain with the English model files.

### Piper HFC female medium voice

- **Component:**
  `models/voice/piper/en_US-hfc_female-medium.onnx` and its JSON configuration.
- **Local evidence:**
  `models/voice/piper/en_US-hfc_female-medium.MODEL_CARD.md`
- **Upstream:**
  [rhasspy/piper-voices hfc_female medium](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/hfc_female/medium)
- **Dataset:** [Hi-Fi-CAPTAIN](https://ast-astrec.nict.go.jp/en/release/hi-fi-captain/)
- **Terms named by the bundled card:**
  [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- **Derivation named by the bundled card:** fine-tuned from the U.S. English
  Lessac medium voice.

The upstream Piper voice repository itself is labeled MIT, while this
specific bundled model card names CC BY-NC-SA 4.0 for its dataset. Until
artifact-specific terms are clearer, a release should preserve the model
card and attribution, remain non-commercial, apply the share-alike
obligation where required, and avoid claiming that the voice is
unconditionally MIT.

### Qwen upstream notice

- **Local evidence:** `LICENSES/QWEN_APACHE-2.0.txt`
- **Purpose:** records the Apache-2.0 notice associated with identifiable
  upstream Qwen materials.

That notice does not, by itself, establish the rights of every community
abliteration or GGUF conversion in this workspace. The derivative artifact
records below control the current release decision.

### Qwen2.5-Coder 7B abliterated derivative

- **Component:**
  `models/Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf`
- **Upstream artifact repository:**
  [criscarleo/Qwen2.5-Coder-7B-Instruct-abliterated](https://huggingface.co/criscarleo/Qwen2.5-Coder-7B-Instruct-abliterated)
- **Uploader-declared license:** AGPL-3.0
- **Exact identity:** `8,098,525,056` bytes and SHA-256
  `FBB484A986646E20A2C1A83CB00973B2384436B81E3AC4C6400B9B3DFFB9C6D0`
  match the repository's Q8_0 GGUF at observed revision
  `0936e32925dc0d7dd0e65c117c86112c4873a23b`.
- **Packaged license text:** `LICENSES/AGPL-3.0.txt`
- **Reference:**
  [GNU Affero General Public License version 3](https://www.gnu.org/licenses/agpl-3.0.html)

This model is included in the full Windows researchA package, accompanied by the complete
official AGPL-3.0 text because that is the uploader's declaration. Including
the text does not independently prove the derivative's legal status. A
publisher must review the declaration and any additional upstream
obligations. Do not describe this artifact as Apache-2.0-only.

## Release-carried terms and unresolved gaps

### Qwen3 4B abliterated derivative

- **Component:** `models/Qwen3-4B-abliterated-bf16_q8_0.gguf`
- **Upstream artifact repository:**
  [Mungert/Qwen3-4B-abliterated-GGUF](https://huggingface.co/Mungert/Qwen3-4B-abliterated-GGUF)
- **Uploader declaration:** no license is declared; source, fine-tuned-from,
  developer, risks, and limitations are also left unresolved in the model
  card.
- **Exact identity:** `4,645,051,328` bytes and SHA-256
  `947656A42E73BDA324C527F06953596B77E4D91BC590476955205B5F64D4E974`
  match the repository's file at observed revision
  `56175aed285a884480f49bb18d2a1b0e05a7749f`.

Repository availability is not permission to redistribute. The project owner
has deliberately included this exact file in the full Windows researchA package while
preserving this warning. That release decision does not resolve the missing
license declaration and must not be described as proof of permission.

### Qwen2.5-Coder 14B abliterated derivative and GGUF

- **Component:**
  `models/Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf`
- **Exact GGUF repository:**
  [bartowski/Qwen2.5-Coder-14B-Instruct-abliterated-GGUF](https://huggingface.co/bartowski/Qwen2.5-Coder-14B-Instruct-abliterated-GGUF)
- **Derivative source named by that repository:**
  [huihui-ai/Qwen2.5-Coder-14B-Instruct-abliterated](https://huggingface.co/huihui-ai/Qwen2.5-Coder-14B-Instruct-abliterated)
- **Exact identity:** `8,988,111,200` bytes and SHA-256
  `E89A7AE4E2B456BF33C75CFF35664751DF20FF273E551D7CF7640AA9E84D3B79`
  match the Bartowski Q4_K_M file at observed revision
  `91e7d17796389c79de80776bbd947afa81c1e34d`.
- **Uploader declarations:** both named repositories display `apache-2.0`.
- **Release status:** intentionally published as the separate versioned Beta
  6 full-maintenance model pack.

The exact byte source and named derivative chain are now recorded. Those
uploader declarations are evidence, not an independent legal conclusion.
`LICENSES/QWEN_APACHE-2.0.txt` accompanies the release where those declared
terms apply. A same-named TensorBlock GGUF has a different SHA-256 and is not
the source of this artifact.

### Silero VAD

- **Component:** `models/voice/silero_vad.onnx`
- **Locally recorded source:** the setup script downloads it from the
  k2-fsa/sherpa-onnx `asr-models` release.
- **Upstream model project:**
  [snakers4/silero-vad](https://github.com/snakers4/silero-vad)
- **Published license:** MIT
- **Attribution:** Copyright (c) 2020-present Silero Team
- **Packaged notice:** `LICENSES/SILERO_VAD_MIT.txt`

The upstream project describes its pretrained VAD models as MIT-licensed. The
release preserves that notice. The exact local SHA-256 in `MODELS.md` proves
which bytes are shipped; it is not an upstream signature or an independent
legal conclusion.

### Developer-only legacy GGUF

The legacy Qwen3 Instruct GGUF listed in `MODELS.md` is not selected for the
full Windows package or the optional 14B pack. Its presence must not cause it
to be copied into a public archive.

## Installed runtime dependencies

`setup/requirements-release-windows.txt` records the selected top-level
runtime versions:

- requests 2.34.2
- numpy 2.5.1
- soundcard 0.4.6
- sounddevice 0.5.5
- soundfile 0.14.0
- sherpa-onnx 1.13.4
- piper-tts 1.5.0
- pypdf 6.14.2

The repository does not currently contain a verified license-and-notice
inventory for those installed distributions and their transitive
dependencies. This document therefore does not guess their terms. A public
binary release should generate an inventory from the exact bundled wheels or
installed distribution metadata and include every required notice.

The embedded Python runtime and any downloaded bootstrap material require the
same release-time review.

## Release gate

Before publishing any archive:

1. Generate an exact file manifest with byte size and SHA-256.
2. Confirm that every included model, runtime, wheel, DLL, font, audio asset,
   and image has a provenance record, including an explicit unresolved marker
   where terms remain incomplete.
3. Include the corresponding license texts, references, and attribution
   inside every archive or asset set that contains the material.
4. Make the exact model-bearing asset list and unresolved declarations visible
   in the release notes; never turn uncertainty into a claim of permission.
5. Do not use “open source” for the whole project while `RIGHTS.md` remains
   the project’s rights statement.
6. Re-run this review whenever an artifact, upstream revision, or package
   version changes.
