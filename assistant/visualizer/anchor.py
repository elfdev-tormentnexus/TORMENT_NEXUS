"""
The slow layer every scene is read against.

Without one, a visualizer has no scale. Every element moved at audio speed,
so a frantic passage and a lazy one filled the frame equally and neither
read as fast: there was nothing standing still to be fast *relative to*.
These anchors move on wall-clock time alone -- never on the music -- which
is the entire point. A reference that speeds up with the thing it measures
is not a reference.

They are deliberately dim, large in scale, and slow enough to look almost
static over a second or two. The eye should find them without being drawn
to them.

RASTER-AWARE LINES
------------------
`lines()` is the shared version of a mistake worth not repeating. A line
drawn thinner than one pixel of the output raster is not a fine line, it is
an absent one: the sampler lands on its peak only by luck and the result is
speckle. acid_lattice.py drew its whole mesh that way and looked broken
next to the other scenes; grid.py:192 makes the same argument for its
ground lines. Measure how fast the coordinate moves per pixel, and never
draw narrower than that.
"""

import math


# Reaching e^-1 at about 1.15 pixels: certain to be sampled, still thinner
# than one braille cell so the anchor never becomes a band. Below about
# 0.38 the guarantee is lost; far above it the lines close into a wall.
_MIN_WIDTH_PIXELS = 1.15

# The dither ramp in every scene runs from 0.17 to roughly 0.81, so
# brightness here is really coverage. Around 0.30 the anchor reads as a
# continuous dim line rather than a scatter of dots.
DEFAULT_STRENGTH = 0.30


def lines(np, coordinate, base_width=0.075):
    """Soft lattice lines at every integer of `coordinate`, raster-aware."""
    gradient_y, gradient_x = np.gradient(coordinate)
    step = np.sqrt(gradient_x * gradient_x + gradient_y * gradient_y)
    width = np.maximum(base_width, step * _MIN_WIDTH_PIXELS)

    return np.exp(-((np.sin(coordinate * math.pi) / width) ** 2))


def strata(np, xx, yy, slow, scale=2.15, drift=0.085):
    """
    Slow horizontal bands, gently warped so they are not a ruled grid.

    Suits scenes built on a ground plane or a horizon: the bands read as
    depth, and something in the frame is finally holding still.
    """
    field = (
        yy * scale
        + np.sin(xx * 0.85 - slow * 0.045) * 0.34
        + np.sin(xx * 1.9 + slow * 0.028) * 0.11
        - slow * drift
    )

    return lines(np, field)


def rings(np, xx, yy, slow, scale=1.85, drift=0.07, aspect=0.62):
    """
    Slow concentric rings expanding from the centre.

    Suits anything built around a vanishing point -- a tunnel, a starfield,
    a reactor -- where horizontal bands would fight the geometry. `aspect`
    compensates for terminal cells being taller than they are wide.
    """
    radius = np.sqrt((xx * aspect) ** 2 + yy ** 2)

    return lines(np, radius * scale - slow * drift)


def diagonal(np, xx, yy, slow, scale=1.60, drift=0.06, tilt=0.55):
    """
    A slow diagonal drift, for scenes whose own motion is axis-aligned.

    Crossing the scene's grain is what keeps the anchor legible as a
    separate layer instead of merging into whatever it sits behind.
    """
    field = (xx * tilt + yy) * scale - slow * drift

    return lines(np, field)


def apply(np, intensity, field, strength=DEFAULT_STRENGTH, mid=0.0):
    """
    Lay an anchor under whatever the scene draws on top.

    `mid` lifts it slightly with the music so silence is not bare, while
    the motion stays on the clock -- brightness may respond to audio, and
    position may not.
    """
    intensity[:] = np.maximum(intensity, field * (strength + mid * 0.075))
