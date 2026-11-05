import pytest

from analysis.power import SIMULATOR_BUDGET_SESSIONS, read_report, sample_size_per_arm


def test_known_case():
    # baseline 5%, +10% relative lift, alpha 0.05 two-sided, power 0.80 → ~31k per arm (hand-computed)
    assert 30_500 <= sample_size_per_arm(0.05, 0.10) <= 31_700


def test_bigger_effect_needs_fewer():
    assert sample_size_per_arm(0.05, 0.20) < sample_size_per_arm(0.05, 0.10)


def test_rejects_bad_inputs():
    for baseline, mde in [(0, 0.1), (1, 0.1), (0.05, 0), (0.05, -0.1), (0.6, 1.0)]:
        with pytest.raises(ValueError):
            sample_size_per_arm(baseline, mde)


def test_plan_fits_simulator_budget():
    report = read_report()
    n = sample_size_per_arm(report["baseline"], report["mde_relative"])
    assert report["n_per_arm"] == n, "power_report.md is out of date"
    assert 2 * n <= SIMULATOR_BUDGET_SESSIONS
    assert report["true_effect_relative"] > report["mde_relative"]
