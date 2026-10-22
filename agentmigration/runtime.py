"""Chapter 8: the consumer loop with intent-before-effect checkpoints, so a run
survives its process. Chapter 15: budget ceilings enforced by code; the model is
informed, the code decides."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .envelope import Envelope, EnvelopeError
from .tools import Tool, ToolError, idempotency_key, validate_and_coerce, shape, RepeatDetector


class Crash(Exception):
    """Raised by tests to simulate the process dying at a chosen moment."""


@dataclass
class Run:
    run_id: str
    steps: int = 0
    tokens: int = 0
    done: bool = False
    trace: list[dict[str, Any]] = field(default_factory=list)   # committed steps
    intent: dict[str, Any] | None = None                        # written before the effect
    output: Any = None
    exhausted_reason: str | None = None


class CheckpointStore:
    """In-memory stand-in for the recorder's table. Every write is a full snapshot."""

    def __init__(self):
        self.runs: dict[str, Run] = {}
        self.effects: dict[str, Any] = {}      # idempotency key -> result (the 'service')

    def resume_or_start(self, env: Envelope) -> Run:
        return self.runs.setdefault(env.run_id, Run(run_id=env.run_id))

    def checkpoint_intent(self, run: Run, name: str, args: dict, key: str) -> None:
        run.intent = {"name": name, "args": args, "key": key}

    def checkpoint_result(self, run: Run, result: Any) -> None:
        assert run.intent is not None
        run.trace.append({**run.intent, "result": result})
        run.intent = None
        run.steps += 1


RESERVE_SECONDS = 2.0


def step(run: Run, env: Envelope, model, tools: dict[str, Tool], store: CheckpointStore,
         repeat: RepeatDetector, tokens_per_step: int = 1000, crash_before_effect: Callable[[Run], bool] | None = None,
         now: Callable[[], float] = time.time) -> Run:
    """One step. Listing 15.1 with Listing 8.1's checkpoints folded in."""
    if now() >= env.deadline - RESERVE_SECONDS:
        return conclude(run, model, "deadline")
    if run.steps >= env.budget.steps - 1:
        return conclude(run, model, "steps")
    if run.tokens >= env.budget.tokens * 0.9:
        return conclude(run, model, "tokens")

    # A restart with an intent and no result: finish that call first.
    if run.intent is not None:
        name, args, key = run.intent["name"], run.intent["args"], run.intent["key"]
        tool = tools[name]
        if tool.mutates and key in store.effects:          # the effect already happened
            store.checkpoint_result(run, store.effects[key])
        else:
            store.checkpoint_result(run, _execute(tool, args, key, store))
        return run

    call = model.next_call(run)
    if call is None:
        run.output = model.final_output(run)
        run.done = True
        return run
    tool = tools.get(call.name)
    if tool is None:
        store.checkpoint_intent(run, call.name, call.args, "-")
        store.checkpoint_result(run, str(ToolError(f"No tool named `{call.name}`.", f"Available: {sorted(tools)}.", retryable=True)))
        return run
    log: list[str] = []
    try:
        repeat.check(call.name, call.args)
        args = validate_and_coerce(tool, call.args, log)
    except ToolError as e:
        store.checkpoint_intent(run, call.name, call.args, "-")
        store.checkpoint_result(run, str(e))
        if not e.retryable:
            return conclude(run, model, "terminal tool error")
        return run
    key = idempotency_key(run.run_id, call.name, args)
    store.checkpoint_intent(run, call.name, args, key)
    if crash_before_effect and crash_before_effect(run):
        raise Crash()
    store.checkpoint_result(run, _execute(tool, args, key, store))
    run.tokens += tokens_per_step
    return run


def _execute(tool: Tool, args: dict, key: str, store: CheckpointStore) -> str:
    if key in store.effects:                      # idempotent: same key, same result
        return store.effects[key]
    result = shape(tool, str(tool.fn(**args)))
    store.effects[key] = result
    return result


def conclude(run: Run, model, reason: str) -> Run:
    run.exhausted_reason = reason
    run.output = model.final_output(run)          # one last step, reserved in the budget
    run.done = True
    return run


def consume(env: Envelope, model, tools: dict[str, Tool], store: CheckpointStore,
            crash_before_effect: Callable[[Run], bool] | None = None, now=time.time) -> Run:
    """Listing 8.1: validate, refuse if bad, resume, loop until done."""
    env.validate(now())
    run = store.resume_or_start(env)
    repeat = RepeatDetector()
    for t in run.trace:                            # rebuild the detector's memory on resume
        repeat.check(t["name"], t["args"])
    while not run.done:
        step(run, env, model, tools, store, repeat, crash_before_effect=crash_before_effect, now=now)
    return run
