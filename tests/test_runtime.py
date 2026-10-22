"""Chapter 8: kill the consumer between intent and effect; the run resumes at the
committed step and the write executes once. Redelivery, expired deadline, and
exhausted budget are refused before any model call."""
import pytest
from agentmigration.envelope import Envelope, Budget, EnvelopeError
from agentmigration.fake_model import FakeModel, Call
from agentmigration.runtime import consume, CheckpointStore, Crash
from agentmigration.tools import Tool, Param

NOW = 1_000_000.0
posted = []


def post_comment(path, body):
    posted.append((path, body))
    return f"posted {path}"


TOOLS = {
    "read_file": Tool("read_file", {"path": Param("string"), "start_line": Param("integer", minimum=1)},
                      lambda path, start_line: f"{path}:{start_line} contents"),
    "post_comment": Tool("post_comment", {"path": Param("string"), "body": Param("string")}, post_comment,
                         mutates=True, reversible=True, undo="delete_comment"),
}


def env(**kw):
    base = dict(message_id="m1", run_id="r1", correlation_id="c1", deadline=NOW + 100,
                budget=Budget(steps=10, tokens=100_000, children=2), principal="system:pipeline", tenant="repo:a")
    base.update(kw)
    return Envelope(**base)


def script():
    return FakeModel(script=[Call("read_file", {"path": "a.py", "start_line": 1}),
                             Call("post_comment", {"path": "a.py", "body": "missing null check"}),
                             Call("read_file", {"path": "b.py", "start_line": 1})], final="done")


def test_crash_before_effect_resumes_same_run_and_write_executes_once():
    posted.clear()
    store = CheckpointStore()
    model = script()
    # crash the first time the write's intent is recorded, before it executes
    with pytest.raises(Crash):
        consume(env(), model, TOOLS, store, crash_before_effect=lambda run: run.intent and run.intent["name"] == "post_comment", now=lambda: NOW)
    run = store.runs["r1"]
    assert run.steps == 1 and run.intent["name"] == "post_comment" and posted == []
    # a new consumer picks the run up: same run, intent finished, then continues
    model2 = script(); model2.calls_made = 2        # the first two decisions were already made
    run = consume(env(), model2, TOOLS, store, now=lambda: NOW)
    assert run.done and run.output == "done"
    assert [t["name"] for t in run.trace] == ["read_file", "post_comment", "read_file"]
    assert posted == [("a.py", "missing null check")]


def test_redelivered_message_produces_one_outcome():
    posted.clear()
    store = CheckpointStore()
    consume(env(), script(), TOOLS, store, now=lambda: NOW)
    consume(env(), script(), TOOLS, store, now=lambda: NOW)   # redelivery: same run id
    assert posted == [("a.py", "missing null check")]


def test_expired_deadline_is_refused_without_a_model_call():
    m = script()
    with pytest.raises(EnvelopeError):
        consume(env(deadline=NOW - 1), m, TOOLS, CheckpointStore(), now=lambda: NOW)
    assert m.calls_made == 0


def test_exhausted_budget_is_refused_without_a_model_call():
    m = script()
    with pytest.raises(EnvelopeError):
        consume(env(budget=Budget(steps=0, tokens=0, children=0)), m, TOOLS, CheckpointStore(), now=lambda: NOW)
    assert m.calls_made == 0


def test_step_ceiling_concludes_with_a_reserved_last_step():
    m = FakeModel(script=[Call("read_file", {"path": "a.py", "start_line": 1})] * 50, final="partial")
    run = consume(env(budget=Budget(steps=4, tokens=100_000, children=0)), m, TOOLS, CheckpointStore(), now=lambda: NOW)
    assert run.done and run.exhausted_reason in ("steps", "terminal tool error") and run.output == "partial"
    assert run.steps <= 4


def test_child_envelope_never_exceeds_parent_and_chain_is_capped():
    e = env()
    c = e.child("orchestrator", share=0.5)
    assert c.budget.steps == 5 and c.budget.children == 1 and c.causation == ["orchestrator"]
    pp = e
    for _ in range(3):
        pp = pp.child("a").child("b") if pp.budget.children > 0 else pp
    bad = Envelope(**{**e.__dict__, "causation": ["a", "b", "a", "b", "a"]})
    with pytest.raises(EnvelopeError):
        bad.validate(NOW)
