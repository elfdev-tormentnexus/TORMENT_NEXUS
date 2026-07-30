# researchA testing session — findings, evidence, and what to do next

Written by Claude, 2026-07-29, during and after the researchA cut. Every
claim below was measured against the live system or read from source, not
recalled. Where something is inferred rather than verified, it says so.

Read §1 for the status board, §2 for the one fix that matters most, and §7
if you only have five minutes.

---

## 1. Status board

| thing | state |
| --- | --- |
| researchA release | **Published.** `prerelease=true`, 25 assets, 21.21 GB |
| tag `researchA` | Annotated, dereferences to **`dc119b4`**, verified |
| asset integrity | 25/25 size + SHA-256 matched to local; 14/25 also re-downloaded and decoded |
| `master` | Untouched at `ef10a4c` (beta-5 era), 77 commits behind `beta-6-release` |
| working tree | Clean at `dc119b4` **except** the README aesthetic pass (uncommitted, see §6) |
| test suite | 923 pass, 2 expected skips, as of the pre-publish run |

**Nothing below blocks anything.** The release is out and correct. These are
improvements, ranked.

---

## 2. The intermittent "[no response]" bug — root cause found

This is the highest-value item in the document. It is a long-standing,
user-visible bug that was never reproducible on demand, and it is two lines.

**Cause.** The shipped chat model `Qwen3-4B-abliterated-bf16_q8_0.gguf` is a
**hybrid thinking** variant — its chat template carries `enable_thinking` and
defaults it *on*. It is not the `Qwen3-4B-Instruct-2507` non-thinking release
that `config.py:410` still describes.

Measured on the live server, identical prompt ("What is 17 plus 26?"):

| request | completion tokens | `reasoning_content` | `content` |
| --- | ---: | ---: | --- |
| no kwarg, `max_tokens=600` | 351 | 907 chars | `"17 plus 26 equals 43."` |
| no kwarg, `max_tokens=200` | 200, `finish_reason: length` | — | **empty** |
| `enable_thinking: false` | 12 | none | `"17 + 26 = 43."` |

The suppression works where it is sent. There are **14** production
`/v1/chat/completions` call sites in `assistant/` and only **12** guards.

**The two unguarded sites:**

| file:line | what it is | `max_tokens` |
| --- | --- | ---: |
| `assistant/main.py:2599` | silence-breaker — "the assistant talking to an empty room" | **40** |
| `assistant/main.py:2654` | system-awareness remark | **48** |

A reasoning block runs a few hundred tokens. It cannot fit in 40 or 48, so
`content` returns empty **every time** those paths fire. They only fire on an
idle timer, which is exactly why typing could never reproduce it.

**Why the existing backstop misses it.** `config.py:414` calls the `<think>`
stripper "a backstop either way." Current llama.cpp returns reasoning in a
separate **`reasoning_content`** field, not inline tags, so the stripper never
sees anything. Nothing in the codebase reads `reasoning_content` — zero
matches across `assistant/` and `tools/`.

### Implementation — warranted

1. Add `"chat_template_kwargs": {"enable_thinking": False},` to both payloads.
2. **Add a regression asserting every `/v1/chat/completions` payload built in
   `assistant/` carries the kwarg.** The 14-vs-12 mismatch is precisely what a
   test can hold and a reader cannot. Same shape as the `session_rhythm`
   finding: the guard was right everywhere it was applied, and nothing checked
   that it was applied everywhere.
3. Correct `config.py:410-415`. It says the guard is precautionary "in case the
   model is ever swapped back to a thinking/hybrid variant." That swap has
   happened; the guard is now load-bearing and the comment should say so,
   or someone will remove it as dead weight.

---

## 3. The truncation warning fires backwards

Found by adversarial input testing. `machinespirit.py:56` states the
assumption the mechanism rests on:

> llama.cpp truncates a longer input rather than refusing it

**That is false against this build.** Measured boundary:

| input | tokens | result |
| --- | ---: | --- |
| `"cat " * 510` | 512 | accepted |
| `"cat " * 511` | 513 | **refused**, `trajectory()` returns `None` |

`looks_truncated()` is `len(path) >= CONTEXT_TOKENS`, so it trips only when an
input fits *exactly*. Verified:

```
input that fits EXACTLY: tokens = 512
looks_truncated(path)   = True
spread[truncated]       = True
```

That surfaces to the user as *"only the first 512 tokens fit… this measures
that much and not the rest"* — when there is no rest. Meanwhile 513 tokens
never reaches `spread()` at all, so the flag cannot fire for the case it was
written for. The `trail` command instead says *"Both embedding servers
answered, but no trajectory came back"*, which reads as a fault rather than a
length limit the user could act on.

Sites: `machinespirit.py:118`, `:370`, `:545`; `command_handlers.py:3370`,
`:3421`.

### Implementation — suggested

The honest fix is to stop inferring. `trajectory()` collapses four distinct
failures into one bare `None` — not configured, non-200, `RequestException`,
`ValueError`, empty payload. The server distinguishes them and the function
discards the distinction. Carrying a reason would fix both this and §4.

Note the project already recognised this pattern: `anchor_vectors()` carries
a note that a pooled-embedder failure *"looks identical to one that fails
because the unpooled one is — see `diagnose()`"*. That reasoning was applied
to the two-server case; input overflow falls outside it.

---

## 4. Empty input has a fixed meaning — latent, not live

`""`, `" "`, `"\n\n"`, `"\t"` all tokenize to bare `[CLS][SEP]` and produce
**identical** readings:

```
tokens=2  effective_rank=1.0001  anchors=1
top anchor = 'a medication taken on a schedule'  support=0.2987
```

Null input is not refused, and it does not read as nothing. It reads,
deterministically, as a health topic.

**Not currently reachable** — `command_handlers.py:3288` strips and guards,
and calibration uses a fixed corpus. This is a landmine for the next caller,
not a live defect.

### Implementation — suggested

A guard in `trajectory()` itself rather than relying on every future call site
remembering. At minimum a comment, because "empty text yields a confident
medication reading" is not discoverable.

---

## 5. Research: the Fourier residual now has three of four controls

`VECTOR_TRANSLATION_RESEARCH.md` §5b names four required controls for the
unexplained ~+0.010 sinusoidal edge. Three now have numbers.

**Reproduction first.** Fourier matched the published table exactly at all
three parameter counts (0.8920 / 0.9260 / 0.9522) and random matched within
0.002 once the control was built correctly — see the caveat below.

**Control #2, permutation.** Scrambling token order collapses the edge to zero
at every k (+0.0106 → −0.0000 at k=13) while the random basis moves by
±0.0002, as an exchangeable basis must. The residual is **order-dependent,
not content-dependent**.

**Control #1, matched-length unrelated texts.** 32 held-out texts at 39
tokens: mean edge **+0.0050** at k=13 and **+0.0042** at k=21, sd ≈ mean,
positive in 27/32 and 28/32. The effect is real but the published **+0.010 is
roughly double the typical value** — it came from one text sitting near the
top of the distribution.

**Control #3, position basis, recovered empirically.** Averaging token vectors
position-by-position across unrelated texts cancels content and leaves the
positional footprint; SVD gives a basis. On held-out texts it beats random by
+0.0016–0.0019 — about **40% of Fourier's edge**. Real, but not the whole
story.

**Local smoothness measured and excluded.** Centred on each text's own mean,
adjacent tokens correlate at **+0.034** and gap-2 is already **−0.006**,
decaying to −0.038 by gap 20. The neighbour effect is confined to gap 1 and is
far too high-frequency for 13–21 smooth basis functions. What Fourier exploits
is the slow monotone drift, not the neighbour spike.

### Implementation — warranted (documentation)

- Change "Fourier's genuine edge over random is about +0.010" to **+0.004 to
  +0.005, sd ≈ 0.005, varies by text and is occasionally negative**.
- Record that control #1 and a form of control #3 have been run, and that
  adjacent-token local smoothness is excluded as the explanation.
- Control #4 — a model with a genuinely different position mechanism —
  remains the test that would settle it.

### Open question worth a fresh look

**The polynomial column may be measuring the solver, not the basis.** Fourier
and random reproduce exactly; polynomial diverges progressively — exact at
k=5, off 0.004 at k=13, off **0.025** at k=21 (mine 0.9491/0.9510 vs published
0.9243). A degree-20 Vandermonde over 39 points is severely ill-conditioned.
Under plain least squares the polynomial-vs-sinusoid gap at k=21 is **0.0012,
not the published 0.0279**. If the published number reflects conditioning,
then "sinusoids are the right shape where polynomials are the wrong one" is a
statement about the fit, not the bases. I could not resolve this — **no
committed fitting code exists for that table**, which is itself worth fixing.

### Methodological caveats on my own numbers

- My corpus is the project's own documentation: one register, shared
  vocabulary. Homogeneous content does not cancel cleanly when averaging by
  position, which could inflate control #3 specifically. **This is the weakest
  joint** and the first thing to redo with a general corpus.
- One token length (39), 32 held-out texts, sd as large as the mean.
- A random basis **must include a constant column**. Degree 0 alone is 0.8733
  and the structured bases inherit it free; a pure zero-mean Gaussian basis
  scores 0.33–0.72 and is not a matched control. My first attempt got this
  wrong, which is why the mistake is recorded rather than deleted.

---

## 6. GitHub presentation — partially done, uncommitted

An onboarding/aesthetic pass on `README.md` is **applied locally and not
committed**. The design rule used: the cryptic register lives in framing and
furniture; the CAUTION block, requirements table, and numbered steps stay
literal, because a disclaimer that reads as flavour stops working as one.

Applied so far:

- a centred epigraph under the title (`researchA · the pixels are the payload
  · MACHINESOUL1`) and a one-line subtitle;
- a new **"The two languages"** section explaining machinesoul vs
  machinespirit — the single best onboarding addition, because it answers "why
  is this repo full of PNGs" and is entirely true;
- italic framing lines on "Choose your path" and the install section
  (*"You are not downloading the program. You are downloading its image, and
  developing it."*).

All 7 documentation tests pass after these edits.

**The published release body was also corrected** — it still claimed the
release "remains a draft until its uploaded assets are downloaded again",
which was false once published. Replaced with the actual verification record,
plus a matching epigraph. Verified afterwards: no mojibake, all asset
instructions intact.

### Constraints anyone continuing this must respect

`README.md` and `docs/INSTALL_WINDOWS.md` must name an **identical set** of
asset filenames — the test compares the two sets rather than a fixed list.
Current set is 11. README must also contain literally: `setup/requirements.txt`,
`.\setup\test_assistant.bat`, `researchA`, `SABLEROSETTA1`, "each model must
build its own half", "re-encode", "every", "Source code". It must **not**
contain `.zip.part01.png`, `MUSIC_VISUALIZER_PATCH`, `WITH_MUSIC_PATCH`,
`v0.1.0-beta.3`, or any mojibake marker. All local markdown links must resolve.

### The bigger onboarding problem, found while pushing the above

**The repository's default branch is `master`, so the GitHub landing page
serves the beta-5 README.** Measured: README on `master` is 15,253 characters
and contains no `researchA`, no `SABLERESEARCHA-*` asset names, and no
`SABLEROSETTA1`. README on `beta-6-release` is 29,201 characters and has all
of it.

Anyone arriving at the repository sees install documentation for a build two
releases old, with no path to the release that is actually published. The
aesthetic pass is real but secondary — the front door has been stale for 77
commits, and no amount of rewriting `beta-6-release` changes what a visitor
reads.

This was the unpriced consequence of leaving `master` untouched when the tag
was retargeted. Retargeting the tag was correct; nobody costed the homepage.

**Two options, both needing a decision rather than a default:**

- Change the repository's default branch to `beta-6-release`. Smallest
  action, immediately correct landing page, no history rewritten. `master`
  keeps its meaning as the older stable line.
- Merge `beta-6-release` into `master`. Makes researchA the mainline. Larger,
  and changes what "master" has meant in this project so far.

Do not do either without deciding deliberately. The release itself is
unaffected either way — the tag points at `dc119b4` and its assets are
correct.

### Remaining, if wanted

The install steps and the `<details>` block were left in their existing plain
voice. They could take the same treatment, but they are the part a confused
person reads under pressure, so restraint there is deliberate rather than
unfinished.

---

## 7. If you only have five minutes

1. Apply the two-line fix in §2 and add the "every payload carries the kwarg"
   regression. It fixes a bug that has bothered you for months.
2. Correct the +0.010 figure in `VECTOR_TRANSLATION_RESEARCH.md` per §5.
3. Decide whether the README pass in §6 gets committed, changed, or reverted —
   it is sitting uncommitted and is the only dirty thing in the tree.

Everything else can wait indefinitely without harm.

---

## 8. Verified good — no action needed

Recorded so nobody re-audits them.

- **Calibration reads exactly as recorded.** All seven rows re-measured
  against the live model: drift `0.000000` on effective rank, entropy, and
  purity; `top_anchor` stable on all seven. Model name and anchor digest both
  match the record. The published 1.5238 / 1.5132 / 1.4354 and 1.694-over-39
  figures reproduce.
- **The reading surface is robust.** 30 adversarial inputs — null bytes, RTL
  scripts, zero-width joiners, combining diacritics, 2000-character words,
  prompt-injection-shaped text, path-traversal JSON — produced zero invariant
  violations. No crash, no NaN, effective rank never left `[1, n]`, purity
  stayed in `(0, 1]`, trail always sorted.
- **Both coder GGUFs are valid.** Headers parse clean: Coder-7B (qwen2, 7.6B,
  Q8_0, 28 blocks, ctx 32768) and Coder-14B (qwen2, 14B, Q4_K_M, 48 blocks,
  ctx 32768). Launchers reference the correct paths and roles and guard for
  missing files. **Not** load-tested — neither was started and generated
  through.
- **The 14B is not a strict upgrade.** 14B at Q4_K_M against 7B at Q8_0 is
  roughly double the parameters at roughly half the precision per weight. The
  release body's framing — for *long* sessions rather than *better* — is the
  honest one and should stay.
- **The capsule description hook works as designed**, including printing its
  own "not covered by the sha256 gate" disclaimer on every read.

---

## 9. Wi-Fi CSI — the queue changed, the order did not

`WIFI_CSI_REPRODUCTION.md` concludes CSI needs "a separate x86 machine running
Ubuntu 22.04.1." **That is an IAX constraint, not a CSI constraint.** Verified
by reading source, not marketing:

- **No kernel lock.** `KuskoSoft/FeitCSI-iwlwifi` is a DKMS backports tree
  (`backport-include/`, `compat/`, `AUTOINSTALL="yes"`, builds against
  `/lib/modules/$kernelver`, Makefile enumerates the 6.x series). IAX
  hard-`exit`s on anything but 5.15.x; this is the opposite design.
- **The Python parser already exists.** `Gi-z/CSIKit` ships
  `CSIKit/reader/readers/read_feitcsi.py`. The "port the MATLAB decoder" work
  item does not need doing for this route. FeitCSI also exposes a UDP socket,
  so the sidecar shape and the `core/wifi_experimental.py` contract are
  unchanged.
- **Wider firmware coverage** — ships `cc-a0` (AX200), which IAX lacks.

**Correction to the guardrail reasoning:** it is not only `iwlwifi` that gets
replaced. DKMS installs `compat`, `iwlwifi`, `iwlxvt`, `iwlmvm`, **`mac80211`,
and `cfg80211`** into `/updates`. The last two are the shared 802.11 stack, and
the Pi's onboard Broadcom radio rides on them. The genuinely unaffected
fallback on a Pi is **Ethernet**, not onboard Wi-Fi.

**The sequencing rule still holds.** The LD2450 has not arrived and has not
been measured. Nothing here changes the order in `SENSING_MODULE.md` — it
changes only the *cost* of step 3 if the first two are measured and rejected:
a card, an M.2 E-key HAT, and a spare SD card rather than a whole machine.

Better than a repair script: do CSI work on a **separate boot medium**. A
repair patch is code that must execute correctly on a broken machine; a second
SD card is physics.

Still open: M.2 E-key HAT availability for the Pi 5 (most Pi 5 M.2 HATs are
M-key for NVMe), whether a Whisplay HAT and an M.2 HAT can share the board,
and whether FeitCSI has been *demonstrated* on arm64 as opposed to claimed.

---

## 10. Scratchpad artifacts

Full working files, including the scripts, live in this session's scratchpad:

| file | what |
| --- | --- |
| `THINKING_LEAK_DIAGNOSIS.md` | §2 in full |
| `STRESS_FINDINGS_machinespirit.md` | §3, §4, the 30-case harness results |
| `stress_machinespirit.py`, `find_cutoff.py` | reproduce §3/§4 |
| `FOURIER_RESIDUAL_FULL_PICTURE.md` | §5 in full |
| `basis_permutation_control_v2.py`, `position_basis_control.py`, `local_smoothness_check.py` | reproduce §5 |
| `FEITCSI_VIABILITY.md` | §9 in full |
| `recheck_calibration.py`, `gguf_header.py` | reproduce §8 |

Anything needing the live reading surface requires hazard mode, and the
unpooled server is **not** inherited by a separate process:

```bash
TORMENT_NEXUS_MACHINESPIRIT_URL="http://127.0.0.1:8084" TORMENT_NEXUS_MACHINESPIRIT_KEY="machinespirit" python stress_machinespirit.py
```
