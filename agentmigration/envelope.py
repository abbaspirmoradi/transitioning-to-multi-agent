"""Chapter 8: the envelope. Absolute deadline, budget decremented per hop, and a cap
on the causation chain. Validated at every consumer."""
from __future__ import annotations
import time
from dataclasses import dataclass, field, replace


class EnvelopeError(ValueError):
    pass


@dataclass
class Budget:
    steps: int
    tokens: int
    children: int
    currency: float = 0.0

    def empty(self) -> bool:
        return self.steps <= 0 or self.tokens <= 0


@dataclass
class Envelope:
    message_id: str
    run_id: str
    correlation_id: str
    deadline: float                 # absolute epoch seconds
    budget: Budget
    principal: str
    tenant: str
    trust: str = "principal"
    causation: list[str] = field(default_factory=list)   # producer ids, oldest first
    prompt_version: str = "0"
    policy_version: str = "0"
    schema_version: int = 1
    max_chain: int = 8
    max_repeats_in_chain: int = 2

    def validate(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if self.deadline <= now:
            raise EnvelopeError("deadline already passed")
        if self.budget.empty():
            raise EnvelopeError("budget exhausted")
        if len(self.causation) > self.max_chain:
            raise EnvelopeError("causation chain too long")
        for p in set(self.causation):
            if self.causation.count(p) > self.max_repeats_in_chain:
                raise EnvelopeError(f"producer {p} repeats in the chain: ping-pong")

    def child(self, producer: str, share: float = 1.0, message_id: str | None = None) -> "Envelope":
        """A child holds at most what the parent held; never more."""
        if self.budget.children <= 0:
            raise EnvelopeError("no children remaining in budget")
        share = min(max(share, 0.0), 1.0)
        b = Budget(steps=int(self.budget.steps * share), tokens=int(self.budget.tokens * share),
                   children=self.budget.children - 1, currency=self.budget.currency * share)
        return replace(self, message_id=message_id or f"{self.message_id}.{producer}",
                       budget=b, causation=self.causation + [producer])
