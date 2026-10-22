"""Chapter 5's six facade tests. The model is behind the agent adapter; here it is a stub."""
from agentmigration.facade import (ReviewCommenter, Policy, Route, Context, Recorder, Comment, AgentError)


class Baseline:
    def comments(self, diff, ctx):
        return [Comment("a.py", 1, 1, "style", "baseline finding")]


class Agent:
    def __init__(self, out=None, raise_=None, slow=0.0):
        self.out, self.raise_, self.slow = out or [], raise_, slow

    def comments(self, diff, ctx, deadline=None):
        if self.raise_:
            raise self.raise_
        if self.slow:
            import time; time.sleep(self.slow)
        return self.out


def ctx(cohort="team-a"):
    return Context(run_id="r1", cohort=cohort, deadline_seconds=0.05, key="pr-1")


def test_routing_decision_selects_expected_path():
    p = Policy(by_cohort={"team-a": Route.AGENT})
    rec = Recorder()
    f = ReviewCommenter(Baseline(), Agent([Comment("b.py", 2, 3, "test-gap", "agent finding")]), p, rec)
    assert f.comments("diff", ctx("team-a"))[0].body == "agent finding"
    assert f.comments("diff", ctx("team-b"))[0].body == "baseline finding"


def test_agent_error_falls_back_and_is_recorded_as_fallback():
    rec = Recorder()
    f = ReviewCommenter(Baseline(), Agent(raise_=AgentError("boom")), Policy(default=Route.AGENT), rec)
    out = f.comments("diff", ctx())
    assert out[0].body == "baseline finding"
    assert rec.rows[-1].route is Route.FALLBACK and "boom" in rec.rows[-1].error


def test_deadline_exceeded_falls_back():
    rec = Recorder()
    f = ReviewCommenter(Baseline(), Agent(out=[], slow=0.1), Policy(default=Route.AGENT), rec)
    out = f.comments("diff", ctx())
    assert out[0].body == "baseline finding" and rec.rows[-1].route is Route.FALLBACK


def test_invalid_output_is_dropped_counted_and_never_returned():
    rec = Recorder()
    bad = Comment("/etc/passwd", 1, 1, "style", "x")
    good = Comment("a.py", 5, 6, "reliability", "ok")
    f = ReviewCommenter(Baseline(), Agent([bad, good]), Policy(default=Route.AGENT), rec)
    out = f.comments("diff", ctx())
    assert out == [good] and rec.rows[-1].dropped == 1


def test_shadow_serves_baseline_and_records_both():
    rec = Recorder()
    agent_out = [Comment("a.py", 9, 9, "secrets", "leak")]
    f = ReviewCommenter(Baseline(), Agent(agent_out), Policy(default=Route.SHADOW), rec)
    out = f.comments("diff", ctx())
    assert out[0].body == "baseline finding"
    assert rec.rows[-1].output == agent_out and rec.rows[-1].baseline[0].body == "baseline finding"


def test_kill_switch_routes_everything_to_baseline_without_restart():
    p = Policy(default=Route.AGENT)
    rec = Recorder()
    f = ReviewCommenter(Baseline(), Agent([Comment("b.py", 2, 3, "test-gap", "agent")]), p, rec)
    assert f.comments("diff", ctx())[0].body == "agent"
    p.kill_all = True
    assert f.comments("diff", ctx())[0].body == "baseline finding"
