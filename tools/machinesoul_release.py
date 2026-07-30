"""Plan, cut, and reassemble a direct machinesoul release.

The public artifacts are PNG/APNG machinesoul capsules. This tool never
creates a ZIP or tar layer: it preserves the staged files directly, records
where each source segment lives in the ordered pixel-vector field, and
reassembles the original tree only after every decoded capsule verifies.

Cut policy:

* Prefer the end of a complete file.
* For large text, prefer a blank structural seam before ``def``/``class``.
* For a file larger than one capsule, search backward from the size ceiling
  for the quietest four-coordinate vector window.
* Every in-file cut is aligned to a complete RGBA vector.

The plan is written before any capsule. ``cut`` requires the exact SHA-256 of
that reviewed plan, so a changed or unreviewed map cannot be used by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import sys
import tempfile
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

import machinesoul


FORMAT = "MACHINESOUL_RELEASE1"
# Deliberately NOT renamed per release, despite reading like "researchA".
# This is a wire-format discriminator, not a release marker. Three things
# settle it: it occupies the same "format" slot as FORMAT above, both ending
# in a version digit; _load_reassembly_manifest() compares it for equality to
# decide whether a manifest is readable at all; and the release identity is
# carried by a separate "prefix" field, which the operator supplies with
# --prefix at cut time (researchA published prefix "SABLERESEARCHA-WINDOWS").
# So researchB capsules do not inherit a researchA marker from this string,
# while changing it would make every already-published researchA combined
# manifest unreadable -- the equality check fails, the reader falls through
# to the "component applies only to a combined manifest" error, and ~21 GB of
# published assets can no longer be reassembled. Bump the trailing digit only
# if the combined manifest's own structure changes incompatibly.
COMBINED_FORMAT = "SABLERESEARCHA_MANIFEST1"
COMBINED_COMPONENTS = ("windows", "optional_14b")
VECTOR_WIDTH = 4
DEFAULT_PAYLOAD_LIMIT = 1_797_000_000
GITHUB_ASSET_LIMIT = 2 * 1024**3
BLOCK = 8 * 1024**2
QUIET_RADIUS = 32 * 1024**2
QUIET_WINDOW = 64 * 1024
QUIET_STEP = 128 * 1024
TEXT_EXTENSIONS = {
    ".bat", ".cfg", ".cmd", ".css", ".csv", ".html", ".ini", ".js",
    ".json", ".md", ".ps1", ".py", ".toml", ".tsv", ".txt", ".xml",
    ".yaml", ".yml",
}
STRUCTURAL_SEAM = re.compile(
    rb"\n[ \t]*\n(?=(?:async[ \t]+)?def[ \t]|class[ \t]|"
    rb"if[ \t]+__name__|#[-=]{3,}|REM[ \t])",
    re.IGNORECASE,
)


class ReleaseError(RuntimeError):
    """A release would not preserve the reviewed source exactly."""


@dataclass(frozen=True)
class SourceFile:
    path: str
    full_path: str
    size: int
    sha256: str


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_range(path: str, offset: int, length: int) -> str:
    digest = hashlib.sha256()
    remaining = length
    with open(path, "rb") as handle:
        handle.seek(offset)
        while remaining:
            block = handle.read(min(BLOCK, remaining))
            if not block:
                raise ReleaseError(f"{path} ended inside a planned segment")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def _is_reparse(path: str) -> bool:
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
    except AttributeError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _safe_relative(path: str) -> str:
    normalized = path.replace("\\", "/")
    pure = Path(normalized)
    if (
        not normalized
        or pure.is_absolute()
        or normalized.startswith("/")
        or any(part in {"", ".", ".."} for part in pure.parts)
        or ":" in pure.parts[0]
    ):
        raise ReleaseError(f"unsafe release path: {path!r}")
    return normalized


def inventory(source: str) -> list[SourceFile]:
    """Hash a regular file or a directory tree without following links."""
    source = os.path.realpath(source)
    if os.path.islink(source) or _is_reparse(source):
        raise ReleaseError("release source cannot be a link or reparse point")

    if os.path.isfile(source):
        files = [(os.path.basename(source), source)]
    elif os.path.isdir(source):
        files = []
        for folder, directories, names in os.walk(source):
            directories.sort()
            names.sort()
            for name in names:
                full = os.path.join(folder, name)
                if os.path.islink(full) or _is_reparse(full):
                    raise ReleaseError(
                        f"release source contains a link or reparse point: {full}"
                    )
                if not os.path.isfile(full):
                    raise ReleaseError(f"release source is not a file: {full}")
                relative = os.path.relpath(full, source).replace("\\", "/")
                files.append((_safe_relative(relative), full))
    else:
        raise ReleaseError(f"release source does not exist: {source}")

    if not files:
        raise ReleaseError("release source contains no files")

    result = []
    for relative, full in sorted(files):
        result.append(
            SourceFile(
                path=relative,
                full_path=full,
                size=os.path.getsize(full),
                sha256=_sha256_file(full),
            )
        )
    return result


def _align(value: int, width: int = VECTOR_WIDTH) -> int:
    return (value + width - 1) // width * width


def _vector_activity(window: bytes) -> float:
    """Lower means a flatter, quieter pixel-vector region."""
    if len(window) < 8:
        return 1.0

    compressed = len(zlib.compress(window, 1)) / len(window)
    sample_step = max(VECTOR_WIDTH, len(window) // 2048)
    sample_step = _align(sample_step)
    previous = window[0:VECTOR_WIDTH]
    motion = 0
    energy = 0
    count = 0
    for at in range(sample_step, len(window) - VECTOR_WIDTH + 1, sample_step):
        current = window[at:at + VECTOR_WIDTH]
        motion += sum(abs(a - b) for a, b in zip(current, previous))
        energy += sum(current)
        previous = current
        count += 1
    if not count:
        return compressed

    motion /= count * VECTOR_WIDTH * 255
    energy /= count * VECTOR_WIDTH * 255
    return round(0.55 * compressed + 0.35 * motion + 0.10 * energy, 8)


def _structural_cut(path: str, start: int, hard_end: int) -> dict | None:
    extension = os.path.splitext(path)[1].lower()
    if extension not in TEXT_EXTENSIONS:
        return None
    low = max(start + VECTOR_WIDTH, hard_end - QUIET_RADIUS)
    with open(path, "rb") as handle:
        handle.seek(low)
        area = handle.read(hard_end - low)

    candidates = []
    for match in STRUCTURAL_SEAM.finditer(area):
        absolute = low + match.end()
        aligned = absolute - (absolute % VECTOR_WIDTH)
        if aligned > start and aligned <= hard_end:
            candidates.append(aligned)
    if not candidates:
        return None

    chosen = max(candidates)
    preview_start = max(0, chosen - low - 60)
    preview_end = min(len(area), chosen - low + 80)
    preview = area[preview_start:preview_end].decode("utf-8", "replace")
    preview = " ".join(preview.split())
    return {
        "offset": chosen,
        "kind": "text_structure",
        "activity": 0.0,
        "detail": "blank seam before a rule/def/class boundary",
        "preview": preview[:140],
    }


def quiet_cut(path: str, start: int, hard_end: int) -> dict:
    """Choose a quiet aligned point no later than the capsule ceiling."""
    if hard_end - start <= VECTOR_WIDTH:
        return {
            "offset": hard_end,
            "kind": "forced",
            "activity": 1.0,
            "detail": "minimum remaining span",
        }

    structural = _structural_cut(path, start, hard_end)
    if structural:
        return structural

    low = max(start + VECTOR_WIDTH, hard_end - QUIET_RADIUS)
    low = _align(low)
    high = hard_end - (hard_end % VECTOR_WIDTH)
    if low > high:
        low = high

    candidates = list(range(low, high + 1, QUIET_STEP))
    if not candidates or candidates[-1] != high:
        candidates.append(high)

    half = QUIET_WINDOW // 2
    scored = []
    with open(path, "rb") as handle:
        for candidate in candidates:
            window_start = max(start, candidate - half)
            handle.seek(window_start)
            window = handle.read(QUIET_WINDOW)
            scored.append((_vector_activity(window), candidate))

    score, chosen = min(scored, key=lambda item: (item[0], -item[1]))
    ordered = sorted(item[0] for item in scored)
    rank = ordered.index(score)
    percentile = round(100 * rank / max(1, len(ordered) - 1), 1)
    return {
        "offset": chosen,
        "kind": "quiet_vector_window",
        "activity": score,
        "activity_percentile": percentile,
        "detail": (
            f"quietest aligned {QUIET_WINDOW // 1024} KiB vector window "
            f"within {QUIET_RADIUS // 1024**2} MiB before the ceiling"
        ),
        "profile": [
            {"offset": candidate, "activity": activity}
            for activity, candidate in scored
        ],
    }


def _new_capsule(prefix: str, index: int) -> dict:
    return {
        "index": index,
        "name": f"{prefix}.part{index:02d}.png",
        "decoded_name": f"{prefix}.part{index:02d}.msv",
        "data_size": 0,
        "entries": [],
        "boundary": None,
    }


def make_plan(
    source: str,
    prefix: str,
    payload_limit: int = DEFAULT_PAYLOAD_LIMIT,
) -> dict:
    if payload_limit < VECTOR_WIDTH * 2:
        raise ReleaseError("payload limit is too small to cut safely")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix):
        raise ReleaseError(f"unsafe capsule prefix: {prefix!r}")

    files = inventory(source)
    capsules = []
    current = _new_capsule(prefix, 1)

    def finish(boundary: dict):
        nonlocal current
        if not current["entries"]:
            return
        current["boundary"] = boundary
        capsules.append(current)
        current = _new_capsule(prefix, len(capsules) + 1)

    for item in files:
        file_offset = 0
        while file_offset < item.size or (item.size == 0 and file_offset == 0):
            data_offset = _align(current["data_size"])
            room = payload_limit - data_offset
            remaining = item.size - file_offset

            if item.size == 0:
                current["entries"].append(
                    {
                        "path": item.path,
                        "file_offset": 0,
                        "data_offset": data_offset,
                        "length": 0,
                    }
                )
                current["data_size"] = data_offset
                file_offset = 1
                continue

            if remaining <= room:
                current["entries"].append(
                    {
                        "path": item.path,
                        "file_offset": file_offset,
                        "data_offset": data_offset,
                        "length": remaining,
                    }
                )
                current["data_size"] = data_offset + remaining
                file_offset = item.size
                continue

            if file_offset == 0 and current["entries"]:
                previous = current["entries"][-1]
                finish(
                    {
                        "kind": "file_end",
                        "activity": 0.0,
                        "path": previous["path"],
                        "offset": (
                            previous["file_offset"] + previous["length"]
                        ),
                        "detail": "preferred whole-file structural seam",
                    }
                )
                continue

            hard_end = file_offset + room
            cut = quiet_cut(item.full_path, file_offset, hard_end)
            length = cut["offset"] - file_offset
            if length <= 0 or length > room:
                raise ReleaseError(f"invalid cut selected for {item.path}")
            current["entries"].append(
                {
                    "path": item.path,
                    "file_offset": file_offset,
                    "data_offset": data_offset,
                    "length": length,
                }
            )
            current["data_size"] = data_offset + length
            cut["path"] = item.path
            finish(cut)
            file_offset += length

    if current["entries"]:
        last = current["entries"][-1]
        finish(
            {
                "kind": "release_end",
                "activity": 0.0,
                "path": last["path"],
                "offset": last["file_offset"] + last["length"],
                "detail": "end of the preserved release",
            }
        )

    root = os.path.realpath(source)
    if os.path.isfile(root):
        root = os.path.dirname(root)
    return {
        "format": FORMAT,
        "source_root": root,
        "prefix": prefix,
        "vector_width": VECTOR_WIDTH,
        "payload_limit": payload_limit,
        "total_size": sum(item.size for item in files),
        "files": [
            {"path": item.path, "size": item.size, "sha256": item.sha256}
            for item in files
        ],
        "capsules": capsules,
    }


def _write_json(path: str, value: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def plan_markdown(plan: dict, plan_sha256: str) -> str:
    lines = [
        f"# {plan['prefix']} machinesoul cut review",
        "",
        f"- Plan SHA-256: `{plan_sha256}`",
        f"- Preserved files: {len(plan['files']):,}",
        f"- Source extent: {plan['total_size']:,}",
        f"- Proposed PNG/APNG capsules: {len(plan['capsules'])}",
        f"- Maximum vector-field extent per capsule: "
        f"{plan['payload_limit']:,}",
        f"- Vector alignment: {plan['vector_width']} coordinates (RGBA)",
        "",
        "No capsule has been written. The cutter requires the plan hash above.",
        "",
        "| Capsule | Preserved extent | Entries | Cut seam | Activity |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for capsule in plan["capsules"]:
        boundary = capsule["boundary"]
        seam = (
            f"`{boundary['path']}` @ {boundary['offset']:,}: "
            f"{boundary['detail']}"
        )
        activity = boundary.get("activity", 0.0)
        lines.append(
            f"| `{capsule['name']}` | {capsule['data_size']:,} | "
            f"{len(capsule['entries'])} | {seam} | {activity:.6f} |"
        )
        if boundary.get("preview"):
            lines.append(
                f"|  |  |  | Context: `{boundary['preview']}` |  |"
            )
    lines.extend(
        [
            "",
            "Whole-file and release-end seams are treated as zero activity. "
            "In-file model cuts are selected from aligned vector windows and "
            "ranked by the activity metric recorded in the JSON plan.",
            "",
        ]
    )
    return "\n".join(lines)


def write_plan(plan: dict, json_path: str, markdown_path: str) -> str:
    _write_json(json_path, plan)
    digest = _sha256_file(json_path)
    with open(markdown_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(plan_markdown(plan, digest))
    return digest


def _canvas(width: int, height: int, colour=(7, 11, 18)) -> list[bytearray]:
    row = bytes(colour) * width
    return [bytearray(row) for _ in range(height)]


def _rect(rows, x0, y0, x1, y1, colour) -> None:
    height = len(rows)
    width = len(rows[0]) // 3
    x0, x1 = max(0, x0), min(width, x1)
    y0, y1 = max(0, y0), min(height, y1)
    pixel = bytes(colour)
    for y in range(y0, y1):
        for x in range(x0, x1):
            at = x * 3
            rows[y][at:at + 3] = pixel


def _line(rows, x0, y0, x1, y1, colour, thickness=1) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        _rect(
            rows,
            x0 - thickness // 2,
            y0 - thickness // 2,
            x0 + (thickness + 1) // 2,
            y0 + (thickness + 1) // 2,
            colour,
        )
        if x0 == x1 and y0 == y1:
            break
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


_FONT = {
    " ": "00000/00000/00000/00000/00000/00000/00000",
    "!": "00100/00100/00100/00100/00100/00000/00100",
    "#": "01010/11111/01010/01010/11111/01010/00000",
    "-": "00000/00000/00000/11111/00000/00000/00000",
    ".": "00000/00000/00000/00000/00000/00110/00110",
    "/": "00001/00010/00100/01000/10000/00000/00000",
    "0": "01110/10001/10011/10101/11001/10001/01110",
    "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111",
    "3": "11110/00001/00001/01110/00001/00001/11110",
    "4": "00010/00110/01010/10010/11111/00010/00010",
    "5": "11111/10000/10000/11110/00001/00001/11110",
    "6": "01110/10000/10000/11110/10001/10001/01110",
    "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110",
    "9": "01110/10001/10001/01111/00001/00001/01110",
    ":": "00000/00110/00110/00000/00110/00110/00000",
    "=": "00000/11111/00000/11111/00000/00000/00000",
    "?": "01110/10001/00001/00010/00100/00000/00100",
    "@": "01110/10001/10111/10101/10111/10000/01110",
    "A": "01110/10001/10001/11111/10001/10001/10001",
    "B": "11110/10001/10001/11110/10001/10001/11110",
    "C": "01111/10000/10000/10000/10000/10000/01111",
    "D": "11110/10001/10001/10001/10001/10001/11110",
    "E": "11111/10000/10000/11110/10000/10000/11111",
    "F": "11111/10000/10000/11110/10000/10000/10000",
    "G": "01111/10000/10000/10111/10001/10001/01111",
    "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "01110/00100/00100/00100/00100/00100/01110",
    "J": "00111/00010/00010/00010/10010/10010/01100",
    "K": "10001/10010/10100/11000/10100/10010/10001",
    "L": "10000/10000/10000/10000/10000/10000/11111",
    "M": "10001/11011/10101/10101/10001/10001/10001",
    "N": "10001/11001/10101/10011/10001/10001/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110",
    "P": "11110/10001/10001/11110/10000/10000/10000",
    "Q": "01110/10001/10001/10001/10101/10010/01101",
    "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110",
    "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110",
    "V": "10001/10001/10001/10001/10001/01010/00100",
    "W": "10001/10001/10001/10101/10101/10101/01010",
    "X": "10001/10001/01010/00100/01010/10001/10001",
    "Y": "10001/10001/01010/00100/00100/00100/00100",
    "Z": "11111/00001/00010/00100/01000/10000/11111",
    "_": "00000/00000/00000/00000/00000/00000/11111",
}


def _draw_text(rows, x, y, value, colour=(225, 235, 245), scale=1) -> None:
    """Draw review labels without adding an image-library dependency."""
    cursor = x
    for character in value.upper():
        glyph = _FONT.get(character, _FONT["?"]).split("/")
        for row_index, pattern in enumerate(glyph):
            for column, bit in enumerate(pattern):
                if bit == "1":
                    _rect(
                        rows,
                        cursor + column * scale,
                        y + row_index * scale,
                        cursor + (column + 1) * scale,
                        y + (row_index + 1) * scale,
                        colour,
                    )
        cursor += 6 * scale


def _fit_label(value: str, characters: int) -> str:
    if len(value) <= characters:
        return value
    return value[:max(1, characters - 3)] + "..."


def _path_colour(path: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(path.encode("utf-8")).digest()
    return (
        55 + digest[0] % 170,
        55 + digest[1] % 170,
        55 + digest[2] % 170,
    )


def _cut_colour(kind: str) -> tuple[int, int, int]:
    if kind == "quiet_vector_window":
        return (255, 62, 196)
    if kind == "text_structure":
        return (73, 220, 255)
    if kind in {"file_end", "release_end"}:
        return (83, 255, 150)
    return (255, 184, 73)


def _write_apng(path: str, frames, delay_ms=1400, text_chunks=()) -> None:
    height = len(frames[0])
    width = len(frames[0][0]) // 3
    out = [
        b"\x89PNG\r\n\x1a\n",
        machinesoul._chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        ),
    ]
    for key, value in text_chunks:
        out.append(
            machinesoul._chunk(
                b"tEXt",
                key.encode("latin-1") + b"\x00" + value.encode("utf-8"),
            )
        )
    out.append(machinesoul._chunk(b"acTL", struct.pack(">II", len(frames), 0)))
    sequence = 0
    for index, rows in enumerate(frames):
        raw = b"".join(b"\x00" + bytes(row) for row in rows)
        out.append(
            machinesoul._chunk(
                b"fcTL",
                struct.pack(
                    ">IIIIIHHBB",
                    sequence,
                    width,
                    height,
                    0,
                    0,
                    delay_ms,
                    1000,
                    0,
                    0,
                ),
            )
        )
        sequence += 1
        compressed = zlib.compress(raw, 9)
        if index == 0:
            out.append(machinesoul._chunk(b"IDAT", compressed))
        else:
            out.append(
                machinesoul._chunk(
                    b"fdAT",
                    struct.pack(">I", sequence) + compressed,
                )
            )
            sequence += 1
    out.append(machinesoul._chunk(b"IEND", b""))
    with open(path, "wb") as handle:
        handle.write(b"".join(out))


def render_plan_apng(plan_path: str, out_path: str) -> dict:
    """Render one lossless overview frame plus one frame per proposed cut."""
    plan_sha = _sha256_file(plan_path)
    with open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    if plan.get("format") != FORMAT:
        raise ReleaseError("not a machinesoul cut plan")

    width, height = 1200, 420
    left, right = 48, width - 48
    file_starts = {}
    position = 0
    for record in plan["files"]:
        file_starts[record["path"]] = position
        position += record["size"]
    total = max(1, position)

    frames = []
    overview = _canvas(width, height)
    _draw_text(
        overview,
        left,
        18,
        _fit_label(f"{plan['prefix']} CUT MAP", 90),
        (235, 244, 255),
        2,
    )
    _draw_text(overview, left, 46, f"PLAN SHA256 {plan_sha}")
    _draw_text(
        overview,
        left,
        63,
        f"{len(plan['capsules'])} CAPSULES / "
        f"{len(plan['files'])} PRESERVED FILES / "
        f"{plan['total_size']} PRESERVED SOURCE UNITS",
        (155, 179, 205),
    )
    _rect(overview, left, 94, right, 172, (20, 29, 43))
    for record in plan["files"]:
        start = file_starts[record["path"]]
        end = start + record["size"]
        x0 = left + int((right - left) * start / total)
        x1 = left + max(1, int((right - left) * end / total))
        _rect(overview, x0, 100, x1, 166, _path_colour(record["path"]))
    for capsule in plan["capsules"]:
        boundary = capsule["boundary"]
        global_cut = file_starts[boundary["path"]] + boundary["offset"]
        x = left + int((right - left) * global_cut / total)
        colour = _cut_colour(boundary["kind"])
        _line(overview, x, 86, x, 184, colour, 4)
    _draw_text(overview, left, 208, "COLOURED BANDS = SOURCE FILES")
    _rect(overview, left, 232, left + 54, 238, _cut_colour("file_end"))
    _draw_text(overview, left + 66, 229, "FILE OR RELEASE SEAM")
    _rect(
        overview,
        left,
        260,
        left + 54,
        266,
        _cut_colour("quiet_vector_window"),
    )
    _draw_text(overview, left + 66, 257, "QUIET IN-FILE VECTOR WINDOW")
    _rect(overview, left, 288, left + 54, 294, _cut_colour("text_structure"))
    _draw_text(overview, left + 66, 285, "RULE / DEF / CLASS SEAM")
    _rect(overview, left, 316, left + 54, 322, _cut_colour("forced"))
    _draw_text(overview, left + 66, 313, "FORCED FALLBACK")
    _draw_text(
        overview,
        left,
        354,
        "FRAME 0 = WHOLE RELEASE. LATER FRAMES = ONE PROPOSED CAPSULE.",
        (155, 179, 205),
    )
    _draw_text(
        overview,
        left,
        374,
        "LOWER ACTIVITY IS QUIETER. NO CAPSULE HAS BEEN CUT.",
        (255, 218, 122),
    )
    frames.append(overview)

    for capsule in plan["capsules"]:
        rows = _canvas(width, height)
        boundary = capsule["boundary"]
        colour = _cut_colour(boundary["kind"])
        _draw_text(
            rows,
            left,
            17,
            f"CAPSULE {capsule['index']:02d} OF "
            f"{len(plan['capsules']):02d} / "
            f"{boundary['kind'].replace('_', ' ')}",
            colour,
            2,
        )
        _draw_text(
            rows,
            left,
            43,
            _fit_label(f"FILE {boundary['path']}", 180),
        )
        _draw_text(
            rows,
            left,
            58,
            f"CUT OFFSET {boundary['offset']} / "
            f"ACTIVITY {boundary.get('activity', 0.0):.8f}",
            (155, 179, 205),
        )
        _rect(rows, left, 84, right, 180, (20, 29, 43))
        extent = max(1, capsule["data_size"])
        for entry in capsule["entries"]:
            x0 = left + int((right - left) * entry["data_offset"] / extent)
            x1 = left + max(
                1,
                int(
                    (right - left)
                    * (entry["data_offset"] + entry["length"])
                    / extent
                ),
            )
            _rect(rows, x0, 92, x1, 172, _path_colour(entry["path"]))
        _line(rows, right - 2, 76, right - 2, 188, colour, 5)
        _draw_text(
            rows,
            left,
            195,
            _fit_label(boundary["detail"], 180),
            colour,
        )

        profile = boundary.get("profile", [])
        if profile:
            low = min(item["offset"] for item in profile)
            high = max(item["offset"] for item in profile)
            activities = [item["activity"] for item in profile]
            minimum, maximum = min(activities), max(activities)
            span = max(1e-9, maximum - minimum)
            points = []
            for item in profile:
                x = left + int(
                    (right - left) * (item["offset"] - low) / max(1, high - low)
                )
                y = 352 - int(115 * (item["activity"] - minimum) / span)
                points.append((x, y))
            for first, second in zip(points, points[1:]):
                _line(rows, *first, *second, (128, 165, 196), 2)
            chosen_x = left + int(
                (right - left)
                * (boundary["offset"] - low)
                / max(1, high - low)
            )
            _line(rows, chosen_x, 224, chosen_x, 362, colour, 4)
            _draw_text(
                rows,
                left,
                370,
                f"ACTIVITY SEARCH {low} TO {high} / "
                "SELECTED LINE IS THE QUIETEST REVIEWED WINDOW",
                (155, 179, 205),
            )
        else:
            _line(rows, left, 286, right, 286, colour, 5)
            _draw_text(
                rows,
                left,
                302,
                "STRUCTURAL SEAM / NO IN-FILE ACTIVITY SEARCH NEEDED",
                (155, 179, 205),
            )
        _draw_text(rows, left, 402, f"PLAN {plan_sha}", (100, 123, 150))
        frames.append(rows)

    legend = (
        "frame 0=whole release; later frames=one capsule each; "
        "green=file/release seam; cyan=text rule/def seam; "
        "magenta=quiet in-file vector window; orange=forced; "
        "coloured bands=source files; graph=local vector activity"
    )
    _write_apng(
        out_path,
        frames,
        text_chunks=(
            ("PlanSHA256", plan_sha),
            ("Legend", legend),
            ("FrameCount", str(len(frames))),
        ),
    )
    return {
        "plan_sha256": plan_sha,
        "frames": len(frames),
        "width": width,
        "height": height,
        "sha256": _sha256_file(out_path),
        "bytes": os.path.getsize(out_path),
    }


def _validate_source(plan: dict) -> dict[str, SourceFile]:
    root = plan["source_root"]
    by_path = {}
    for record in plan["files"]:
        relative = _safe_relative(record["path"])
        full = os.path.realpath(os.path.join(root, relative.replace("/", os.sep)))
        if full != root and not full.startswith(root + os.sep):
            raise ReleaseError(f"source path escapes root: {relative}")
        if os.path.islink(full) or _is_reparse(full) or not os.path.isfile(full):
            raise ReleaseError(f"planned source is missing or unsafe: {relative}")
        size = os.path.getsize(full)
        digest = _sha256_file(full)
        if size != record["size"] or digest != record["sha256"]:
            raise ReleaseError(f"planned source changed after review: {relative}")
        by_path[relative] = SourceFile(relative, full, size, digest)
    return by_path


def _write_decoded_part(
    capsule: dict,
    sources: dict[str, SourceFile],
    path: str,
) -> str:
    running = hashlib.sha256()
    written = 0
    with open(path, "xb") as out:
        for entry in capsule["entries"]:
            target = entry["data_offset"]
            if target < written:
                raise ReleaseError("capsule entries overlap")
            padding = target - written
            if padding:
                block = b"\x00" * padding
                out.write(block)
                running.update(block)
                written += padding

            source = sources[entry["path"]]
            remaining = entry["length"]
            with open(source.full_path, "rb") as handle:
                handle.seek(entry["file_offset"])
                while remaining:
                    block = handle.read(min(BLOCK, remaining))
                    if not block:
                        raise ReleaseError(
                            f"{source.path} changed while cutting"
                        )
                    out.write(block)
                    running.update(block)
                    written += len(block)
                    remaining -= len(block)
    if written != capsule["data_size"]:
        raise ReleaseError(
            f"planned {capsule['data_size']} source units, wrote {written}"
        )
    return running.hexdigest()


def cut(
    plan_path: str,
    approved_sha256: str,
    out_dir: str,
    manifest_path: str,
) -> dict:
    actual_plan_sha = _sha256_file(plan_path)
    if actual_plan_sha.lower() != approved_sha256.lower():
        raise ReleaseError(
            "reviewed plan hash does not match; no capsule was written"
        )
    with open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    if plan.get("format") != FORMAT:
        raise ReleaseError("not a machinesoul release plan")

    sources = _validate_source(plan)
    os.makedirs(out_dir, exist_ok=True)
    completed = []
    for record in plan["capsules"]:
        capsule = json.loads(json.dumps(record))
        raw = os.path.join(out_dir, "." + capsule["decoded_name"] + ".building")
        png = os.path.join(out_dir, capsule["name"])
        check = raw + ".verified"
        if any(os.path.exists(path) for path in (raw, png, check)):
            raise ReleaseError(f"cut output already exists for {capsule['name']}")

        try:
            decoded_sha = _write_decoded_part(capsule, sources, raw)
            for entry in capsule["entries"]:
                source = sources[entry["path"]]
                entry["sha256"] = _sha256_range(
                    source.full_path,
                    entry["file_offset"],
                    entry["length"],
                )

            machinesoul.build_stream(raw, png)
            if os.path.getsize(png) >= GITHUB_ASSET_LIMIT:
                raise ReleaseError(
                    f"{capsule['name']} exceeds GitHub's asset ceiling"
                )
            meta = machinesoul.extract_stream(png, check)
            if meta["sha256"] != decoded_sha:
                raise ReleaseError(
                    f"{capsule['name']} did not decompile to its source"
                )
            if _sha256_file(check) != decoded_sha:
                raise ReleaseError(
                    f"{capsule['name']} verification copy differs"
                )
            capsule["decoded_sha256"] = decoded_sha
            capsule["capsule_size"] = os.path.getsize(png)
            capsule["capsule_sha256"] = _sha256_file(png)
            completed.append(capsule)
        except BaseException:
            if os.path.exists(png):
                os.remove(png)
            raise
        finally:
            for temporary in (raw, check):
                if os.path.exists(temporary):
                    os.remove(temporary)

    # The reviewed plan is a local build record and needs the absolute source
    # root so `cut` can prove it is cutting the same tree.  That workstation
    # path is private build metadata, not part of the public reconstruction
    # language.
    manifest = {
        key: value
        for key, value in plan.items()
        if key != "source_root"
    }
    manifest["plan_sha256"] = actual_plan_sha
    manifest["capsules"] = completed
    _write_json(manifest_path, manifest)
    return manifest


def _validate_manifest(manifest: dict) -> None:
    if manifest.get("format") != FORMAT:
        raise ReleaseError("not a machinesoul release manifest")
    paths = set()
    for record in manifest.get("files", []):
        path = _safe_relative(record["path"])
        if path in paths:
            raise ReleaseError(f"duplicate manifest path: {path}")
        paths.add(path)
        if record["size"] < 0 or not re.fullmatch(
            r"[0-9a-f]{64}", record["sha256"]
        ):
            raise ReleaseError(f"invalid file record: {path}")


def combine_manifests(
    windows_path: str,
    optional_14b_path: str,
    out_path: str,
) -> dict:
    """Write the two independently cut components as one public manifest."""
    components = {}
    for name, path in (
        ("windows", windows_path),
        ("optional_14b", optional_14b_path),
    ):
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        _validate_manifest(manifest)
        components[name] = manifest

    combined = {
        "format": COMBINED_FORMAT,
        "components": components,
    }
    _write_json(out_path, combined)
    return combined


def _load_reassembly_manifest(
    manifest_path: str,
    component: str | None,
) -> dict:
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    if manifest.get("format") == COMBINED_FORMAT:
        if component not in COMBINED_COMPONENTS:
            choices = ", ".join(COMBINED_COMPONENTS)
            raise ReleaseError(
                f"combined manifest requires a component: {choices}"
            )
        components = manifest.get("components")
        if not isinstance(components, dict) or component not in components:
            raise ReleaseError(f"combined manifest is missing {component}")
        manifest = components[component]
    elif component is not None:
        raise ReleaseError("component applies only to a combined manifest")

    _validate_manifest(manifest)
    return manifest


def _promote_directory(temporary: str, destination: str) -> None:
    """Finish atomically, tolerating brief Windows scanner file handles."""
    delays = (0.1, 0.25, 0.5, 1.0, 2.0)
    for attempt in range(len(delays) + 1):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError:
            if attempt == len(delays):
                raise
            time.sleep(delays[attempt])


def reassemble(
    manifest_path: str,
    segments_dir: str,
    out_dir: str,
    component: str | None = None,
) -> None:
    manifest = _load_reassembly_manifest(manifest_path, component)
    out_dir = os.path.realpath(out_dir)
    if os.path.exists(out_dir):
        raise ReleaseError(f"reassembly target already exists: {out_dir}")
    parent = os.path.dirname(out_dir)
    os.makedirs(parent, exist_ok=True)
    temporary = tempfile.mkdtemp(
        prefix="." + os.path.basename(out_dir) + ".assembling-",
        dir=parent,
    )

    try:
        capsules = {}
        entries_by_path: dict[str, list[tuple[dict, dict]]] = {}
        for capsule in manifest["capsules"]:
            decoded = os.path.realpath(
                os.path.join(segments_dir, capsule["decoded_name"])
            )
            segment_root = os.path.realpath(segments_dir)
            if not decoded.startswith(segment_root + os.sep):
                raise ReleaseError("decoded capsule path escapes its folder")
            if (
                not os.path.isfile(decoded)
                or os.path.getsize(decoded) != capsule["data_size"]
                or _sha256_file(decoded) != capsule["decoded_sha256"]
            ):
                raise ReleaseError(
                    f"decoded capsule is missing or damaged: "
                    f"{capsule['decoded_name']}"
                )
            capsules[capsule["index"]] = (capsule, decoded)
            for entry in capsule["entries"]:
                path = _safe_relative(entry["path"])
                entries_by_path.setdefault(path, []).append((capsule, entry))

        for file_record in manifest["files"]:
            relative = _safe_relative(file_record["path"])
            destination = os.path.realpath(
                os.path.join(temporary, relative.replace("/", os.sep))
            )
            if not destination.startswith(temporary + os.sep):
                raise ReleaseError(f"output path escapes target: {relative}")
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            expected_offset = 0
            digest = hashlib.sha256()
            with open(destination, "xb") as out:
                pieces = sorted(
                    entries_by_path.get(relative, []),
                    key=lambda item: item[1]["file_offset"],
                )
                for capsule, entry in pieces:
                    if entry["file_offset"] != expected_offset:
                        raise ReleaseError(
                            f"segments do not cover {relative} consecutively"
                        )
                    decoded = capsules[capsule["index"]][1]
                    remaining = entry["length"]
                    segment_digest = hashlib.sha256()
                    with open(decoded, "rb") as source:
                        source.seek(entry["data_offset"])
                        while remaining:
                            block = source.read(min(BLOCK, remaining))
                            if not block:
                                raise ReleaseError(
                                    f"decoded segment ends inside {relative}"
                                )
                            out.write(block)
                            digest.update(block)
                            segment_digest.update(block)
                            expected_offset += len(block)
                            remaining -= len(block)
                    if segment_digest.hexdigest() != entry["sha256"]:
                        raise ReleaseError(
                            f"segment hash mismatch while restoring {relative}"
                        )

            if (
                expected_offset != file_record["size"]
                or digest.hexdigest() != file_record["sha256"]
            ):
                raise ReleaseError(f"restored file differs: {relative}")

        _promote_directory(temporary, out_dir)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _cmd_plan(args) -> None:
    plan = make_plan(args.source, args.prefix, args.payload_limit)
    digest = write_plan(plan, args.out, args.markdown)
    print(f"plan: {args.out}")
    print(f"review: {args.markdown}")
    print(f"sha256: {digest}")
    print(f"capsules: {len(plan['capsules'])}")


def _cmd_cut(args) -> None:
    manifest = cut(
        args.plan,
        args.approved_sha256,
        args.out_dir,
        args.manifest,
    )
    print(f"cut {len(manifest['capsules'])} verified machinesoul capsules")
    print(f"manifest: {args.manifest}")


def _cmd_render(args) -> None:
    report = render_plan_apng(args.plan, args.out)
    print(f"cut map: {args.out}")
    print(f"plan sha256: {report['plan_sha256']}")
    print(
        f"frames: {report['frames']} at "
        f"{report['width']}x{report['height']}"
    )
    print(f"cut map sha256: {report['sha256']}")


def _cmd_reassemble(args) -> None:
    reassemble(args.manifest, args.segments_dir, args.out, args.component)
    print(f"reassembled and verified: {args.out}")


def _cmd_combine(args) -> None:
    combine_manifests(args.windows, args.optional_14b, args.out)
    print(f"combined manifest: {args.out}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    plan_parser = sub.add_parser("plan", help="write a reviewable cut map")
    plan_parser.add_argument("source")
    plan_parser.add_argument("--prefix", required=True)
    plan_parser.add_argument("--payload-limit", type=int,
                             default=DEFAULT_PAYLOAD_LIMIT)
    plan_parser.add_argument("--out", required=True)
    plan_parser.add_argument("--markdown", required=True)
    plan_parser.set_defaults(func=_cmd_plan)

    cut_parser = sub.add_parser("cut", help="cut only an approved plan")
    cut_parser.add_argument("plan")
    cut_parser.add_argument("--approved-sha256", required=True)
    cut_parser.add_argument("--out-dir", required=True)
    cut_parser.add_argument("--manifest", required=True)
    cut_parser.set_defaults(func=_cmd_cut)

    render = sub.add_parser(
        "render",
        help="render the hashed cut plan as a lossless APNG review map",
    )
    render.add_argument("plan")
    render.add_argument("--out", required=True)
    render.set_defaults(func=_cmd_render)

    restore = sub.add_parser(
        "reassemble",
        help="rebuild and verify the original directory from decoded capsules",
    )
    restore.add_argument("manifest")
    restore.add_argument("segments_dir")
    restore.add_argument("--out", required=True)
    restore.add_argument("--component", choices=COMBINED_COMPONENTS)
    restore.set_defaults(func=_cmd_reassemble)

    combine = sub.add_parser(
        "combine",
        help="combine the Windows and optional 14B manifests",
    )
    combine.add_argument("--windows", required=True)
    combine.add_argument("--optional-14b", required=True)
    combine.add_argument("--out", required=True)
    combine.set_defaults(func=_cmd_combine)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ReleaseError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
