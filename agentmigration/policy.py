"""Chapter 10: run tokens that narrow and never widen, the tool set filtered by scope
at run start, and the per-call policy check in the tool layer."""
from __future__ import annotations
from dataclasses import dataclass, field, replace

from .tools import Tool

TRUST_ORDER = ["derived", "external", "internal", "principal", "system"]


def trust_at_least(level: str, minimum: str) -> bool:
    return TRUST_ORDER.index(level) >= TRUST_ORDER.index(minimum)


@dataclass(frozen=True)
class Resources:
    repo: str
    pull_request: int


@dataclass
class RunToken:
    principal: str
    tenant: str
    run_id: str
    tools: frozenset[str]
    resources: Resources
    exp: float
    children: int
    parent: str | None = None

    def attenuate(self, tools: set[str], child_run_id: str) -> "RunToken":
        """A child token is a subset of the parent's; a request for more is refused."""
        if not tools <= set(self.tools):
            raise PermissionError("attenuation cannot add tools")
        if self.children <= 0:
            raise PermissionError("no children remaining")
        return replace(self, tools=frozenset(tools), run_id=child_run_id,
                       children=self.children - 1, parent=self.run_id)


@dataclass
class Decision:
    allowed: bool
    rule: str

    def __bool__(self) -> bool:
        return self.allowed


def filter_tool_set(all_tools: dict[str, Tool], token: RunToken) -> dict[str, Tool]:
    """Default deny, layer one: a tool outside the scope is not offered at all."""
    return {n: t for n, t in all_tools.items() if n in token.tools}


def resource_of(call_name: str, args: dict) -> Resources | None:
    """What resource a call touches. The tool layer knows; the model never says."""
    return None  # in the reference system every tool acts on the token's own repo/PR


def authorise(tool: Tool, args: dict, token: RunToken, route: str, trust: str,
              rate_counts: dict[str, int], rate_limits: dict[str, int]) -> Decision:
    """Deterministic, reads nothing from the model. Chapter 10, Listing 10.2."""
    if tool.name not in token.tools:
        return Decision(False, "tool not in scope")
    if tool.mutates and route == "shadow":
        return Decision(False, "no writes in shadow")
    path = args.get("path")
    if isinstance(path, str) and (path.startswith("/") or ".." in path.split("/")):
        return Decision(False, "path outside the pull request's repository")
    if not trust_at_least(trust, tool.min_trust):
        return Decision(False, "arguments from content below the tool's trust floor")
    limit = rate_limits.get(tool.name)
    if limit is not None and rate_counts.get(tool.name, 0) >= limit:
        return Decision(False, "rate ceiling for this tool")
    rate_counts[tool.name] = rate_counts.get(tool.name, 0) + 1
    return Decision(True, "in scope; resource covered; trust and rate within limits")


def denial_message(decision: Decision) -> str:
    """Says less than a developer-facing error would. Chapter 10."""
    return "This tool cannot act on that resource; no action was taken. Terminal."
