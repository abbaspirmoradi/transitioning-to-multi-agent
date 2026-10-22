"""Chapter 16: a per-tool circuit breaker that trips on error rate or latency, because
the cascade produces no errors until it is far advanced."""
from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Breaker:
    window: int = 20
    max_error_rate: float = 0.5
    max_p95_seconds: float = 60.0
    open_for: float = 30.0
    probes_to_close: int = 3
    state: str = "closed"
    opened_at: float = 0.0
    _samples: deque = field(default_factory=lambda: deque(maxlen=20))
    _probe_ok: int = 0

    def allow(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if self.state == "open":
            if now - self.opened_at >= self.open_for:
                self.state = "half-open"
                self._probe_ok = 0
                return True
            return False
        return True

    def record(self, ok: bool, seconds: float, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._samples.append((ok, seconds))
        if self.state == "half-open":
            if ok:
                self._probe_ok += 1
                if self._probe_ok >= self.probes_to_close:
                    self.state = "closed"
                    self._samples.clear()
            else:
                self._trip(now)
            return
        if len(self._samples) < 5:
            return
        errs = sum(1 for o, _ in self._samples if not o) / len(self._samples)
        lat = sorted(s for _, s in self._samples)
        p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))]
        if errs > self.max_error_rate or p95 > self.max_p95_seconds:
            self._trip(now)

    def _trip(self, now: float) -> None:
        self.state = "open"
        self.opened_at = now
