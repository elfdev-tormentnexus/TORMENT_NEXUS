"""
Ask the running model server whether it reports per-token logprobs.

The vector panel's entropy strip has no data source without this, so it is
worth knowing before building the integration rather than after.

Requires TORMENT_NEXUS to be running -- the app is what starts the server.
Read-only: it sends one short completion and prints what came back.

    python tools/probe_logprobs.py
"""

import math
import os
import sys


sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assistant"),
)

import requests  # noqa: E402

from core.config import SERVER_URL, MODEL_REQUEST_HEADERS  # noqa: E402


BAR = "▁▂▃▄▅▆▇█"


def _entropy(logprobs):
    """Normalised 0..1 entropy over the reported candidates."""
    probabilities = [math.exp(item["logprob"]) for item in logprobs]
    total = sum(probabilities) or 1.0
    normalised = [p / total for p in probabilities]

    raw = -sum(p * math.log(p) for p in normalised if p > 0)
    ceiling = math.log(len(normalised)) if len(normalised) > 1 else 1.0

    return min(1.0, raw / ceiling)


def main():
    try:
        response = requests.post(
            SERVER_URL + "/v1/chat/completions",
            headers=MODEL_REQUEST_HEADERS,
            json={
                "messages": [{
                    "role": "user",
                    "content": "Say one short sentence about the weather.",
                }],
                "max_tokens": 24,
                "temperature": 0.8,
                "stream": False,
                "logprobs": True,
                # Entropy over only the top few candidates has a narrow
                # dynamic range. A wider window costs nothing and gives the
                # strip something to actually resolve.
                "top_logprobs": 10,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=90,
        )
    except requests.exceptions.ConnectionError:
        print(f"No server at {SERVER_URL}.")
        print("Start TORMENT_NEXUS first -- the app is what launches it.")
        return 1
    except Exception as error:
        print(f"Could not reach the server: {error}")
        return 1

    if response.status_code >= 400:
        print(f"Server returned {response.status_code}: {response.text[:300]}")
        return 1

    payload = response.json()["choices"][0]
    logprobs = payload.get("logprobs")

    if not logprobs or not logprobs.get("content"):
        print("NOT SUPPORTED -- this build returns no logprobs.")
        print("The entropy strip has no data source; the panel is cloud-only.")
        return 2

    print("LOGPROBS SUPPORTED\n")
    print(f"{'token':<14} {'entropy':>7}  {'':<10} nearly said instead")
    print("-" * 74)

    values = []
    overruled = 0

    for item in logprobs["content"]:
        alternatives = item.get("top_logprobs") or []

        if not item["token"].strip():
            # Stop and whitespace tokens are not decisions; they would sit
            # at zero and drag the strip's floor down.
            continue

        level = _entropy(alternatives) if len(alternatives) > 1 else 0.0
        values.append(level)

        # The sampled token is not always the most likely one -- that is the
        # whole point of a non-zero temperature. Drop it by identity rather
        # than assuming it sits at index 0, or the genuinely interesting
        # cases hide the candidate that actually lost.
        chosen = item["token"]
        others = [a["token"] for a in alternatives if a["token"] != chosen]
        was_overruled = bool(alternatives) and alternatives[0]["token"] != chosen
        overruled += int(was_overruled)

        bar = BAR[min(len(BAR) - 1, int(level * len(BAR)))] * 8
        mark = "*" if was_overruled else " "
        listed = ", ".join(repr(token) for token in others[:3])

        print(f"{repr(chosen):<14} {level:>7.2f} {mark}{bar:<10} {listed}")

    if not values:
        print("No scorable tokens came back.")
        return 2

    print("-" * 74)
    print(
        f"mean {sum(values) / len(values):.2f}   "
        f"peak {max(values):.2f}   "
        f"floor {min(values):.2f}   "
        f"spread {max(values) - min(values):.2f}"
    )
    print(f"{overruled} of {len(values)} tokens were not the top candidate (*)")
    print("\nTall bars are forks -- moments it nearly said something else.")
    print("That column is exactly what the panel's entropy strip renders.")
    print("A narrow spread means the strip needs display stretching to read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
