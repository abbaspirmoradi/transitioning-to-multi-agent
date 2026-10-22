"""Chapter 3: coercion is lossless only; rejections are model-readable; errors are snapshots."""
import pytest
from agentmigration.tools import Tool, Param, ToolError, validate_and_coerce, shape, idempotency_key, RepeatDetector


def read_file(path, start_line, end_line=None):
    return "\n".join(f"{i}: line" for i in range(start_line, (end_line or start_line + 200) + 1))


READ = Tool("read_file", {"path": Param("string"), "start_line": Param("integer", minimum=1),
                          "end_line": Param("integer", required=False)}, read_file, result_cap=120)


def test_lossless_coercions_are_applied_and_logged():
    log = []
    out = validate_and_coerce(READ, {"path": " src/a.py ", "start_line": "42"}, log)
    assert out == {"path": "src/a.py", "start_line": 42, "end_line": None}
    assert log == ["coerced read_file.path: trimmed", "coerced read_file.start_line: str->int"]


def test_missing_required_field_is_a_retryable_four_part_error():
    with pytest.raises(ToolError) as e:
        validate_and_coerce(READ, {"start_line": 1}, [])
    assert str(e.value) == "Missing required field `path`. Provide path (string). Retryable."


def test_unknown_fields_are_rejected_not_ignored():
    with pytest.raises(ToolError):
        validate_and_coerce(READ, {"path": "a", "start_line": 1, "repo": "x"}, [])


def test_truncation_is_marked_never_silent():
    out = shape(READ, read_file("a", 1, 400))
    assert "[truncated: showing 120 of" in out


def test_idempotency_key_ignores_argument_order_and_is_per_run():
    a = idempotency_key("r1", "post", {"x": 1, "y": 2})
    b = idempotency_key("r1", "post", {"y": 2, "x": 1})
    c = idempotency_key("r2", "post", {"x": 1, "y": 2})
    assert a == b != c


def test_repeat_detector_ends_a_loop_with_a_terminal_error():
    d = RepeatDetector(limit=2)
    d.check("read_file", {"path": "a", "start_line": 1})
    d.check("read_file", {"path": "a", "start_line": 1})
    with pytest.raises(ToolError) as e:
        d.check("read_file", {"path": "a", "start_line": 1})
    assert not e.value.retryable and "will not change" in str(e.value)
