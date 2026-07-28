# Rights and reuse

Status: project rights statement for `v0.2.0-beta.6`, reviewed 2026-07-28.

## No project-wide license grant yet

This repository does not currently contain a project-wide software or
documentation license.

That means no general permission is granted by this project to copy, modify,
redistribute, publish, sell, sublicense, or incorporate project-authored
code, documentation, artwork, or other original material into another work.
Rights normally reserved to each copyright holder remain reserved unless a
specific file or a later license says otherwise.

The repository is **source-visible**, not presently offered as an
open-source-licensed project.

## Viewing is not a reuse license

The repository can be viewed through GitHub, and the platform may technically
permit cloning or downloading it. Visibility and technical access are not a
project-wide grant to reuse or redistribute the material.

You may inspect the source to understand the project, evaluate whether to run
it, and prepare a responsible issue report to the extent allowed by
applicable law and the hosting platform’s terms. Do not assume broader
permission from the absence of a license file.

If you need permission for another use, ask the repository owner and obtain a
clear written grant before relying on it.

## Third-party material

Third-party components keep their own licenses and are not relicensed by this
statement. This includes language and embedding models, voice models,
llama.cpp, Python packages, DLLs, fonts, and other incorporated material.

See `MODELS.md` and `THIRD_PARTY_NOTICES.md`. Some current artifacts have
restrictive or unresolved terms:

- the Qwen2.5-Coder 7B abliterated uploader declares AGPL-3.0;
- the Qwen3 4B abliterated uploader declares no license;
- the bundled Piper HFC female model card identifies CC BY-NC-SA 4.0 for its
  dataset;
- other runtime notices still require a release-time inventory.

`LICENSES/QWEN_APACHE-2.0.txt` applies only where the underlying material and
derivation actually qualify for those terms. It is not a license for the
entire repository and does not cure a derivative artifact’s missing or
different license.

## Beta 6 distribution decision

The repository owner has explicitly chosen a model-bearing Beta 6:

- the full Windows package contains the exact 4B abliterated director, 7B
  abliterated maintenance coder, and BGE embedding weights listed in
  `MODELS.md`;
- the exact 14B abliterated full-maintenance coder is a separate, versioned
  add-on asset set; and
- the legacy Qwen3 Instruct alternate is not selected.

This section records scope so the release cannot quietly imply that it is
model-free. It does not grant a license, override an upstream license, or
convert an uploader's missing license declaration into permission. The 4B
uploader still declares no license. The 7B uploader declares AGPL-3.0. The
exact 14B GGUF and its named derivative repositories display Apache-2.0, as
recorded with exact hashes and observed revisions in `MODELS.md`.

## User data and generated material

The project makes no ownership claim over an operator’s private conversations,
memories, activity records, credentials, personal music, or other data merely
because the application stores or processes it locally.

Model output may reproduce or resemble third-party material, contain false
attribution, or be unsuitable for reuse. The project does not promise that
generated output is original, non-infringing, accurate, or available under
any particular license. The operator is responsible for reviewing a proposed
use.

## Contributions

Opening an issue or pull request does not change this repository’s rights
status. Contributors retain rights they hold in their work unless they make a
separate, explicit grant.

Because there is not yet a published contribution license or contributor
agreement, discuss substantial contributions with the maintainer before
investing significant work. A maintainer may require clear provenance and an
explicit license statement before merging.

See `CONTRIBUTING.md`.

## No warranty

The project is experimental and provided without a promise of fitness,
accuracy, safety, availability, support, or compatibility. Third-party
licenses may contain their own warranty disclaimers.

This document is intended to state the repository’s current permission
boundary clearly. It is not legal advice and does not limit rights that
applicable law grants independently.
