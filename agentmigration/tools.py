"""Chapter 3: the tool layer. Validate, coerce (losslessly), shape, and phrase errors
so the model can learn from them. Chapter 16: the repeat detector."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable


class ToolError(Exception):
    """A four-part error: what was wrong, what would be valid, retryable?, what to do."""

    def __init__(self, what: str, valid: str = "", retryable: bool = False, instead: str = ""):
        self.what, self.valid, self.retryable, self.instead = what, valid, retryable, instead
        super().__init__(str(self))

    def __str__(self) -> str:
        parts = [self.what]
        if self.valid:
            parts.append(self.valid)
        if self.instead:
            parts.append(self.instead)
        parts.append("Retryable." if self.retryable else "Terminal.")
        return " ".join(parts)


@dataclass
class Param:
    type: str                      # "string" | "integer"
    required: bool = True
    minimum: int | None = None
    enum: list[str] | None = None
    default: Any = None


@dataclass
class Tool:
    name: str
    params: dict[str, Param]
    fn: Callable[..., Any]
    mutates: bool = False
    expensive: bool = False
    reversible: bool = True
    undo: str | None = None
    min_trust: str = "external"    # the lowest trust level allowed to call it
    result_cap: int = 4000         # characters returned to the model


def canonical(args: dict[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"))


def idempotency_key(run_id: str, name: str, args: dict[str, Any]) -> str:
    """Derived by the tool layer, never requested from the model."""
    return hashlib.sha256(f"{run_id}|{name}|{canonical(args)}".encode()).hexdigest()[:16]


def validate_and_coerce(tool: Tool, args: dict[str, Any], log: list[str]) -> dict[str, Any]:
    """Schema validation, then lossless coercion only. Anything ambiguous is rejected."""
    out: dict[str, Any] = {}
    for pname, p in tool.params.items():
        if pname not in args:
            if p.required:
                raise ToolError(f"Missing required field `{pname}`.",
                                f"Provide {pname} ({p.type}).", retryable=True)
            out[pname] = p.default
            continue
        v = args[pname]
        if p.type == "integer":
            if isinstance(v, str) and v.strip().lstrip("-").isdigit():
                log.append(f"coerced {tool.name}.{pname}: str->int")
                v = int(v.strip())
            if not isinstance(v, int) or isinstance(v, bool):
                raise ToolError(f"Field `{pname}` must be an integer; got {v!r}.", retryable=True)
            if p.minimum is not None and v < p.minimum:
                raise ToolError(f"Field `{pname}` must be at least {p.minimum}; got {v}.", retryable=True)
        elif p.type == "string":
            if not isinstance(v, str):
                raise ToolError(f"Field `{pname}` must be a string; got {type(v).__name__}.", retryable=True)
            if v != v.strip():
                log.append(f"coerced {tool.name}.{pname}: trimmed")
                v = v.strip()
            if p.enum is not None:
                folded = {e.lower(): e for e in p.enum}
                if v not in p.enum and v.lower() in folded:
                    log.append(f"coerced {tool.name}.{pname}: case")
                    v = folded[v.lower()]
                if v not in p.enum:
                    raise ToolError(f"Field `{pname}` must be one of {p.enum}; got {v!r}.", retryable=True)
        out[pname] = v
    extra = set(args) - set(tool.params)
    if extra:
        raise ToolError(f"Unknown field(s) {sorted(extra)}.", f"Allowed: {sorted(tool.params)}.", retryable=True)
    return out


def shape(tool: Tool, result: str) -> str:
    """Truncate with an explicit marker; never silently."""
    if len(result) <= tool.result_cap:
        return result
    return result[: tool.result_cap] + f"\n[truncated: showing {tool.result_cap} of {len(result)} characters; call again with a narrower range]"


@dataclass
class RepeatDetector:
    """Chapter 16: end a loop before the ceiling does."""
    limit: int = 3
    seen: dict[str, int] = field(default_factory=dict)

    def check(self, name: str, args: dict[str, Any]) -> None:
        k = f"{name}|{canonical(args)}"
        self.seen[k] = self.seen.get(k, 0) + 1
        if self.seen[k] > self.limit:
            raise ToolError(
                f"You have called `{name}` with these arguments {self.seen[k]} times; the result will not change.",
                instead="Conclude with what you have.", retryable=False)
