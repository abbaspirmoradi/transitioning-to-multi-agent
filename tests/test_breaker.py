"""Chapter 16: the breaker trips on latency with no errors at all, fails fast while
open, and closes after successful probes."""
from agentmigration.breaker import Breaker


def test_trips_on_latency_without_errors_then_recovers():
    b = Breaker(max_p95_seconds=10, open_for=30, probes_to_close=2)
    t = 0.0
    for _ in range(6):
        b.record(ok=True, seconds=45.0, now=t)
    assert b.state == "open" and not b.allow(now=t + 1)
    assert b.allow(now=t + 31) and b.state == "half-open"
    b.record(ok=True, seconds=1.0, now=t + 32)
    b.record(ok=True, seconds=1.0, now=t + 33)
    assert b.state == "closed"


def test_failed_probe_reopens():
    b = Breaker(max_error_rate=0.2, open_for=1)
    for ok in [False, False, True, True, True]:
        b.record(ok=ok, seconds=0.1, now=0)
    assert b.state == "open"
    assert b.allow(now=2)
    b.record(ok=False, seconds=0.1, now=2)
    assert b.state == "open"
