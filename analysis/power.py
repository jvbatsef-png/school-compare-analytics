"""Sample size for the Compare A/B test (two proportions, two-sided)."""
import math
import re
from pathlib import Path

from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

REPORT_PATH = Path(__file__).resolve().parent / "power_report.md"

# Assumption: ~3 s per Playwright session, 4 in parallel ≈ 1.25 h. Re-measured in stage 4.
SIMULATOR_BUDGET_SESSIONS = 6000


def sample_size_per_arm(baseline: float, mde_relative: float,
                        alpha: float = 0.05, power: float = 0.80) -> int:
    """Visitors needed in each arm to detect a relative lift of `mde_relative` over `baseline`."""
    target = baseline * (1 + mde_relative)
    if not 0 < baseline < 1 or mde_relative <= 0 or not 0 < target < 1:
        raise ValueError("baseline and baseline*(1+mde) must be in (0, 1), and mde > 0")
    effect = proportion_effectsize(target, baseline)
    n = NormalIndPower().solve_power(effect_size=effect, alpha=alpha, power=power,
                                     ratio=1.0, alternative="two-sided")
    return math.ceil(n)


def read_report(path: Path = REPORT_PATH) -> dict:
    """Read `- key: value` lines from the Decisions section of power_report.md."""
    values = {}
    for key, value in re.findall(r"^- (\w+): ([\d.]+)\s*$", path.read_text(encoding="utf-8"), re.M):
        values[key] = int(value) if key == "n_per_arm" else float(value)
    return values
