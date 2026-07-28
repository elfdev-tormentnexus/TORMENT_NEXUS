import os
import sys
import time
import random
import math
import shutil
import textwrap
import threading

from core import dev_auth

if os.name == "nt":
    import msvcrt
else:
    import select
    import termios
    import tty


# ============================================================
# ANSI & TERMINAL SETUP
# ============================================================

def enable_ansi():
    os.system("")

_real_stdout = sys.stdout
_terminal_settings = None
_UI_ERROR_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "ui_errors.log",
)
_VISUALIZER_OUTPUT_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "visualizer_output.log",
)


class _VisualizerOutputGuard:
    """
    Keep library diagnostics from drawing over the full-screen visualizer.

    The renderer deliberately writes through `_real_stdout`; ordinary Python
    stdout/stderr are redirected to a local log only while music mode owns the
    terminal. They are restored as soon as the mode closes.
    """

    encoding = "utf-8"
    errors = "replace"

    def __init__(self):
        self._lock = threading.Lock()
        self._handle = None
        self._previous_stdout = None
        self._previous_stderr = None
        self._started = False

    @property
    def active(self):
        return self._started

    def start(self):
        if self.active:
            return

        try:
            os.makedirs(os.path.dirname(_VISUALIZER_OUTPUT_LOG), exist_ok=True)
            self._handle = open(
                _VISUALIZER_OUTPUT_LOG,
                "a",
                encoding="utf-8",
                buffering=1,
            )
        except OSError:
            self._handle = None

        self._previous_stdout = sys.stdout
        self._previous_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self
        self._started = True

    def stop(self):
        if not self.active:
            return

        if sys.stdout is self:
            sys.stdout = self._previous_stdout
        if sys.stderr is self:
            sys.stderr = self._previous_stderr

        self._previous_stdout = None
        self._previous_stderr = None
        self._started = False
        handle, self._handle = self._handle, None
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass

    def write(self, text):
        text = str(text or "")
        if not text:
            return 0

        with self._lock:
            if self._handle is not None:
                try:
                    self._handle.write(text)
                except OSError:
                    pass
        return len(text)

    def flush(self):
        with self._lock:
            if self._handle is not None:
                try:
                    self._handle.flush()
                except OSError:
                    pass

    def isatty(self):
        return False


_visualizer_output_guard = _VisualizerOutputGuard()

def write_raw(s):
    _real_stdout.write(s)
    _real_stdout.flush()

def clear_screen():
    write_raw("\x1b[2J\x1b[H")

def hide_cursor():
    write_raw("\x1b[?25l")

def show_cursor():
    write_raw("\x1b[?25h")


def enable_character_input():
    """
    Put POSIX terminals into cbreak mode for the life of the UI.

    select() cannot see individual keystrokes while the terminal is
    still in its default canonical (line-buffered) mode. cbreak keeps
    Ctrl+C signals working while making each key immediately readable.
    """
    global _terminal_settings

    if os.name == "nt" or _terminal_settings is not None or not sys.stdin.isatty():
        return

    fd = sys.stdin.fileno()
    _terminal_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)


def restore_character_input():
    global _terminal_settings

    if os.name == "nt" or _terminal_settings is None:
        return

    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _terminal_settings)
    finally:
        _terminal_settings = None


# ============================================================
# RAW KEYBOARD DRIVER
# ============================================================

def get_char():
    """
    Captures keypresses without blocking screen redraws.

    Returns a single character, None if nothing is waiting, "" for an
    extended key this doesn't otherwise handle, or the sentinel strings
    "UP"/"DOWN"/"LEFT"/"RIGHT"/"ESC". The explicit Escape sentinel lets voice mode always
    offer a silent manual exit without mistaking an arrow sequence for it.
    """
    if os.name == "nt":
        if not msvcrt.kbhit():
            return None
        ch = msvcrt.getwch()
        if ch == "\x1b":
            return "ESC"
        if ch in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            if code == "H":
                return "UP"
            if code == "P":
                return "DOWN"
            if code == "K":
                return "LEFT"
            if code == "M":
                return "RIGHT"
            return ""
        return ch
    else:
        # The UI enables cbreak mode once at startup, so select() sees
        # individual keys here instead of waiting for a full line.
        if not select.select([sys.stdin], [], [], 0)[0]:
            return None

        ch = sys.stdin.read(1)

        if ch == "\x1b":
            # Might be the start of an arrow-key escape sequence
            # (ESC [ A/B/C/D). Give the rest a brief moment to arrive.
            if select.select([sys.stdin], [], [], 0.02)[0]:
                ch2 = sys.stdin.read(1)

                if ch2 == "[" and select.select([sys.stdin], [], [], 0.02)[0]:
                    ch3 = sys.stdin.read(1)

                    if ch3 == "A":
                        return "UP"
                    if ch3 == "B":
                        return "DOWN"
                    if ch3 == "C":
                        return "RIGHT"
                    if ch3 == "D":
                        return "LEFT"

            return "ESC"

        return ch


# ============================================================
# COLOR PALETTE
# ============================================================

RESET = "\x1b[0m"
BOLD  = "\x1b[1m"

RED          = "\x1b[38;5;196m"
GREY         = "\x1b[38;5;245m"
GRAY         = GREY  # alias
YELLOW       = "\x1b[38;5;226m"
GREEN        = "\x1b[38;5;46m"
CYAN         = "\x1b[38;5;51m"
BLUE         = "\x1b[38;5;39m"
MAGENTA      = "\x1b[38;5;201m"
WHITE        = "\x1b[38;5;255m"
ORANGE       = "\x1b[38;5;208m"
C_RED_BRIGHT = 196
C_RED_MID    = 160
C_RED_DARK   = 124
C_RED_DEEP   = 52
C_RED_BLOOD  = 88

C_NEON_VIOLET = 171

# memory_store.py and commands/command_handlers.py reference these.
VIOLET = "\x1b[38;5;141m"
PURPLE = "\x1b[38;5;129m"
BLACK  = "\x1b[38;5;16m"
GREY_DIM = "\x1b[38;5;244m"

def fg(code):
    return f"\x1b[38;5;{code}m"


# ============================================================
# ARASAKA / CP2077 CONDENSED ANGULAR FONT (5 wide x 7 tall)
#
# Design rules, all deliberate:
#   - Tall and narrow. Condensed proportion is the single biggest
#     signal; a near-square font reads as generic pixel art.
#   - Zero curves. Every counter is rectilinear, every terminal flat.
#   - Uniform 1px stroke, so it stays crisp at terminal resolution.
#   - Enclosed letters are hard rectangles, not rounded capsules.
# ============================================================

_FONT = {
    "A": [" ███ ", "█   █", "█   █", "█████", "█   █", "█   █", "█   █"],
    "B": ["████ ", "█   █", "█   █", "████ ", "█   █", "█   █", "████ "],
    "C": ["█████", "█    ", "█    ", "█    ", "█    ", "█    ", "█████"],
    "D": ["████ ", "█   █", "█   █", "█   █", "█   █", "█   █", "████ "],
    "E": ["█████", "█    ", "█    ", "████ ", "█    ", "█    ", "█████"],
    "F": ["█████", "█    ", "█    ", "████ ", "█    ", "█    ", "█    "],
    "G": ["█████", "█    ", "█    ", "█  ██", "█   █", "█   █", "█████"],
    "H": ["█   █", "█   █", "█   █", "█████", "█   █", "█   █", "█   █"],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "  █  ", "  █  ", "█████"],
    "J": ["█████", "   █ ", "   █ ", "   █ ", "   █ ", "█  █ ", "████ "],
    "K": ["█   █", "█  █ ", "█ █  ", "██   ", "█ █  ", "█  █ ", "█   █"],
    "L": ["█    ", "█    ", "█    ", "█    ", "█    ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █", "█   █", "█   █"],
    "N": ["█   █", "██  █", "██  █", "█ █ █", "█  ██", "█  ██", "█   █"],
    "O": ["█████", "█   █", "█   █", "█   █", "█   █", "█   █", "█████"],
    "P": ["████ ", "█   █", "█   █", "████ ", "█    ", "█    ", "█    "],
    "Q": ["█████", "█   █", "█   █", "█   █", "█ █ █", "█  ██", "█████"],
    "R": ["████ ", "█   █", "█   █", "████ ", "█ █  ", "█  █ ", "█   █"],
    "S": ["█████", "█    ", "█    ", "█████", "    █", "    █", "█████"],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  ", "  █  ", "  █  "],
    "U": ["█   █", "█   █", "█   █", "█   █", "█   █", "█   █", "█████"],
    "V": ["█   █", "█   █", "█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "W": ["█   █", "█   █", "█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "X": ["█   █", "█   █", " █ █ ", "  █  ", " █ █ ", "█   █", "█   █"],
    "Y": ["█   █", "█   █", " █ █ ", "  █  ", "  █  ", "  █  ", "  █  "],
    "Z": ["█████", "    █", "   █ ", "  █  ", " █   ", "█    ", "█████"],
    "0": ["█████", "█   █", "█  ██", "█ █ █", "██  █", "█   █", "█████"],
    "1": ["  ██ ", " █ █ ", "   █ ", "   █ ", "   █ ", "   █ ", "█████"],
    "2": ["█████", "    █", "    █", "█████", "█    ", "█    ", "█████"],
    "3": ["█████", "    █", "    █", " ████", "    █", "    █", "█████"],
    "4": ["█   █", "█   █", "█   █", "█████", "    █", "    █", "    █"],
    "5": ["█████", "█    ", "█    ", "█████", "    █", "    █", "█████"],
    "6": ["█████", "█    ", "█    ", "█████", "█   █", "█   █", "█████"],
    "7": ["█████", "    █", "   █ ", "  █  ", " █   ", " █   ", " █   "],
    "8": ["█████", "█   █", "█   █", "█████", "█   █", "█   █", "█████"],
    "9": ["█████", "█   █", "█   █", "█████", "    █", "    █", "█████"],
    "-": ["     ", "     ", "     ", "█████", "     ", "     ", "     "],
    "_": ["     ", "     ", "     ", "     ", "     ", "     ", "█████"],
    ".": ["     ", "     ", "     ", "     ", "     ", " ██  ", " ██  "],
    "+": ["     ", "  █  ", "  █  ", "█████", "  █  ", "  █  ", "     "],
    " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
}

_FONT_W = 5
_FONT_H = 7

_PIXEL = "\u2588"

# Blank rows above the letters inside the header band.
TOP_PAD = 1

# --- per-glyph corruption, fired by the passing wave ---
# Each glyph corrupts as the crest crosses ITS midpoint, so the damage
# cascades letter to letter instead of washing over the whole word.
CORRUPT_WINDOW = 3.5     # cells either side of the midpoint that trigger it
CORRUPT_DROP = 0.30      # share of the glyph's pixels that blank out at peak
CORRUPT_NOISE = 0.45     # share that degrade into broken block glyphs
CORRUPT_JOLT = 0.65      # influence above which the whole glyph kicks sideways

_CORRUPT_CHARS = ["\u2593", "\u2592", "\u2591", "\u2580", "\u2584"]

# Pixel-only material used by the generating-state face collapse.
# No letters, crosses, slashes, box-drawing joints, or terminal-hacker glyphs.
_MAX_CORRUPT_BLOCKS = ["░", "▒", "▓", "█", "▀", "▄", "▌", "▐"]

# Developer-mode indicator: a smooth, rapid colour cycle confined to
# the purple/violet spectrum -- no rainbow, and (after the random
# spark-flash version read as a strobe) no sudden brightness jumps
# either. Kept in the same R:95-175 / B:95-175 register as the red
# theme (C_RED_DEEP..C_RED_DARK below are R:95-175, G:0, B:0) instead
# of reaching up to full-brightness blue (255), so it reads as a dark
# wine/maroon purple that sits alongside the red rather than a bright
# lavender that fights it. Ramps up and back down so the wrap-around
# step is as small as every other step.
_DEV_ARC_COLOURS = [53, 89, 90, 125, 126, 127, 126, 125, 90, 89]
_DEV_COLOUR_SPEED = 9.0

# --- slow ripple ---
# Deliberately far slower than the streak churn, so the two motions
# read as separate systems instead of one uniform shimmer.
RIPPLE_SPEED = 7.0   # cells per second the crest travels
RIPPLE_WIDTH = 13    # half-width of the crest, in cells
RIPPLE_LIFT = 0.78   # influence above which a cell lifts one row

# --- chat area ---
CHAT_INDENT = 2          # columns reserved for the left rail
CHAT_FADE_AFTER = 7      # lines newer than this stay at full brightness
_RAIL = "\u258f"          # thin left rail
_RAIL_ACTIVE = "\u2590"   # marker on the newest line
_SEPARATOR = "\u2500"     # rule above the input row

# Dimming ramps, keyed by the colour a line was written in. Older lines
# step down the ramp so the backlog recedes instead of competing with
# whatever just arrived.
# Keyed off the palette constants themselves, NOT hardcoded escape
# strings -- otherwise changing a colour silently disables its fade.
_FADE_RAMPS = {
    GREY:   [245, 242, 240, 238, 236, 234],   # assistant
    RED:    [196, 160, 124, 88, 52, 52],      # user
    GREEN:  [46, 40, 34, 28, 22, 22],         # memory events
    YELLOW: [226, 220, 178, 136, 100, 94],
    VIOLET: [141, 104, 97, 61, 60, 59],
    WHITE:  [255, 250, 245, 240, 236, 234],
}


def _faded(color, level):
    ramp = _FADE_RAMPS.get(color)

    if not ramp:
        return color

    return fg(ramp[min(level, len(ramp) - 1)])


# --- reactive generating state ---
# While the model is producing tokens the wall runs hotter and the
# ripple moves faster, so the header reflects real machine state
# instead of just ticking on a timer.
GENERATING_HEAT_BOOST = 0.30
GENERATING_RIPPLE_MULT = 2.6

# --- vertical sync tear ---
SYNC_TEAR_CHANCE = 0.06
SYNC_ROLL_CHANCE = 0.03

# --- letter jitter (the fast horizontal buzz) ---
# Was effectively 8.5% of frames, i.e. a shift roughly once a second,
# which reads as constant vibration. Raising the heat threshold and
# dropping the chance makes it an occasional glitch instead.
ROW_JITTER_HEAT = 0.55     # heat must exceed this before it can fire
ROW_JITTER_CHANCE = 0.05   # chance per frame once above the threshold
ROW_JITTER_MAX = 1         # max cells a row can shift

# --- per-pixel colour flicker ---
PIXEL_FLICKER_HEAT = 0.55
PIXEL_FLICKER_CHANCE = 0.015
_STREAK_CHARS   = ["─", "━", "╍", "╌", "░", "╶", "╴", "▔", "─", " "]

# --- wearable emoticon / responsive compact header ---
#
# The LCD original draws the face on a circular projected surface. A normal
# terminal character is too coarse to reproduce that faithfully, so the face
# is first drawn into a virtual monochrome pixel buffer and packed into Unicode
# Braille cells (2 x 4 virtual pixels per terminal cell).
#
# This gives us enough resolution for the actual six wearable expressions,
# while keeping the whole mark small enough to remain centred in a narrow
# quarter-screen terminal.
FACE_PIXEL_W = 40
FACE_PIXEL_H = 32
FACE_CELL_W = FACE_PIXEL_W // 2
FACE_CELL_H = FACE_PIXEL_H // 4

# Voice mode gives the face more physical presence without replacing the
# compact normal header. Keeping both dimensions aligned to Braille's 2 x 4
# grid avoids padding artifacts after scaling.
VOICE_FACE_PIXEL_W = 56
VOICE_FACE_PIXEL_H = 44
VOICE_FACE_CELL_W = VOICE_FACE_PIXEL_W // 2
VOICE_FACE_CELL_H = VOICE_FACE_PIXEL_H // 4
VOICE_COMPACT_PIXEL_W = 48
VOICE_COMPACT_PIXEL_H = 36

FACE_RADIUS = 14
FACE_PROJECTION_SCALE = FACE_RADIUS / 50.0

# Header geometry. The face is always the centrepiece; the model label is a
# compact line beneath it rather than a 7-row billboard.
FACE_TOP = 0
TITLE_ROW = FACE_CELL_H + 1
STATUS_ROW = TITLE_ROW + 1
HEADER_MIN_HEIGHT = STATUS_ROW + 1

# The neutral face returns between every alternate expression:
# 0, 1, 0, 2, 0, 3, 0, 4, 0, 5, then repeat.
FACE_EMOTION_SEQUENCE = (0, 1, 0, 2, 0, 3, 0, 4, 0, 5)

# Faster than the wearable's original 35-second interval. Twelve seconds keeps
# the display visibly alive without making the expression changes frantic.
FACE_EMOTION_INTERVAL = 12.0
FACE_FLASH_FRAMES = 6
FACE_GLITCH_CHANCE = 0.34

# Braille dot bit layout:
#   1 4
#   2 5
#   3 6
#   7 8
_BRAILLE_BITS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)


# ============================================================
# CANVAS FRAME ENGINE
# ============================================================

class CanvasCell:
    __slots__ = ("char", "color")
    def __init__(self, char=" ", color=RESET):
        self.char = char
        self.color = color

class LayeredDisplayEngine:
    def __init__(self):
        self.width = 80
        self.height = 24
        self.header_height = HEADER_MIN_HEIGHT
        self.title_text = "TORMENT_NEXUS"
        self.quant_text = "Q4_K_M"

        self.chat_history = []
        self.current_input = ""
        self.input_prompt = ""

        # --- music visualizer mode ---
        # When active the whole viewport becomes the visualiser; the chat
        # log and header are not drawn. Populated lazily so the audio and
        # numpy dependencies are only paid for if the mode is used.
        self.music_mode = False
        self.music_visualizer = None
        self.music_audio = None
        self.music_status = ""
        self.music_palette_index = 0
        self.music_scene_index = 0
        self.music_volume_percent = 100
        self._music_scene_started_at = 0.0
        self._music_palette_started_at = 0.0
        self._music_last_frame = 0.0
        self.input_masked = False

        # -1 means "not currently cycling" -- typing or submitting resets
        # it, so the next Up/Down starts a fresh pass through the list.
        self.cycle_index = -1

        # Live streaming line: grows token by token, committed to
        # chat_history once the reply completes.
        self.live_text = ""
        self.live_color = RESET
        self.streaming = False

        # A completed long response can temporarily own the chat viewport.
        # The underlying history is untouched, so closing the pager returns
        # immediately to the normal bottom-of-conversation view.
        self.page_lines = None
        self.page_index = 0

        # True while tokens are being pulled from the server.
        self.generating = False

        # Developer mode is indicated by the face itself. The prompt remains
        # visually clean; the emoticon cycles rapidly through the purple
        # spectrum instead.
        self.dev_mode = False
        # Voice mode is identified by scale, not a separate colour palette:
        # the familiar header effects continue across the enlarged face.
        self.voice_mode = False
        self.voice_speaking = False

        # --- face ---
        self.face_sequence_index = 0
        self.face_emotion = FACE_EMOTION_SEQUENCE[0]
        self._face_last_switch = time.time()
        self.face_flash = 0

        # Optional externally supplied phase text. Generic values such as
        # "connecting" are translated into the richer telemetry display.
        self.status_text = ""
        self.background_status_text = ""
        self.background_started_at = 0.0
        self.has_content = False

        # Live inference telemetry. These counters are driven entirely by the
        # existing stream API, so main.py does not need new hooks.
        self.generation_started_at = 0.0
        self.last_token_at = 0.0
        self.prompt_tokens = 0
        self.stream_tokens = 0
        self.stream_chars = 0
        self.stream_chunks = 0
        self.activity_summary = ""
        self.activity_summary_until = 0.0

        # Accumulated separately from time_counter so the ripple speed
        # can change without the crest jumping position.
        self.ripple_phase = 0.0

        self.time_counter = 0.0
        self.running = False
        self.lock = threading.Lock()
        self.render_thread = None
        self._last_render_error = ""

    def update_size(self):
        s = shutil.get_terminal_size(fallback=(80, 24))
        self.width = max(s.columns, 40)
        self.height = max(s.lines, 15)

    # ------------------------------------------------------------
    # WEARABLE FACE RASTERIZER
    # ------------------------------------------------------------

    @staticmethod
    def _pixel_buffer():
        return [
            [False for _ in range(FACE_PIXEL_W)]
            for _ in range(FACE_PIXEL_H)
        ]

    @staticmethod
    def _set_pixel(buf, x, y):
        x = int(round(x))
        y = int(round(y))

        if 0 <= x < FACE_PIXEL_W and 0 <= y < FACE_PIXEL_H:
            buf[y][x] = True

    def _line_pixels(self, buf, x0, y0, x1, y1, thickness=1):
        """Integer line drawing used for the projected facial geometry."""
        x0 = int(round(x0))
        y0 = int(round(y0))
        x1 = int(round(x1))
        y1 = int(round(y1))

        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            radius = max(0, thickness - 1)

            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    self._set_pixel(buf, x0 + ox, y0 + oy)

            if x0 == x1 and y0 == y1:
                break

            e2 = 2 * err

            if e2 >= dy:
                err += dy
                x0 += sx

            if e2 <= dx:
                err += dx
                y0 += sy

    def _fill_rect_pixels(self, buf, cx, cy, half_w, half_h):
        for y in range(int(cy - half_h), int(cy + half_h) + 1):
            for x in range(int(cx - half_w), int(cx + half_w) + 1):
                self._set_pixel(buf, x, y)

    def _fill_disc_pixels(self, buf, cx, cy, radius):
        r2 = radius * radius

        for y in range(int(cy - radius), int(cy + radius) + 1):
            for x in range(int(cx - radius), int(cx + radius) + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                    self._set_pixel(buf, x, y)

    @staticmethod
    def _surface(lat, lon):
        """Same spherical surface mapping used by the wearable program."""
        la = math.radians(lat)
        lo = math.radians(lon)

        return (
            math.cos(la) * math.sin(lo),
            math.sin(la),
            math.cos(la) * math.cos(lo),
        )

    @staticmethod
    def _project_surface(point):
        cx = FACE_PIXEL_W // 2
        cy = FACE_PIXEL_H // 2

        return (
            cx + point[0] * FACE_RADIUS,
            cy - point[1] * FACE_RADIUS,
        )

    def _build_face_pixels(self, emotion, reactive_level):
        """
        Recreate build(e) + face(...) from the MicroPython wearable.

        reactive_level is the assistant equivalent of audio level. It stays
        low while idle and rises while the model is generating, giving the
        mouth a restrained version of the wearable's vertical wave motion.
        """
        buf = self._pixel_buffer()
        cx = FACE_PIXEL_W // 2
        cy = FACE_PIXEL_H // 2

        # Circular shell.
        previous = None
        first = None

        for degree in range(0, 361, 4):
            angle = math.radians(degree)
            px = cx + math.cos(angle) * FACE_RADIUS
            py = cy + math.sin(angle) * FACE_RADIUS

            if previous is not None:
                self._line_pixels(
                    buf,
                    previous[0],
                    previous[1],
                    px,
                    py,
                )
            else:
                first = (px, py)

            previous = (px, py)

        if first is not None and previous is not None:
            self._line_pixels(
                buf,
                previous[0],
                previous[1],
                first[0],
                first[1],
            )

        blocks = []
        dots = []
        lines = []
        mouth = []

        # Exact expression definitions translated from build(e).
        if emotion == 0:
            blocks.append((self._surface(20, -24), 7, 11))
            blocks.append((self._surface(20, 24), 7, 11))

            for lon in range(-34, 35, 3):
                depth = 1.0 - (lon / 34.0) ** 2
                mouth.append((
                    self._surface(-6, lon),
                    self._surface(-6 - depth * 26, lon),
                ))

        elif emotion == 1:
            dots.append((self._surface(12, -24), 6))
            dots.append((self._surface(12, 24), 6))

            for lon in range(-30, 31, 3):
                depth = 1.0 - (lon / 30.0) ** 2
                mouth.append((
                    self._surface(-22 + depth * 10, lon),
                    self._surface(-30 + depth * 10, lon),
                ))

        elif emotion == 2:
            blocks.append((self._surface(16, -24), 7, 8))
            blocks.append((self._surface(16, 24), 7, 8))
            lines.append((
                self._surface(36, -36),
                self._surface(25, -12),
            ))
            lines.append((
                self._surface(25, 12),
                self._surface(36, 36),
            ))

            for lon in range(-28, 29, 3):
                depth = 1.0 - (lon / 28.0) ** 2
                mouth.append((
                    self._surface(-20 + depth * 7, lon),
                    self._surface(-26 + depth * 7, lon),
                ))

        elif emotion == 3:
            dots.append((self._surface(20, -24), 9))
            dots.append((self._surface(20, 24), 9))

            for lon in range(-16, 17, 3):
                q = max(0.0, 1.0 - (lon / 16.0) ** 2)
                depth = math.sqrt(q)
                mouth.append((
                    self._surface(-18 + depth * 13, lon),
                    self._surface(-18 - depth * 13, lon),
                ))

        elif emotion == 4:
            lines.append((
                self._surface(27, -33),
                self._surface(13, -17),
            ))
            lines.append((
                self._surface(13, -33),
                self._surface(27, -17),
            ))
            lines.append((
                self._surface(27, 17),
                self._surface(13, 33),
            ))
            lines.append((
                self._surface(13, 17),
                self._surface(27, 33),
            ))

            for lon in range(-26, 27, 3):
                mouth.append((
                    self._surface(-22, lon),
                    self._surface(-26, lon),
                ))

        elif emotion == 5:
            blocks.append((self._surface(20, -24), 7, 11))
            lines.append((
                self._surface(19, 13),
                self._surface(19, 35),
            ))

            for lon in range(-28, 29, 3):
                depth = 1.0 - (lon / 28.0) ** 2
                mouth.append((
                    self._surface(-10 - depth * 5 + lon * 0.2, lon),
                    self._surface(-17 - depth * 9 + lon * 0.2, lon),
                ))

        else:
            # Defensive fallback. Generating no longer selects an emotion;
            # its face comes from _build_corrupted_face_pixels() instead.
            blocks.append((self._surface(20, -24), 7, 11))
            blocks.append((self._surface(20, 24), 7, 11))

            for lon in range(-34, 35, 3):
                depth = 1.0 - (lon / 34.0) ** 2
                mouth.append((
                    self._surface(-6, lon),
                    self._surface(-6 - depth * 26, lon),
                ))

        # Eyes.
        for point, width, height in blocks:
            px, py = self._project_surface(point)
            half_w = max(1, int(round(width * FACE_PROJECTION_SCALE)))
            half_h = max(1, int(round(height * FACE_PROJECTION_SCALE)))
            self._fill_rect_pixels(buf, px, py, half_w, half_h)

        for point, radius in dots:
            px, py = self._project_surface(point)
            scaled_radius = max(
                1,
                int(round(radius * FACE_PROJECTION_SCALE)),
            )
            self._fill_disc_pixels(buf, px, py, scaled_radius)

        # Brows / X eyes / wink.
        for p0, p1 in lines:
            x0, y0 = self._project_surface(p0)
            x1, y1 = self._project_surface(p1)
            self._line_pixels(buf, x0, y0, x1, y1)

        # Mouth columns, including the wearable's reactive wave.
        for index, (top_point, bottom_point) in enumerate(mouth):
            x0, y0 = self._project_surface(top_point)
            x1, y1 = self._project_surface(bottom_point)

            if reactive_level > 0:
                wave = (
                    math.sin(self.time_counter * 5.2 + index * 0.62)
                    * reactive_level
                    * 0.18
                )
                y0 += wave
                y1 += wave
                y1 += (
                    reactive_level
                    * 0.10
                    * (
                        1.0
                        + math.sin(
                            self.time_counter * 3.6
                            + index * 0.9
                        )
                    )
                )

            self._line_pixels(buf, x0, y0, x1, y1)

        return buf

    def _build_corrupted_face_pixels(self):
        """
        Build an emotionless generating-state signal collapse.

        There are deliberately no eyes, brows, or mouth. The only surviving
        identity is the circular wearable-face region, which is repeatedly
        torn apart by missing arcs, ghost shells, dense static, blackout
        blocks, vertical fractures, and horizontally displaced scan slices.
        """
        raw = self._pixel_buffer()
        cx = FACE_PIXEL_W // 2
        cy = FACE_PIXEL_H // 2
        phase = self.time_counter

        # Broken primary shell plus unstable ghost copies.
        ghost_shells = [
            (0.0, 0.0, 1.00, 0.22),
            (-1.5, 0.5, 1.04, 0.48),
            (2.0, -0.5, 0.94, 0.62),
        ]

        for ox, oy, scale, dropout in ghost_shells:
            previous = None

            for degree in range(0, 361, 5):
                if random.random() < dropout:
                    previous = None
                    continue

                angle = math.radians(degree)
                radius = FACE_RADIUS * scale
                wobble = math.sin(
                    angle * 7.0 + phase * 9.0
                ) * random.uniform(0.0, 1.6)

                px = cx + ox + math.cos(angle) * (radius + wobble)
                py = cy + oy + math.sin(angle) * (radius + wobble * 0.5)

                if previous is not None:
                    self._line_pixels(
                        raw,
                        previous[0],
                        previous[1],
                        px,
                        py,
                    )

                previous = (px, py)

        # Dense interior signal noise. It follows the circular face region,
        # but contains no readable expression.
        for y in range(FACE_PIXEL_H):
            for x in range(FACE_PIXEL_W):
                dx = x - cx
                dy = y - cy

                if dx * dx + dy * dy > (FACE_RADIUS - 1) ** 2:
                    continue

                band = 0.5 + 0.5 * math.sin(
                    y * 1.7 + phase * 13.0
                )
                density = 0.16 + band * 0.24

                if random.random() < density:
                    raw[y][x] = True

        # Vertical fractures and hard data bars.
        for _ in range(random.randint(5, 9)):
            x = random.randint(cx - FACE_RADIUS + 2, cx + FACE_RADIUS - 2)
            y0 = random.randint(cy - FACE_RADIUS + 1, cy + 2)
            y1 = random.randint(cy - 1, cy + FACE_RADIUS - 1)
            thickness = random.choice([1, 1, 2])

            self._line_pixels(
                raw,
                x,
                y0,
                x + random.choice([-1, 0, 0, 1]),
                y1,
                thickness=thickness,
            )

        # Random blackout blocks carve large missing areas from the signal.
        for _ in range(random.randint(4, 7)):
            block_w = random.randint(3, 9)
            block_h = random.randint(2, 6)
            left = random.randint(
                max(0, cx - FACE_RADIUS),
                min(FACE_PIXEL_W - block_w, cx + FACE_RADIUS - 1),
            )
            top = random.randint(
                max(0, cy - FACE_RADIUS),
                min(FACE_PIXEL_H - block_h, cy + FACE_RADIUS - 1),
            )

            for y in range(top, top + block_h):
                for x in range(left, left + block_w):
                    raw[y][x] = False

        # Horizontal scan-slice displacement. Entire rows vanish, duplicate,
        # or jump several virtual pixels sideways.
        torn = self._pixel_buffer()

        for y, row in enumerate(raw):
            if random.random() < 0.16:
                continue

            shift = int(
                math.sin(phase * 12.0 + y * 0.77) * 3.5
            )

            if random.random() < 0.34:
                shift += random.randint(-8, 8)

            for x, value in enumerate(row):
                if not value:
                    continue

                nx = x + shift

                if 0 <= nx < FACE_PIXEL_W:
                    torn[y][nx] = True

                    # Occasional vertical ghosting.
                    if random.random() < 0.10 and y + 1 < FACE_PIXEL_H:
                        torn[y + 1][nx] = True

        # One or two bright cross-face tear bands.
        for _ in range(random.randint(1, 2)):
            y = random.randint(4, FACE_PIXEL_H - 5)
            start = random.randint(0, 8)
            end = random.randint(FACE_PIXEL_W - 9, FACE_PIXEL_W - 1)

            for x in range(start, end):
                if random.random() > 0.18:
                    torn[y][x] = True

        return torn

    @staticmethod
    def _braille_rows(pixel_buffer):
        """Pack any virtual pixel buffer into 2 x 4 Braille cells."""
        rows = []
        pixel_height = len(pixel_buffer)
        pixel_width = len(pixel_buffer[0]) if pixel_height else 0
        cell_height = (pixel_height + 3) // 4
        cell_width = (pixel_width + 1) // 2

        for cell_y in range(cell_height):
            row = []

            for cell_x in range(cell_width):
                bits = 0

                for dot_y in range(4):
                    for dot_x in range(2):
                        px = cell_x * 2 + dot_x
                        py = cell_y * 4 + dot_y

                        if (
                            py < pixel_height
                            and px < pixel_width
                            and pixel_buffer[py][px]
                        ):
                            bits |= _BRAILLE_BITS[dot_y][dot_x]

                row.append(chr(0x2800 + bits) if bits else " ")

            rows.append("".join(row))

        return rows

    @staticmethod
    def _scale_pixel_buffer(pixel_buffer, target_width, target_height):
        """Nearest-neighbour scaling keeps the face's deliberate hard edges."""
        source_height = len(pixel_buffer)
        source_width = len(pixel_buffer[0]) if source_height else 0

        if not source_width or not source_height:
            return [
                [False for _ in range(target_width)]
                for _ in range(target_height)
            ]

        return [
            [
                pixel_buffer[
                    min(source_height - 1, int(y * source_height / target_height))
                ][
                    min(source_width - 1, int(x * source_width / target_width))
                ]
                for x in range(target_width)
            ]
            for y in range(target_height)
        ]

    def _dev_face_colour_code(self, offset=0):
        """Current entry in the rapid purple-only colour cycle for the developer-mode face."""
        index = (
            int(self.time_counter * _DEV_COLOUR_SPEED) + offset
        ) % len(_DEV_ARC_COLOURS)

        return _DEV_ARC_COLOURS[index]

    @staticmethod
    def _pixel_noise_cell(char):
        """
        Turn a rendered face cell into irregular pixel noise.

        Braille cells are mutated at the dot-bit level, preserving the visual
        language of a damaged raster image instead of substituting readable
        terminal symbols.
        """
        code = ord(char)

        if 0x2800 <= code <= 0x28FF:
            bits = code - 0x2800
        else:
            bits = random.randint(1, 255)

        # Randomly erase and inject individual sub-pixels.
        for bit in (1, 2, 4, 8, 16, 32, 64, 128):
            roll = random.random()

            if roll < 0.22:
                bits &= ~bit
            elif roll > 0.76:
                bits |= bit

        # Occasionally invert the local dot field for a photographic-negative
        # flash rather than a character substitution.
        if random.random() < 0.16:
            bits ^= 0xFF

        if bits == 0:
            bits = random.choice((1, 2, 4, 8, 16, 32, 64, 128))

        return chr(0x2800 + bits)

    # ------------------------------------------------------------
    # SHARED HEADER EFFECTS
    # ------------------------------------------------------------

    def _header_effect_cell(
        self,
        canvas,
        char,
        x,
        y,
        base_color,
        heat,
        ripple_x,
        tear_row,
        tear_shift,
        row_shifts,
        roll,
        flash=False,
        max_corrupt=False,
        speech_mouth=False,
    ):
        if char == " ":
            return

        original_x = x
        influence = 0.0
        distance = abs(x - ripple_x)

        if distance < RIPPLE_WIDTH:
            influence = 1.0 - (distance / RIPPLE_WIDTH)

        # The same travelling corruption logic used by the original title,
        # with a separate catastrophic mode for the generating-state face.
        corruption = 1.0 if max_corrupt else influence

        if flash and not max_corrupt:
            corruption = max(corruption, 0.72)

        if max_corrupt:
            chance = random.random()

            # Missing samples and displaced raster cells create the collapse.
            if chance < 0.28:
                return

            # Most surviving cells remain dot-based, but their individual
            # sub-pixels are damaged independently.
            char = self._pixel_noise_cell(char)

            # Rare overexposure/bloom produces a solid pixel fragment. These
            # are abstract raster shapes, not readable terminal symbols.
            if random.random() < 0.13:
                char = random.choice(_MAX_CORRUPT_BLOCKS)

            x += random.randint(-3, 3)
            y += random.choice([-1, 0, 0, 0, 1])

        elif speech_mouth:
            # Speech animation is deliberately confined to the mouth. It
            # resembles a noisy audio waveform rather than making the whole
            # voice-mode face collapse like the normal generation effect.
            chance = random.random()

            if chance < 0.12:
                return

            if chance < 0.68:
                char = self._pixel_noise_cell(char)

            x += random.choice([-1, 0, 0, 0, 1])
            y += random.choice([-1, 0, 0, 0, 0, 1])
        elif corruption > 0.0:
            chance = random.random()

            if chance < corruption * CORRUPT_DROP:
                return

            if chance < corruption * (
                CORRUPT_DROP + CORRUPT_NOISE
            ):
                char = random.choice(_CORRUPT_CHARS)

        if (
            corruption > CORRUPT_JOLT
            and random.random() < (0.82 if max_corrupt else 0.35)
        ):
            x += random.choice(
                [-3, -2, -1, 0, 1, 2, 3]
                if max_corrupt
                else [-1, 0, 1]
            )

        if 0 <= y < len(row_shifts):
            x += row_shifts[y]

        y += roll

        color = base_color

        if speech_mouth:
            color = fg(random.choice([
                C_RED_BRIGHT,
                C_RED_MID,
                C_RED_DARK,
                C_RED_BLOOD,
            ]))
        elif max_corrupt:
            if self.dev_mode:
                colour_offset = random.choice([-2, -1, 0, 0, 1, 2])
                color = fg(
                    self._dev_face_colour_code(colour_offset)
                )
            else:
                color = fg(random.choice([
                    C_RED_BRIGHT,
                    C_RED_MID,
                    C_RED_DARK,
                    C_RED_BLOOD,
                    C_RED_DEEP,
                ]))

        elif influence > RIPPLE_LIFT:
            color = fg(C_RED_BRIGHT)
            y -= 1
        elif influence > 0.45:
            color = fg(C_RED_MID)
        elif influence > 0.0:
            color = fg(C_RED_BLOOD)
        elif (
            heat > PIXEL_FLICKER_HEAT
            and random.random() < PIXEL_FLICKER_CHANCE
        ):
            color = fg(C_RED_BLOOD)

        if (
            flash
            and not max_corrupt
            and random.random() < FACE_GLITCH_CHANCE
        ):
            color = fg(C_RED_BRIGHT)
            x += random.choice([-1, 0, 1])

        if tear_row is not None and y >= tear_row:
            x += tear_shift

        if (
            0 <= x < self.width
            and 0 <= y < self.header_height
        ):
            canvas[y][x] = CanvasCell(char, color)

    def draw_background_corruption_streaks(
        self,
        canvas,
        block_start,
        block_width,
        heat,
    ):
        block_end = block_start + block_width

        for row_y in range(self.header_height):
            if random.random() >= (0.24 + heat * 0.34):
                continue

            # Draw independently on both sides of the centred face.
            regions = [
                (1, max(1, block_start - 2)),
                (
                    min(self.width - 1, block_end + 2),
                    self.width - 1,
                ),
            ]

            for left, right in regions:
                available = right - left

                if available < 3:
                    continue

                streak_len = random.randint(
                    2,
                    max(2, min(available, 14)),
                )
                streak_x = random.randint(
                    left,
                    max(left, right - streak_len),
                )

                for offset in range(streak_len):
                    x = streak_x + offset

                    if (
                        0 <= x < self.width
                        and canvas[row_y][x].char == " "
                    ):
                        canvas[row_y][x] = CanvasCell(
                            random.choice(_STREAK_CHARS),
                            fg(C_RED_DEEP),
                        )

    def _generation_status_line(self):
        """
        Return a pixel-only inference carrier.

        The strip contains only shaded raster blocks and Braille-dot noise.
        There are no letters, numbers, crosses, slashes, brackets, arrows, or
        box-drawing symbols.
        """
        if not self.generating:
            return ""

        usable = max(10, min(46, self.width - 8))
        phase = int(self.time_counter * 12.0)

        if not self.has_content:
            track = [" "] * usable
            crest = "░▒▓█▓▒░"
            start = phase % max(1, usable + len(crest))

            for index, char in enumerate(crest):
                position = start + index - len(crest)

                if 0 <= position < usable:
                    track[position] = char

            # Sparse dot-grain around the moving exposure crest.
            for index in range(usable):
                if random.random() < 0.07:
                    track[index] = chr(
                        0x2800 + random.randint(1, 255)
                    )
                elif random.random() < 0.025:
                    track[index] = " "

            return "".join(track)

        # Once output arrives, stream volume controls how much of the band is
        # illuminated. Texture still remains entirely pixel-based.
        lit_width = 1 + (
            (self.stream_chars // 6) % max(1, usable)
        )
        shades = "░▒▓█"
        track = []

        for index in range(usable):
            if index < lit_width:
                char = shades[
                    (index + self.stream_chunks + phase) % len(shades)
                ]
            else:
                char = " "

            if random.random() < 0.09:
                char = chr(0x2800 + random.randint(1, 255))
            elif random.random() < 0.035:
                char = " "

            track.append(char)

        return "".join(track)

    @staticmethod
    def _format_elapsed(seconds):
        seconds = max(0.0, float(seconds or 0.0))

        if seconds < 10:
            return f"{seconds:.1f}s"

        whole = int(seconds)
        minutes, secs = divmod(whole, 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            return f"{hours}h {minutes}m {secs}s"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def _activity_parts(self):
        """Current timer/status pair, or (None, None) while idle."""
        now = time.time()

        labels = {
            "building prompt": "Preparing context",
            "connecting": "Reading context",
            "thinking": "Writing response",
            "checking search": "Checking search need",
            "searching the web": "Searching the web",
            "checking edit": "Reviewing code change",
            "self-improvement": "Reviewing self-improvement",
            "checking memory": "Checking memory",
            "interpreting command": "Understanding requested tool",
            "loading voice": "Loading offline speech models",
            "checking voice setup": "Checking offline voice setup",
            "listening": "Listening  |  ESC returns to typing",
            "transcribing": "Transcribing speech locally",
            "synthesizing speech": "Preparing spoken reply",
            "shaping measured machine cadence": (
                "Applying measured machine cadence"
            ),
            "pausing between phrases": "Holding a deliberate phrase break",
            "speaking": "Speaking  |  ESC returns to typing",
        }

        if self.generating:
            phase = labels.get(
                self.status_text.lower().strip(),
                self.status_text.strip() or "Working",
            )
            elapsed = (
                max(0.0, now - self.generation_started_at)
                if self.generation_started_at
                else 0.0
            )
            parts = [phase]

            if self.has_content or self.stream_tokens:
                parts.append(f"{self.stream_tokens} tok")
            elif self.prompt_tokens:
                parts.append(f"~{self.prompt_tokens} ctx")

            return (
                f"Working for {self._format_elapsed(elapsed)}",
                "  |  ".join(parts),
            )

        if self.background_status_text:
            phase = labels.get(
                self.background_status_text.lower().strip(),
                self.background_status_text.strip(),
            )
            elapsed = (
                max(0.0, now - self.background_started_at)
                if self.background_started_at
                else 0.0
            )
            return (
                f"Working for {self._format_elapsed(elapsed)}",
                phase,
            )

        if self.activity_summary and now < self.activity_summary_until:
            return (None, self.activity_summary)

        return (None, None)

    def _activity_lines(self, compact=False):
        """Left-aligned activity rows, compacted on very short terminals."""
        timer, status = self._activity_parts()

        if not timer and not status:
            return []

        if compact and timer and status:
            return [f"  {timer}  |  {status}"]

        out = []

        if timer:
            out.append("  " + timer)
        if status:
            out.append("  " + status)

        return out

    def _activity_line(self):
        """Compatibility helper for tests and narrow renderers."""
        lines = self._activity_lines(compact=True)
        return lines[0] if lines else ""

    def draw_header(self, canvas, heat):
        """
        Compact responsive header.

        The face remains centred at every supported terminal width. The model
        name is kept to one line beneath it, so quarter-screen mode no longer
        pushes the face out of the title's leftover margin.
        """
        compact_voice = self.voice_mode and self.height < 18
        voice_pixel_width = (
            VOICE_COMPACT_PIXEL_W if compact_voice else VOICE_FACE_PIXEL_W
        )
        voice_pixel_height = (
            VOICE_COMPACT_PIXEL_H if compact_voice else VOICE_FACE_PIXEL_H
        )
        face_cell_width = (
            voice_pixel_width // 2 if self.voice_mode else FACE_CELL_W
        )
        face_cell_height = (
            voice_pixel_height // 4 if self.voice_mode else FACE_CELL_H
        )
        title_row = face_cell_height + 1
        status_row = title_row + 1
        self.header_height = status_row + 1

        face_start_x = max(
            0,
            (self.width - face_cell_width) // 2,
        )
        block_start = face_start_x
        block_width = face_cell_width

        self.draw_background_corruption_streaks(
            canvas,
            block_start,
            block_width,
            heat,
        )

        # Shared effect state for the entire header. Both face and label pass
        # through these same values during this frame.
        span = max(1, self.width + RIPPLE_WIDTH * 2)
        ripple_x = -RIPPLE_WIDTH + (self.ripple_phase % span)

        tear_row = None
        tear_shift = 0

        if random.random() < SYNC_TEAR_CHANCE:
            tear_row = random.randint(
                0,
                self.header_height - 1,
            )
            tear_shift = random.choice([-2, -1, 1, 2])

        roll = 1 if random.random() < SYNC_ROLL_CHANCE else 0
        row_shifts = [0] * self.header_height

        if (
            heat > ROW_JITTER_HEAT
            and random.random() < ROW_JITTER_CHANCE
        ):
            row_shifts[
                random.randint(0, self.header_height - 1)
            ] = random.choice(
                [-ROW_JITTER_MAX, ROW_JITTER_MAX]
            )

        now = time.time()

        if (
            not self.generating
            and not self.voice_mode
            and now - self._face_last_switch
            >= FACE_EMOTION_INTERVAL
        ):
            self._face_last_switch = now
            self.face_sequence_index = (
                self.face_sequence_index + 1
            ) % len(FACE_EMOTION_SEQUENCE)
            self.face_emotion = FACE_EMOTION_SEQUENCE[
                self.face_sequence_index
            ]
            self.face_flash = FACE_FLASH_FRAMES

        # Voice mode always uses the default expression. During playback only
        # the mouth receives a restrained waveform-like distortion.
        if self.voice_mode:
            face_pixels = self._scale_pixel_buffer(
                self._build_face_pixels(0, 0.0),
                voice_pixel_width,
                voice_pixel_height,
            )
        # Outside voice mode, generation keeps its dramatic full-face collapse.
        elif self.generating:
            face_pixels = self._build_corrupted_face_pixels()
        else:
            face_pixels = self._build_face_pixels(
                self.face_emotion,
                0.0,
            )

        face_rows = self._braille_rows(face_pixels)

        flash = self.face_flash > 0

        if self.face_flash > 0:
            self.face_flash -= 1

        if self.voice_mode:
            # Scale alone marks voice mode. Keep it out of the developer-mode
            # purple palette and use the normal idle/generating header colours.
            face_color = fg(C_RED_MID) if self.generating else WHITE
        elif self.dev_mode:
            face_color = fg(self._dev_face_colour_code())
        elif self.generating:
            face_color = fg(C_RED_MID)
        else:
            face_color = WHITE

        for row_y, row in enumerate(face_rows):
            for col_x, char in enumerate(row):
                speech_mouth = (
                    self.voice_mode
                    and self.voice_speaking
                    and row_y >= int(face_cell_height * 0.50)
                    and int(face_cell_width * 0.18)
                    <= col_x
                    < int(face_cell_width * 0.82)
                )
                self._header_effect_cell(
                    canvas=canvas,
                    char=char,
                    x=face_start_x + col_x,
                    y=FACE_TOP + row_y,
                    base_color=face_color,
                    heat=heat,
                    ripple_x=ripple_x,
                    tear_row=tear_row,
                    tear_shift=tear_shift,
                    row_shifts=row_shifts,
                    roll=roll,
                    flash=flash,
                    # Preserve the voice-specific mouth distortion during
                    # playback. In every other phase, the enlarged face uses
                    # the regular generating-state collapse too.
                    max_corrupt=(
                        self.generating
                        and not (
                            self.voice_mode
                            and self.voice_speaking
                        )
                    ),
                    speech_mouth=speech_mouth,
                )

        # Compact title directly beneath the face. It is responsive and never
        # participates in the face visibility calculation.
        label = self.title_text.upper()

        if len(label) > self.width - 4:
            label = label[:max(1, self.width - 5)] + "…"

        label_start = max(0, (self.width - len(label)) // 2)

        for offset, char in enumerate(label):
            self._header_effect_cell(
                canvas=canvas,
                char=char,
                x=label_start + offset,
                y=title_row,
                base_color=fg(C_RED_DARK),
                heat=heat,
                ripple_x=ripple_x,
                tear_row=tear_row,
                tear_shift=tear_shift,
                row_shifts=row_shifts,
                roll=roll,
                flash=flash,
            )

        # A symbol-only inference carrier occupies the final compact row.
        # It contains no ASCII text and shares the distortion pipeline.
        status_line = self._generation_status_line()

        if status_line:
            max_status_w = max(1, self.width - 4)

            if len(status_line) > max_status_w:
                status_line = status_line[:max(1, max_status_w - 1)] + "…"

            status_start = max(
                0,
                (self.width - len(status_line)) // 2,
            )

            for offset, char in enumerate(status_line):
                self._header_effect_cell(
                    canvas=canvas,
                    char=char,
                    x=status_start + offset,
                    y=status_row,
                    base_color=fg(C_RED_MID),
                    heat=heat,
                    ripple_x=ripple_x,
                    tear_row=tear_row,
                    tear_shift=tear_shift,
                    row_shifts=row_shifts,
                    roll=roll,
                    flash=flash,
                )
        else:
            # Idle fragments retain the original cyberpunk HUD texture.
            baseline_y = status_row

            for x in range(
                max(0, label_start - 3),
                min(self.width, label_start + len(label) + 3),
            ):
                if random.random() < 0.20:
                    self._header_effect_cell(
                        canvas=canvas,
                        char=random.choice(["─", "╍", "·"]),
                        x=x,
                        y=baseline_y,
                        base_color=fg(C_RED_DEEP),
                        heat=heat,
                        ripple_x=ripple_x,
                        tear_row=tear_row,
                        tear_shift=tear_shift,
                        row_shifts=row_shifts,
                        roll=roll,
                        flash=flash,
                    )

    def trigger_disintegration_transition(self):
        """Flash the face and label through the shared corruption pass."""
        self.face_flash = max(
            self.face_flash,
            FACE_FLASH_FRAMES,
        )

    def render_frame(self):
        with self.lock:
            self.time_counter += 0.08

            mult = GENERATING_RIPPLE_MULT if self.generating else 1.0
            self.ripple_phase += RIPPLE_SPEED * mult * 0.08

            self.update_size()
            w, h = self.width, self.height

            canvas = [[CanvasCell() for _ in range(w)] for _ in range(h)]

            if self.music_mode:
                self._draw_music(canvas, w, h)
                self._blit(canvas)
                return

            # Layer 0: Header & Streaks
            heat = 0.25 + random.uniform(0.0, 0.35)

            if self.generating:
                heat = min(1.0, heat + GENERATING_HEAT_BOOST)

            self.draw_header(canvas, heat)

            # Layer 1: Chat Output Buffer
            chat_area_h = max(1, h - self.header_height - 3)

            # Drop expired notices, and reduce to the (text, colour) pairs
            # everything downstream expects. Pruning here rather than on a
            # timer means a message disappears on the next drawn frame,
            # with no extra thread to keep alive.
            now = time.monotonic()
            live = [entry for entry in self.chat_history
                    if entry[2] is None or entry[2] > now]

            if len(live) != len(self.chat_history):
                self.chat_history[:] = live

            if self.page_lines is not None:
                page_size = max(1, chat_area_h - 1)
                page_count = max(
                    1,
                    (len(self.page_lines) + page_size - 1) // page_size,
                )
                self.page_index = max(
                    0,
                    min(self.page_index, page_count - 1),
                )
                start = self.page_index * page_size
                visible_lines = self.page_lines[start:start + page_size]
                action = (
                    "SPACE finish"
                    if self.page_index + 1 >= page_count
                    else "SPACE next"
                )
                visible_lines = visible_lines + [(
                    f"[page {self.page_index + 1}/{page_count}"
                    f" \u00b7 {action} \u00b7 ESC close]",
                    VIOLET,
                )]
            else:
                lines = [
                    (_decaying_text(text, colour, expires, now), colour)
                    for text, colour, expires in live
                ]

                if self.live_text:
                    wrap_w = max(w - CHAT_INDENT - 2, 10)
                    caret = "\u2588" if self.streaming else ""

                    for wrapped_line in _wrapped_display_lines(
                        self.live_text + caret,
                        wrap_w,
                    ):
                        lines.append((wrapped_line, self.live_color))

                for activity_line in self._activity_lines(
                    compact=chat_area_h < 4
                ):
                    lines.append((activity_line, GREY_DIM))

                visible_lines = lines[-chat_area_h:]
            newest = len(visible_lines) - 1

            for idx, (text, col) in enumerate(visible_lines):
                row_y = self.header_height + idx

                if row_y >= h - 2:
                    break

                # Age from the newest line, not screen position, so a
                # short session doesn't render pre-faded.
                age = newest - idx
                level = max(0, age - CHAT_FADE_AFTER)
                shade = _faded(col, level)

                rail_char = _RAIL_ACTIVE if idx == newest else _RAIL
                rail_col = fg(C_RED_MID) if idx == newest else fg(C_RED_DEEP)
                canvas[row_y][0] = CanvasCell(rail_char, rail_col)

                for col_x, char in enumerate(text[:w - CHAT_INDENT - 1]):
                    canvas[row_y][col_x + CHAT_INDENT] = CanvasCell(char, shade)

            # Rule between the backlog and the input row
            sep_y = h - 3

            if sep_y > self.header_height:
                for x in range(0, w):
                    canvas[sep_y][x] = CanvasCell(_SEPARATOR, fg(C_RED_DEEP))

            # Layer 2: Interactive Prompt Input Line
            prompt_y = h - 2
            canvas[prompt_y][0] = CanvasCell(_RAIL_ACTIVE, fg(C_RED_BRIGHT))

            shown_input = (
                "\u2022" * len(self.current_input)
                if (
                    self.input_masked
                    or dev_auth.is_numeric_input_in_progress(self.current_input)
                )
                else dev_auth.redact_credential_like_text(self.current_input)
            )
            input_width = max(1, w - CHAT_INDENT - 1)
            full_prompt = _visible_input_line(
                self.input_prompt,
                shown_input,
                input_width,
            )
            for col_x, char in enumerate(full_prompt):
                canvas[prompt_y][col_x + CHAT_INDENT] = CanvasCell(char, BOLD + RED)

            self._blit(canvas)

    @staticmethod
    def _blit(canvas):
        """
        Push a finished canvas in one write without triggering terminal wrap.

        Writing the bottom-right cell makes some Windows terminals advance to
        a new row and scroll the entire screen. Music mode made that look like
        a jittering code stream beneath the animation.
        """
        buffer = ["\x1b[?7l"]
        last_row = len(canvas) - 1

        for r_idx, row in enumerate(canvas):
            buffer.append(f"\x1b[{r_idx + 1};1H")
            cur_color = None

            # The final cell of the final row is intentionally untouched.
            # Music mode never places content there, and avoiding it prevents
            # hosts that auto-wrap at the right edge from scrolling.
            visible_row = row[:-1] if r_idx == last_row and row else row
            for cell in visible_row:
                if cell.color != cur_color:
                    buffer.append(cell.color)
                    cur_color = cell.color

                buffer.append(cell.char)

            buffer.append(RESET)

        buffer.append("\x1b[?7h\x1b[H")
        write_raw("".join(buffer))

    # ------------------------------------------------------------
    # MUSIC VISUALIZER
    # ------------------------------------------------------------

    # Each palette runs dark -> bright, with a near-white final oscilloscope
    # trace. Music mode moves to the next palette every twenty seconds.
    _MUSIC_PALETTES = (
        ("electric blue", (
            fg(17), fg(18), fg(19), fg(20), fg(27), fg(33), fg(45),
            fg(153), WHITE,
        )),
        ("ultraviolet", (
            fg(53), fg(54), fg(55), fg(56), fg(93), fg(129), fg(165),
            fg(219), WHITE,
        )),
        ("inferno", (
            fg(52), fg(88), fg(124), fg(160), fg(196), fg(202), fg(208),
            fg(226), WHITE,
        )),
        ("toxic cyan", (
            fg(22), fg(23), fg(29), fg(30), fg(35), fg(42), fg(48),
            fg(159), WHITE,
        )),
    )
    # The original radial tunnel remains first: it is the visual identity
    # already established for music mode.
    _MUSIC_SCENES = (
        "radial tunnel",
        "spectrum cathedral",
        "orbital reactor",
        "corrupt cube",
        "neon horizon",
        "plasma flow",
        "datastream rain",
        "wormhole",
    )
    _MUSIC_SCENE_ROTATION_SECONDS = 165
    _MUSIC_PALETTE_ROTATION_SECONDS = 20

    def _draw_music(self, canvas, width, height):
        """Full-viewport visualiser. Replaces the header and chat log."""
        captured_features = (
            self.music_audio.features()
            if self.music_audio is not None
            else {"bass": 0.0, "mid": 0.0, "treble": 0.0, "level": 0.0, "beat": 0.0}
        )

        if self.music_audio is not None and self.music_audio.error:
            self.music_status = f"audio capture stopped: {self.music_audio.error}"

        now = time.time()
        delta = now - self._music_last_frame if self._music_last_frame else 0.08
        self._music_last_frame = now
        # A stall (resize, scheduling hiccup) must not jump the animation.
        delta = max(0.01, min(0.25, delta))

        if (
            self.music_visualizer is not None
            and now - self._music_scene_started_at
            >= self._MUSIC_SCENE_ROTATION_SECONDS
        ):
            _replace_music_scene(self.music_scene_index + 1, now=now)
            self.music_status = "scene rotated automatically"

        if self.music_visualizer is not None:
            if self._music_palette_started_at <= 0.0:
                self._music_palette_started_at = now
            palette_elapsed = now - self._music_palette_started_at
            if palette_elapsed >= self._MUSIC_PALETTE_ROTATION_SECONDS:
                steps = max(
                    1,
                    int(
                        palette_elapsed
                        // self._MUSIC_PALETTE_ROTATION_SECONDS
                    ),
                )
                self.music_palette_index = (
                    self.music_palette_index + steps
                ) % len(self._MUSIC_PALETTES)
                palette_name, palette = self._MUSIC_PALETTES[
                    self.music_palette_index
                ]
                self.music_visualizer.palette = tuple(palette)
                self._music_palette_started_at += (
                    steps * self._MUSIC_PALETTE_ROTATION_SECONDS
                )
                self.music_status = (
                    f"palette rotated automatically: {palette_name}"
                )

        stage_h = max(1, height - 1)

        if self.music_visualizer is not None:
            from visualizer.reactivity import shape_features
            features = shape_features(
                captured_features,
                self._MUSIC_SCENES[self.music_scene_index],
            )
            self.music_visualizer.step(delta, features, width, stage_h)

            for y, row in enumerate(
                self.music_visualizer.render(width, stage_h, features)
            ):
                if y >= stage_h:
                    break

                for x, cell in enumerate(row):
                    if cell and x < width:
                        canvas[y][x] = CanvasCell(cell[0], cell[1])
        else:
            features = captured_features

        self._draw_music_status(canvas, width, height, features)

    def _draw_music_status(self, canvas, width, height, features):
        """A minimal HUD that leaves the visual field nearly full-screen."""
        text_row = height - 1

        if text_row < 0:
            return

        scene_name = self._MUSIC_SCENES[self.music_scene_index]
        remaining = max(
            0,
            int(self._MUSIC_SCENE_ROTATION_SECONDS - (
                time.time() - self._music_scene_started_at
            )),
        )
        palette_remaining = max(
            0,
            int(math.ceil(
                self._MUSIC_PALETTE_ROTATION_SECONDS - (
                    time.time() - self._music_palette_started_at
                )
            )),
        )
        controls = (
            f"scene {self.music_scene_index + 1}/{len(self._MUSIC_SCENES)}: "
            f"{scene_name} | auto {remaining // 60}:{remaining % 60:02d} | "
            f"colour {palette_remaining}s | ←/→ scene | "
            f"space next local | [/] vol {self.music_volume_percent}% | "
            f"{MUSIC_TOGGLE_LABEL} exit"
        )
        status = f"{self.music_status} | {controls}" if self.music_status else controls
        level = max(0.0, min(1.0, features.get("level", 0.0)))
        meter_width = min(12, max(4, width // 10))
        meter = "━" * int(level * meter_width)
        status = f"{meter:<{meter_width}}  {status}"

        for i, ch in enumerate(status[:max(0, width - 2)]):
            canvas[text_row][i + 1] = CanvasCell(
                ch,
                fg(45) if i < meter_width else GREY,
            )

    def _loop(self):
        while self.running:
            try:
                self.render_frame()
            except Exception as error:
                # A renderer failure should not kill input handling, but it
                # must not vanish without evidence either. Log each distinct
                # failure once so a broken animation remains diagnosable.
                message = f"{type(error).__name__}: {error}"

                if message != self._last_render_error:
                    self._last_render_error = message

                    try:
                        os.makedirs(os.path.dirname(_UI_ERROR_LOG), exist_ok=True)

                        with open(_UI_ERROR_LOG, "a", encoding="utf-8") as log:
                            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            log.write(f"[{stamp}] {message}\n")
                    except OSError:
                        pass

            time.sleep(0.08)

    def start(self):
        self.running = True
        hide_cursor()
        clear_screen()
        self.render_thread = threading.Thread(target=self._loop, daemon=True)
        self.render_thread.start()

    def stop(self):
        self.running = False

        if self.music_audio is not None:
            self.music_audio.stop()
        self.music_audio = None
        self.music_visualizer = None
        self.music_mode = False
        _visualizer_output_guard.stop()

        if (
            self.render_thread is not None
            and self.render_thread is not threading.current_thread()
        ):
            self.render_thread.join(timeout=1.0)

        self.render_thread = None
        show_cursor()
        clear_screen()

_engine = LayeredDisplayEngine()


# ============================================================
# API INTERFACE
# ============================================================

def _set_terminal_title(title):
    """Name the host terminal without printing a visible command."""
    title = str(title or "TORMENT_NEXUS")

    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        else:
            sys.stdout.write(f"\033]0;{title}\007")
            sys.stdout.flush()
    except Exception:
        # Cosmetic only; a host that blocks title updates must still launch.
        pass


def print_startup_screen(model_path=None, layout_seed=None, display_name=None):
    enable_ansi()
    enable_character_input()

    # The header names the system, not the model.  Keep parsing the model label
    # only for its quantisation metadata, so it remains available to future
    # diagnostics without competing with TORMENT_NEXUS's visible identity.
    _engine.title_text = "TORMENT_NEXUS"
    _set_terminal_title("TORMENT_NEXUS")

    if display_name:
        base = display_name.upper()
    elif model_path:
        base = os.path.basename(str(model_path).replace("\\", "/")).upper()
        base = base.rsplit(".", 1)[0]
    else:
        base = ""

    if base:
        quant_keywords = ["Q4_K_M", "Q4_K_S", "Q5_K_M", "Q8_0", "Q2_K", "FP16", "INT4", "INT8"]
        for qk in quant_keywords:
            if qk in base:
                _engine.quant_text = qk
                break

    _engine.start()

def trigger_wireframe_disintegration():
    _engine.trigger_disintegration_transition()

# How long a notice spends corrupting before it goes.
DECAY_SECONDS = 1.6

# Glyphs an expiring line rots into. Kept to a narrow band of similar
# visual weight so the line dissolves rather than appearing to flash
# brighter as it goes.
DECAY_GLYPHS = "▓▒░#%&$@*+=~-_:."


def _decaying_text(text, colour, expires_at, now):
    """
    Corrupt a notice during its final moments instead of blinking it out.

    Only applies to VIOLET, which is the colour of system notices. An
    earlier full-UI corruption effect was removed because it fought
    readability; confining it to text that is already leaving keeps the
    look without ever obscuring something the operator still needs.

    Characters are chosen fresh each frame on purpose -- the flicker is
    the effect. Spaces are preserved so the line keeps its shape and
    dissolves in place rather than turning into a solid bar.
    """
    if expires_at is None or colour != VIOLET or not text:
        return text

    remaining = expires_at - now

    if remaining >= DECAY_SECONDS:
        return text

    # 0 at the start of the decay window, 1 as it expires.
    progress = max(0.0, min(1.0, 1.0 - (remaining / DECAY_SECONDS)))

    # Ease in, so it holds legible longer and then goes quickly.
    corruption = progress ** 2

    return "".join(
        character
        if character == " " or random.random() > corruption
        else random.choice(DECAY_GLYPHS)
        for character in text
    )


def print_framed(text="", color="", expires_in=None):
    """
    Add a message to the chat area.

    `expires_in` gives the message a lifetime in seconds, after which it
    removes itself from the transcript. Intended for notices that explain
    a transient condition -- an unavailable microphone, a device that
    could not be opened -- which are useful the moment they appear and
    then sit there implying the problem is ongoing.

    Anything the operator said, or the assistant replied, must never
    expire: a conversation that quietly edits itself is worse than a
    cluttered one.
    """
    expires_at = (
        time.monotonic() + float(expires_in)
        if expires_in
        else None
    )

    with _engine.lock:
        width = max(_engine.width - CHAT_INDENT - 2, 10)

        for wrapped_line in _wrapped_display_lines(text, width):
            _engine.chat_history.append(
                (wrapped_line, color or RESET, expires_at)
            )

        # Without this the buffer grows for the whole session.
        if len(_engine.chat_history) > 500:
            del _engine.chat_history[:-300]


def _wrapped_display_lines(text, width):
    """Wrap text without flattening explicit newlines or list indentation."""
    wrapper = textwrap.TextWrapper(
        width=max(1, int(width)),
        replace_whitespace=False,
        drop_whitespace=False,
        break_long_words=True,
        break_on_hyphens=False,
    )
    wrapped = []

    for logical_line in str(text or "").split("\n"):
        wrapped.extend(wrapper.wrap(logical_line) or [""])

    return wrapped


def _visible_input_line(prompt, shown_input, width):
    """Keep the cursor and newest typed text visible in a one-line prompt."""
    width = max(1, int(width))
    full = f"{prompt}{shown_input}\u2588"

    if len(full) <= width:
        return full
    if width == 1:
        return "\u2588"

    return "\u2026" + full[-(width - 1):]


def page_text_if_needed(text, color=GREY):
    """
    Show a completed long response one viewport at a time.

    Space/Enter/Down advances, Up/Backspace goes back, and Escape/Q closes.
    The response is already retained in chat history; clearing page_lines
    therefore returns the ordinary view to the conversation's bottom.
    """
    with _engine.lock:
        _engine.update_size()
        width = max(_engine.width - CHAT_INDENT - 2, 10)
        lines = [
            (line, color or RESET)
            for line in _wrapped_display_lines(text, width)
        ]
        chat_area_h = max(
            1,
            _engine.height - _engine.header_height - 3,
        )

        if (
            not _engine.running
            or len(lines) <= chat_area_h
        ):
            return False

        _engine.page_lines = lines
        _engine.page_index = 0

    try:
        while _engine.running:
            key = get_char()

            if key is None:
                time.sleep(0.01)
                continue

            with _engine.lock:
                chat_area_h = max(
                    1,
                    _engine.height - _engine.header_height - 3,
                )
                page_size = max(1, chat_area_h - 1)
                page_count = max(
                    1,
                    (len(_engine.page_lines) + page_size - 1) // page_size,
                )

                if key in ("ESC", "q", "Q"):
                    break
                if key in ("UP", "\x08", "\x7f"):
                    _engine.page_index = max(0, _engine.page_index - 1)
                    continue
                if key in (" ", "\r", "\n", "DOWN", "RIGHT"):
                    if _engine.page_index + 1 >= page_count:
                        break
                    _engine.page_index += 1
    finally:
        with _engine.lock:
            _engine.page_lines = None
            _engine.page_index = 0

    return True

# Supplies the list of names Up/Down cycles through. Injected rather
# than imported directly -- commands/command_handlers.py already
# imports this module, so ui.py importing it back would be circular.
_command_source = None


def set_command_source(fn):
    """fn() -> list[str] of currently-typable command names."""
    global _command_source
    _command_source = fn


def _cycle_command(direction):
    """
    direction: +1 for Up, -1 for Down. Overwrites current_input with
    the next/previous name in the injected command list, wrapping at
    either end. No-ops quietly if nothing was ever wired up.
    """
    if _command_source is None:
        return

    names = _command_source()

    if not names:
        return

    if _engine.cycle_index == -1:
        _engine.cycle_index = 0 if direction > 0 else len(names) - 1
    else:
        _engine.cycle_index = (_engine.cycle_index + direction) % len(names)

    _engine.current_input = names[_engine.cycle_index]


def safe_user_text(text):
    """Prepare submitted user text for display without exposing credentials."""
    if dev_auth.is_credential_like_input(text):
        return "[hidden]"

    return dev_auth.redact_credential_like_text(text)


# Returned by input_framed when it gave up waiting. A sentinel object
# rather than None, which already means "cancelled", or "", which is a
# legitimate empty submission.
IDLE = object()


def input_framed(
    label,
    color=RED,
    initial_text="",
    masked=False,
    allow_cycle=True,
    allow_cancel=False,
    idle_timeout=None,
):
    """
    Block for a line of input.

    `idle_timeout` returns the IDLE sentinel after that many seconds with
    no keypress at all. The timer resets on every key, and never fires
    while there is a partially typed line waiting -- someone mid-sentence
    is present, however long they pause, and interrupting them to ask if
    they are still there would be both wrong and irritating.
    """
    _engine.input_prompt = label + " "
    # A response can finish while the user is still composing the next
    # message. Restore that draft instead of clearing it at the next
    # blocking prompt.
    _engine.current_input = initial_text or ""
    _engine.input_masked = bool(masked)
    _engine.cycle_index = -1

    last_activity = time.monotonic()

    while _engine.running:
        if (
            idle_timeout
            and not _engine.current_input
            and time.monotonic() - last_activity >= idle_timeout
        ):
            return IDLE

        ch = get_char()

        if ch is not None:
            last_activity = time.monotonic()
        if ch is None:
            time.sleep(0.01)
            continue

        if ch in ("\r", "\n"):
            user_text = _engine.current_input
            shown = "[hidden]" if masked else safe_user_text(user_text)
            print_framed(f"{label} {shown}", color)
            _engine.current_input = ""
            _engine.input_masked = False
            _engine.cycle_index = -1
            return user_text
        elif ch == MUSIC_TOGGLE_KEY:
            print_framed(toggle_music_mode(), color=VIOLET)
        elif ch == MUSIC_NEXT_TRACK_KEY and music_mode_active():
            skip_local_track()
        elif ch == "LEFT" and music_mode_active():
            cycle_music_scene(-1)
        elif ch == "RIGHT" and music_mode_active():
            cycle_music_scene(1)
        elif ch == MUSIC_VOLUME_DOWN_KEY and music_mode_active():
            cycle_music_volume(-5)
        elif ch == MUSIC_VOLUME_UP_KEY and music_mode_active():
            cycle_music_volume(5)
        elif ch == "ESC" and allow_cancel:
            _engine.current_input = ""
            _engine.input_masked = False
            _engine.cycle_index = -1
            print_framed(f"{label} [cancelled]", color)
            return None
        elif ch == "UP" and allow_cycle:
            _cycle_command(1)
        elif ch == "DOWN" and allow_cycle:
            _cycle_command(-1)
        elif ch in ("\x08", "\x7f"):
            _engine.current_input = _engine.current_input[:-1]
            _engine.cycle_index = -1
        elif len(ch) == 1 and ord(ch) >= 32:
            _engine.current_input += ch
            _engine.cycle_index = -1

    # Engine stopped mid-input; return a string so callers that do
    # user_input.lower() don't hit AttributeError on None.
    _engine.current_input = ""
    _engine.input_masked = False
    return ""


def input_secret(label="OWNER PASSCODE >"):
    """Read a secret without rendering or recording its characters."""
    previous_prompt = _engine.input_prompt

    try:
        return input_framed(
            label,
            color=VIOLET,
            masked=True,
            allow_cycle=False,
            allow_cancel=True,
        )
    finally:
        # Authentication is a temporary modal prompt. Restore the calling
        # mode's ordinary input label immediately so a command response or
        # unrelated runtime error never leaves "OWNER PASSCODE" on screen.
        with _engine.lock:
            _engine.input_prompt = previous_prompt
            _engine.current_input = ""
            _engine.input_masked = False
            _engine.cycle_index = -1


def input_draft():
    """Return text currently composed in the non-blocking input row."""
    return _engine.current_input


def stream_begin(label="AI >", color=GREY):
    """Open a live reply and reset inference telemetry."""
    now = time.time()

    with _engine.lock:
        # Preserve an already-running operation timer when this reply
        # follows a search or another preparatory phase.
        started_at = (
            _engine.generation_started_at
            if _engine.generating and _engine.generation_started_at
            else now
        )
        _engine.live_text = label + " " if label else ""
        _engine.live_color = color or RESET
        _engine.streaming = True
        _engine.generating = True
        _engine.status_text = ""
        _engine.has_content = False
        _engine.generation_started_at = started_at
        _engine.last_token_at = 0.0
        _engine.prompt_tokens = 0
        _engine.stream_tokens = 0
        _engine.stream_chars = 0
        _engine.stream_chunks = 0
        _engine.activity_summary = ""
        _engine.activity_summary_until = 0.0


def stream_append(text, token_increment=0):
    """Append streamed text and update live token-stream telemetry."""
    if not text and not token_increment:
        return

    with _engine.lock:
        if text:
            _engine.has_content = True
            _engine.live_text += text
            _engine.stream_chars += len(text)
            _engine.stream_chunks += 1
            _engine.last_token_at = time.time()

        _engine.stream_tokens += max(0, int(token_increment or 0))


def subtitle_begin(label="AI >", color=GREY):
    """Open a playback-synchronised line without resetting generation stats."""
    with _engine.lock:
        _engine.live_text = label + " " if label else ""
        _engine.live_color = color or RESET
        _engine.streaming = True
        _engine.has_content = False


def subtitle_end():
    """Commit a synchronised subtitle while leaving activity telemetry intact."""
    with _engine.lock:
        final = _engine.live_text
        color = _engine.live_color
        _engine.live_text = ""
        _engine.streaming = False
        _engine.has_content = False

    if final.strip():
        print_framed(final, color)

    return final


def set_prompt_tokens(count):
    """Show the approximate context size while llama.cpp evaluates it."""
    with _engine.lock:
        _engine.prompt_tokens = max(0, int(count or 0))


def set_stream_tokens(count):
    """Replace the live estimate with the server's exact final count."""
    with _engine.lock:
        _engine.stream_tokens = max(0, int(count or 0))


def set_status(text):
    """
    Supply an optional generation phase.

    Generic values such as "connecting" and "thinking" are automatically
    expanded into the animated inference telemetry. More specific text is
    shown as an external phase in the header.
    """
    with _engine.lock:
        _engine.status_text = text or ""


def set_background_status(text):
    """Activity that should never overwrite a foreground response phase."""
    with _engine.lock:
        text = text or ""

        if text and not _engine.background_status_text:
            _engine.background_started_at = time.time()
        elif not text:
            _engine.background_started_at = 0.0

        _engine.background_status_text = text


def finish_activity(completion_label="Done"):
    """End a non-chat operation and briefly retain its timer/token summary."""
    with _engine.lock:
        elapsed = (
            max(0.0, time.time() - _engine.generation_started_at)
            if _engine.generation_started_at
            else 0.0
        )
        token_count = _engine.stream_tokens

        _engine.activity_summary = (
            f"{completion_label} in {_engine._format_elapsed(elapsed)}"
            + (f"  |  {token_count} tok" if token_count else "")
        )
        _engine.activity_summary_until = time.time() + 4.0
        _engine.generating = False
        _engine.status_text = ""
        _engine.generation_started_at = 0.0
        _engine.last_token_at = 0.0
        _engine.prompt_tokens = 0
        _engine.stream_tokens = 0
        _engine.stream_chars = 0
        _engine.stream_chunks = 0
        _engine._face_last_switch = time.time()


def stream_end(completion_label="Done"):
    """
    Commits the live line into the chat buffer and drops back to the
    idle visual state.
    """
    with _engine.lock:
        final = _engine.live_text
        color = _engine.live_color
        elapsed = (
            max(0.0, time.time() - _engine.generation_started_at)
            if _engine.generation_started_at
            else 0.0
        )
        token_count = _engine.stream_tokens

        _engine.activity_summary = (
            f"{completion_label} in {_engine._format_elapsed(elapsed)}"
            f"  |  {token_count} tok"
        )
        _engine.activity_summary_until = time.time() + 4.0

        _engine.streaming = False
        _engine.generating = False
        _engine.live_text = ""
        _engine.status_text = ""
        _engine.generation_started_at = 0.0
        _engine.last_token_at = 0.0
        _engine.prompt_tokens = 0
        _engine.stream_tokens = 0
        _engine.stream_chars = 0
        _engine.stream_chunks = 0
        _engine._face_last_switch = time.time()

    if final.strip():
        print_framed(final, color)

    return final


def stream_abort(completion_label="Stopped"):
    """Close a failed/cancelled stream without committing an empty AI label."""
    with _engine.lock:
        elapsed = (
            max(0.0, time.time() - _engine.generation_started_at)
            if _engine.generation_started_at
            else 0.0
        )
        token_count = _engine.stream_tokens
        _engine.activity_summary = (
            f"{completion_label} in {_engine._format_elapsed(elapsed)}"
            + (f"  |  {token_count} tok" if token_count else "")
        )
        _engine.activity_summary_until = time.time() + 4.0
        _engine.streaming = False
        _engine.generating = False
        _engine.live_text = ""
        _engine.status_text = ""
        _engine.generation_started_at = 0.0
        _engine.last_token_at = 0.0
        _engine.prompt_tokens = 0
        _engine.stream_tokens = 0
        _engine.stream_chars = 0
        _engine.stream_chunks = 0
        _engine._face_last_switch = time.time()


def begin_input(label):
    """
    Arms the input row for typing without blocking -- pairs with
    poll_input(). Use this instead of input_framed() when something
    else needs to keep running (e.g. a reply still streaming in)
    while the person types.
    """
    _engine.input_prompt = label + " "
    _engine.current_input = ""
    _engine.input_masked = False
    _engine.cycle_index = -1


def poll_input():
    """
    Non-blocking single-step companion to begin_input(). Call this
    once per loop iteration; it reads at most one keypress and
    returns None immediately if there isn't one waiting. Returns the
    finished line once Enter is pressed (and resets the input row for
    whatever comes next).
    """
    event = poll_input_event()

    if event is None or event[0] != "line":
        return None

    return event[1]


def poll_input_event():
    """
    Non-blocking input event used by modes that need a dedicated Escape key.

    Returns ("line", text), ("escape", None), or None. Ordinary callers can
    continue using poll_input(), which intentionally ignores Escape events.
    """
    ch = get_char()

    if ch is None:
        return None

    if ch == MUSIC_TOGGLE_KEY:
        print_framed(toggle_music_mode(), color=VIOLET)
        return None

    if ch == MUSIC_NEXT_TRACK_KEY and music_mode_active():
        skip_local_track()
        return None

    if ch == "LEFT" and music_mode_active():
        cycle_music_scene(-1)
        return None

    if ch == "RIGHT" and music_mode_active():
        cycle_music_scene(1)
        return None

    if ch == MUSIC_VOLUME_DOWN_KEY and music_mode_active():
        cycle_music_volume(-5)
        return None

    if ch == MUSIC_VOLUME_UP_KEY and music_mode_active():
        cycle_music_volume(5)
        return None

    if ch == "ESC":
        return ("escape", None)
    if ch in ("\r", "\n"):
        user_text = _engine.current_input
        _engine.current_input = ""
        _engine.cycle_index = -1
        return ("line", user_text)
    elif ch == "UP":
        _cycle_command(1)
    elif ch == "DOWN":
        _cycle_command(-1)
    elif ch in ("\x08", "\x7f"):
        _engine.current_input = _engine.current_input[:-1]
        _engine.cycle_index = -1
    elif len(ch) == 1 and ord(ch) >= 32:
        _engine.current_input += ch
        _engine.cycle_index = -1

    return None


# ============================================================
# MUSIC VISUALIZER MODE
#
# Ctrl+B rather than the more obvious Ctrl+M: Ctrl+M transmits byte
# 0x0D, which is byte-for-byte identical to Enter. A terminal cannot
# tell them apart, so binding it would break submitting input. Any
# free control code works here -- change MUSIC_TOGGLE_KEY and nothing
# else.
# ============================================================

MUSIC_TOGGLE_KEY = "\x02"          # Ctrl+B
MUSIC_TOGGLE_LABEL = "ctrl+b"
MUSIC_NEXT_TRACK_KEY = " "
MUSIC_NEXT_TRACK_LABEL = "space"
MUSIC_VOLUME_DOWN_KEY = "["
MUSIC_VOLUME_UP_KEY = "]"
MUSIC_VOLUME_LABEL = "[/]"


def music_mode_active():
    return _engine.music_mode


def set_music_status(text):
    with _engine.lock:
        _engine.music_status = str(text or "")


def local_track_changed(name, error=None):
    """Refresh the HUD when library repeat advances on its worker thread."""
    if error is not None:
        set_music_status(f"local library repeat stopped: {error}"[:70])
        return

    set_music_status(f"playing {name} (local) | library repeat on"[:70])


def cycle_music_palette():
    """Advance the palette and restart its automatic twenty-second timer."""
    with _engine.lock:
        if not _engine.music_mode or _engine.music_visualizer is None:
            return "Music mode is off."

        _engine.music_palette_index = (
            _engine.music_palette_index + 1
        ) % len(_engine._MUSIC_PALETTES)
        name, palette = _engine._MUSIC_PALETTES[_engine.music_palette_index]
        _engine.music_visualizer.palette = tuple(palette)
        _engine._music_palette_started_at = time.time()
        _engine.music_status = f"palette: {name}"
        return _engine.music_status


def skip_local_track():
    """Advance local playback without touching Spotify or browser audio."""
    from visualizer import local_player

    try:
        name = local_player.get_player().play_next()
        status = f"playing next local song: {name}"
    except local_player.LocalPlaybackError as error:
        status = str(error)

    with _engine.lock:
        _engine.music_status = status

    return status


def _make_music_scene(name, palette):
    """Construct a visualizer lazily; normal chat never imports these scenes."""
    if name == "radial tunnel":
        from visualizer.radial import RadialVisualizer
        return RadialVisualizer(palette)
    if name == "spectrum cathedral":
        from visualizer.spectrum import SpectrumVisualizer
        return SpectrumVisualizer(palette)
    if name == "orbital reactor":
        from visualizer.reactor import ReactorVisualizer
        return ReactorVisualizer(palette)
    if name == "corrupt cube":
        from visualizer.cube import CubeVisualizer
        return CubeVisualizer(palette)
    if name == "neon horizon":
        from visualizer.grid import GridVisualizer
        return GridVisualizer(palette)
    if name == "plasma flow":
        from visualizer.plasma import PlasmaVisualizer
        return PlasmaVisualizer(palette)
    if name == "datastream rain":
        from visualizer.datastream import DatastreamVisualizer
        return DatastreamVisualizer(palette)
    if name == "wormhole":
        from visualizer.wormhole import WormholeVisualizer
        return WormholeVisualizer(palette)
    raise ValueError(f"Unknown music scene: {name}")


def _replace_music_scene(index, now=None):
    """Replace the active scene; callers coordinate access to the engine."""
    _engine.music_scene_index = index % len(_engine._MUSIC_SCENES)
    name = _engine._MUSIC_SCENES[_engine.music_scene_index]
    _palette_name, palette = _engine._MUSIC_PALETTES[_engine.music_palette_index]
    _engine.music_visualizer = _make_music_scene(name, palette)
    _engine._music_scene_started_at = time.time() if now is None else now
    return name


def cycle_music_scene(direction=1):
    """Manually select the next or previous scene without touching playback."""
    with _engine.lock:
        if not _engine.music_mode:
            return "Music mode is off."
        try:
            name = _replace_music_scene(_engine.music_scene_index + direction)
        except Exception as error:
            _engine.music_status = f"scene unavailable: {error}"
            return _engine.music_status
        _engine.music_status = f"scene: {name}"
        return _engine.music_status


def set_music_volume(percent):
    """Set local-library playback gain without changing system or Spotify volume."""
    value = max(0, min(100, int(round(float(percent)))))
    from visualizer import local_player
    local_player.get_player().set_volume(value / 100.0)
    with _engine.lock:
        _engine.music_volume_percent = value
        if _engine.music_mode:
            _engine.music_status = f"local music volume: {value}%"
    return value


def music_volume_percent():
    """The retained gain for TORMENT_NEXUS local music playback."""
    with _engine.lock:
        return _engine.music_volume_percent


def cycle_music_volume(delta):
    """Adjust the next/current local track in five-percent steps."""
    return set_music_volume(music_volume_percent() + int(delta))


def enter_music_mode():
    """
    Enter the visualizer without ever toggling an active session off.

    Audio capture and the visual field are created on entry and torn down on
    exit, so a session that never opens music mode pays nothing for it
    -- neither the import cost nor a capture thread holding the sound
    device open.
    """
    if _engine.music_mode:
        return "Music mode already on."

    _visualizer_output_guard.start()
    try:
        from visualizer.audio_source import AudioSource
        _make_music_scene("radial tunnel", _engine._MUSIC_PALETTES[0][1])
    except Exception as error:
        _visualizer_output_guard.stop()
        return f"Music mode unavailable: {error}"

    source = AudioSource()
    try:
        started = source.start()
    except Exception as error:
        _visualizer_output_guard.stop()
        return f"Music mode unavailable: {error}"

    palette_name, _palette = _engine._MUSIC_PALETTES[_engine.music_palette_index]
    _engine.music_audio = source if started else None
    _engine.music_mode = True
    _engine.music_scene_index = 0
    _engine._music_scene_started_at = time.time()
    _engine._music_palette_started_at = _engine._music_scene_started_at
    _replace_music_scene(_engine.music_scene_index, now=_engine._music_scene_started_at)
    _engine._music_last_frame = 0.0
    clear_screen()

    if not started:
        # The visualiser still runs, it just has nothing to react to.
        # Saying so beats letting it look like the music is silent.
        _engine.music_status = (
            f"no audio capture -- idle animation | palette: {palette_name}"
        )
        return (
            "Music mode on, but system audio capture failed:\n"
            f"{source.error}\n\n"
            f"The visualiser is running idle. ←/→ cycles scenes; "
            f"colours change every 20 seconds; {MUSIC_NEXT_TRACK_LABEL} "
            f"plays the next local song; {MUSIC_VOLUME_LABEL} "
            f"changes local-music volume; {MUSIC_TOGGLE_LABEL} exits."
        )

    _engine.music_status = (
        f"listening: {source.device_name} | palette: {palette_name}"
    )
    return (
        f"Music mode on -- reacting to system audio.\n"
        f"Play anything (Spotify, browser, a file) and it will respond.\n"
        f"Scenes rotate every 2:45. ←/→ changes them now; "
        f"colours change every 20 seconds; {MUSIC_NEXT_TRACK_LABEL} "
        f"plays the next local song; {MUSIC_VOLUME_LABEL} "
        f"changes local-music volume; {MUSIC_TOGGLE_LABEL} exits."
    )


def exit_music_mode():
    """Leave the visualizer and restore normal terminal output."""
    if not _engine.music_mode:
        _visualizer_output_guard.stop()
        return "Music mode is already off."

    if _engine.music_audio is not None:
        _engine.music_audio.stop()

    _engine.music_audio = None
    _engine.music_visualizer = None
    _engine.music_mode = False
    _visualizer_output_guard.stop()
    clear_screen()
    return "Music mode off."


def toggle_music_mode():
    """Enter or leave the full-screen visualizer."""
    return exit_music_mode() if _engine.music_mode else enter_music_mode()


def set_dev_mode(flag):
    """Enable or disable the rapid purple-cycle developer-mode face."""
    with _engine.lock:
        _engine.dev_mode = bool(flag)


def set_voice_mode(flag):
    """Show whether the dedicated offline voice conversation is active."""
    with _engine.lock:
        _engine.voice_mode = bool(flag)
        _engine.voice_speaking = False
        _engine._face_last_switch = time.time()


def set_voice_speaking(flag):
    """Animate only the voice face's mouth while audio is playing."""
    with _engine.lock:
        _engine.voice_speaking = bool(flag) and _engine.voice_mode


def is_generating():
    """True while tokens are being pulled. The memory worker waits on this."""
    return _engine.generating


def set_generating(flag):
    """
    Drives the header's reactive state on its own. Use when waiting on
    the server before any tokens have arrived.
    """
    with _engine.lock:
        flag = bool(flag)

        if flag and not _engine.generating:
            _engine.generation_started_at = time.time()
            _engine.prompt_tokens = 0
            _engine.stream_tokens = 0
            _engine.activity_summary = ""
            _engine.activity_summary_until = 0.0
        elif not flag:
            _engine.generation_started_at = 0.0
            _engine.status_text = ""

        _engine.generating = flag


def teardown():
    _engine.generating = False
    _engine.streaming = False
    _engine.voice_mode = False
    _engine.voice_speaking = False
    _engine.stop()
    restore_character_input()
