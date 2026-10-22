"""Chapter 10: the tool set is filtered by scope; attenuation never widens; the
cross-tenant probe and a path escape are denied; shadow refuses writes."""
import pytest
from agentmigration.policy import RunToken, Resources, filter_tool_set, authorise
from agentmigration.tools import Tool, Param

ALL = {
    "read_file": Tool("read_file", {"path": Param("string")}, lambda path: ""),
    "post_comment": Tool("post_comment", {"body": Param("string")}, lambda body: "", mutates=True, min_trust="principal"),
    "send_email": Tool("send_email", {"to": Param("string")}, lambda to: "", mutates=True, min_trust="principal"),
}


def token(tools=("read_file", "post_comment")):
    return RunToken("system:pipeline", "repo:acme/payments", "r1", frozenset(tools), Resources("acme/payments", 42), exp=1e12, children=2)


def test_tool_set_is_filtered_by_scope_before_the_model_sees_it():
    assert set(filter_tool_set(ALL, token())) == {"read_file", "post_comment"}


def test_attenuation_cannot_add_tools_or_exceed_children():
    t = token()
    child = t.attenuate({"read_file"}, "r1.w1")
    assert child.tools == frozenset({"read_file"}) and child.parent == "r1" and child.children == 1
    with pytest.raises(PermissionError):
        t.attenuate({"read_file", "send_email"}, "r1.w2")


def test_write_denied_in_shadow_and_below_trust_floor():
    t = token()
    assert not authorise(ALL["post_comment"], {"body": "x"}, t, "shadow", "principal", {}, {})
    assert not authorise(ALL["post_comment"], {"body": "x"}, t, "agent", "external", {}, {})
    assert authorise(ALL["post_comment"], {"body": "x"}, t, "agent", "principal", {}, {})


def test_path_escape_is_denied_at_the_resource_level():
    t = token()
    assert not authorise(ALL["read_file"], {"path": "../other-repo/secrets.txt"}, t, "agent", "external", {}, {})
    assert authorise(ALL["read_file"], {"path": "src/api/handlers.py"}, t, "agent", "external", {}, {})


def test_rate_ceiling_is_policy():
    t = token()
    counts = {}
    for _ in range(3):
        d = authorise(ALL["read_file"], {"path": "a"}, t, "agent", "external", counts, {"read_file": 3})
    assert d and not authorise(ALL["read_file"], {"path": "a"}, t, "agent", "external", counts, {"read_file": 3})
