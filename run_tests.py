"""Run the test suite without pytest (a tiny shim for `pytest.raises`).
With pytest installed, prefer `python -m pytest`."""
import sys, importlib, inspect, traceback, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))


class _Pytest:
    class raises:
        def __init__(self, exc):
            self.exc, self.value = exc, None

        def __enter__(self):
            return self

        def __exit__(self, t, v, tb):
            if t is None:
                raise AssertionError(f"did not raise {self.exc}")
            if not issubclass(t, self.exc):
                return False
            self.value = v
            return True


if "pytest" not in sys.modules:
    try:
        import pytest  # noqa: F401
    except ImportError:
        sys.modules["pytest"] = _Pytest

ok = fail = 0
for f in sorted(pathlib.Path(__file__).parent.joinpath("tests").glob("test_*.py")):
    m = importlib.import_module(f"tests.{f.stem}")
    for name, fn in inspect.getmembers(m, inspect.isfunction):
        if name.startswith("test_") and fn.__module__ == m.__name__:
            try:
                fn(); ok += 1
            except Exception:
                fail += 1; print("FAIL", f.stem, name); traceback.print_exc(limit=4)
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
