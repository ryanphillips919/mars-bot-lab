# Construction expansion study (new, unvalidated research branch)

The rules here are **invented Mini Mars practice rules**, not Lucid rules.

## Hypothesis

Constructed bases should become more valuable with longer travel routes,
abundant distant gold, cheaper banked-iron costs, and sufficient time and rovers
to use the investment. The existing economy is heavily constrained by return
trips and the opportunity cost of acquiring iron. No advantage is assumed.

## Changes

- Seeded, 180-degree-symmetric uniform and clustered maps.
- Configurable 15/30/50-sized maps, 100/200/400-turn horizons, 4/6/8-iron
  construction prices, and initial banked-iron controls.
- The historical builders remain available; scaled-horizon and deliberate
  site-planning variants are **experimental**, not competition defaults.
- Additional base-delivery telemetry and separate construction benchmarks.

## Run the tests and a small smoke comparison

```sh
make test
python3 -m mini_mars.runner.construction_study screen --case-limit 1 --candidate coordinated-planned-build --matches 1 --output /tmp/mars-construction-smoke.json
python3 -m mini_mars.runner.profile_decisions --repetitions 5
```

Run the full 54-condition matrix with all candidates by omitting
`--case-limit` and `--candidate`; this is **computationally expensive**.
Each scenario includes both initially unfunded and pre-funded cases, with both
bot slots swapped for every seed. The initially funded control grants the same
banked iron to **both** players, avoiding a free resource handicap.
In a gold-only-versus-builder comparison, only the candidate can spend that
iron.

```sh
python3 -m mini_mars.runner.construction_study screen --matches 20 --output /tmp/construction-screen.json
python3 -m mini_mars.runner.construction_study validate --case-limit 3 --matches 100 --seed 91000 --output /tmp/construction-validation.json
```

The validation command uses a prefix of the matrix only; carefully preselect
cases based on screening and record the selection rationale. Never treat a
screening result or unrun benchmark as evidence. Do not reuse exploration seeds
for final held-out validation.

## Important limitations

The planner uses only observed or remembered map cells, estimates future
one-way gold-return savings and iron acquisition cost, and does not model
opponents or guarantee optimal investment. Resources can be depleted before
predicted visits. A constructed base is only a success if it produces more
**banked gold**, and the new base-usage counters help distinguish actual use
from merely placing a structure. Payback is an estimate, not an observed
counterfactual.

The GitHub plugin can create commits and pull requests but does not by itself
run Python. Run validation locally using `make test` and the experiment commands
above. No GitHub Actions workflows are configured for this research project.
The research branch includes no claimed tournament findings.
