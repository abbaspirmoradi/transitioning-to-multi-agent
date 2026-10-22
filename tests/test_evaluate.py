"""Chapter 14: gate on the lower bound; safety rows are asserted; small samples are not evaluated."""
from agentmigration.evaluate import Row, gate, rate_interval, agreement


def test_interval_arithmetic_matches_the_book():
    _, lo, hi = rate_interval(45, 300)          # a rate near 0.15 with n=300
    assert abs((hi - lo) / 2 - 0.04) < 0.005    # about four points either side
    _, lo, hi = rate_interval(6, 40)
    assert (hi - lo) / 2 > 0.11                 # over eleven with n=40


def test_gate_blocks_on_one_category_tail_and_passes_aggregate_improvers():
    rows = [Row("test-gap", 410, 0.91, 381), Row("style", 350, 0.88, 283),
            Row("containment corpus", 96, 1.0, 96, safety=True), Row("tiny", 20, 0.5, 20)]
    ok, results = gate(rows)
    verdicts = {name: v for name, v, _ in results}
    assert verdicts["test-gap"] == "pass" and verdicts["style"] == "fail"
    assert verdicts["containment corpus"] == "pass" and verdicts["tiny"] == "not evaluated"
    assert not ok


def test_safety_row_below_100_percent_fails_regardless_of_n():
    ok, results = gate([Row("canary absent", 1200, 1.0, 1199, safety=True)])
    assert not ok


def test_grader_agreement_is_measured_before_it_counts():
    assert agreement(["a", "b", "a", "a"], ["a", "b", "b", "a"]) == 0.75
