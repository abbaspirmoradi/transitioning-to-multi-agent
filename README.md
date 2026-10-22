# Transitioning Applications to Multi-Agent Architectures

Companion code for the book by Abbas Pirmoradi (OldWishes Press, 2026).
ISBN 979-8175218320.

See [ERRATA.md](ERRATA.md) for corrections, and open an issue if you find one.

---

# Companion code

Runnable versions of the listings in *Transitioning Applications to Multi-Agent
Architectures*. Standard library only; no model provider is called. Where the book
has a model, this code has `FakeModel`, a scripted stand-in, so that every test here
is deterministic and runs in milliseconds. That is the book's own argument: most of an
agent system is ordinary code, and it is tested as ordinary code.

```
python -m pip install -e ".[test]"
python -m pytest          # or, without pytest: python run_tests.py
```

| Module | Chapter | What it implements |
|---|---|---|
| `tools.py` | 3, 16 | schema validation, lossless coercion, result shaping, four-part errors, idempotency keys, repeat detector |
| `facade.py` | 5, 6 | the facade: routes, deadline, filter, fallback, recorder, shadow |
| `envelope.py` | 8 | envelope validation, absolute deadline, budget split, causation-chain cap |
| `runtime.py` | 8, 15 | consumer loop with intent-before-effect checkpoints and budget ceilings |
| `policy.py` | 10 | run tokens, attenuation, per-call authorisation, tool-set filtering |
| `trust.py` | 11 | trust levels and propagation |
| `resolve.py` | 9 | dedup, verify-as-filter, vote, adjudicate (stub), escalation packet |
| `undo.py` | 13 | reversibility metadata and reverse-order rollback with an honest report |
| `breaker.py` | 16 | per-tool circuit breaker on error rate or latency |
| `evaluate.py` | 14 | interval-based gate, grader agreement |

Each `chNN/` directory has a short README pointing at the modules and tests for that
chapter. The book prints no prices, model names, or benchmark numbers; if you want
current figures for the budget model in Chapter 15, put them in `ch15/figures.md` and
keep them there, not in the book.

The code follows the book's conventions: the model never supplies an identifier it did
not receive; the tool layer decides, the model is informed; safety properties are
asserted, quality properties are scored.
