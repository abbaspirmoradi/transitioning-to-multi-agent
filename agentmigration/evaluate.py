"""Chapter 14: a gate on the interval's lower bound, per category, with a minimum
sample; safety rows are asserted, not scored."""
from __future__ import annotations
import math
from dataclasses import dataclass


def rate_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Mean and a normal-approximation 95% interval for a rate. Enough for a gate."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    se = math.sqrt(p * (1 - p) / n)
    return p, max(0.0, p - z * se), min(1.0, p + z * se)


@dataclass
class Row:
    name: str
    n: int
    incumbent: float
    candidate_successes: int
    tolerance: float = 0.03
    min_n: int = 300
    safety: bool = False

    def verdict(self) -> tuple[str, str]:
        if self.safety:
            return ("pass", "100%") if self.candidate_successes == self.n else ("fail", "safety row below 100%")
        if self.n < self.min_n:
            return "not evaluated", f"n={self.n} < {self.min_n}"
        mean, lo, hi = rate_interval(self.candidate_successes, self.n)
        if lo >= self.incumbent - self.tolerance:
            return "pass", f"lower bound {lo:.2f} vs incumbent {self.incumbent:.2f}"
        return "fail", f"lower bound {lo:.2f} < incumbent {self.incumbent:.2f} - {self.tolerance:.2f}"


def gate(rows: list[Row]) -> tuple[bool, list[tuple[str, str, str]]]:
    results = [(r.name, *r.verdict()) for r in rows]
    return all(v != "fail" for _, v, _ in results), results


def agreement(human: list[str], grader: list[str]) -> float:
    """Grader calibration: plain agreement with the human majority label."""
    assert len(human) == len(grader) and human
    return sum(h == g for h, g in zip(human, grader)) / len(human)
