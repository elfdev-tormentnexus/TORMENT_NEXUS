"""Build the labelled public derivative of the private Research C evidence.

Four collector artifacts cannot be committed as written:

    handoffs/researchc_experiments_2026-07-30/preflight_prompts.json
    .../rate_distortion/rate_distortion_stable_messages.json
    .../rate_distortion/rate_distortion_spec.json
    .../rate_distortion/rate_distortion_rows.jsonl

The two prompt artifacts hold the exact runtime system prompt, which carries
installation-local chosen-name state.  The spec and rows hold absolute host
paths in their per-call binding records.  This tool writes a derivative that
keeps every response, grading, statistical, task, and timing field, replaces
the repeated raw binding with one consolidated sanitized binding record, and
commits to each private original by SHA-256 so the untransformed file stays
verifiable without being published.

The transformation is deliberately lossy in one direction only.  It never
invents, reorders, regrades, or rounds a measurement.

Usage:
    python publish_evidence.py --check
    python publish_evidence.py
"""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "handoffs" / "researchc_experiments_2026-07-30"
RATE = EXPERIMENTS / "rate_distortion"
PUBLIC = EXPERIMENTS / "public"
TRANSFORMATION_VERSION = "researchc-public-derivative-1"

PRIVATE_SOURCES = {
    "preflight_prompts": EXPERIMENTS / "preflight_prompts.json",
    "rate_distortion_stable_messages": RATE / "rate_distortion_stable_messages.json",
    "rate_distortion_spec": RATE / "rate_distortion_spec.json",
    "rate_distortion_rows": RATE / "rate_distortion_rows.jsonl",
}

# Field paths removed or replaced by this transformation.  Each entry names
# the reason, because "sanitized" on its own is not an audit trail.
REMOVED_FIELD_PATHS = {
    "$.bindings.hazard_runtime.assistant.executable_path":
        "absolute host path to the Python interpreter running Sable",
    "$.bindings.hazard_runtime.machinespirit_helper.executable_path":
        "absolute host path to the unpooled helper binary",
    "$.bindings.live_server.listener.executable_path":
        "absolute host path to the director binary",
    "$.bindings.live_server.props.model_path":
        "absolute host path to the director model",
    "$.bindings.live_server.props.model_alias":
        "llama.cpp defaults the alias to the model path, so it repeats it",
    "$.rows[*].bindings":
        "the identical binding record repeated on all 120 rows; replaced by "
        "bindings_sha256 pointing at the one consolidated public record",
    "$.baseline / $.perturbed (preflight_prompts.json)":
        "full runtime system prompt including chosen-name state; replaced by "
        "per-artifact digests and the single manipulated inventory line",
    "$.messages[*].content (rate_distortion_stable_messages.json)":
        "full runtime system prompt and style demonstration; replaced by "
        "per-message role, length, and digest",
}

# Basename-only replacements for the path fields above.
_PATH_TO_BASENAME = (
    ("executable_path", "executable_basename"),
    ("model_path", "model_basename"),
)

_ABSOLUTE_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/][^\r\n\t\"]*"
)
_UNC_PATH = re.compile(r"(?i)(?<![A-Za-z0-9_])\\\\[^\\/\r\n\t\"]+[\\/][^\r\n\t\"]*")
_SECRET_TEXT = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


class PublishError(RuntimeError):
    pass


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
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


def _local_identity_terms():
    """Every host-local label that must not survive into a public artifact.

    The assistant's chosen name is deliberately *not* on this list.  It is
    installation state in ``chosen_name.json``, which is gitignored, but the
    word itself is ordinary project vocabulary in sixty-three tracked files
    including README.md and assistant/core/chosen_name.py.  Treating it as a
    host identifier here would fail every artifact for prose that the
    repository already publishes, and would not protect the thing that
    actually needs protecting.  What needs protecting is the exact runtime
    prompt text, which ``withheld_text_leaks`` checks directly.
    """
    terms = {
        os.environ.get("USERNAME"),
        os.environ.get("USER"),
        Path.home().name,
        str(ROOT),
        str(Path.home()),
        os.environ.get("USERPROFILE"),
    }
    return tuple(
        sorted(
            {str(t).strip() for t in terms if t and len(str(t).strip()) >= 3},
            key=len,
            reverse=True,
        )
    )


def _withheld_texts():
    """Every prompt string this transformation refuses to publish."""
    stable = json.loads(
        PRIVATE_SOURCES["rate_distortion_stable_messages"].read_text(
            encoding="utf-8"
        )
    )
    preflight = json.loads(
        PRIVATE_SOURCES["preflight_prompts"].read_text(encoding="utf-8")
    )
    texts = [message["content"] for message in stable["messages"]]
    texts.extend([preflight["baseline"], preflight["perturbed"]])
    return [text for text in texts if len(text) >= 120]


def withheld_text_leaks(value, withheld, window=80):
    """Detect any substantial verbatim run of withheld prompt text.

    Sliding a fixed window over each withheld string and searching the
    serialized artifact catches a partial copy as well as a whole one, which
    a whole-string equality check would not.
    """
    encoded = canonical_json(value)
    leaks = []
    for index, text in enumerate(withheld):
        for start in range(0, len(text) - window, window // 2):
            fragment = text[start:start + window]
            if fragment.strip() and fragment in encoded:
                leaks.append(
                    f"withheld_text[{index}] offset {start}: {fragment[:60]!r}"
                )
                break
    return leaks


def privacy_violations(value, terms):
    """Structural and textual leaks in a would-be public artifact."""
    problems = []

    def inspect(item, path):
        if isinstance(item, dict):
            for key, sub in item.items():
                folded = str(key).casefold()
                if folded == "command_line":
                    problems.append(f"{path}.{key}:raw-command-line")
                if folded.endswith("_path") or folded in {
                    "executable_path",
                    "model_path",
                    "model_alias",
                    "cwd",
                    "root",
                }:
                    problems.append(f"{path}.{key}:path-bearing-key")
                if "api_key" in folded or folded in {
                    "authorization",
                    "cookie",
                    "password",
                    "secret",
                    "username",
                }:
                    problems.append(f"{path}.{key}:sensitive-key")
                inspect(sub, f"{path}.{key}")
            return
        if isinstance(item, list):
            for index, member in enumerate(item):
                inspect(member, f"{path}[{index}]")
            return
        if not isinstance(item, str):
            return
        if _ABSOLUTE_PATH.search(item) or _UNC_PATH.search(item):
            problems.append(f"{path}:absolute-path")
        folded = item.casefold()
        for term in terms:
            if re.search(
                rf"(?i)(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])",
                item,
            ) or (len(term) > 8 and term.casefold() in folded):
                problems.append(f"{path}:local-identity({term})")
        if any(pattern.search(item) for pattern in _SECRET_TEXT):
            problems.append(f"{path}:credential-shaped-text")

    inspect(value, "$")
    return problems


def _basename(value):
    text = str(value or "").strip().strip("\"'").replace("\\", "/")
    return text.rstrip("/").rsplit("/", 1)[-1] if text else ""


def consolidated_binding(raw):
    """One sanitized binding record: roles, PIDs, ports, sizes, and hashes."""
    hazard = raw["hazard_runtime"]
    listener = raw["live_server"]["listener"]
    props = raw["live_server"]["props"]

    def process(entry, role):
        result = {
            "role": role,
            "pid": entry["pid"],
            "parent_pid": entry["parent_pid"],
            "executable_basename": _basename(entry["executable_path"]),
            "executable_sha256": entry["executable_sha256"],
            "command_line_sha256": entry["command_line_sha256"],
        }
        for key, value in sorted(entry.items()):
            if key.endswith("_present"):
                result[key] = value
        return result

    value = {
        "transformation": TRANSFORMATION_VERSION,
        "assistant_mode": {
            "value": raw["assistant_mode"]["operator_reported"],
            "source": "operator_reported",
            "ui_mode_independently_verified": False,
            "topology_independently_verified": True,
            "scope": (
                "The operator reported the visible Sable UI mode. The process, "
                "hash, and port checks recorded here verify topology only. "
                "They do not establish which UI mode was selected. The "
                "original artifact's assistant_mode.independently_verified="
                "true wording overstated this and is corrected here."
            ),
            "collection_route": raw["assistant_mode"]["relevance"],
        },
        "processes": [
            process(hazard["assistant"], "sable_assistant_parent"),
            process(listener, "one_slot_director"),
            process(hazard["machinespirit_helper"], "machinespirit_helper"),
        ],
        "loopback": {
            "director_url": raw["server_url"],
            "machinespirit_helper_port": 8084,
            "agent_interface_8099_listener": hazard[
                "agent_interface_8099_listener"
            ],
        },
        "model": {
            "basename": raw["model_name"],
            "bytes": raw["model_bytes"],
            "sha256": raw["model_sha256"],
            "ftype": props["model_ftype"],
            "alias_was_absolute": True,
            "alias_note": (
                "llama.cpp defaults model_alias to the model path, so the "
                "original alias field was an absolute host path and is "
                "dropped rather than shown."
            ),
        },
        "server": {
            "basename": raw["server_name"],
            "executable_sha256": raw["server_executable_sha256"],
            "bundle_sha256": raw["server_bundle_sha256"],
            "bundle_caveat": (
                "This collector-era bundle digest omitted mtmd.dll. The "
                "launcher, main implementation libraries, model, repository, "
                "prompt, and sampler were still bound, but this value is not "
                "a complete CPU dependency-closure digest."
            ),
            "revision": raw["server_revision"],
            "build_info": props["build_info"],
            "total_slots": props["total_slots"],
            "n_ctx": props["n_ctx"],
            "chat_format": props["chat_format"],
            "reasoning_format": props["reasoning_format"],
            "chat_template_sha256": props["chat_template_sha256"],
        },
        "console_pulse": {
            "helper_sha256": hazard["console_pulse_helper_sha256"],
            "interval_seconds": hazard["console_pulse_interval_seconds"],
        },
        "original_live_server_identity_sha256": raw["live_server"]["sha256"],
    }
    value["sha256"] = sha256_value(value)
    return value


def public_spec(raw_spec, binding):
    spec = json.loads(json.dumps(raw_spec))
    spec["bindings"] = {
        "consolidated_binding_sha256": binding["sha256"],
        "see": "public_binding.json",
    }
    spec["assistant_mode"] = {
        "value": raw_spec["assistant_mode"]["operator_reported"],
        "source": "operator_reported",
        "ui_mode_independently_verified": False,
        "topology_independently_verified": True,
        "collection_route": raw_spec["assistant_mode"]["collection_route"],
        "correction": (
            "The original spec recorded independently_verified=true for the "
            "operator-reported hazard mode. Only process topology was "
            "checked."
        ),
    }
    spec["public_derivative"] = {
        "transformation": TRANSFORMATION_VERSION,
        "private_original_sha256": sha256_file(
            PRIVATE_SOURCES["rate_distortion_spec"]
        ),
        "spec_sha256_note": (
            "spec_sha256 still commits to the private original's core. It "
            "does not revalidate against this transformed file, and no "
            "collector should be asked to reload this derivative."
        ),
    }
    return spec


def public_rows(binding, raw_spec_binding):
    """Replace each row's repeated raw binding with the consolidated digest.

    Collapsing 120 identical records is only sound if they really are
    identical, and identical to the spec's, so that is checked rather than
    assumed.  A row whose binding differed would be a drift the collector
    should have caught, and silently folding it away would hide it.
    """
    expected = sha256_value(raw_spec_binding)
    rows = []
    with PRIVATE_SOURCES["rate_distortion_rows"].open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if sha256_value(row.pop("bindings")) != expected:
                raise PublishError(
                    f"row {number} carries a different binding record than "
                    "the frozen spec; refusing to consolidate"
                )
            row["bindings_sha256"] = binding["sha256"]
            row["bindings_note"] = "see public_binding.json"
            rows.append(row)
    return rows


def public_stable_messages():
    raw = json.loads(
        PRIVATE_SOURCES["rate_distortion_stable_messages"].read_text(
            encoding="utf-8"
        )
    )
    messages = raw["messages"]
    return {
        "schema": raw["schema"],
        "transformation": TRANSFORMATION_VERSION,
        "content_withheld": True,
        "why": (
            "These messages are the stable production prefix: the runtime "
            "persona system prompt plus a fixed style demonstration. They "
            "carry installation-local chosen-name state and no experimental "
            "content -- the controlled source index and every question live "
            "in the per-call messages, which are published in full through "
            "rate_distortion_queries.json and the rows. Withholding the text "
            "costs no reproducibility of any reported number."
        ),
        "private_original_sha256": sha256_file(
            PRIVATE_SOURCES["rate_distortion_stable_messages"]
        ),
        "message_count": len(messages),
        "messages": [
            {
                "index": index,
                "role": message["role"],
                "characters": len(message["content"]),
                "utf8_bytes": len(message["content"].encode("utf-8")),
                "content_sha256": sha256_text(message["content"]),
            }
            for index, message in enumerate(messages)
        ],
        "stable_system_sha256": sha256_text(messages[0]["content"]),
    }


def public_preflight_prompts():
    raw = json.loads(
        PRIVATE_SOURCES["preflight_prompts"].read_text(encoding="utf-8")
    )
    baseline = raw["baseline"].splitlines()
    perturbed = raw["perturbed"].splitlines()
    if len(baseline) != len(perturbed):
        raise PublishError("preflight prompts differ in line count")
    changed = [
        {
            "line_number": index + 1,
            "baseline": left,
            "perturbed": right,
        }
        for index, (left, right) in enumerate(zip(baseline, perturbed))
        if left != right
    ]
    if len(changed) != 1:
        raise PublishError(
            f"expected exactly one manipulated line, found {len(changed)}"
        )
    line = changed[0]
    before = re.search(r"assistant/ui \d+f [\d,]+L", line["baseline"])
    after = re.search(r"assistant/ui \d+f [\d,]+L", line["perturbed"])
    if not before or not after:
        raise PublishError("the manipulated aggregate is not where expected")
    return {
        "schema": raw["schema"],
        "transformation": TRANSFORMATION_VERSION,
        "content_withheld": True,
        "why": (
            "Both prompts are the full runtime system prompt including "
            "installation-local chosen-name state. The entire experimental "
            "manipulation is the one inventory line reproduced below, and "
            "that line is a public repository aggregate."
        ),
        "private_original_sha256": sha256_file(
            PRIVATE_SOURCES["preflight_prompts"]
        ),
        "baseline_sha256": sha256_text(raw["baseline"]),
        "perturbed_sha256": sha256_text(raw["perturbed"]),
        "characters": len(raw["baseline"]),
        "line_count": len(baseline),
        "changed_line_count": 1,
        "manipulation": {
            "line_number": line["line_number"],
            "field": "assistant/ui directory aggregate on the Shape line",
            "baseline_aggregate": before.group(0),
            "perturbed_aggregate": after.group(0),
            "note": (
                "Only the substituted aggregate is reproduced, not the "
                "surrounding prompt line, so no run of withheld prompt text "
                "is published. Both aggregates are public repository facts."
            ),
        },
    }


def build():
    raw_spec = json.loads(
        PRIVATE_SOURCES["rate_distortion_spec"].read_text(encoding="utf-8")
    )
    binding = consolidated_binding(raw_spec["bindings"])
    artifacts = {
        "public_binding.json": binding,
        "public_rate_distortion_spec.json": public_spec(raw_spec, binding),
        "public_rate_distortion_stable_messages.json": public_stable_messages(),
        "public_preflight_prompts.json": public_preflight_prompts(),
    }
    rows = public_rows(binding, raw_spec["bindings"])
    return artifacts, rows, binding


def audit(artifacts, rows):
    """Every reason this derivative would not be publishable, or an empty list."""
    terms = _local_identity_terms()
    withheld = _withheld_texts()
    problems = []
    for name, value in sorted(artifacts.items()):
        problems.extend(
            f"{name}: {issue}" for issue in privacy_violations(value, terms)
        )
        problems.extend(
            f"{name}: {issue}"
            for issue in withheld_text_leaks(value, withheld)
        )
    problems.extend(
        f"rows: {issue}" for issue in privacy_violations(rows, terms)
    )
    problems.extend(
        f"rows: {issue}" for issue in withheld_text_leaks(rows, withheld)
    )
    return problems


def write(artifacts, rows):
    problems = audit(artifacts, rows)
    if problems:
        raise PublishError(f"derivative is not publishable: {problems[:6]}")

    PUBLIC.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, value in artifacts.items():
        path = PUBLIC / name
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        written[name] = sha256_file(path)

    rows_path = PUBLIC / "public_rate_distortion_rows.jsonl"
    with rows_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")
    written[rows_path.name] = sha256_file(rows_path)

    manifest = {
        "schema": 1,
        "transformation": TRANSFORMATION_VERSION,
        "purpose": (
            "Publishable derivative of four private Research C collector "
            "artifacts. Every response, grading, statistical, task, and "
            "timing field is preserved unchanged. No measurement was "
            "recomputed, reordered, or rounded."
        ),
        "not_revalidatable": (
            "These files do not revalidate under the original collector "
            "digests. spec_sha256, stable_artifact_sha256, and the row "
            "bindings commit to the private originals, which are retained "
            "locally and gitignored."
        ),
        "private_originals": {
            key: {
                "repository_path": str(
                    path.relative_to(ROOT)
                ).replace("\\", "/"),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "committed": False,
                "reason": (
                    "runtime system prompt including chosen-name state"
                    if "prompt" in key or "messages" in key
                    else "absolute host paths in per-call binding records"
                ),
            }
            for key, path in sorted(PRIVATE_SOURCES.items())
        },
        "public_artifacts": {
            name: {"sha256": digest, "bytes": (PUBLIC / name).stat().st_size}
            for name, digest in sorted(written.items())
        },
        "removed_field_paths": REMOVED_FIELD_PATHS,
        "corrections": [
            "assistant_mode.independently_verified was true in the private "
            "originals. Hazard mode was operator-reported; only process "
            "topology was independently checked.",
            "server_bundle_sha256 "
            "2cfd58b8b4a2e9a1081cab1168877dfa6598f0c430c6970afbd41a37f08f96ab "
            "omitted mtmd.dll and is not a complete dependency-closure "
            "digest.",
        ],
    }
    manifest_path = PUBLIC / "PUBLIC_DERIVATIVE_MANIFEST.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="build and privacy-scan in memory without writing files",
    )
    args = parser.parse_args(argv)
    artifacts, rows, binding = build()
    if args.check:
        problems = audit(artifacts, rows)
        print(json.dumps({
            "rows": len(rows),
            "consolidated_binding_sha256": binding["sha256"],
            "problems": problems[:12],
            "publishable": not problems,
        }, indent=2, sort_keys=True))
        return 0 if not problems else 1
    manifest = write(artifacts, rows)
    print(json.dumps({
        "output": str(PUBLIC.relative_to(ROOT)).replace("\\", "/"),
        "rows": len(rows),
        "public_artifacts": sorted(manifest["public_artifacts"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
