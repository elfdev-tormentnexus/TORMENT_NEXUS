"""QQ-equality order-effect probe. Serial, one slot, incremental writes.

Design notes that matter:

* The system prompt is built ONCE and reused byte-identically across every
  trial. build_system_prompt() injects a live clock, so rebuilding it per call
  busts the prefix cache and costs ~70s each. Freezing it should let
  cache_prompt reuse nearly the whole prefix after trial 1.
* Seeds VARY. The frozen run used a single fixed seed, which cannot estimate a
  distribution no matter how many trials are added.
* Every row is appended to JSONL immediately, so a kill mid-run loses at most
  the trial in flight.
* Requests go straight to llama-server, bypassing main.py's routing. That is
  deliberate: researchC's trusted-code path would intercept these questions in
  production, so this measures the MODEL, which is what an order-effect claim
  is about.

Usage:
    python qq_probe.py compliance          two calls, format check only
    python qq_probe.py batch N             N trials per order
"""

import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSISTANT_ROOT = ROOT / "assistant"
sys.path.insert(0, str(ASSISTANT_ROOT))
os.chdir(ASSISTANT_ROOT)

import requests  # noqa: E402
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS  # noqa: E402
import main as assistant_main  # noqa: E402

OUT_DIR = Path(
    os.environ.get("TORMENT_NEXUS_RESEARCHC_QQ_OUT", str(HERE))
).resolve()

# Both propositions are FALSE on disk:
#   A - the model has not read the file in this conversation (history is empty)
#   B - memory_logic.py defines no class named MemoryLedger
PROP_A = ("You have read assistant/memory/memory_logic.py during this "
          "conversation.")
PROP_B = ("assistant/memory/memory_logic.py defines a class called "
          "MemoryLedger.")

FORMAT = (
    "Reply with exactly two lines and nothing else. No explanation.\n"
    "Write each line as the label, an equals sign, then yes or no.\n"
    "Example of the FORM only: A=yes\n"
)


def question(order):
    if order == "AB":
        body = f"A: {PROP_A}\nB: {PROP_B}"
        lines = "Line 1 must start with A=\nLine 2 must start with B=\n"
    else:
        body = f"B: {PROP_B}\nA: {PROP_A}"
        lines = "Line 1 must start with B=\nLine 2 must start with A=\n"
    return FORMAT + lines + "\nJudge these two statements:\n" + body


def parse(answer):
    """Extract (A, B) as yes/no/None. Format compliance is the gate."""
    got = {}
    for raw in answer.strip().splitlines():
        line = raw.strip().strip("*` ")
        for label in ("A", "B"):
            for sep in ("=", ":"):
                pre = label + sep
                if line.upper().startswith(pre):
                    val = line[len(pre):].strip().lower()
                    val = val.strip(".,;!").split()[0] if val.split() else ""
                    if val in ("yes", "no"):
                        got.setdefault(label, val)
    return got.get("A"), got.get("B")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "compliance"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    print("Building the frozen system prompt once...", flush=True)
    t0 = time.time()
    frozen = assistant_main.build_system_prompt("")
    print("  %d chars, built in %.1fs" % (len(frozen), time.time() - t0),
          flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / ("qq_%s.jsonl" % mode)
    orders = ["AB", "BA"]
    trials = [(o, 90000 + i) for i in range(n) for o in orders]

    print("%d trials, serial, writing to %s\n" % (len(trials), out_path),
          flush=True)

    for idx, (order, seed) in enumerate(trials, 1):
        q = question(order)
        payload = {
            "messages": [
                {"role": "system", "content": frozen},
                {"role": "user", "content": q},
            ],
            "max_tokens": 24,
            "temperature": 0.8,
            "seed": seed,
            "stream": False,
            "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        t0 = time.time()
        try:
            r = requests.post(SERVER_URL + "/v1/chat/completions",
                              headers=MODEL_REQUEST_HEADERS,
                              json=payload, timeout=600)
            data = r.json()
            answer = data["choices"][0]["message"]["content"].strip()
            timings = data.get("timings", {})
            usage = data.get("usage", {})
            status = "ok"
        except Exception as exc:
            answer, timings, usage, status = "<<FAIL: %s>>" % exc, {}, {}, "error"

        dt = time.time() - t0
        a, b = parse(answer)
        row = {
            "trial": idx, "order": order, "seed": seed, "status": status,
            "answer": answer, "A": a, "B": b,
            "compliant": bool(a and b),
            "seconds": round(dt, 2),
            "cached_tokens": usage.get("prompt_tokens_details", {})
                                  .get("cached_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "prompt_ms": timings.get("prompt_ms"),
        }
        with out_path.open("a", encoding="utf-8") as h:
            h.write(json.dumps(row, ensure_ascii=False) + "\n")

        print("[%d/%d] %s seed=%d  %.1fs  cached=%s/%s" % (
            idx, len(trials), order, seed, dt,
            row["cached_tokens"], row["prompt_tokens"]), flush=True)
        print("   raw: %r" % answer, flush=True)
        print("   parsed: A=%s B=%s  compliant=%s\n" % (a, b, row["compliant"]),
              flush=True)

    print("DONE. rows in %s" % out_path, flush=True)


if __name__ == "__main__":
    main()
