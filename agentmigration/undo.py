"""Chapter 13: every write declares its inverse; rollback compensates in reverse
order and reports what it could not reverse."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class WriteRecord:
    tool: str
    undo_tool: str | None
    undo_args: dict[str, Any]
    window_open: Callable[[], bool] = lambda: True


@dataclass
class RollbackReport:
    reversed: list[str] = field(default_factory=list)
    not_reversed: list[tuple[str, str]] = field(default_factory=list)

    def __str__(self) -> str:
        a = f"reversed {len(self.reversed)}: {', '.join(self.reversed) or 'none'}"
        b = "; ".join(f"{t} cannot be reversed: {why}" for t, why in self.not_reversed)
        return a + ("; " + b if b else "")


def rollback(writes: list[WriteRecord], undo_tools: dict[str, Callable[..., Any]]) -> RollbackReport:
    """Called by deterministic code from the record. The agent does not undo itself."""
    rep = RollbackReport()
    for w in reversed(writes):
        if w.undo_tool is None:
            rep.not_reversed.append((w.tool, "no inverse declared"))
            continue
        if not w.window_open():
            rep.not_reversed.append((w.tool, "window closed"))
            continue
        undo_tools[w.undo_tool](**w.undo_args)
        rep.reversed.append(w.tool)
    return rep
