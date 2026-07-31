# Models and provenance

Status: release artifact inventory for `researchC`, reviewed
2026-07-28.

This file separates model behavior, application authority, and redistribution
rights. A model’s name or alignment does not grant it tool authority, and a
base model’s license does not automatically establish the license of a
community-modified derivative.

All hashes below are SHA-256 values computed from the local files. Byte sizes
are exact. A matching repository file was treated as the byte source only
when its published size and complete SHA-256 both matched the local artifact.

## researchC model-bearing release decision

The full Windows researchC package intentionally carries the 4B director, 7B maintenance
coder, and BGE embedding model. The 14B full-maintenance coder is intentionally
published as a separate, versioned add-on asset set because of its size.

That is a statement of what the project owner chose to publish, not a legal
opinion or a claim that every uploader granted adequate redistribution rights.
In particular, the exact 4B source repository still declares no license.
Recipients and downstream redistributors must review the evidence below and
make their own decision.

## Behavioral disclosure

The current director and maintenance coder are community-modified
“abliterated” models. Their weights were modified to reduce learned refusal
behavior.

They may comply with requests that other assistants reject and can produce
false, harmful, illegal, explicit, biased, manipulative, or insecure content
with confidence. Abliteration does not increase truthfulness or capability,
and it does not guarantee that a model will never refuse.

Trusted Python code, not model alignment, defines available actions. Those
controls are not an operating-system sandbox. See `SAFETY.md`.

## Current language and retrieval models

### Qwen3 4B abliterated Q8 director

- **Local filename:** `models/Qwen3-4B-abliterated-bf16_q8_0.gguf`
- **Role:** default director for ordinary conversation, persona, planning,
  and requests routed through application-owned capabilities.
- **Exact size:** `4,645,051,328` bytes
- **SHA-256:** `947656A42E73BDA324C527F06953596B77E4D91BC590476955205B5F64D4E974`
- **Upstream artifact repository:**
  [Mungert/Qwen3-4B-abliterated-GGUF](https://huggingface.co/Mungert/Qwen3-4B-abliterated-GGUF)
- **Source revision observed:** `56175aed285a884480f49bb18d2a1b0e05a7749f`
- **Identity evidence:** the repository's
  `Qwen3-4B-abliterated-bf16_q8_0.gguf` reports the same exact byte size and
  SHA-256 as this local file.
- **License status:** the uploader declares no license. The model card says
  “More Information Needed” for license, developer, source, fine-tuned-from,
  risks, and limitations.
- **Release status:** included in the full Windows researchC package by the project
  owner's explicit decision. The missing license declaration remains
  unresolved; inclusion must not be represented as proof of permission.

The local Apache-2.0 Qwen notice records terms that may apply to identifiable
upstream Qwen materials. It does not fill the uploader’s missing declaration
or, by itself, grant rights to this modified GGUF.

### Qwen2.5-Coder 7B abliterated Q8 maintenance coder

- **Local filename:**
  `models/Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf`
- **Role:** bundled on-demand maintenance coder used by bounded coding and
  autonomous-maintenance profiles; it is not the ordinary conversational
  director.
- **Exact size:** `8,098,525,056` bytes
- **SHA-256:** `FBB484A986646E20A2C1A83CB00973B2384436B81E3AC4C6400B9B3DFFB9C6D0`
- **Upstream artifact repository:**
  [criscarleo/Qwen2.5-Coder-7B-Instruct-abliterated](https://huggingface.co/criscarleo/Qwen2.5-Coder-7B-Instruct-abliterated)
- **Source revision observed:** `0936e32925dc0d7dd0e65c117c86112c4873a23b`
- **Identity evidence:** the repository's Q8_0 GGUF reports the same exact
  byte size and SHA-256 as this local file.
- **License status:** the uploader declares `AGPL-3.0`.
- **Release status:** included in the full Windows researchC package. Any redistribution
  must be reviewed for the uploader-declared AGPL-3.0 terms and any applicable
  upstream model terms. The included Qwen Apache-2.0 notice must not be
  presented as replacing the uploader’s AGPL declaration.

AGPL-3.0 reference:
[GNU Affero General Public License version 3](https://www.gnu.org/licenses/agpl-3.0.html).
The package carries the complete official text as
`LICENSES/AGPL-3.0.txt` because this is the uploader-declared license. Its
inclusion records and follows that declaration; it does not independently
prove the derivative's legal status.

### BGE small English v1.5 Q8 embedding model

- **Local filename:** `models/embedding/bge-small-en-v1.5-q8_0.gguf`
- **Role:** non-generative semantic embeddings for memory retrieval, history
  recall, and the retrieval-vector display. It does not write memories or
  generate answers.
- **Exact size:** `36,806,944` bytes
- **SHA-256:** `EC38E8DA142596BAA913124AE50550DE284B6916BF59577EF2F0CB9660C2F514`
- **Base model:**
  [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5)
- **Exact GGUF repository:**
  [CompendiumLabs/bge-small-en-v1.5-gguf](https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf)
- **Source revision observed:** `d32f8c040ea3b516330eeb75b72bcc2d3a780ab7`
- **Identity evidence:** that repository's
  `bge-small-en-v1.5-q8_0.gguf` reports the same exact byte size and SHA-256
  as this local file. The similarly named ggml-org conversion has different
  bytes and is not the source of this artifact.
- **Provenance:** the CompendiumLabs model card identifies
  `BAAI/bge-small-en-v1.5` as its source and describes a GGUF conversion for
  llama.cpp.
- **License status:** the BAAI base and the exact CompendiumLabs conversion
  repository declare MIT.

Embedding vectors are derived from private memories, history, and queries.
Treat `assistant/cache/embeddings.json` as private even though it does not
store the original text verbatim.

## Current offline voice models

### Piper HFC female voice

- **Model:** `models/voice/piper/en_US-hfc_female-medium.onnx`
- **Role:** default local text-to-speech voice.
- **Exact size:** `63,201,294` bytes
- **SHA-256:** `914C473788FC1FA8B63ACE1CDCDB44588F4AE523D3AB37DF1536616835A140B7`
- **Configuration:**
  `models/voice/piper/en_US-hfc_female-medium.onnx.json`
- **Configuration size:** `5,033` bytes
- **Configuration SHA-256:**
  `03F1FA0622B80463283592D97ACA9F6E89AEC345A5C56B7257723E0093C58B6C`
- **Bundled model card:**
  `models/voice/piper/en_US-hfc_female-medium.MODEL_CARD.md`
- **Upstream voice directory:**
  [rhasspy/piper-voices hfc_female medium](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/hfc_female/medium)
- **Provenance:** the bundled card identifies the Hi-Fi-CAPTAIN dataset and
  says this voice was fine-tuned from the U.S. English Lessac medium voice.
- **License status:** the bundled model card identifies
  [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
  for the dataset. This project conservatively treats the voice artifact as
  requiring that attribution, non-commercial, and share-alike notice unless
  clearer artifact-specific terms are established.

### Moonshine tiny English int8 speech recognizer

Directory:
`models/voice/sherpa-onnx-moonshine-tiny-en-int8/`

Role: local English automatic speech recognition through sherpa-onnx.

| File | Exact bytes | SHA-256 |
| --- | ---: | --- |
| `preprocess.onnx` | `6,800,738` | `F33ADDCE61A143460FE753B5EE5B7DB255E5140B5B779C065B94F6C83FF0BF4E` |
| `encode.int8.onnx` | `18,249,187` | `8774DFBA578DE027EC6595C2C654A0836434489BC963A0DB124A7F181F571ACB` |
| `cached_decode.int8.onnx` | `45,264,830` | `2AFF28BBA6A03D8DCF5C9FEAC45462629BAE37317442299F28115AD09DA773F6` |
| `uncached_decode.int8.onnx` | `53,216,096` | `216737000DD5881A17AA043F6BBD286ADD33E4C3B0AE257153E2EC15438BDC41` |
| `tokens.txt` | `436,688` | `1165C2AEB9F72F457A83BE2D459A09054F27490ACD9B41BD43794DFD25E296EA` |

- **Combined size of the five runtime files:** `123,967,539` bytes
- **Upstream:** [Moonshine](https://github.com/moonshine-ai/moonshine)
- **Distribution source:** the setup script downloads the sherpa-onnx
  `sherpa-onnx-moonshine-tiny-en-int8` release archive.
- **License status:** the bundled directory contains an MIT license for the
  English model, copyright Useful Sensors.

### Silero voice-activity detector

- **Local filename:** `models/voice/silero_vad.onnx`
- **Role:** local speech-versus-silence detection; it does not transcribe
  speech.
- **Exact size:** `643,854` bytes
- **SHA-256:** `9E2449E1087496D8D4CABA907F23E0BD3F78D91FA552479BB9C23AC09CBB1FD6`
- **Distribution source:** the locally verified setup code downloads this
  file from the k2-fsa sherpa-onnx `asr-models` release.
- **Upstream model project:**
  [snakers4/silero-vad](https://github.com/snakers4/silero-vad)
- **License evidence:** the upstream Silero VAD project publishes its code and
  pretrained models under MIT and carries the Silero Team MIT notice.
- **Packaged notice:** `LICENSES/SILERO_VAD_MIT.txt`
- **Release status:** included in the full Windows researchC package. The local hash
  identifies the shipped bytes; the upstream notice identifies the terms
  published for Silero VAD rather than proving a separate artifact signature.

## Optional researchC full-maintenance companion

### Qwen2.5-Coder 14B abliterated Q4_K_M

- **Local filename:**
  `models/Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf`
- **Role:** opt-in full-maintenance coder for deliberately requested long
  self-heal and extended editing sessions under the widest,
  typed-confirmation maintenance profile.
- **Exact size:** `8,988,111,200` bytes
- **SHA-256:** `E89A7AE4E2B456BF33C75CFF35664751DF20FF273E551D7CF7640AA9E84D3B79`
- **Exact GGUF repository:**
  [bartowski/Qwen2.5-Coder-14B-Instruct-abliterated-GGUF](https://huggingface.co/bartowski/Qwen2.5-Coder-14B-Instruct-abliterated-GGUF)
- **Source revision observed:** `91e7d17796389c79de80776bbd947afa81c1e34d`
- **Identity evidence:** that repository's Q4_K_M file reports the same exact
  byte size and SHA-256. A same-named TensorBlock GGUF reports a different
  SHA-256 and is not the source of this local file.
- **Derivative source named by the quantizer:**
  [huihui-ai/Qwen2.5-Coder-14B-Instruct-abliterated](https://huggingface.co/huihui-ai/Qwen2.5-Coder-14B-Instruct-abliterated)
- **License declarations:** both the exact GGUF repository and the named
  derivative repository display `apache-2.0`. This records uploader metadata;
  it is not an independent legal conclusion about every input to the
  derivative chain.
- **Release status:** current optional companion to researchC, not an old or
  superseded model. The researchC release republishes its exact verified
  model as a separate machinesoul vector-field set rather than placing the
  8.4 GB model inside the main Windows package.

The versioned model-pack manifest and installer refuse any source file whose
size or SHA-256 differs from the values above.

## Developer-workspace model not selected for researchC

This file currently exists in the development workspace but is not selected
by either the full Windows package or the optional 14B model pack:

| Local filename | Intended role | Exact bytes | SHA-256 | Provenance status |
| --- | --- | ---: | --- | --- |
| `models/Qwen3-4B-Instruct-2507-Q5_K_M.gguf` | Legacy/non-default director alternative | `2,889,513,216` | `1E4544DFA0A5F4477C03AA8E2CE42E96F217946B7F9CD130392C3FFFBC1449FD` | Not established by local metadata; do not redistribute without a separate review. |

Its presence on a developer’s disk is not a statement that it is part of the
public release.

## Verification

On Windows PowerShell, verify an artifact before use:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath ".\models\your-model.gguf"
```

Compare the complete 64-character value, not a shortened screenshot. A hash
confirms byte identity with this inventory; it does not prove that an
artifact is safe, lawful, accurate, or appropriately licensed.
