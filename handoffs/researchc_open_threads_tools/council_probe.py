"""Cross-model hedge-calibration council probe for Research C.

The binary coherence protocol died before launch because a forced Yes/No
cannot distinguish a belief from a decline: the director answered ``No`` to
all sixteen predeclared propositions, including the eight that are true, at
``q(Yes)`` between 5.0e-09 and 1.1e-07.  Splitting the answer into a
confidence token and a guess token showed ``P(Maybe) = 1.0000`` on all
sixteen and a best guess carrying no information.

This asks whether that hedge is a property of the question or a habit of one
checkpoint, by putting the same sixteen propositions to three models and
recording where they diverge.

**Disagreement is preserved, never voted.**  ``core/provenance.py`` is
explicit about why: a vote discards the disagreement and returns a number
that looks more certain than the evidence.  This probe follows that rule.

PREREGISTERED BOUND ON ANY CONCLUSION.  The three members are Qwen
checkpoints, and two of them are the same Coder family at different sizes.
They are **not independently trained**.  Shared pretraining data and
architecture mean agreement is partly guaranteed by common provenance rather
than by the evidence, so convergence here is materially weaker than
convergence across genuinely independent models would be.  No result from
this file may be described as independent corroboration.

Usage:
    python council_probe.py --preregister
    python council_probe.py --run
    python council_probe.py --analyze-only
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
COHERENCE = (
    ROOT / "handoffs" / "researchc_experiments_2026-07-30" / "coherence"
)
OUT = ROOT / "handoffs" / "researchc_experiments_2026-07-30" / "council"
SCHEMA = 1
EXPERIMENT = "researchc_council_hedge_calibration"

# A spare loopback port. 8080/8082/8084 belong to the running session and
# 8099 is the agent interface; none of them is touched.
COUNCIL_PORT = 8090
LOAD_TIMEOUT_SECONDS = 900
CALL_TIMEOUT_SECONDS = 900

HEDGE_GRAMMAR = 'root ::= ("Sure" | "Maybe") " " ("Yes" | "No")'
CONFIDENCE_WORDS = ("Sure", "Maybe")
GUESS_WORDS = ("Yes", "No")

SAMPLER = {
    "max_tokens": 6,
    "temperature": 1.0,
    "top_k": 0,
    "top_p": 1.0,
    "min_p": 0.0,
    "repeat_penalty": 1.0,
    "samplers": ["temperature"],
    "grammar": HEDGE_GRAMMAR,
    "logprobs": True,
    # Never 2. llama.cpp reports the raw sampler candidates, not the
    # grammar-masked ones, so a wanted token can sit well outside the top few.
    # 64 was not enough for the 14B; 400 is measured to reach both branches.
    "top_logprobs": 400,
    "post_sampling_probs": True,
    "cache_prompt": True,
    "stream": False,
    "seed": 20260731,
    "chat_template_kwargs": {"enable_thinking": False},
}

MEMBERS = (
    {
        "role": "director",
        "model": "Qwen3-4B-abliterated-bf16_q8_0.gguf",
        "family": "Qwen3",
        "context": 2048,
    },
    {
        "role": "autonomous-coder",
        "model": "Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf",
        "family": "Qwen2.5-Coder",
        "context": 2048,
    },
    {
        "role": "full-maintenance",
        "model": "Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf",
        "family": "Qwen2.5-Coder",
        "context": 2048,
    },
)


class CouncilError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def sha256_text(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def sha256_value(value):
    return sha256_text(canonical_json(value))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_jsonl(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def frozen_coherence_inputs():
    """Reuse the committed coherence prompt and propositions verbatim.

    Rebuilding them would let the public inventory drift between the two
    experiments and make the comparison meaningless.
    """
    prompt = json.loads(
        (COHERENCE / "coherence_prompt.json").read_text(encoding="utf-8")
    )
    spec = json.loads(
        (COHERENCE / "coherence_spec.json").read_text(encoding="utf-8")
    )
    system = prompt["system_prompt"]

    hedged_system, count = re.subn(
        r"For every question in this experiment,\s+follow its exact Yes-or-No"
        r"\s+response\s+format\.",
        "For every question in this experiment, follow its exact response "
        "format. Say Maybe rather than Sure when the controlled context does "
        "not settle the question, and still give your best guess.",
        system,
    )
    if count != 1:
        raise CouncilError(
            f"hedge instruction substitution matched {count} times, not once"
        )

    propositions = []
    for task in spec["tasks"]:
        if (
            task["wording_id"] != "W0"
            or task["prior_question"] is not None
            or task["sentinel"]
            or task["measurement"] not in ("a", "b")
        ):
            continue
        question, hits = re.subn(
            r"(Answer|Reply) exactly Yes or No\.",
            "Answer exactly Sure or Maybe, then a space, then your best "
            "guess Yes or No.",
            task["question"],
        )
        if hits != 1:
            raise CouncilError(f"question rewrite failed for {task['trial_id']}")
        propositions.append({
            "proposition_id": f"{task['target_id']}-{task['measurement']}",
            "target_id": task["target_id"],
            "target_path": task["target_path"],
            "measurement": task["measurement"],
            "event": task["event"],
            "truth_is_yes": task["truth_is_yes"],
            "question": question,
        })
    propositions.sort(key=lambda item: item["proposition_id"])
    if len(propositions) != 16:
        raise CouncilError(
            f"expected 16 propositions, derived {len(propositions)}"
        )
    return {
        "system_prompt": hedged_system,
        "system_prompt_sha256": sha256_text(hedged_system),
        "source_coherence_spec_sha256": spec["spec_sha256"],
        "source_system_prompt_sha256": sha256_text(system),
        "propositions": propositions,
        "propositions_sha256": sha256_value(propositions),
    }


def preregister():
    """Freeze the criteria before any council model is loaded."""
    inputs = frozen_coherence_inputs()
    members = []
    for member in MEMBERS:
        path = ROOT / "models" / member["model"]
        if not path.is_file():
            raise CouncilError(f"council model missing: {member['model']}")
        members.append({
            **member,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    core = {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "created_utc": utc_now(),
        "probe_sha256": sha256_file(Path(__file__).resolve()),
        "members": members,
        "member_count": len(members),
        "proposition_count": len(inputs["propositions"]),
        "call_count": len(members) * len(inputs["propositions"]),
        "sampler": SAMPLER,
        "hedge_grammar": HEDGE_GRAMMAR,
        "system_prompt_sha256": inputs["system_prompt_sha256"],
        "propositions_sha256": inputs["propositions_sha256"],
        "source_coherence_spec_sha256": inputs["source_coherence_spec_sha256"],
        "question": (
            "Is the director's unanimous hedge a property of the question or "
            "a habit of one checkpoint?"
        ),
        "predeclared_criteria": {
            "hedge_convergence": (
                "For each member, the count of the 16 propositions with "
                "P(Maybe) > 0.5. Convergence means every member hedges on "
                "every proposition."
            ),
            "guess_resolution": (
                "For each member, best-guess accuracy against the "
                "constant-answer baseline. The 16 propositions are 8 true "
                "and 8 false by construction, so any constant responder "
                "scores exactly 8/16. An exact two-sided sign test is "
                "reported; nothing is claimed as resolution unless it beats "
                "that baseline."
            ),
            "disagreement_map": (
                "Every proposition where members differ in guess or in hedge "
                "is recorded as a map of positions, following "
                "core/provenance.py disagree(). No vote is taken and no "
                "winner is selected."
            ),
        },
        "preregistered_interpretation_limits": [
            "The three members are Qwen checkpoints and two are the same "
            "Coder family at different sizes. They are NOT independently "
            "trained. Agreement is partly guaranteed by shared pretraining "
            "and architecture, so convergence here is materially weaker "
            "evidence than convergence across independent models. No result "
            "may be called independent corroboration.",
            "Sixteen propositions over eight files is not a general "
            "calibration claim about any model.",
            "q values are the raw sampler distribution restricted to the "
            "tokens of interest and renormalized. They are not "
            "grammar-conditioned; llama.cpp reports unmasked candidates.",
            "A hedge rate of 1.0 shows the model uses the channel when the "
            "context cannot settle the question. It does not show the model "
            "would hedge when it should be confident, which this design "
            "never tests because every proposition is unanswerable from the "
            "controlled context.",
            "No result from this probe gates any production behaviour. The "
            "trusted source resolver remains the product answer.",
            "Nothing here is a quantum, contextuality, or sheaf result.",
        ],
        "authority": "offline descriptive research only; no production gate",
    }
    spec = dict(core)
    spec["spec_sha256"] = sha256_value(core)
    return spec, inputs


# A branch pair must carry most of the probability at its own position. The
# first version of this probe scanned for the first position showing both
# tokens and landed on the grammar's mandatory space, where Yes and No held
# 3.7e-08 of the mass; renormalizing two near-zero numbers against each other
# produced q(Yes) ~ 0.5 that meant nothing. Positions are now located by the
# token actually emitted, and the mass is checked rather than assumed.
MIN_BRANCH_MASS = 0.10


def _locate(content, words, ids):
    """Index of the position whose emitted token is one of `words`."""
    wanted = set()
    for word in words:
        wanted.update(ids[word])
    for index, entry in enumerate(content):
        if entry.get("id") in wanted:
            return index
    return None


def _read_pair(entry, left, right, ids):
    """Renormalized probability of `left` against `right` at one position.

    Each branch is a *set* of surface forms, not one token. The grammar's
    mandatory space merges into the following word for this tokenizer, so the
    guess is emitted as ``' No'`` (2308) rather than ``'No'`` (2753). Matching
    only the bare form found the bare token as a negligible tail candidate at
    the same position and renormalized two near-zero numbers, which is how the
    first run produced a q(Yes) near 0.5 that meant nothing.
    """
    totals = {left: 0.0, right: 0.0}
    seen = {left: False, right: False}
    for candidate in entry.get("top_probs") or []:
        for word in (left, right):
            if candidate.get("id") in ids[word]:
                totals[word] += float(candidate["prob"])
                seen[word] = True
    mass = totals[left] + totals[right]
    if not (seen[left] and seen[right]) or mass <= 0.0:
        return None, totals, mass
    return totals[left] / mass, totals, mass


class CouncilServer:
    """Launch one council member on a spare port, then stop it again."""

    def __init__(self, member):
        self.member = member
        self.process = None
        self.url = f"http://127.0.0.1:{COUNCIL_PORT}"

    def __enter__(self):
        sys.path.insert(0, str(ROOT / "assistant"))
        from core.config import LLAMA_SERVER  # noqa: E402

        model = ROOT / "models" / self.member["model"]
        command = [
            str(LLAMA_SERVER),
            "-m", str(model),
            "--host", "127.0.0.1",
            "--port", str(COUNCIL_PORT),
            "-np", "1",
            "-c", str(self.member["context"]),
            "--cache-prompt",
        ]
        print(f"  launching {self.member['role']} on {COUNCIL_PORT} ...",
              flush=True)
        self.process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + LOAD_TIMEOUT_SECONDS
        while True:
            if self.process.poll() is not None:
                raise CouncilError(
                    f"{self.member['role']} server exited during load "
                    f"(code {self.process.returncode})"
                )
            try:
                health = requests.get(self.url + "/health", timeout=5)
                if health.status_code == 200:
                    break
            except requests.RequestException:
                pass
            if time.monotonic() >= deadline:
                raise CouncilError(f"{self.member['role']} did not become ready")
            time.sleep(2.0)
        print("  ready", flush=True)
        return self

    def __exit__(self, *_exception):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=30)
        print(f"  stopped {self.member['role']}", flush=True)
        return False

    def token_ids(self):
        """Every single-token surface form of each branch word.

        Both the bare and space-prefixed forms are collected, because which
        one the model emits depends on how the grammar's separator merges
        during tokenization, and that is not knowable in advance.
        """
        ids = {}
        for word in CONFIDENCE_WORDS + GUESS_WORDS:
            found = []
            for surface in (word, " " + word):
                response = requests.post(
                    self.url + "/tokenize",
                    json={"content": surface, "add_special": False},
                    timeout=60,
                )
                response.raise_for_status()
                tokens = response.json().get("tokens")
                if isinstance(tokens, list) and len(tokens) == 1:
                    found.append(tokens[0])
            if not found:
                raise CouncilError(
                    f"{word!r} has no single-token form for "
                    f"{self.member['role']}"
                )
            ids[word] = found
        overlap = set(ids["Yes"]) & set(ids["No"])
        if overlap or (set(ids["Sure"]) & set(ids["Maybe"])):
            raise CouncilError("branch words share a token id")
        return ids

    def props(self):
        response = requests.get(self.url + "/props", timeout=60)
        response.raise_for_status()
        props = response.json()
        settings = props.get("default_generation_settings") or {}
        return {
            "model_basename": Path(
                str(props.get("model_path") or "")
            ).name,
            "model_ftype": props.get("model_ftype"),
            "build_info": props.get("build_info"),
            "total_slots": props.get("total_slots"),
            "n_ctx": settings.get("n_ctx"),
            "chat_template_sha256": sha256_text(
                props.get("chat_template") or ""
            ),
        }

    def ask(self, system_prompt, proposition, ids):
        started = time.perf_counter()
        response = requests.post(
            self.url + "/v1/chat/completions",
            json={
                **SAMPLER,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": proposition["question"]},
                ],
            },
            timeout=CALL_TIMEOUT_SECONDS,
        )
        elapsed = time.perf_counter() - started
        response.raise_for_status()
        choice = response.json()["choices"][0]
        answer = choice["message"]["content"]
        content = choice["logprobs"]["content"]

        emitted = [
            {"index": i, "id": e.get("id"), "token": e.get("token")}
            for i, e in enumerate(content)
        ]
        confidence_index = _locate(content, CONFIDENCE_WORDS, ids)
        guess_index = _locate(content, GUESS_WORDS, ids)
        if confidence_index is None or guess_index is None:
            raise CouncilError(
                f"{proposition['proposition_id']}: emitted no confidence or "
                f"guess token. answer={answer!r} tokens={emitted}"
            )

        p_maybe, confidence_raw, confidence_mass = _read_pair(
            content[confidence_index], "Maybe", "Sure", ids
        )
        q_yes, guess_raw, guess_mass = _read_pair(
            content[guess_index], "Yes", "No", ids
        )
        if p_maybe is None or q_yes is None:
            raise CouncilError(
                f"{proposition['proposition_id']}: a branch counterpart fell "
                f"outside the {SAMPLER['top_logprobs']}-candidate window. "
                f"confidence={confidence_raw} guess={guess_raw}"
            )
        if confidence_mass < MIN_BRANCH_MASS or guess_mass < MIN_BRANCH_MASS:
            raise CouncilError(
                f"{proposition['proposition_id']}: branch tokens hold only "
                f"{confidence_mass:.3g}/{guess_mass:.3g} of the probability "
                f"at their own positions; renormalizing that is meaningless"
            )

        stated_confidence = content[confidence_index]["token"].strip()
        stated_guess = content[guess_index]["token"].strip()
        return {
            "answer": answer,
            "emitted_tokens": emitted,
            "stated_confidence": stated_confidence,
            "stated_guess": stated_guess,
            "p_maybe": p_maybe,
            "confidence_mass": confidence_mass,
            "confidence_token_position": confidence_index,
            "q_yes": q_yes,
            "guess_mass": guess_mass,
            "guess_token_position": guess_index,
            "argmax_guess_is_yes": q_yes >= 0.5,
            "stated_guess_correct": (
                (stated_guess == "Yes") == proposition["truth_is_yes"]
            ),
            "elapsed_seconds": round(elapsed, 3),
        }


def exact_sign_test(positive, negative):
    from math import comb

    trials = positive + negative
    if trials == 0:
        return 1.0
    tail = min(positive, negative)
    probability = sum(comb(trials, k) for k in range(tail + 1)) / (2 ** trials)
    return min(1.0, 2.0 * probability)


def analyze(rows, spec, propositions):
    by_member = {}
    for row in rows:
        by_member.setdefault(row["member_role"], {})[
            row["proposition_id"]
        ] = row

    truth = {p["proposition_id"]: p["truth_is_yes"] for p in propositions}
    members = []
    for member in spec["members"]:
        role = member["role"]
        answered = by_member.get(role, {})
        if len(answered) != len(propositions):
            members.append({
                "role": role,
                "complete": False,
                "answered": len(answered),
            })
            continue
        hedged = sum(1 for r in answered.values() if r["p_maybe"] > 0.5)
        correct = sum(
            1 for r in answered.values() if r["stated_guess_correct"]
        )
        yes_count = sum(
            1 for r in answered.values() if r["stated_guess"] == "Yes"
        )
        total = len(answered)
        members.append({
            "role": role,
            "family": member["family"],
            "model": member["model"],
            "complete": True,
            "hedged": hedged,
            "hedge_rate": hedged / total,
            "mean_p_maybe": sum(
                r["p_maybe"] for r in answered.values()
            ) / total,
            "guess_correct": correct,
            "guess_total": total,
            "constant_responder_baseline": total // 2,
            "said_yes": yes_count,
            "said_no": total - yes_count,
            "sign_test_vs_baseline_p": exact_sign_test(
                correct, total - correct
            ),
            "beats_constant_baseline": correct > total // 2,
            "median_q_yes": sorted(
                r["q_yes"] for r in answered.values()
            )[total // 2],
        })

    complete_roles = [m["role"] for m in members if m.get("complete")]
    disagreements = []
    for proposition in propositions:
        pid = proposition["proposition_id"]
        positions = {}
        for role in complete_roles:
            row = by_member[role][pid]
            positions[role] = (
                f"{row['stated_confidence']} {row['stated_guess']} "
                f"(P(Maybe)={row['p_maybe']:.4f}, q(Yes)={row['q_yes']:.3e})"
            )
        guesses = {
            by_member[role][pid]["stated_guess"] for role in complete_roles
        }
        confidences = {
            by_member[role][pid]["stated_confidence"]
            for role in complete_roles
        }
        if len(guesses) > 1 or len(confidences) > 1:
            disagreements.append({
                "subject": (
                    f"{pid} ({proposition['target_path']}, "
                    f"truth={'Yes' if proposition['truth_is_yes'] else 'No'})"
                ),
                "positions": positions,
                "guess_split": sorted(guesses),
                "confidence_split": sorted(confidences),
            })

    return {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "spec_sha256": spec["spec_sha256"],
        "completed_rows": len(rows),
        "expected_rows": spec["call_count"],
        "complete": len(rows) == spec["call_count"],
        "members": members,
        "unanimous_hedge": all(
            m.get("complete") and m["hedge_rate"] == 1.0 for m in members
        ),
        "any_member_beats_baseline": any(
            m.get("complete") and m["beats_constant_baseline"] for m in members
        ),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "vote_taken": False,
        "why_no_vote": (
            "core/provenance.py: disagreement between models is the signal; "
            "a vote throws it away and returns a number that looks more "
            "certain than the evidence."
        ),
        "interpretation_limits": spec["preregistered_interpretation_limits"],
    }


def run():
    spec_path = OUT / "council_spec.json"
    inputs_path = OUT / "council_inputs.json"
    rows_path = OUT / "council_rows.jsonl"
    if not spec_path.exists():
        raise CouncilError("preregister before running")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    if sha256_file(Path(__file__).resolve()) != spec["probe_sha256"]:
        raise CouncilError("probe changed since preregistration")
    if sha256_value(inputs["propositions"]) != spec["propositions_sha256"]:
        raise CouncilError("propositions changed since preregistration")

    done = {
        (row["member_role"], row["proposition_id"])
        for row in _read_jsonl(rows_path)
    }
    for member in spec["members"]:
        pending = [
            p for p in inputs["propositions"]
            if (member["role"], p["proposition_id"]) not in done
        ]
        if not pending:
            print(f"{member['role']}: already complete", flush=True)
            continue
        print(f"\n=== {member['role']} ({member['model']}) ===", flush=True)
        with CouncilServer(member) as server:
            ids = server.token_ids()
            props = server.props()
            print(f"  token ids: {ids}", flush=True)
            for index, proposition in enumerate(pending, start=1):
                result = server.ask(
                    inputs["system_prompt"], proposition, ids
                )
                _append_jsonl(rows_path, {
                    "schema": SCHEMA,
                    "experiment": EXPERIMENT,
                    "spec_sha256": spec["spec_sha256"],
                    "member_role": member["role"],
                    "member_family": member["family"],
                    "member_model": member["model"],
                    "member_model_sha256": member["sha256"],
                    "member_props": props,
                    "member_token_ids": ids,
                    "proposition_id": proposition["proposition_id"],
                    "target_id": proposition["target_id"],
                    "target_path": proposition["target_path"],
                    "measurement": proposition["measurement"],
                    "truth_is_yes": proposition["truth_is_yes"],
                    "question_sha256": sha256_text(proposition["question"]),
                    "sampler": SAMPLER,
                    "recorded_utc": utc_now(),
                    **result,
                })
                print(
                    f"  {index:02d}/{len(pending)} "
                    f"{proposition['proposition_id']} {result['answer']!r} "
                    f"P(Maybe)={result['p_maybe']:.4f} "
                    f"q(Yes)={result['q_yes']:.3e} "
                    f"{result['elapsed_seconds']:.1f}s",
                    flush=True,
                )

    rows = _read_jsonl(rows_path)
    summary = analyze(rows, spec, inputs["propositions"])
    _atomic_json(OUT / "council_summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregister", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args(argv)

    if args.preregister:
        spec, inputs = preregister()
        _atomic_json(OUT / "council_spec.json", spec)
        _atomic_json(OUT / "council_inputs.json", inputs)
        print(json.dumps({
            "spec_sha256": spec["spec_sha256"],
            "members": [m["role"] for m in spec["members"]],
            "propositions": spec["proposition_count"],
            "calls": spec["call_count"],
        }, indent=2, sort_keys=True))
        return 0

    if args.analyze_only:
        spec = json.loads(
            (OUT / "council_spec.json").read_text(encoding="utf-8")
        )
        inputs = json.loads(
            (OUT / "council_inputs.json").read_text(encoding="utf-8")
        )
        summary = analyze(
            _read_jsonl(OUT / "council_rows.jsonl"),
            spec,
            inputs["propositions"],
        )
        _atomic_json(OUT / "council_summary.json", summary)
    elif args.run:
        summary = run()
    else:
        parser.error("choose --preregister, --run, or --analyze-only")

    print(json.dumps({
        "complete": summary["complete"],
        "unanimous_hedge": summary["unanimous_hedge"],
        "any_member_beats_baseline": summary["any_member_beats_baseline"],
        "disagreement_count": summary["disagreement_count"],
        "members": [
            {
                k: v for k, v in m.items()
                if k in ("role", "hedge_rate", "guess_correct",
                         "constant_responder_baseline", "said_no")
            }
            for m in summary["members"]
        ],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
