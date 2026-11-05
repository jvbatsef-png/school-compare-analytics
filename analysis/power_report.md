# Power report: Compare A/B test

Owner: statistician · Decided before any traffic runs. Numbers computed by `analysis/power.py`.

## The question

How many visitors does each arm need so that, if Compare really moves `lead_rate` by at least the minimum effect we care about, the test will see it?

## The four inputs, in plain words

- **Baseline (15%)**: today's `lead_rate`, the share of visitors who saw results and sent at least one info request. In a real company it comes from history; here the world is synthetic, so we set it. Real marketplaces usually convert lower, which makes tests need far more traffic.
- **Minimum detectable effect (+20% relative, 15% → 18%)**: the smallest lift worth shipping the button for. A business decision, not a statistical one. Smaller effects need much bigger samples.
- **Alpha (0.05, two-sided)**: the false-alarm risk — calling a win when the button does nothing, 5% of the time.
- **Power (0.80)**: the chance of catching a real effect of at least the MDE. One time in five a real effect of exactly that size would be missed.

## The trade-off

Visitors needed per arm (from `sample_size_per_arm`):

| baseline \ MDE | +10% | +20% | +30% | +50% |
|---|---|---|---|---|
| 5% | 31,218 | 8,143 | 3,766 | 1,458 |
| 10% | 14,745 | 3,835 | 1,769 | 681 |
| 15% | 9,253 | 2,399 | 1,103 | 422 |
| 20% | 6,508 | 1,681 | 770 | 292 |

The simulator budget is 6,000 visitors (3,000 per arm). Detecting a +10% lift at a 5% baseline would need over 31,000 per arm: small sites can only test big changes.

## Decisions

- baseline: 0.15
- mde_relative: 0.20
- n_per_arm: 2399
- total_visitors: 4798
- true_effect_relative: 0.25

The simulator's true effect is +25% (15% → 18.75%), above the MDE. Power at that true effect is 0.935; at exactly the MDE it is 0.80. The readout in stage 7 must recover an estimate whose confidence interval contains the true effect.

## Notes

- The decision readout runs on the ground-truth log, where every visitor counts, so n per arm is the full 2,399. GA4 loses visitors to consent and ad blockers: the same test read on GA4 data has fewer visitors and less power, and stage 7 shows that estimate next to the decision one.
- The unit is the visitor who reached search results (triggered analysis, see `docs/measurement-plan.md`); every simulated visitor runs a search.
- Guardrails are not powered separately; a significant drop is read as a stop signal, a non-significant one is not proof of no harm.
