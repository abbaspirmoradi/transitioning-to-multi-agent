"""Chapter 9: resolution in order of cost. Deduplicate, verify (as a filter), vote,
adjudicate, escalate. Verification is the only step that corrects errors of fact."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from .facade import Comment


def same_claim(a: Comment, b: Comment) -> bool:
    """Chapter 6's equivalence rule: file, overlapping range, category. Body ignored."""
    return (a.path == b.path and a.category == b.category
            and a.start_line <= b.end_line and b.start_line <= a.end_line)


def deduplicate(items: list[Comment]) -> list[Comment]:
    kept: list[Comment] = []
    for c in items:
        if not any(same_claim(c, k) for k in kept):
            kept.append(c)
    return kept


@dataclass
class Verified:
    item: Comment
    status: str          # "verified" | "partial" | "unverified" | "failed"
    detail: str = ""


def verify_filter(items: list[Comment], verifier: Callable[[Comment], tuple[str, str]]) -> list[Verified]:
    """Run the verifier on each; drop failures, with the failure recorded."""
    out = []
    for c in items:
        status, detail = verifier(c)
        if status != "failed":
            out.append(Verified(c, status, detail))
    return out


def vote(samples: list[Any], unanimity: bool = False) -> Any | None:
    """Only for discrete answers. Returns None on a tie or, if required, non-unanimity."""
    if not samples:
        return None
    counts = Counter(samples).most_common()
    if unanimity:
        return counts[0][0] if len(counts) == 1 else None
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        return None
    return counts[0][0]


@dataclass
class Verdict:
    choice: int | None       # index into the candidates, or None for "cannot decide"
    confidence: float
    grounds: str


def adjudicate(candidates: list[Verified], judge: Callable[[list[Verified]], Verdict]) -> Verdict:
    """A judge is only trusted after its agreement with people has been measured (Chapter 14)."""
    return judge(candidates)


@dataclass
class EscalationPacket:
    input_ref: str
    candidates: list[Verified]
    strategy_tried: list[str]
    adjudicator_grounds: str = ""
    options: list[str] = field(default_factory=lambda: ["prefer_a", "prefer_b", "both", "neither"])


def resolve(a: Comment, b: Comment, verifier, judge=None, reversible: bool = True, input_ref: str = "") -> tuple[str, Any]:
    """The decision tree of Figure 9.1, for one pair."""
    tried = []
    if same_claim(a, b):
        return "deduplicate", a
    tried.append("dedup")
    survivors = verify_filter([a, b], verifier)
    tried.append("verify")
    if len(survivors) == 1:
        return "verify", survivors[0].item
    if len(survivors) == 0:
        return "verify", None
    if judge is not None and reversible:
        v = adjudicate(survivors, judge)
        tried.append("adjudicate")
        if v.choice is not None:
            return "adjudicate", survivors[v.choice].item
        return "escalate", EscalationPacket(input_ref, survivors, tried, v.grounds)
    return "escalate", EscalationPacket(input_ref, survivors, tried)
