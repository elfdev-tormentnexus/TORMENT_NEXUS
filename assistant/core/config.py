import os
import platform
import secrets
from urllib.parse import urlparse


ASSISTANT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_HOME = os.path.dirname(ASSISTANT_ROOT)
DUMP_FOLDER = os.path.join(PROJECT_HOME, "dump")


def _first_existing(paths):
    for path in paths:
        if os.path.isfile(path):
            return path

    return paths[0]


def _default_llama_server():
    binary = "llama-server.exe" if os.name == "nt" else "llama-server"
    base = os.path.join(PROJECT_HOME, "llama.cpp", "build", "bin")
    candidates = (
        (
            os.path.join(base, "Release", binary),
            os.path.join(base, binary),
        )
        if os.name == "nt"
        else (
            os.path.join(base, binary),
            os.path.join(base, "Release", binary),
        )
    )
    return _first_existing(candidates)


LLAMA_SERVER = (
    os.environ.get("TORMENT_NEXUS_LLAMA_SERVER", "").strip()
    or _default_llama_server()
)
MODEL_PATH = (
    os.environ.get("TORMENT_NEXUS_MODEL_PATH", "").strip()
    or os.path.join(
        PROJECT_HOME,
        "models",
        "Qwen3-4B-abliterated-bf16_q8_0.gguf",
    )
)

# What the UI header shows. Kept separate from MODEL_PATH's filename
# so the on-disk name can stay descriptive (matching what it was
# downloaded as) while the header shows a shorter label. Desktop profiles
# may override it without changing the shipped director model path.
MODEL_DISPLAY_NAME = (
    os.environ.get("TORMENT_NEXUS_MODEL_DISPLAY_NAME", "").strip()
    or "Qwen3-4B-Abliterated-Q8_0"
)

# Models have distinct jobs, but the authority boundary is still trusted Python
# code rather than a model's alignment behavior. An unknown explicit value is
# restricted instead of silently becoming the director.
MODEL_ROLE_DIRECTOR = "director"
MODEL_ROLE_AUTONOMOUS_CODER = "autonomous-coder"
MODEL_ROLE_FULL_MAINTENANCE = "full-maintenance"
MODEL_ROLE_RESTRICTED = "restricted"
MODEL_ROLES = {
    MODEL_ROLE_DIRECTOR,
    MODEL_ROLE_AUTONOMOUS_CODER,
    MODEL_ROLE_FULL_MAINTENANCE,
}
_configured_model_role = os.environ.get("TORMENT_NEXUS_MODEL_ROLE", "").strip().lower()
MODEL_ROLE = (
    _configured_model_role
    if _configured_model_role in MODEL_ROLES
    else (
        MODEL_ROLE_DIRECTOR
        if not _configured_model_role
        else MODEL_ROLE_RESTRICTED
    )
)
SERVER_URL = (
    os.environ.get("TORMENT_NEXUS_SERVER_URL", "").strip()
    or "http://127.0.0.1:8080"
).rstrip("/")
_SERVER_PARSED = urlparse(SERVER_URL)
SERVER_HOST = (
    os.environ.get("TORMENT_NEXUS_SERVER_HOST", "").strip()
    or _SERVER_PARSED.hostname
    or "127.0.0.1"
)

try:
    SERVER_PORT = _SERVER_PARSED.port or 8080
except ValueError:
    SERVER_PORT = 8080

# An explicit server identity prevents one launch profile from silently
# reusing another profile's authenticated model process on the same port.
# Leave this blank for the original single-profile launch behaviour.
SERVER_ALIAS = os.environ.get("TORMENT_NEXUS_SERVER_ALIAS", "").strip()


def _load_or_create_model_api_key():
    """
    Keep the loopback model API private from arbitrary browser pages.

    llama-server otherwise enables permissive CORS with no authentication,
    allowing a web page open on the same computer to submit requests to the
    local model. A persistent random key survives assistant restarts and can
    still be overridden explicitly for advanced setups.
    """
    configured = os.environ.get("TORMENT_NEXUS_MODEL_API_KEY", "").strip()

    if configured:
        return configured

    key_path = os.path.join(ASSISTANT_ROOT, ".model_api_key")

    try:
        with open(key_path, "r", encoding="utf-8") as key_file:
            stored = key_file.read().strip()

        if stored:
            os.environ["TORMENT_NEXUS_MODEL_API_KEY"] = stored
            return stored
    except FileNotFoundError:
        pass
    except OSError:
        # A read-only installation still works for this process; it simply
        # cannot reuse an orphaned authenticated server after a full restart.
        key_path = None

    generated = secrets.token_urlsafe(32)

    if key_path:
        try:
            descriptor = os.open(
                key_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )

            with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
                key_file.write(generated)
        except FileExistsError:
            with open(key_path, "r", encoding="utf-8") as key_file:
                generated = key_file.read().strip() or generated
        except OSError:
            pass

    os.environ["TORMENT_NEXUS_MODEL_API_KEY"] = generated
    return generated


MODEL_API_KEY = _load_or_create_model_api_key()
MODEL_REQUEST_HEADERS = {
    "Authorization": f"Bearer {MODEL_API_KEY}",
}
_MODEL_API_KEY_PATH = os.path.join(ASSISTANT_ROOT, ".model_api_key")

try:
    with open(_MODEL_API_KEY_PATH, "r", encoding="utf-8") as key_file:
        _stored_model_api_key = key_file.read().strip()
except OSError:
    _stored_model_api_key = ""

# Prefer llama.cpp's key-file option so the normal generated secret is not
# visible in a process listing. An environment-only override intentionally
# falls back to --api-key unless it exactly matches the protected file.
MODEL_API_KEY_FILE = (
    _MODEL_API_KEY_PATH
    if (
        _stored_model_api_key
        and secrets.compare_digest(_stored_model_api_key, MODEL_API_KEY)
    )
    else None
)

CORE_MEMORY_FILE = os.path.join(ASSISTANT_ROOT, "memory", "core_memory.txt")
MEMORY_FILE = os.path.join(ASSISTANT_ROOT, "memory", "memories.json")
HISTORY_FILE = os.path.join(ASSISTANT_ROOT, "memory", "conversation_history.txt")

# What the machine was seen doing, kept across restarts. This file records
# window titles, which routinely contain file names, URLs and message
# previews -- treat it with the same care as the conversation history. It is
# gitignored and carries a DENY_PATTERNS entry so it cannot reach a release.
ACTIVITY_FILE = os.path.join(ASSISTANT_ROOT, "memory", "activity_log.jsonl")

# Consent is separate from the observations themselves. A fresh installation
# has no file and therefore starts off; an operator who explicitly enables
# activity awareness keeps that choice across restarts until `activity off`.
ACTIVITY_CONSENT_FILE = os.path.join(
    ASSISTANT_ROOT,
    ".activity_consent.json",
)

# Observations older than this are dropped on load and on write. Long enough
# to notice a pattern across a fortnight, short enough that it is not a
# permanent record of everything ever done on this computer.
try:
    ACTIVITY_RETENTION_DAYS = max(
        0.0,
        min(365.0, float(
            os.environ.get("TORMENT_NEXUS_ACTIVITY_RETENTION_DAYS", "14")
        )),
    )
except ValueError:
    ACTIVITY_RETENTION_DAYS = 14.0

# Desktop-only research seam for a separate, owner-authorised Wi-Fi CSI
# experiment. It intentionally starts disabled and has no default file: the
# normal Windows Wi-Fi driver is never touched by TORMENT_NEXUS. When a future
# local collector is explicitly configured, it may write a short aggregate
# status record here; core.wifi_experimental rejects anything more detailed.
WIFI_EXPERIMENTAL_STATUS_FILE = os.environ.get(
    "TORMENT_NEXUS_WIFI_EXPERIMENT_FILE", ""
).strip()
WIFI_EXPERIMENTAL_ENABLED = (
    os.environ.get("TORMENT_NEXUS_WIFI_EXPERIMENT", "").strip().lower()
    in {"1", "true", "on", "yes"}
)
PROMPT_CACHE_DIR = (
    os.environ.get("TORMENT_NEXUS_PROMPT_CACHE_DIR", "").strip()
    or os.path.join(ASSISTANT_ROOT, "cache", "prompt")
)

# ------------------------------------------------------------------
# Semantic retrieval
#
# Memory retrieval here has always been literal word overlap, and the
# project has been honest about the cost: a memory phrased "the T-Deck mesh
# transmitter" shares no token with a question about "the radio", so it is
# discarded before ranking ever happens. memory_vectors.isolated() exists to
# count exactly those, and /memory/search labels its own results
# "word-overlap" so an empty answer reads as the finding rather than a fault.
#
# A second, tiny GGUF served by the same llama-server binary closes that gap
# without replacing what already works. Word overlap is good at the thing
# small embedders are bad at -- exact identifiers like Q5_K_M, 4090, PiSugar
# -- so the two are combined rather than swapped.
#
# There is no default model file, and no download. Absent one, every path
# below degrades to the old behaviour rather than erroring: this must stay
# true, because the Pi target has 8GB shared with a 4.6GB director and the
# operator decides what else gets resident.
EMBED_MODEL_PATH = os.environ.get("TORMENT_NEXUS_EMBED_MODEL_PATH", "").strip()

if not EMBED_MODEL_PATH:
    _embed_default = os.path.join(
        PROJECT_HOME,
        "models",
        "embedding",
        "bge-small-en-v1.5-q8_0.gguf",
    )
    EMBED_MODEL_PATH = _embed_default if os.path.isfile(_embed_default) else ""

# 8080 is the director and 8081 is SearXNG, so this is the next one free.
EMBED_SERVER_URL = (
    os.environ.get("TORMENT_NEXUS_EMBED_SERVER_URL", "").strip()
    or "http://127.0.0.1:8082"
).rstrip("/")
_EMBED_PARSED = urlparse(EMBED_SERVER_URL)
EMBED_SERVER_HOST = _EMBED_PARSED.hostname or "127.0.0.1"

try:
    EMBED_SERVER_PORT = _EMBED_PARSED.port or 8082
except ValueError:
    EMBED_SERVER_PORT = 8082

# machinespirit: the second, UNPOOLED embedding server.
#
# llama.cpp fixes pooling at launch, so a per-token trajectory cannot come
# from the pooled instance above -- it has to be a separate process started
# with `--pooling none`. That is what the hazard launcher starts, and it is
# cheap: the same 36 MB model a second time, against the director's
# gigabytes.
#
# Empty by default. Nothing starts this on the operator's behalf, and when
# it is absent every machinespirit entry point reports unavailable rather
# than falling back to the pooled server, which would silently return a
# single point where a path was asked for.
MACHINESPIRIT_URL = os.environ.get(
    "TORMENT_NEXUS_MACHINESPIRIT_URL", "").strip().rstrip("/")
MACHINESPIRIT_KEY = os.environ.get(
    "TORMENT_NEXUS_MACHINESPIRIT_KEY", "").strip()

# The operator can switch this off even with a model present, because a
# second resident model is a memory decision and not only a feature one.
EMBED_ENABLED = (
    bool(EMBED_MODEL_PATH)
    and os.environ.get("TORMENT_NEXUS_EMBED", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)

# Embeddings are computed once per memory and reused forever, so the cache
# is the thing that keeps this off the chat path entirely. It is keyed by
# model identity as well as text: swapping the embedder must not silently
# leave the old model's geometry in place, because nothing downstream could
# tell that the numbers no longer mean the same thing.
EMBED_CACHE_FILE = os.path.join(ASSISTANT_ROOT, "cache", "embeddings.json")

# How alike a zero-word-overlap memory must be to the question before
# semantic similarity is even eligible for automatic prompt injection.
#
# The original five-pair probe suggested 0.38, but a broader 30-pair audit
# showed that threshold admitted many unrelated memories. Automatic
# retrieval now requires at least 0.55 *and* a 0.06 lead over the runner-up,
# and it contributes at most one semantic-only memory. Explicit searches use
# a separately labelled best-first ranking. Recalibrate both requirements if
# the embedding model changes; the geometry belongs to the model.
try:
    EMBED_MIN_COSINE = max(
        0.0,
        min(1.0, float(os.environ.get("TORMENT_NEXUS_EMBED_MIN_COSINE", "0.55"))),
    )
except ValueError:
    EMBED_MIN_COSINE = 0.55

# A small embedder answers in single-digit milliseconds on CPU, but the
# request still crosses a socket. This bounds a stall rather than allowing
# a wedged server to hold up a reply.
try:
    EMBED_TIMEOUT_SECONDS = max(
        0.5,
        min(30.0, float(os.environ.get("TORMENT_NEXUS_EMBED_TIMEOUT", "6"))),
    )
except ValueError:
    EMBED_TIMEOUT_SECONDS = 6.0

# Conversation history is written for the prompt's trailing-slice budget,
# not for recall. Embedding whole exchanges makes "what did we decide about
# the packager" answerable from a file that is currently write-only.
HISTORY_RECALL_ENABLED = (
    os.environ.get("TORMENT_NEXUS_HISTORY_RECALL", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
try:
    HISTORY_RECALL_LIMIT = max(
        0,
        min(5, int(os.environ.get("TORMENT_NEXUS_HISTORY_RECALL_LIMIT", "2"))),
    )
except ValueError:
    HISTORY_RECALL_LIMIT = 2

# Audio files here play with no network, no account, and no Spotify.
# Whatever is dropped in becomes a track named after its filename.
MUSIC_LIBRARY_DIR = os.path.join(ASSISTANT_ROOT, "music")

# llama-server's own stdout/stderr gets piped here instead of your
# terminal, so its timing logs stop shredding the UI. Check this file
# if the server misbehaves.
SERVER_LOG_FILE = os.path.join(ASSISTANT_ROOT, "logs", "llama_server.log")

# Master switch for all the DEBUG / rejection-reason chatter.
# Flip to True when you're debugging the memory pipeline.
DEBUG = False

# Show "[Memory Saved]" confirmations during chat. Rejections and
# duplicates stay quiet unless DEBUG is on.
SHOW_MEMORY_EVENTS = True

# A full autonomous cycle makes multiple model requests and can take
# noticeably longer on the target Pi. Running it before chat made the
# app look as if its keyboard was broken because the input loop did
# not exist yet. Keep startup responsive by default; autonomy remains
# available through "run autonomous cycle". Set the environment
# variable to 1 only when deliberately opting back into startup runs.
AUTONOMOUS_ON_STARTUP = (
    os.environ.get("TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP", "").strip() == "1"
)


def _bounded_int_env(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)).strip())
    except ValueError:
        value = default

    return max(minimum, min(maximum, value))


# Context window passed to llama-server (-c). Shared with main.py's
# prompt-budget accounting so the two can never drift out of sync.
#
# Raised from 4096 after the identity and honesty rules grew: the system
# prompt alone was taking 53% of the window, and a small model spending
# half its attention on instructions answers correctly but blandly --
# every reply became "How may I assist you today?". Doubling the window
# costs roughly 600MB of KV cache and drops the prompt to about a fifth
# of it, which leaves room for the conversation to have a shape.
#
# Drop this back to 4096 on the Pi, where the memory matters more than
# the headroom does.
CONTEXT_SIZE = _bounded_int_env(
    "TORMENT_NEXUS_CONTEXT_SIZE",
    8192,
    2048,
    8192,
)

# Max tokens per assistant reply. This is a ceiling, not a requested length;
# raising it prevents useful answers from being cut off while short replies
# still stop naturally. It remains configurable for slower Pi deployments.
MAX_TOKENS = _bounded_int_env(
    "TORMENT_NEXUS_MAX_TOKENS",
    420,
    128,
    min(1024, CONTEXT_SIZE // 2),
)

# The base Qwen3 hybrid models emit <think> reasoning blocks unless
# told not to. Qwen3-4B-Instruct-2507 is the dedicated non-thinking
# release and shouldn't emit them at all, but this is left on (the
# template just ignores the unused kwarg) as a no-cost guard in case
# the model is ever swapped back to a thinking/hybrid variant. The
# <think> stripper in main.py stays as a backstop either way.
QWEN_NO_THINK = True

# Which backend web/search_engine.py dispatches to -- "searxng" or
# "brave". Lets the assistant answer questions that need current
# information (see web/search_engine.py, web/search_intent.py).
SEARCH_BACKEND = (
    os.environ.get("TORMENT_NEXUS_SEARCH_BACKEND", "").strip().lower()
    or "searxng"
)

# Self-hosted SearXNG (see searxng/docker-compose.yml at the project
# root). Port 8081, not 8080 -- that's already SERVER_URL above.
SEARXNG_URL = (
    os.environ.get("TORMENT_NEXUS_SEARXNG_URL", "").strip()
    or "http://127.0.0.1:8081"
).rstrip("/")

# Brave Search API. Get a key at
# https://api-dashboard.search.brave.com/register and set a spending
# cap in the dashboard; the account itself has none by default. Left
# blank until configured -- search_engine_brave.search() refuses
# cleanly rather than erroring when this is empty. Kept around so
# switching SEARCH_BACKEND back to "brave" later doesn't need
# rewiring, just a key.
BRAVE_API_KEY = os.environ.get("TORMENT_NEXUS_BRAVE_API_KEY", "").strip()
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

_MACHINE = platform.machine().lower()
_DEFAULT_LLAMA_THREADS = 4 if _MACHINE in {"aarch64", "arm64"} else None

try:
    _configured_threads = os.environ.get("TORMENT_NEXUS_LLAMA_THREADS", "").strip()
    LLAMA_THREADS = (
        max(1, min(32, int(_configured_threads)))
        if _configured_threads
        else _DEFAULT_LLAMA_THREADS
    )
except ValueError:
    LLAMA_THREADS = _DEFAULT_LLAMA_THREADS


def _optional_bounded_int_env(name, minimum, maximum):
    raw = os.environ.get(name, "").strip()

    if not raw:
        return None

    try:
        value = int(raw)
    except ValueError:
        return None

    return max(minimum, min(maximum, value))


# Unset deliberately means "do not pass -ngl" so the existing CPU/Pi launch
# remains unchanged. Desktop profiles set this explicitly: 99 for the 4B
# companion, and the measured 16 for the 7B Q8 maintenance model.
LLAMA_GPU_LAYERS = _optional_bounded_int_env(
    "TORMENT_NEXUS_LLAMA_GPU_LAYERS",
    0,
    999,
)

_configured_flash_attn = os.environ.get(
    "TORMENT_NEXUS_LLAMA_FLASH_ATTN",
    "",
).strip().lower()
LLAMA_FLASH_ATTN = (
    _configured_flash_attn
    if _configured_flash_attn in {"on", "off", "auto"}
    else None
)
LLAMA_CACHE_TYPE_K = os.environ.get(
    "TORMENT_NEXUS_LLAMA_CACHE_TYPE_K",
    "",
).strip().lower() or None
LLAMA_CACHE_TYPE_V = os.environ.get(
    "TORMENT_NEXUS_LLAMA_CACHE_TYPE_V",
    "",
).strip().lower() or None

LLAMA_CACHE_RAM_MB = _bounded_int_env(
    "TORMENT_NEXUS_LLAMA_CACHE_RAM_MB",
    256,
    64,
    1024,
)

# Dedicated offline voice mode. The one-time setup_voice script downloads a
# compact Moonshine recognizer, Silero voice detector, and Piper voice beneath
# models/voice. Optional device values may be a numeric sounddevice index or a
# device-name string; leaving them blank uses the operating system defaults.
VOICE_MODEL_ROOT = os.path.join(PROJECT_HOME, "models", "voice")
VOICE_ON_STARTUP = (
    os.environ.get("TORMENT_NEXUS_START_IN_VOICE_MODE", "0").strip().lower()
    not in {"0", "false", "off", "no", "text"}
)
VOICE_ASR_DIR = os.path.join(
    VOICE_MODEL_ROOT,
    "sherpa-onnx-moonshine-tiny-en-int8",
)
VOICE_VAD_MODEL = os.path.join(VOICE_MODEL_ROOT, "silero_vad.onnx")
# Chosen by measurement, not by name. voice_training/screen_voices.py scored
# 1014 candidates against the reference recording; this speaker ranked 2nd
# overall and 1st on the property that decided it -- it sits at 149.8 Hz
# natively against a 149.5 Hz target, so it needs essentially no pitch
# correction at all.
#
# That matters beyond pitch. Correction is applied by resampling, which also
# stretches time and drags formants down, and those side effects are what
# produced both the slow-motion delivery and the over-dark timbre earlier.
# A voice that starts on target pays none of it.
#
# For reference, the previous voice (en_US-hfc_female-medium) placed 1010th
# of 1014: 4.54st pitch variation against this one's 1.79st, and a 7.10st
# stress-peak against 2.64st. It is an expressive, bright voice that was
# being asked to sound bored.
VOICE_TTS_NAME = (
    os.environ.get("TORMENT_NEXUS_PIPER_VOICE", "").strip()
    or "en_US-hfc_female-medium"
)

# Which speaker inside a multi-speaker model. Ignored (and must be None) for
# single-speaker voices such as hfc_female or lessac.
try:
    _speaker = os.environ.get("TORMENT_NEXUS_PIPER_SPEAKER", "").strip()
    VOICE_TTS_SPEAKER = int(_speaker) if _speaker else None
except ValueError:
    VOICE_TTS_SPEAKER = None
VOICE_TTS_MODEL = os.path.join(
    VOICE_MODEL_ROOT,
    "piper",
    VOICE_TTS_NAME + ".onnx",
)

# Piper remains responsible for articulation, pitch, and feminine source
# timbre. Ordinary machine cadence uses direct variable-speed resampling with
# no vocoder. Set TORMENT_NEXUS_ROBOT_VOICE=0 for untouched Piper output, or tune
# the overall cadence depth from 0.0 to 1.0 with the strength variable.
VOICE_ROBOT_ENABLED = (
    os.environ.get("TORMENT_NEXUS_ROBOT_VOICE", "1").strip().lower()
    not in {"0", "false", "off", "none", "clean"}
)

try:
    VOICE_ROBOT_STRENGTH = max(
        0.0,
        min(
            1.0,
            float(
                os.environ.get(
                    "TORMENT_NEXUS_ROBOT_STRENGTH",
                    "0.94",
                )
            ),
        ),
    )
except ValueError:
    VOICE_ROBOT_STRENGTH = 0.94

# A modest formant lift keeps the fixed carrier from pulling the chosen voice
# toward an androgynous or masculine register.  It applies to speech and Daisy
# alike, while the carrier itself handles the separate pitch contour.
try:
    VOICE_ROBOT_FORMANT_SHIFT = max(
        0.85,
        min(
            1.25,
            float(
                os.environ.get(
                    "TORMENT_NEXUS_ROBOT_FORMANT_SHIFT",
                    "1.12",
                )
            ),
        ),
    )
except ValueError:
    VOICE_ROBOT_FORMANT_SHIFT = 1.12

# A restrained set of asymmetric note plateaus gives ordinary replies a
# deliberate machine cadence. The speech vocoder snaps each plateau to a
# chromatic grid, so this controls only deliberate group-to-group movement;
# it cannot reintroduce within-syllable pitch wobble. A value of 0 disables
# those deliberate steps entirely.
try:
    VOICE_CADENCE_STRENGTH = max(
        0.0,
        min(
            1.0,
            float(
                os.environ.get(
                    "TORMENT_NEXUS_CADENCE_STRENGTH",
                    "0.35",
                )
            ),
        ),
    )
except ValueError:
    VOICE_CADENCE_STRENGTH = 0.35

# Very low variation and slower phoneme timing give ordinary replies a
# deliberately controlled delivery before the cadence resampler changes the
# duration of individual speech groups. The short explicit gap combines with
# Piper's punctuation timing to approximate the measured reference pacing.
# Constant semitone shift for the whole speaking voice, negative for a
# colder/deeper register. Applied through the same variable-speed resampler
# the cadence uses, so no vocoder or phase vocoder is involved and the
# shimmer that a fixed carrier produced does not come back.
#
# +12 semitones -- a full octave up, chosen by ear over the measurements.
#
# The reference recording sits at ~150 Hz, and that was re-verified four
# ways (varying the pitch-search floor, isolating the loudest speech, and
# high-passing above 150 Hz) after the low result looked suspicious; every
# method agreed, so it is not a measurement artifact. Shifting *down* to
# meet it is therefore the numerically faithful choice -- and it is the one
# that was rejected, because it reads as male. Formants cannot be held well
# enough through a large downward shift, so the voice slid between
# androgynous and male depending on the phoneme.
#
# Going up avoids that entirely and is also the better-conditioned
# direction for PSOLA: raising pitch packs grains closer together, so their
# overlap increases rather than thinning, which is what caused the
# inconsistency on the way down.
#
# So this deliberately sits far from the reference number while being
# closer to the intent. Do not "correct" it back toward 150 Hz on the
# strength of the measurements alone.
try:
    VOICE_PITCH_SEMITONES = max(
        -12.0,
        min(
            12.0,
            float(os.environ.get("TORMENT_NEXUS_PITCH_SEMITONES", "5.0")),
        ),
    )
except ValueError:
    VOICE_PITCH_SEMITONES = 5.0

# How slow the delivery should actually sound, as a multiple of the voice's
# natural rate. This is the number to tune -- 1.0 is normal, higher is more
# deliberate.
#
# It is NOT passed to Piper directly. Lowering the pitch is done by reading
# the waveform slower, so VOICE_PITCH_SEMITONES already stretches time on
# its own: at -5 semitones that is a 1.33x stretch before Piper's own
# length_scale is applied at all. Setting both by hand meant they multiplied
# -- 1.90 x 1.33 came out at 2.54x, which sounded like slow motion rather
# than like an unhurried speaker. Deriving one from the other keeps the
# audible pace stable no matter how far the pitch is dialled.
# Ordinary speech follows the unhurried pace of the Daisy performance.  This
# is intentionally applied at synthesis time, before the fixed-carrier voice
# shaping, so its cadence remains stable and intelligible instead of becoming
# a crude post-playback time stretch.  It can still be tuned without code.
try:
    VOICE_SPEECH_PACE = max(
        0.70,
        min(2.00, float(os.environ.get("TORMENT_NEXUS_SPEECH_PACE", "1.50"))),
    )
except ValueError:
    VOICE_SPEECH_PACE = 1.50

# How much longer voiced sounds are held, applied in voice/offline_voice.py
# by PSOLA. Consonants keep their original attack, so the result reads as
# synthesised rather than merely slow. 1.0 is off; 1.6 makes vowels about
# half again as long.
try:
    VOICE_VOWEL_STRETCH = max(
        1.0,
        min(3.0, float(os.environ.get("TORMENT_NEXUS_VOWEL_STRETCH", "1.6"))),
    )
except ValueError:
    VOICE_VOWEL_STRETCH = 1.6

# No compensation term any more. The register shift is done by PSOLA
# (voice/offline_voice.py), which preserves duration exactly, so pace is
# now just pace. This used to divide out the time stretch that resampling
# imposed -- resampling lowered pitch *by* reading slower, which is what
# made the delivery sound like slow motion once the two multiplied.
VOICE_SPEECH_LENGTH_SCALE = max(0.5, VOICE_SPEECH_PACE)
VOICE_SPEECH_NOISE_SCALE = 0.04
VOICE_SPEECH_NOISE_W_SCALE = 0.035
# Silence inserted after a sentence ends.
#
# The reference recording measured a 0.51s median between phrases, and
# 0.45 was set to match it. That was then raised to 0.72 because the
# vocoder's flat pitch removed the falling intonation that normally signals
# an ending, and the pause had to carry that on its own.
#
# The voice now has that fall: each spoken chunk carries its own declination
# and a tail drop, measured at about 1.2 semitones from the first half of a
# sentence to the second. The compensation is no longer needed, and holding
# it produced 18 pauses over half a second per minute against the
# reference's 6, which reads as hesitant rather than deliberate.
try:
    VOICE_SPEECH_PAUSE_SECONDS = max(
        0.0,
        min(3.0, float(os.environ.get("TORMENT_NEXUS_PAUSE_SECONDS", "0.52"))),
    )
except ValueError:
    VOICE_SPEECH_PAUSE_SECONDS = 0.52

# Silence inserted where a long sentence had to be split mid-way.
#
# Those breaks land on an arbitrary word boundary, not a real clause end,
# so giving them the full sentence pause invents a full stop that the text
# never had. Short enough to read as drawing breath rather than finishing
# a thought.
try:
    VOICE_SPEECH_CLAUSE_PAUSE_SECONDS = max(
        0.0,
        min(2.0, float(os.environ.get("TORMENT_NEXUS_CLAUSE_PAUSE", "0.16"))),
    )
except ValueError:
    VOICE_SPEECH_CLAUSE_PAUSE_SECONDS = 0.16

# Route ordinary speech through the same vocoder the sung Daisy Bell
# performance uses, instead of PSOLA.
#
# This is the only approach available here that separates pitch from
# formants. A fixed oscillator carrier provides the pitch while the
# spectral envelope -- and therefore the perceived vocal tract and gender
# -- comes from the Piper voice. Resampling and PSOLA both move the two
# together, which is why every attempt to lower the register with them
# drifted toward sounding male.
#
# Its carrier remains cold and tightly constrained.  A shallow energy-derived
# step contour is still applied in the vocoder itself so longer sentences keep
# the deliberate machine cadence without becoming melodic.
VOICE_SPEECH_VOCODER = (
    os.environ.get("TORMENT_NEXUS_SPEECH_VOCODER", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)

# Pitch of that carrier, in Hz. The reference recordings measured 130.6
# and 149.5; the sung path defaults to 172.  The vocoder snaps the resulting
# carrier (including its small phrase offsets) to a chromatic pitch grid,
# which suppresses within-syllable pitch modulation while retaining deliberate
# note-to-note steps between speech groups.
#
# The live path gives each sentence its own stable chromatic pitch bias, so a
# monolithic render does not represent actual playback.  This value anchors
# that chromatic grid; it is not assumed to equal the measured output F0,
# because the vocal-tract envelope can lead a pitch tracker toward a nearby
# harmonic.  Keep it close to the measured register and validate a full live
# reply when tuning it.  Because the vocoder decouples pitch from the spectral
# envelope, moving the carrier alone shifts register without making the voice
# sound like a smaller speaker.
try:
    VOICE_SPEECH_CARRIER_HZ = max(
        60.0,
        min(400.0, float(os.environ.get("TORMENT_NEXUS_CARRIER_HZ", "168.0"))),
    )
except ValueError:
    VOICE_SPEECH_CARRIER_HZ = 168.0

# ------------------------------------------------------------------
# Idle check-in
#
# After a long silence the assistant checks whether anyone is still there,
# then shuts down cleanly if nobody answers. The check is visual by default:
# unsolicited speech is startling when the app has been quiet in the
# background. It can be opted back in explicitly.
#
# The shutdown is the point: a local model holds gigabytes of RAM, and a
# session left open overnight keeps all of it. Asking first, rather than
# closing on a timer alone, means the machine is never reclaimed out
# from under someone who simply went quiet for a while.
#
# Echo every read-only agent-interface call into the chat area as it
# happens. On by default: the interface is already token-gated, host-checked
# and logged to agent_api.jsonl, and being able to watch it live is the
# difference between an audit trail you could read and one you do. Set
# TORMENT_NEXUS_AGENT_WATCH=0 for a quiet transcript during a long agent
# session; the log is written either way.
AGENT_WATCH = (
    os.environ.get("TORMENT_NEXUS_AGENT_WATCH", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)


# Set TORMENT_NEXUS_IDLE_CHECKIN=0 to disable both the prompt and the exit.
IDLE_CHECKIN_ENABLED = (
    os.environ.get("TORMENT_NEXUS_IDLE_CHECKIN", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
IDLE_CHECKIN_SPEAK = (
    os.environ.get("TORMENT_NEXUS_IDLE_SPEAK", "0").strip().lower()
    in {"1", "true", "on", "yes"}
)

# Silence before the check-in. Minimum 60s so a misconfiguration cannot
# turn this into something that interrupts an ordinary pause.
IDLE_CHECKIN_SECONDS = _bounded_int_env(
    "TORMENT_NEXUS_IDLE_SECONDS",
    300,
    60,
    24 * 60 * 60,
)

# Grace period after the spoken question, measured from when the speech
# finishes rather than when it starts -- otherwise a long sentence eats
# most of the window it is asking about.
IDLE_RESPONSE_SECONDS = _bounded_int_env(
    "TORMENT_NEXUS_IDLE_RESPONSE_SECONDS",
    60,
    15,
    60 * 60,
)


# How much of Piper's natural pitch movement to keep. 1.0 keeps all of it,
# 0.0 is perfectly monotone.
#
# This is the setting that finally addresses "not flat enough". Measured
# against the reference: GLaDOS sits at 2.43st pitch deviation and holds
# pitch completely static across 82% of frames, while untouched Piper runs
# 5-6st. Every earlier attempt failed because the stepped-cadence layer
# only *added* movement on top of Piper's contour and never suppressed it.
# 0.45 was chosen to land near the measured 2.43st target.
try:
    VOICE_PITCH_FLATTEN = max(
        0.0,
        min(1.0, float(os.environ.get("TORMENT_NEXUS_PITCH_FLATTEN", "0.45"))),
    )
except ValueError:
    VOICE_PITCH_FLATTEN = 0.45
# Keyed by voice and speaker. The cached performance is minutes of audio
# rendered in whatever voice was active when it was built, so a fixed
# filename would keep serving the old singer indefinitely after a voice
# change -- silently, since the cache is only checked for existence.
_DAISY_VOICE_KEY = VOICE_TTS_NAME + (
    "" if VOICE_TTS_SPEAKER is None else f"-spk{VOICE_TTS_SPEAKER}"
)

try:
    VOICE_DAISY_ACCOMPANIMENT_GAIN = max(
        0.10,
        min(
            1.20,
            float(
                os.environ.get(
                    "TORMENT_NEXUS_DAISY_ACCOMPANIMENT_GAIN",
                    "1.10",
                )
            ),
        ),
    )
except ValueError:
    VOICE_DAISY_ACCOMPANIMENT_GAIN = 1.10

VOICE_DAISY_CACHE = os.path.join(
    VOICE_MODEL_ROOT,
    "cache",
    "daisy_bell_machine_v11_"
    f"mix{int(round(VOICE_DAISY_ACCOMPANIMENT_GAIN * 100))}_"
    f"{_DAISY_VOICE_KEY}.wav",
)

VOICE_SAMPLE_RATE = 16_000

try:
    VOICE_INPUT_CHANNELS = max(
        1,
        min(2, int(os.environ.get("TORMENT_NEXUS_INPUT_CHANNELS", "1"))),
    )
except ValueError:
    VOICE_INPUT_CHANNELS = 1

try:
    VOICE_NUM_THREADS = max(
        1,
        min(4, int(os.environ.get("TORMENT_NEXUS_VOICE_THREADS", "2"))),
    )
except ValueError:
    VOICE_NUM_THREADS = 2

VOICE_INPUT_DEVICE = os.environ.get("TORMENT_NEXUS_INPUT_DEVICE", "").strip() or None
VOICE_OUTPUT_DEVICE = os.environ.get("TORMENT_NEXUS_OUTPUT_DEVICE", "").strip() or None
