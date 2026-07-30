"""
Renders the retrieval field: a memory cloud and a token-entropy strip.

Two independent real measurements share one panel. Neither is decorative and
neither claims a mechanism that was not measured:

- The cloud is memories projected to 2D. Position is the first two principal
  components, hue is the third, and BRIGHTNESS IS RECONSTRUCTION FIDELITY --
  a point the projection is misrepresenting renders dim. The panel shows where
  it is lying rather than hiding it behind a disclaimer.
- The strip is per-token entropy from the sampler's own distribution. Unlike
  the projection this is not lossy; it is the number the model produced.

A lit point and a strip column are related by SEQUENCE, not causation. Nothing
in llama.cpp's HTTP API can attribute a token to a memory, so no arc drawn here
may assert that it does. The one real relationship available is lexical echo --
"this word appears in that memory" -- which is an observation, not a mechanism.

This module is pure rendering. It never reads files, reaches the network, or
imports project state, so it can be previewed standalone:

    python -m ui.vector_panel
"""

import colorsys
import math
import random


HALF_BLOCK = "▀"
RESET = "\x1b[0m"

# A point stops being "recently retrieved" after this many decay steps.
GLOW_STEPS = 40
ECHO_STEPS = 12


def _fg(rgb):
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m"


def _bg(rgb):
    r, g, b = rgb
    return f"\x1b[48;2;{r};{g};{b}m"


def _hsv(hue, sat, val):
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, max(0.0, min(1.0, sat)),
                                  max(0.0, min(1.0, val)))
    return int(r * 255), int(g * 255), int(b * 255)


# ============================================================
# PROJECTION
# ============================================================

def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(v):
    return math.sqrt(_dot(v, v)) or 1.0


def _unit(v):
    n = _norm(v)
    return [x / n for x in v]


def _power_iterate(rows, exclude, steps=24):
    """Top principal direction of `rows`, orthogonal to everything in `exclude`."""
    if not rows:
        return []

    dim = len(rows[0])
    vector = [random.gauss(0.0, 1.0) for _ in range(dim)]

    for _ in range(steps):
        accumulated = [0.0] * dim

        for row in rows:
            scale = _dot(row, vector)
            for i, value in enumerate(row):
                accumulated[i] += scale * value

        for previous in exclude:
            scale = _dot(accumulated, previous)
            for i in range(dim):
                accumulated[i] -= scale * previous[i]

        if not any(accumulated):
            return _unit([random.gauss(0.0, 1.0) for _ in range(dim)])

        vector = _unit(accumulated)

    return vector


def project(vectors, previous=None):
    """
    Project high-dimensional vectors to (x, y, hue, fidelity) in 0..1.

    `previous` is the last projection's components. Passing it keeps the
    layout anchored: principal components are sign-ambiguous and will flip
    between recomputations, which would teleport every point and destroy the
    one-memory-one-pixel correspondence the panel exists to show.
    """
    if not vectors:
        return [], []

    dim = len(vectors[0])
    centre = [
        sum(v[i] for v in vectors) / len(vectors)
        for i in range(dim)
    ]
    centred = [[v[i] - centre[i] for i in range(dim)] for v in vectors]

    components = []
    for _ in range(3):
        components.append(_power_iterate(centred, components))

    # Anchor against the previous frame. Flipping a component's sign is a
    # free choice mathematically and a catastrophe visually.
    if previous:
        for index, component in enumerate(components):
            if index < len(previous) and _dot(component, previous[index]) < 0:
                components[index] = [-x for x in component]

    coords = []
    for row in centred:
        a, b, c = (_dot(row, comp) for comp in components)

        # How much of this point survives the flattening. Points the
        # projection misrepresents are drawn dim.
        kept = math.sqrt(a * a + b * b)
        total = _norm(row)
        fidelity = max(0.0, min(1.0, kept / total)) if total else 0.0

        coords.append([a, b, c, fidelity])

    for axis in range(3):
        values = [c[axis] for c in coords]
        low, high = min(values), max(values)
        span = (high - low) or 1.0
        for c in coords:
            c[axis] = (c[axis] - low) / span

    return coords, components


# ============================================================
# FIELD
# ============================================================

class Field:
    """Holds panel state. Fed by the caller; never reads anything itself."""

    def __init__(self, glow_steps=GLOW_STEPS, echo_steps=ECHO_STEPS):
        # Counted in decay() calls, which the caller makes once per drawn
        # frame -- so the lifetime in seconds depends on its frame rate, and
        # the caller is the only one that knows it.
        self.glow_steps = max(1, int(glow_steps))
        self.echo_steps = max(1, int(echo_steps))
        self.points = []          # [{x, y, hue, fidelity, glow, echo}]
        self._components = None
        self._projection_centre = None
        self._projection_bounds = None
        # Hazard-only, lossy panel overlay. These vectors never enter the
        # model prompt or memory store.
        self.trajectory = []      # [{x, y, hue, fidelity, step}]
        self.entropy = []         # recent per-token entropy, 0..1
        self.echo_column = None
        # The two languages, when the caller supplies them. machinespirit is
        # concept-at-token: one column per token, one row per anchor that
        # scored, brightness is that anchor's support. machinesoul is the
        # preservation field itself -- payload bytes as RGBA, in written
        # order, which is what a capsule literally is.
        self.spirit = []          # [[(anchor_index, support), ...], ...]
        self.spirit_labels = []   # anchor text, indexed by anchor_index
        self.soul = b""           # payload bytes, or empty

    def set_memories(self, vectors):
        """Re-project. Existing glow survives so a new memory nudges the field."""
        coords, self._components = project(vectors, self._components)
        if vectors and self._components:
            dim = len(vectors[0])
            self._projection_centre = [
                sum(row[i] for row in vectors) / len(vectors)
                for i in range(dim)
            ]
            raw = [
                [
                    _dot(
                        [value - centre for value, centre in zip(row, self._projection_centre)],
                        component,
                    )
                    for component in self._components
                ]
                for row in vectors
            ]
            self._projection_bounds = [
                (min(row[axis] for row in raw), max(row[axis] for row in raw))
                for axis in range(3)
            ]
        else:
            self._projection_centre = None
            self._projection_bounds = None
            self.trajectory = []
        glow = [p["glow"] for p in self.points]
        echo = [p["echo"] for p in self.points]

        self.points = []
        for index, (x, y, hue, fidelity) in enumerate(coords):
            self.points.append({
                "x": x,
                "y": y,
                "hue": hue,
                "fidelity": fidelity,
                "glow": glow[index] if index < len(glow) else 0,
                "echo": echo[index] if index < len(echo) else 0,
            })

    def set_trajectory(self, vectors):
        """Project a token path into the existing memory coordinate frame.

        Re-fitting the axes for every sentence would make a visually pleasant
        path that cannot be compared to the retrieval cloud. A missing or
        mismatched frame therefore refuses the overlay.
        """
        self.trajectory = []
        if not vectors or not self._components or not self._projection_centre:
            return False

        dimension = len(self._projection_centre)
        if any(len(row) != dimension for row in vectors):
            return False

        previous = None
        total = max(1, len(vectors) - 1)
        for index, vector in enumerate(vectors):
            centred = [
                value - centre
                for value, centre in zip(vector, self._projection_centre)
            ]
            raw = [_dot(centred, component) for component in self._components]
            coords = []
            for axis, value in enumerate(raw):
                low, high = self._projection_bounds[axis]
                span = (high - low) or 1.0
                coords.append(max(0.0, min(1.0, (value - low) / span)))

            kept = math.sqrt(raw[0] * raw[0] + raw[1] * raw[1])
            fidelity = (
                max(0.0, min(1.0, kept / _norm(centred)))
                if any(centred) else 0.0
            )
            step = 0.0
            if previous is not None:
                step = max(
                    0.0,
                    min(1.0, 1.0 - _dot(_unit(vector), _unit(previous))),
                )

            self.trajectory.append({
                "x": coords[0], "y": coords[1],
                # Hue is an ordered, braille-like sequence code only. It is
                # not a semantic coordinate or a physical property.
                "hue": 0.03 + 0.80 * (index / total),
                "fidelity": fidelity,
                "step": step,
            })
            previous = vector
        return True

    def clear_trajectory(self):
        self.trajectory = []

    # --------------------------------------------------------
    # THE TWO LANGUAGES
    # --------------------------------------------------------

    def set_spirit(self, readings, labels):
        """Take machinespirit's own readout: which anchors scored, per token.

        `readings` is one list per token of (anchor_index, support) pairs --
        exactly what profile() returns, not a re-derivation of it. The panel
        must not compute its own answer here: if it did, it could disagree
        with what `trace` prints for the same text, and a panel that
        disagrees with the instrument it claims to show is worse than none.
        """
        self.spirit = [list(row or []) for row in (readings or [])]
        self.spirit_labels = list(labels or [])

    def clear_spirit(self):
        self.spirit = []

    def set_soul(self, payload):
        """Take the preservation field's own bytes, in written order.

        Not a visualisation of the payload -- the payload. machinesoul maps
        four-coordinate integer vectors straight onto RGBA, so laying the
        same bytes out four at a time reproduces the field a capsule holds
        rather than illustrating it.
        """
        self.soul = bytes(payload or b"")

    def clear_soul(self):
        self.soul = b""

    def retrieve(self, indices):
        """Light the memories `select_relevant()` actually returned."""
        for index in indices:
            if 0 <= index < len(self.points):
                self.points[index]["glow"] = self.glow_steps

    def push_token(self, probabilities, echoed=()):
        """
        Append one generated token.

        `probabilities` is the top-N candidate distribution. `echoed` are the
        indices of lit memories whose text contains this token -- an
        observation about vocabulary, not a claim about causation.
        """
        total = sum(probabilities) or 1.0
        normalised = [p / total for p in probabilities]
        raw = -sum(p * math.log(p) for p in normalised if p > 0)
        ceiling = math.log(len(normalised)) if len(normalised) > 1 else 1.0

        self.entropy.append(min(1.0, raw / ceiling))
        self.echo_column = len(self.entropy) - 1

        for index in echoed:
            if 0 <= index < len(self.points):
                self.points[index]["echo"] = self.echo_steps

    def decay(self):
        for point in self.points:
            point["glow"] = max(0, point["glow"] - 1)
            point["echo"] = max(0, point["echo"] - 1)

    # --------------------------------------------------------
    # RENDER
    # --------------------------------------------------------

    def render_cells(self, width, height, strip_rows=8):
        """
        The panel as `height` rows of (char, style) pairs, `width` wide.

        The terminal UI composites into a cell grid of its own and cannot
        accept pre-joined ANSI lines, while the standalone preview wants
        exactly those. Both come from here so the two cannot drift apart.

        When the caller has supplied the two languages, the panel shows
        those: machinespirit above, machinesoul below. Otherwise it falls
        back to the retrieval cloud and entropy strip, so an ordinary
        session -- which has neither a trajectory nor a capsule in hand --
        is unchanged.
        """
        upper_rows = max(1, height - strip_rows - 1)

        if self.spirit or self.soul:
            rows = self._render_spirit(width, upper_rows)
            rows.append(self._divider(width))
            rows.extend(self._render_soul(width, strip_rows))
            return rows[:height]

        rows = self._render_cloud(width, upper_rows)
        rows.append(self._divider(width))
        rows.extend(self._render_strip(width, strip_rows))

        return rows[:height]

    @staticmethod
    def _divider(width):
        return [("─", _fg((70, 30, 40)))] * width

    def _render_spirit(self, width, rows):
        """Concept at token: columns are tokens, rows are anchors that scored.

        Support drives brightness. The vertical position of an anchor is
        stable for the whole readout, so watching one row light up across
        columns is watching one concept persist through a sentence.
        """
        pixels = [[None] * width for _ in range(rows * 2)]
        if not self.spirit:
            return self._pack(pixels, width, rows)

        visible = self.spirit[-width:]
        ranked = sorted({index for row in visible for index, _ in row})
        if not ranked:
            return self._pack(pixels, width, rows)

        # Anchors keep a fixed lane for the whole readout. Re-sorting per
        # token would make every column a different chart.
        lane = {anchor: slot for slot, anchor in enumerate(ranked)}
        height = rows * 2

        for column, row in enumerate(visible):
            if column >= width:
                break
            for anchor, support in row:
                slot = lane[anchor]
                if len(ranked) > 1:
                    y = int(slot * (height - 1) / (len(ranked) - 1))
                else:
                    y = height // 2
                if not 0 <= y < height:
                    continue

                strength = max(0.0, min(1.0, float(support)))
                # Hue identifies the anchor, brightness is its support, so
                # colour never implies a score it did not measure.
                pixels[y][column] = _hsv(
                    (0.06 + 0.68 * (slot / max(1, len(ranked) - 1))) % 1.0,
                    0.55 + 0.40 * strength,
                    0.22 + 0.78 * strength,
                )

        return self._pack(pixels, width, rows)

    def _render_soul(self, width, rows):
        """The preservation field: payload bytes as RGBA, in written order."""
        pixels = [[None] * width for _ in range(rows * 2)]
        if not self.soul:
            return self._pack(pixels, width, rows)

        capacity = width * rows * 2
        for index in range(capacity):
            offset = index * 4
            if offset + 3 >= len(self.soul):
                break
            r, g, b, a = self.soul[offset:offset + 4]
            row, column = divmod(index, width)
            if row >= rows * 2:
                break
            # Alpha is a preserved coordinate like any other, so it dims the
            # cell rather than being discarded -- a fully transparent vector
            # is still data and must remain visible as one.
            scale = 0.35 + 0.65 * (a / 255.0)
            pixels[row][column] = (
                int(r * scale), int(g * scale), int(b * scale)
            )

        return self._pack(pixels, width, rows)

    def render(self, width, height, strip_rows=8):
        """Return `height` ANSI strings, each `width` cells wide."""
        lines = []

        for row in self.render_cells(width, height, strip_rows):
            out = []
            last = None

            for char, style in row:
                if style != last:
                    out.append(style)
                    last = style

                out.append(char)

            out.append(RESET)
            lines.append("".join(out))

        return lines

    def _render_cloud(self, width, rows):
        # Two vertical pixels per cell via the half block.
        pixels = [[None] * width for _ in range(rows * 2)]

        for point in self.points:
            col = int(point["x"] * (width - 1))
            row = int((1.0 - point["y"]) * (rows * 2 - 1))

            if not (0 <= col < width and 0 <= row < rows * 2):
                continue

            # Brightness carries projection fidelity, so a badly-placed point
            # announces itself. Retrieval and echo add on top.
            value = 0.18 + 0.55 * point["fidelity"]
            sat = 0.35 + 0.45 * point["fidelity"]

            if point["glow"]:
                lift = point["glow"] / self.glow_steps
                value = min(1.0, value + 0.45 * lift)
                sat = min(1.0, sat + 0.35 * lift)

            if point["echo"]:
                value = min(
                    1.0,
                    value + 0.5 * (point["echo"] / self.echo_steps),
                )

            pixels[row][col] = _hsv(point["hue"], sat, value)

        # The HazardSable path is rendered last so the ordered colour cycle
        # remains legible over retrieved memories. Brightness is projection
        # fidelity; a large adjacent-vector change gets a second pixel. This
        # is a lossy visual aid, not extra model context or a physical path.
        for marker in self.trajectory:
            col = int(marker["x"] * (width - 1))
            row = int((1.0 - marker["y"]) * (rows * 2 - 1))
            if not (0 <= col < width and 0 <= row < rows * 2):
                continue

            colour = _hsv(
                marker["hue"], 0.95, 0.35 + 0.65 * marker["fidelity"]
            )
            pixels[row][col] = colour
            if marker["step"] >= 0.08 and row + 1 < rows * 2:
                pixels[row + 1][col] = colour

        return self._pack(pixels, width, rows)

    def _render_strip(self, width, rows):
        pixels = [[None] * width for _ in range(rows * 2)]
        visible = self.entropy[-width:]
        offset = len(self.entropy) - len(visible)

        for col, level in enumerate(visible):
            filled = int(level * (rows * 2 - 1)) + 1

            for step in range(filled):
                row = rows * 2 - 1 - step
                intensity = step / max(1, rows * 2 - 1)

                # Red when it committed, toward violet when the mass split.
                hue = 0.02 + 0.72 * level
                pixels[row][col] = _hsv(
                    hue,
                    0.85,
                    0.30 + 0.65 * (level * 0.6 + intensity * 0.4),
                )

            if self.echo_column is not None and offset + col == self.echo_column:
                pixels[rows * 2 - 1][col] = (255, 240, 200)

        return self._pack(pixels, width, rows)

    @staticmethod
    def _pack(pixels, width, rows):
        """Two pixel rows per text row: foreground is top, background bottom."""
        packed = []

        for row in range(rows):
            top_row = pixels[row * 2]
            bottom_row = pixels[row * 2 + 1]
            out = []

            for col in range(width):
                top, bottom = top_row[col], bottom_row[col]

                if top is None and bottom is None:
                    out.append((" ", RESET))
                    continue

                out.append((
                    HALF_BLOCK,
                    _fg(top or (0, 0, 0)) + _bg(bottom or (0, 0, 0)),
                ))

            packed.append(out)

        return packed


# ============================================================
# STANDALONE PREVIEW
# ============================================================

def _synthetic(count=140, dim=48, clusters=5):
    """Clustered fake embeddings, so the projection has structure to find."""
    centres = [
        [random.gauss(0, 1) for _ in range(dim)]
        for _ in range(clusters)
    ]
    return [
        [
            value + random.gauss(0, 0.35)
            for value in centres[index % clusters]
        ]
        for index in range(count)
    ]


def _demo(frames=240, width=44, height=40):
    import sys
    import time

    field = Field()
    field.set_memories(_synthetic())

    sys.stdout.write("\x1b[?25l")
    try:
        for frame in range(frames):
            if frame % 60 == 0:
                field.retrieve(random.sample(range(len(field.points)), 6))

            if frame % 2 == 0:
                # Bursty confidence: mostly settled, occasional fork.
                if random.random() < 0.22:
                    probs = [random.random() for _ in range(5)]
                else:
                    probs = [0.9] + [random.random() * 0.06 for _ in range(4)]

                lit = [
                    i for i, p in enumerate(field.points) if p["glow"]
                ]
                echoed = (
                    random.sample(lit, 1)
                    if lit and random.random() < 0.25
                    else ()
                )
                field.push_token(probs, echoed)

            field.decay()

            sys.stdout.write("\x1b[H")
            sys.stdout.write("\n".join(field.render(width, height)))
            sys.stdout.flush()
            time.sleep(1 / 30)
    finally:
        sys.stdout.write("\x1b[?25h" + RESET + "\n")


if __name__ == "__main__":
    import os

    os.system("")  # enable ANSI on Windows consoles
    print("\x1b[2J", end="")
    _demo()
