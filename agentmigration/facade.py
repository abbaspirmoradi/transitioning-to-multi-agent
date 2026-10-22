"""Chapter 5: the facade. One contract, two implementations, a policy that chooses,
a deadline the facade owns, a filter against the contract, and a recorder that sees
everything. Chapter 6: shadow is a route, not a deploy."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Route(str, Enum):
    BASELINE = "baseline"
    SHADOW = "shadow"
    AGENT = "agent"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class Comment:
    path: str
    start_line: int
    end_line: int
    category: str
    body: str

    @staticmethod
    def valid(c: Any) -> bool:
        return (isinstance(c, Comment) and c.path and not c.path.startswith("/")
                and 1 <= c.start_line <= c.end_line and c.category in CATEGORIES
                and 0 < len(c.body) <= 2000)


CATEGORIES = {"style", "test-gap", "reliability", "secrets"}


@dataclass
class Policy:
    """Keyed per category and per cohort from day one, so partial rollback is config."""
    default: Route = Route.BASELINE
    by_category: dict[str, Route] = field(default_factory=dict)
    by_cohort: dict[str, Route] = field(default_factory=dict)
    kill_all: bool = False
    version: str = "1"

    def decide(self, ctx: "Context") -> Route:
        if self.kill_all:
            return Route.BASELINE
        r = self.by_cohort.get(ctx.cohort, self.default)
        return r


@dataclass
class Context:
    run_id: str
    cohort: str
    deadline_seconds: float
    key: str            # stable key for stickiness (e.g. the PR id)


@dataclass
class Record:
    route: Route
    run_id: str
    diff_hash: str
    output: list[Comment]
    baseline: list[Comment] | None = None
    error: str | None = None
    dropped: int = 0
    policy_version: str = "1"


class Recorder:
    def __init__(self):
        self.rows: list[Record] = []

    def log(self, **kw):
        self.rows.append(Record(**kw))


class AgentError(Exception):
    pass


class Timeout(Exception):
    pass


def with_deadline(fn: Callable, *args, seconds: float):
    """Reference implementation: cooperative. A real one runs fn in a worker and abandons it."""
    start = time.monotonic()
    out = fn(*args, deadline=start + seconds)
    if time.monotonic() - start > seconds:
        raise Timeout()
    return out


class ReviewCommenter:
    """Listing 5.1, made runnable."""

    def __init__(self, baseline, agent, policy: Policy, rec: Recorder):
        self.baseline, self.agent, self.policy, self.rec = baseline, agent, policy, rec

    def comments(self, diff: str, ctx: Context) -> list[Comment]:
        route = self.policy.decide(ctx)
        base = self.baseline.comments(diff, ctx)
        dh = str(hash(diff))
        if route is Route.BASELINE:
            self.rec.log(route=route, run_id=ctx.run_id, diff_hash=dh, output=base, policy_version=self.policy.version)
            return base
        try:
            out = with_deadline(self.agent.comments, diff, ctx, seconds=ctx.deadline_seconds)
            kept = [c for c in out if Comment.valid(c)]
            dropped = len(out) - len(kept)
        except (Timeout, AgentError) as err:
            self.rec.log(route=Route.FALLBACK, run_id=ctx.run_id, diff_hash=dh, output=base, baseline=base,
                         error=repr(err), policy_version=self.policy.version)
            return base
        self.rec.log(route=route, run_id=ctx.run_id, diff_hash=dh, output=kept, baseline=base,
                     dropped=dropped, policy_version=self.policy.version)
        return kept if route is Route.AGENT else base
