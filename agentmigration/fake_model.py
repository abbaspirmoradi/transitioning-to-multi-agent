"""A scripted stand-in for a model. Tests script what it 'decides'."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Call:
    name: str
    args: dict[str, Any]


@dataclass
class FakeModel:
    """Returns the scripted calls in order, then `final`."""
    script: list[Call] = field(default_factory=list)
    final: Any = None
    calls_made: int = 0

    def next_call(self, run) -> Call | None:
        if self.calls_made < len(self.script):
            c = self.script[self.calls_made]
            self.calls_made += 1
            return c
        return None

    def final_output(self, run):
        return self.final
