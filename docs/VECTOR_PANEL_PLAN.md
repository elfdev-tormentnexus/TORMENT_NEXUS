# Vector panel — design and staging

A dedicated right-gutter UI element that renders the assistant's retrieval
space as points, active only when the terminal is large enough to spare the
columns.

**Not part of Beta 5.1.** This is additive. It gets its own branch, per the
triage rule in `QC_REVIEW_PLAN.md`. Sequenced after the fix patch lands.

---

## What was ruled out, and why

**Detecting a maximized window.** A terminal program sees a character grid.
`shutil.get_terminal_size()` returns columns and rows; there is no window state
in it. The Windows escape hatch — `GetConsoleWindow()` from kernel32 plus
`GetWindowPlacement()` from user32, testing `showCmd == SW_SHOWMAXIMIZED` —
fails on this project's own setup: under Windows Terminal, which is the
Windows 11 default and what a `.bat` double-click opens, `GetConsoleWindow()`
returns a handle to the *hidden pseudo-console* window rather than the visible
one. Its placement is meaningless. There is no equivalent on the Pi target at
all, and `ctypes` is a `_SENSITIVE_IMPORT_ROOTS` entry, so the workaround would
also widen the guard surface to buy an answer that is wrong.

**Gate on available cells instead.** This serves the stated intent better. A
maximized window on any normal display is 150+ columns; a default one is 80×24.
The separation is not close. It also behaves correctly in the two cases the
window-state test gets wrong: a large non-maximized window (space exists, show
it) and a maximized window on a very small display (no space, hide it).

The codebase already establishes this pattern — `ui.py:1625` gates compact
voice rendering on `self.height < 18`.

---

## Activation rule

```
PANEL_MIN_WIDTH   = 150   # columns in the whole terminal
PANEL_MIN_HEIGHT  = 32    # rows
PANEL_WIDTH       = 44    # columns the panel reserves
PANEL_MIN_CONTENT = 90    # chat must keep at least this much
```

Active when `width >= PANEL_MIN_WIDTH and height >= PANEL_MIN_HEIGHT`.
Otherwise `content_width == width` and nothing below changes at all — the
small-window path must be byte-identical to today's rendering.

---

## Layout change

Today chat wraps to the full terminal width — `ui.py:2129`,
`wrap_w = max(w - CHAT_INDENT - 2, 10)`. Maximized at 220 columns that is a
216-character line, roughly triple a comfortable measure. So reserving the
gutter is not only where the panel lives; it fixes a real readability defect at
large sizes. Worth stating in the changelog as its own improvement.

Introduce one derived value in `update_size()`:

```
self.panel_active = width >= PANEL_MIN_WIDTH and height >= PANEL_MIN_HEIGHT
self.content_width = width - PANEL_WIDTH if self.panel_active else width
```

Route **text layout only** through `content_width`. Call sites:

| Site | Today | Becomes |
|---|---|---|
| `ui.py:2129` | `w - CHAT_INDENT - 2` | `content_w - CHAT_INDENT - 2` |
| `ui.py:2162` | `text[:w - CHAT_INDENT - 1]` | `text[:content_w - CHAT_INDENT - 1]` |
| `ui.py:2178` | `range(0, w)` separator | `range(0, content_w)` |
| `ui.py:2184` | `w - CHAT_INDENT - 1` | `content_w - CHAT_INDENT - 1` |
| `ui.py:2579`, `ui.py:2631` | `_engine.width - CHAT_INDENT - 2` | `_engine.content_width - …` |
| `ui.py:1798` | `self.width - 4` status label | `self.content_width - 4` |

Leave the header alone except for centring: the face at `ui.py:1644` should
centre on `content_width` so the header stays balanced against the panel. The
ripple (`ui.py:1658`) keeps spanning the full width — it is ambient chrome and
reads better full-bleed.

**Draw the panel last**, after `_draw_ambient_chrome_corruption`. Then the panel
region is authoritative and no existing layer needs to learn to avoid it.

### The pager is the risk

`page_lines` is built by the wrappers at `ui.py:2579`/`2631` and paged against
`chat_area_h` at `ui.py:2100`. If the terminal is resized across the activation
threshold while a page is open, the pre-wrapped lines no longer match the
content width. Either rewrap on threshold change or freeze `panel_active` for
the life of an open page. Freezing is simpler and the flicker is worse than the
staleness.

This is what makes operator tests 11 and 12 mandatory re-runs.

---

## What it renders

### Stage 1 — the space that exists today (no new dependencies)

Retrieval today is literal word overlap: `memory_logic.select_relevant` keeps a
memory only when `tokens(memory) & query_tokens` is non-empty, and
`memory_store` dedupes on overlap > 0.55.

Render that as a graph. Memories are points; an edge exists where
`memory_logic.similarity()` clears a threshold; place them with a few hundred
iterations of force-directed layout, cached. On each turn, the memories
`select_relevant()` actually returned pulse, and their edges to the query
brighten.

This is worth shipping on its own merit, not as a placeholder. It makes the
current retrieval's failure mode *visible*: memories that share no vocabulary
with anything sit as isolated points, unreachable, and you can see how many
there are. That is both a diagnostic and the honest argument for stage 2.

### Stage 2 — real embedding space

Swap the point source to embeddings; the renderer does not change. Project to
2D with PCA (two-component power iteration is enough — no new dependency beyond
the numpy already present for the audio path). Recompute the projection only
when the memory set changes, never per frame.

Needs an embedding model — `all-MiniLM-L6-v2` at ~23MB, or
`nomic-embed-text-v1.5` at ~85MB Q4, served by a second llama.cpp instance on
its own port. Measure the RAM cost against the Pi 5 budget before committing.

---

## Pixel encoding

One memory, one pixel. That correspondence is the point of the element, so the
rendering is chosen to protect it.

### Glyph: half-blocks, not braille

`_braille_rows()` at `ui.py:1135` is already generic — *"Pack any virtual pixel
buffer into 2 x 4 Braille cells"* — and packs 8 dots per character cell. But
it emits a bare character (`ui.py:1161`) and colour is applied per
`CanvasCell`, so **all eight dots in a cell share one foreground colour**.

Half-blocks (`▀` U+2580, already present in `_CORRUPT_CHARS`) give 1×2 per cell
with foreground painting the top pixel and background the bottom — two
**independently coloured** pixels.

The store caps at `MAX_MEMORIES = 500` (`memory_store.py:29`). A 44×40 panel is
14,080 braille dots or 3,520 half-block pixels. Even the smaller figure is
seven pixels of room per memory at a completely full store. Density is not
scarce here; colour is, and colour is carrying data. **Use half-blocks.**

### Channels

A pixel honestly holds about five channels. Spend them on data, not decoration:

| Channel | Carries |
|---|---|
| x, y | first two principal components |
| hue | third principal component — a free real dimension |
| brightness / saturation | **reconstruction fidelity** (see below) |
| pulse | retrieved on this turn |

**Reconstruction fidelity is the important one.** Every point has a residual —
how much of its variance the 2D projection discarded. Map that to brightness
and points the projection is misrepresenting render dim and washed out. Bright
points are placed truthfully; faded ones are the panel saying *do not trust
where I put this*.

That replaces the honesty disclaimer with something better than a label: the
projection's limit becomes visible instead of hidden, and it costs nothing —
the residual falls out of PCA arithmetic already performed. The panel should
still be named a projection somewhere, but it now also *shows* where it is
lying.

### Layout stability — the requirement that makes 1:1 legible

If the projection is recomputed when the memory set changes, every point moves.
Then there is no point you can track between turns; there is a new picture each
turn, and the 1:1 exists mathematically but not perceptually.

So the layout must be anchored:

- Fix principal-component signs deterministically (PCA components are sign-
  ambiguous and will flip between recomputations otherwise).
- Procrustes-align each new projection to the previous frame — rotate and
  reflect to minimise total point movement before drawing.
- Ease points to their new positions over ~0.5 s rather than snapping, so an
  added memory nudges the space instead of reshuffling it.

Without this the element is a mood light. With it, it is something you can
watch over a session.

### Dependency to confirm first

Whether `fg()` emits 24-bit truecolor or a 256-colour palette. Truecolor gives
smooth hue; the 256 palette would quantise it into visible bands, and that
channel should then carry something categorical instead.

---

## Two signals in one field

The panel carries two independent real measurements. They are complementary in
time, which is what makes them compose rather than compete.

| | Memory cloud | Token entropy |
|---|---|---|
| Shows | what was recalled | what was being decided |
| Source | `select_relevant()` | `logprobs` / `top_logprobs` |
| Fidelity | 384 dims → 5 channels, lossy | the actual sampled distribution |
| Needs | embedding model | a request-body flag |
| When | prompt build | during generation |

Hidden states, activations and attention are **not** reachable through
llama.cpp's HTTP API. Entropy is the closest observable to a decision, and
unlike the projection it is not lossy — it is the number the model produced.

### Verified against the running server

`tools/probe_logprobs.py`, Qwen3-4B-Abliterated-Q8_0, temperature 0.8:

- **Logprobs are supported.** The strip has a real data source.
- **Use `top_logprobs: 10`, not 5.** At 5 the observed spread was 0.39–0.87;
  at 10 it was 0.00–0.72. The wider window roughly doubles the resolution and
  costs nothing. No display stretching is needed on a 10-candidate window.
- **Uncertainty is front-loaded.** In a 14-token sentence the two decisive
  tokens scored 0.72 and 0.69 and everything after them fell to 0.00–0.03.
  Once a phrasing is committed the remainder is close to forced. The strip
  will pulse per sentence rather than shimmer continuously — better, and it
  is what the data actually does.
- **Sampling overrules the argmax about a third of the time** (4 of 14), and
  every instance coincided with a high-entropy token. That is a second free
  bit of real signal and deserves its own colour rather than being folded
  into height.
- Distribution is zero-heavy, so a `sqrt` display curve would use the vertical
  range better. That is a curve on a measured value, which is fine, but the
  scale must be stated rather than silently applied.

### Layout

Panel splits horizontally: point cloud in the upper ~30 rows, entropy strip in
the lower ~8. Both use the half-block pixel scheme.

### Sequence

1. **Prompt build.** `select_relevant()` returns its memories. Those points
   take a sustained glow. Real and checkable — you can verify against what the
   assistant says it recalled.
2. **Generation.** Each token appends a column to the entropy strip. Column
   height and brightness are the uncertainty at that step; the top-5
   alternatives stack as dimmer pixels around the sampled one. Scrolls left.
3. **Settle.** Glow and strip decay.

### The honest link between them

The connection is **sequence, not causation**. Do not draw arcs asserting that
a memory produced a token.

There is one real relationship available, and it is worth using because it
looks like exactly what it is:

- **Lexical echo.** As tokens stream, test each against
  `memory_logic.tokens()` for the currently-lit memories. A hit is a true
  observable statement — *this word appears in that memory* — and earns a
  flare on that point plus a brief arc to the current strip position.
- **Entropy collapse on echo.** When uncertainty drops sharply on a token that
  echoes a lit memory, that correlation is worth showing. Still not proof of
  causation, and must never be labelled as such.

Both are free: `tokens()` already exists, and the logprobs are already in the
stream. Neither claims a mechanism that was not measured.

**Naming.** "Neurons" and "electricity" are fine as visual language and wrong
as mechanism — retrieved memories are text, not units, and entropy is not
current. Keep the metaphor in the aesthetic and out of any label the operator
reads as a claim.

---

## Performance

The render thread runs ~30fps. The panel must not touch it:

- Layout and projection are computed off the render thread and cached.
  Recompute on memory-set change or a slow timer, never per frame.
- Per frame the panel does point transform and plotting only.
- Panel failure renders blank and logs to `_last_render_error`. It must never
  be able to take down the UI. Wrap the whole draw in the existing error path.

---

## Guard implications

Reviewed against the QC findings, since this adds modules to a protected tree.

- `ui/ui.py` is already in `DENIED_FILES`, so panel code living there is
  protected. A new `ui/vector_panel.py` would **not** be — only `ui/ui.py` is
  listed by name. Pure rendering, so that is acceptable.
- The embedding client is different. It reaches the network, which is exactly
  finding #2's category: the 14B maintenance profile could re-point its URL
  without adding an import, because the module would already have `requests`.
  Keep it in its own module and add it to the maintenance deny set in the same
  commit that creates it.
- Build `guard doctor` (additive suggestion #1) **before** this branch. It is
  the check that catches a new network module missing from the deny sets, and
  this branch is the first thing that would exercise it.

---

## Operator tests this adds

- **35.** Maximize the terminal. Panel appears; chat rewraps to a readable
  measure rather than full width.
- **36.** Restore the window down. Panel disappears and the layout is identical
  to today's — no residue in the gutter.
- **37.** Resize slowly across the threshold repeatedly. No tearing, no stale
  columns, no crash.
- **38.** Open a long reply, then resize across the threshold mid-page.
  Confirm the pager stays coherent.
- **39.** With the panel active, confirm points pulse on a turn that retrieves
  memories, and stay still on one that retrieves none (a greeting —
  `select_relevant` returns `[]` for content-free turns).
- **40.** Run at 150×32 exactly, the activation boundary. Confirm both the
  panel and the chat measure are still legible and nothing is clipped.

---

## Sequence

1. Beta 5.1 ships first. This branch does not open until the tree is clean.
2. `guard doctor`.
3. Layout change alone — reserve the gutter, rewrap chat, draw an empty bordered
   panel. Re-run operator tests 11, 12, 35–38. This is the risky part and it is
   worth landing by itself.
4. Stage 1 renderer against the word-overlap graph.
5. Embedding model evaluation on the Pi, then stage 2.
