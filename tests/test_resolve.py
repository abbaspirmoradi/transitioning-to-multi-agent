"""Chapter 9: dedup first, verify as a filter, adjudicate only when reversible, else escalate."""
from agentmigration.facade import Comment
from agentmigration.resolve import resolve, vote, EscalationPacket, Verdict

A = Comment("limiter.py", 41, 52, "reliability", "missing null check")
B = Comment("limiter.py", 44, 44, "style", "the check above makes this redundant")
A2 = Comment("limiter.py", 42, 50, "reliability", "null check missing here")


def test_duplicates_are_not_conflicts():
    assert resolve(A, A2, verifier=lambda c: ("unverified", "")) == ("deduplicate", A)


def test_verifier_filter_resolves_without_a_model():
    v = lambda c: ("failed", "no such check") if c.category == "style" else ("partial", "file and lines exist")
    assert resolve(A, B, verifier=v) == ("verify", A)


def test_no_verifier_and_reversible_goes_to_adjudicator_who_may_abstain():
    v = lambda c: ("unverified", "")
    strategy, out = resolve(A, B, verifier=v, judge=lambda cands: Verdict(None, 0.5, "both plausible"))
    assert strategy == "escalate" and isinstance(out, EscalationPacket) and "adjudicate" in out.strategy_tried


def test_not_reversible_escalates_instead_of_adjudicating():
    strategy, out = resolve(A, B, verifier=lambda c: ("unverified", ""), judge=lambda c: Verdict(0, 0.9, "x"), reversible=False)
    assert strategy == "escalate" and "adjudicate" not in out.strategy_tried


def test_vote_reduces_variance_and_returns_none_on_tie():
    assert vote(["yes", "yes", "no"]) == "yes"
    assert vote(["yes", "no"]) is None
    assert vote(["yes", "yes", "no"], unanimity=True) is None
