"""Reasoning receipts: where an answer came from, and what would check it.

Sable can retrieve, read trajectories, run several models, and hold a large
library. What she could not do until now is say, visibly, which part of an
answer came from a file, which part is the model talking, and which part
nobody has verified. Every capability the project has added makes that
distinction more load-bearing, not less: a bigger library means more chances
to mistake a document for authority.

A receipt is deliberately not a confidence score. A number invites the reader
to trust it and hides the thing worth reading, which is the *kind* of claim
being made:

    OBSERVED   read out of a named local file, quotable and checkable
    INFERRED   the model's own words, grounded in something but not copied
    PROPOSED   a suggestion or plan; nothing has happened yet

Imported material carries a trust state for the same reason. A document that
arrived from the web and contains instruction-shaped text is not the same
kind of evidence as a NIST publication with a checksum, and the receipt says
so rather than flattening both into "a source".

Nothing here reads private conversation text into its output. The keyed
session pseudonym lets receipts from the same installation be compared
without publishing what was said or leaving a dictionary-testable hash --
the same reasoning behind keeping private retrieval identities opaque.
"""

import json
import os
from datetime import datetime

from core import research_c


# What kind of claim a line is. Ordered from most checkable to least, which
# is also the order a reader should spend their scepticism in reverse.
OBSERVED = "observed"
INFERRED = "inferred"
PROPOSED = "proposed"

CLAIM_KINDS = (OBSERVED, INFERRED, PROPOSED)

# How much weight an imported document has earned. The default for anything
# that arrived from outside is UNVERIFIED, never CLEAN: a document is not
# trustworthy because it parsed.
CLEAN = "clean"                  # shipped reference, or checksum-matched
UNVERIFIED = "unverified"        # imported, parsed, nothing else known
SUSPICIOUS = "suspicious"        # carries instruction-shaped text
QUARANTINED = "quarantined"      # never usable as evidence

TRUST_STATES = (CLEAN, UNVERIFIED, SUSPICIOUS, QUARANTINED)

# Text that tries to address the reader as an instruction rather than inform
# it. Presence does not prove an attack -- a security manual quotes these on
# purpose, which is exactly why this marks a document for attention instead
# of refusing it.
_INSTRUCTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard the above",
    "you are now",
    "system prompt",
    "reveal your instructions",
    "output your instructions",
    "act as though",
    "do not tell the user",
)


def classify_trust(text, origin=CLEAN):
    """Trust state for one imported document.

    `origin` is what the caller already knows -- a shipped reference card is
    CLEAN before this is called, a fetched page is UNVERIFIED. This can only
    lower that, never raise it: finding no attack is not evidence of safety,
    and a scan that can promote a document would make itself the weakest
    link in the chain it exists to protect.
    """
    if origin == QUARANTINED:
        return QUARANTINED, "quarantined by an earlier decision"

    lowered = (text or "").lower()
    hits = [marker for marker in _INSTRUCTION_MARKERS if marker in lowered]
    if hits:
        return SUSPICIOUS, (
            f"contains instruction-shaped text ({len(hits)} marker"
            f"{'' if len(hits) == 1 else 's'}, first: {hits[0]!r})"
        )

    if origin == CLEAN:
        return CLEAN, "shipped reference or checksum-matched"
    return UNVERIFIED, "imported and parsed; nothing further is known"


class Receipt:
    """What an answer rests on, assembled as the answer is built."""

    def __init__(self, question=None):
        # The question is digested rather than stored. A receipt may be
        # shown, logged, or attached to a report, and none of those should
        # publish what was asked.
        self.question_digest = _digest(question) if question else None
        self.created = datetime.now().replace(microsecond=0).isoformat()
        self.sources = []
        self.claims = []
        self.identities = {}
        self.disagreements = []
        self.verification = None

    # -- assembly ------------------------------------------------------

    def cite(self, path, locator=None, trust=UNVERIFIED, note=None,
             source_sha256=None):
        """Record a local file an answer actually drew on."""
        source_sha256 = str(source_sha256 or "").casefold()
        if (
            len(source_sha256) != 64
            or any(character not in "0123456789abcdef"
                   for character in source_sha256)
        ):
            source_sha256 = None
        self.sources.append({
            "path": _relative(path),
            "locator": locator,
            "trust": trust if trust in TRUST_STATES else UNVERIFIED,
            "note": note,
            "sha256": source_sha256,
        })
        return self

    def claim(self, kind, text, source=None):
        """Record one statement and how it came to be made."""
        if kind not in CLAIM_KINDS:
            raise ValueError(f"unknown claim kind: {kind!r}")
        self.claims.append({
            "kind": kind,
            "text": text,
            "source": _relative(source) if source else None,
        })
        return self

    def identify(self, role, name, digest=None):
        """Record which model or dictionary produced part of this."""
        self.identities[role] = {"name": name, "digest": digest}
        return self

    def disagree(self, subject, positions):
        """Record where the council did not converge.

        Kept as a map rather than reduced to a winner. Disagreement between
        independently-trained models is the signal; a vote throws it away
        and returns a number that looks more certain than the evidence.
        """
        self.disagreements.append({"subject": subject,
                                   "positions": dict(positions)})
        return self

    def verify_by(self, action):
        """The single thing a reader could do to check this."""
        self.verification = action
        return self

    # -- reading -------------------------------------------------------

    @property
    def weakest_trust(self):
        """The least trustworthy thing this answer leaned on."""
        order = {CLEAN: 0, UNVERIFIED: 1, SUSPICIOUS: 2, QUARANTINED: 3}
        if not self.sources:
            return None
        return max((s["trust"] for s in self.sources), key=lambda t: order[t])

    @property
    def digest(self):
        """An installation-local fingerprint that publishes none of the text."""
        payload = json.dumps({
            "question": self.question_digest,
            "sources": [
                (s["path"], s["locator"], s["trust"], s.get("sha256"))
                        for s in self.sources],
            "claims": [(c["kind"], _digest(c["text"])) for c in self.claims],
            "identities": self.identities,
        }, sort_keys=True, default=str)
        return _digest(payload)

    def as_dict(self):
        return {
            "created": self.created,
            "question_digest": self.question_digest,
            "sources": list(self.sources),
            "claims": list(self.claims),
            "identities": dict(self.identities),
            "disagreements": list(self.disagreements),
            "verification": self.verification,
            "weakest_trust": self.weakest_trust,
            "digest": self.digest,
        }

    def render(self, width=70):
        """The receipt as plain text, for a terminal that has no colour."""
        rule = "-" * min(width, 70)
        out = ["RECEIPT", rule]

        if self.claims:
            for entry in self.claims:
                label = entry["kind"].upper().ljust(8)
                where = f"  [{entry['source']}]" if entry["source"] else ""
                out.append(f"{label} {entry['text']}{where}")
            out.append("")

        if self.sources:
            out.append("Drew on:")
            for entry in self.sources:
                mark = "" if entry["trust"] == CLEAN else f"  ({entry['trust']})"
                where = f":{entry['locator']}" if entry["locator"] else ""
                fingerprint = (
                    f"  sha256:{entry['sha256'][:12]}"
                    if entry.get("sha256")
                    else ""
                )
                out.append(
                    f"  {entry['path']}{where}{mark}{fingerprint}"
                )
            weakest = self.weakest_trust
            if weakest and weakest != CLEAN:
                out.append(f"  -- weakest source is {weakest}; "
                           "treat this answer accordingly")
            out.append("")

        if self.identities:
            out.append("Produced by:")
            for role, value in sorted(self.identities.items()):
                digest = f"  {value['digest'][:16]}" if value.get("digest") else ""
                out.append(f"  {role}: {value['name']}{digest}")
            out.append("")

        if self.disagreements:
            out.append("The council did not agree:")
            for entry in self.disagreements:
                out.append(f"  {entry['subject']}")
                for who, said in sorted(entry["positions"].items()):
                    out.append(f"    {who}: {said}")
            out.append("")

        if self.verification:
            out.append(f"To check it: {self.verification}")
            out.append("")

        out.append(f"receipt {self.digest[:16]}")
        return "\n".join(out)


def _digest(value):
    """Per-install pseudonym; private text is not dictionary-testable."""
    return research_c.digest(value)


def _relative(path):
    """Project-relative where possible, so a receipt names a file not a user.

    An already-relative path is normalised and returned as-is. Sending it
    through abspath() first would resolve it against the working directory,
    which is assistant/ when the app runs -- and a caller citing
    "assistant/knowledge/card.md" would be recorded as living in
    "assistant/assistant/knowledge/card.md". A receipt that cites a path
    nobody can open is worse than one that cites none.
    """
    if not path:
        return path

    text = str(path)
    if not os.path.isabs(text):
        return text.replace(os.sep, "/").lstrip("./")

    try:
        root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        relative = os.path.relpath(text, root).replace(os.sep, "/")
        if relative == ".." or relative.startswith("../"):
            opaque = research_c.digest(
                "external-source-path", os.path.normcase(text)
            )[:16]
            return f"external/source-{opaque}"
        return relative
    except (ValueError, OSError):
        opaque = research_c.digest(
            "external-source-path", os.path.normcase(text)
        )[:16]
        return f"external/source-{opaque}"
