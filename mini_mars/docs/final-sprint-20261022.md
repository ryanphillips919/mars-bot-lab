# Mini Mars final engineering and research sprint — 22 October 2026

## What to use on Saturday

Lucid has announced rovers, iron, gold, bases, exploration, and competing colonies, but **has not published the game rules or bot API**. Mini Mars is an invented practice game. Start with the organizer's sample program and the [Competition Day Field Guide](competition-day-field-guide.md). For a Mini Mars reference, use [`starter`](../bots/competition_starter.py): it is a small standalone JSON Lines bot, beat the older `greedy` decisively, and was statistically indistinguishable from the more complex resource-first coordinator on three tested 100-turn maps. If official rules and time permit an advanced policy, adapt `coordinated-harvest-first`, especially its resource priority and deadline guard. Its clear advantage over `starter` was on the 40-turn practice map. Do not assume Mini Mars's iron or base economics carry over.

The new target-stability variant removes reproduced assignment loops with little measured score change, but has no validated scoring advantage. The partial-cargo return variant reduced useful collection trips and lost score; it remains an experimental control. No advanced variant replaces the small starter as the default competition preparation artifact.

## Scope and source identity

The sprint preserved Halite, Lux, all historical Mini Mars reports, and the JSON Lines protocol. Baseline Git HEAD was `689864dd7c29be2028b50e19b7555d05a8224f86` on `main`, with a clean working tree. Runs used WSL2 Ubuntu, Python **3.12.3**, and `make test`. The [33-case comparison](benchmarks/final-sprint-v1/comparison.json) and [10-case held-out validation](benchmarks/final-sprint-v1/validation.json) record `git_dirty: true`, complete configs, bot commands, Python version, and SHA-256 hashes for 17 relevant source files. Their source hashes match one another and the [score-checked replay manifest](benchmarks/final-sprint-v1/score-checked-replays.json). After validation, a route-map caching change was made; its separate [40-game equivalence check](benchmarks/final-sprint-v2/optimization-check.json), [profile](benchmarks/final-sprint-v2/performance.json), and [diagnostic reruns](benchmarks/final-sprint-v2/diagnostic-seeds.json) record the later source snapshot. Raw tournaments and replays remain in ignored `mini_mars/results/`.

There were **660 complete comparison seed pairs / 1,320 games** and **1,000 complete validation seed pairs / 2,000 games**. Every seed was played in both slots; map seed and bot identity seeds were held fixed across the swap. Across these 3,320 games there were no bot faults, invalid actions, or zero-score games. This is competitive reliability under these scenarios, not a guarantee under the unpublished official protocol. The 95% deterministic percentile intervals resample **whole seed pairs** 5,000 times; exploratory selection and multiple comparisons can make weak intervals optimistic.

## Confirmed findings and fixes

| Severity | Reproduction and cause | Resolution and limit |
| --- | --- | --- |
| **P0: starter fallback crash** | A valid line followed by `{"turn":8,"rovers":null}` raised during the exception fallback because it iterated `None`; the persistent process exited. The earlier full-cargo-on-gold crash was already fixed. | [Starter main](../bots/competition_starter.py) now treats a non-list rover field as empty, emits `bot_error`, and continues to the next line. [Regression](../tests/test_competition_starter.py) sends valid, partial, malformed, then valid lines. The runner already counts `bot_error` as a decision failure, so fallback responses cannot appear clean in tournament reliability. Arbitrary malformed real-game schemas still require organizer-specific handling. |
| **P1: assignment loop at an occupied deposit** | Full-information seed **64008**, `coordinated-nearest` versus historical `coordinated`, scored **80–80**. A rover mining gold on its base deposited every other turn; assignment temporarily released that resource during deposit, another rover claimed it, then reversed when the miner resumed. One back-and-forth and one goal-switch warning were reproduced. | Experimental `coordinated-stable` reserves a still-useful miner's resource through the deposit turn, clears stale targets on forced return/build, and retains an available frontier owner after higher-priority gold claims. A synthetic two-rover test checks the exact reservation, and seeded regressions remove the 64008 warning. It is a policy variant; historical `coordinated` remains unchanged for reproducibility. |
| **P1: frontier reassignment loop** | Scarce seed **67049**, `greedy` versus `coordinated-harvest-first`, scored **35–37**. Frontier ownership changed as bids changed, causing one rover to oscillate late in the game; back-and-forth, cycle, and goal-switch labels describe the same episode. | `coordinated-harvest-stable` retains a still-useful frontier for its worker while feasible gold tasks retain priority. The 67049 regression removes its back-and-forth warning without introducing invalid actions. The held-out score effect remains uncertain; do not present the repair as a scoring win. |
| **P1: speculative trip with partial gold** | Scarce seed **69017**, `coordinated-harvest-first` versus `coordinated-harvest-scored`, scored **49–45**. A rover carrying four gold alternated between a distant deposit and a frontier as assignments changed. | The isolated `coordinated-harvest-cargo` policy allows only cheap marginal gold detours while carrying gold; a deterministic fixture verifies returning from an expensive one-unit detour. It prevents that class of speculation, but lost **1.66** gold per seed on held-out scarce maps. It is **rejected for promotion**. A better selective return rule remains open. |
| **P2: insufficient diagnostic distinction** | A submitted `MINE` could fail because a rival depleted the cell. Accepted movement could reveal terrain or waste time. Previous reports did not explain all target changes or feasible stranded cargo. | [Match metrics](../runner/metrics.py) now separately count submitted, normalized, and effectful actions from engine events/state changes; resource discovery/mine/deposit milestones; target changes; duplicate claims; known-resource and base movement; gold carried away from base; economic idle streaks; and stranded gold after a previously feasible return. These fields are **diagnostics**. Exploring while a deliverable deposit is known is not automatically wrong when another rover owns it. |
| **P2: repeated route-map work** | Each coordinator decision recomputed the same multi-source base-distance map for every free rover. On a synthetic 35×35 full-information, 30-rover observation, cProfile showed 30 such calls. | The coordinator now computes it once per observation and passes it to shared candidate scoring. A call-count regression asserts one map. A repeated 20-seed tournament matched the pre-optimization snapshot in **40/40 games** for scores, faults, warnings, and behavior. |

The [four-seed diagnostic report](benchmarks/final-sprint-v2/diagnostic-seeds.json) also reproduces **69076** at **30–30** with one goal-switch warning. Its rover mostly continued along a useful route, so that warning alone is **not** a confirmed lost-score bug. Repeated target changes are a triage signal, not proof of a loop. No simulator scoring, conservation, map symmetry, or replay inconsistency was confirmed in the expanded tests. The engine still has limited adversarial coverage for very large maps and unusual custom bots.

## Complete-bot leaderboard in invented Mini Mars rules

Candidate minus baseline is mean banked gold over complete paired seeds; wins/losses/ties count the **200 individual games** per validation row. All rows have 100 complete pairs, 200 clean games, no invalid actions, and no zero-score games. Scores from different opponent rows are not additive.

| Scenario and comparison | Candidate difference [95% interval] | Candidate wins / losses / ties | Reading |
| --- | ---: | ---: | --- |
| Default: `starter → greedy` | **−6.64** [−7.41, −5.86] | 14 / 177 / 9 | `starter` clearly above older independent greedy. |
| Default: `starter → coordinated-harvest-first` | +0.55 [−0.12, +1.24] | 85 / 81 / 34 | Similar measured scoring. |
| Obstacle heavy: same comparison | +0.02 [−0.70, +0.74] | 96 / 86 / 18 | Similar measured scoring. |
| Scarce: same comparison | +0.36 [−0.50, +1.21] | 93 / 81 / 26 | Similar measured scoring. Starter had five goal-switch flags in 200 games; coordinator had none. |
| 40 turns: same comparison | **+1.99** [+1.46, +2.53] | 125 / 48 / 27 | Resource-first coordinator is stronger in this invented short horizon. |
| Limited vision: same comparison | −0.21 [−1.26, +0.82] | 86 / 102 / 12 | Similar measured scoring; coordinator had one back-and-forth and one goal-switch flag in 200 games. |

Thus the **simplest reliable starting bot is `starter`**. The **strongest validated advanced bot for short games is `coordinated-harvest-first`**. On default, obstacle-heavy, scarce, and limited-vision maps, neither complete bot has an established advantage over the other. The [20-pair comparison matrix](benchmarks/final-sprint-v1/comparison.json) also showed harvest-first clearly beating greedy in default, obstacle-heavy, scarce, and short maps, and included abundant and iron-rich stress comparisons. The scenario ranking is a ranking within this synthetic economy, not an overall winner for Lucid.

### Controlled modifications

| Fresh-seed comparison | Candidate difference [95% interval] | What the control says |
| --- | ---: | --- |
| Harvest-first → stable assignment, default | −0.04 [−0.34, +0.27] | No established score change. |
| Harvest-first → stable assignment, scarce | −0.24 [−0.73, +0.26] | Fewer target changes and fewer warnings, uncertain score cost. |
| Harvest-first → stable assignment, full information | +0.04 [−0.13, +0.22] | Busy-resource reservation is near score neutral on these maps. |
| Harvest-first → marginal cargo return, scarce | **−1.66** [−2.27, −1.04] | Reject the blunt detour threshold despite fewer outward trips with gold. |

These policies share BFS, resource scoring, and action protocol. Stable assignment does not eliminate every possible loop; the comparison matrix found occasional warnings in other bot matchups. The replay manifest preserves a **51–39** default loss for harvest-first versus starter, a **29–8** short-game win, a **69–64** full-information loss for stable versus harvest-first, and a **45–30** scarce loss for cargo versus harvest-first. Those are representative extremes, not average effects. Each replay was rerun with identical seeds and slots and checked against both tournament scores and final replay bank values.

Construction remains conditional: in default comparison games the coordinator deposited only **0.525 iron per game** on average and built no bases; all 300 rover-turn construction checks per game reported insufficient banked iron. Ignoring the bank, about **32 rover-turns per game** were at eligible current sites, so the absence of builds is primarily an iron acquisition issue in that matchup, not proof that good sites do not exist. The iron-rich comparison raised deposited iron to **2.525 per game** and still rarely reached eight. A [deterministic funded-site test](../tests/test_strategy_v2.py) confirms actual construction can happen. Historical [gold-only versus iron-package evidence](benchmarks/research-loop/comparison.json) found the iron package worse under Mini Mars economics. Current bots do not deliberately navigate to construction sites, and no base policy is validated for Lucid.

## Test and performance evidence

`make test` completed with **4 integration tests and 60 Mini Mars tests passing** after the final strategy optimization. New deterministic checks cover the starter's malformed-input recovery, occupied-resource reservation, stale-target clearing, partial-cargo detour choice, known historical movement loops, every built-in alias completing an eight-turn protocol match, and one shared route-map call. Mutation-style bot fixtures verify wrong-turn and oversized responses are counted as invalid or faulted; existing fixtures exercise malformed JSON, missing responses, timeouts, reported decision errors, bad moves, and movement loops. A seeded stateful generator ran **60 distinct maps × 20 turns**, varying map size, rocks, resources, rover count/position, mixed cargo, capacity, mining rate, vision, construction cost, and extra bases. It submitted legal and deliberately invalid actions, then compared duplicate game states and events while asserting resource conservation, cargo limits, traversability, and score consistency. Existing tests cover fog secrecy, paired slot swaps, seed-level bootstrap repeatability, effectful action accounting, feasible deadline delivery, and funded base construction. Random testing cannot prove all state combinations; the property assertions are scoped to valid generated states.

The [reproducible performance fixture](benchmarks/final-sprint-v2/performance.json) times only `decide()` on one fully visible map per size, with a fresh bot for each of 30 repetitions. Medians after the cache change were:

| Map / rovers | `starter` | harvest-first | stable harvest-first |
| --- | ---: | ---: | ---: |
| 15×15 / 3 | 1.08 ms | 2.03 ms | 1.90 ms |
| 25×25 / 10 | 4.90 ms | 14.02 ms | 14.38 ms |
| 35×35 / 30 | 26.91 ms | 84.29 ms | 84.72 ms |

A prior same-session ad hoc profile gave harvest-first **17.18 ms** and **105.78 ms** on the 25/10 and 35/30 fixtures before caching; subsequent runs gave about **14–14.4 ms** and **84–86 ms**. These are approximate wall-clock comparisons, not controlled CPU benchmarks. The optimization removes redundant `O(R(V+E))` home-map work; per-rover BFS remains `O(R(V+E))`. Held-out subprocess latency on normal 15×15 maps was around **1.0–2.2 ms** for `starter` and harvest-first, rising to **3.38 ms** for harvest-first with full information. It includes Python process and JSON exchange overhead. Actual Lucid runtime limits and map scale are unknown; profile official worst-case observations before adding complexity.

## Reproduce

From repository root:

```sh
make test
python3 -m mini_mars.runner.final_sprint comparison
python3 -m mini_mars.runner.final_sprint validation --cases starter_vs_greedy_default starter_vs_harvest_default starter_vs_harvest_obstacle-heavy starter_vs_harvest_scarce starter_vs_harvest_short-horizon starter_vs_harvest_limited-vision harvest_vs_stable_default harvest_vs_stable_scarce harvest_vs_stable_full-info harvest_vs_cargo_scarce
python3 -m mini_mars.runner.profile_decisions --output /tmp/mini-mars-performance-rerun.json
python3 -m mini_mars match --scenario full-info --bot-a coordinated-nearest --bot-b coordinated --seed 64008
python3 -m mini_mars match --scenario scarce --bot-a greedy --bot-b coordinated-harvest-first --seed 67049
python3 -m mini_mars match --scenario scarce --bot-a coordinated-harvest-first --bot-b coordinated-harvest-scored --seed 69017
```

The versioned benchmark command **refuses to overwrite** its tracked report. To rerun it, copy the study script and choose a new output version and fresh seeds; do not delete existing evidence. The raw `tournament` command shown in each case report can be run directly with a unique output directory. Run `python3 -m mini_mars replay PATH --turns 0,20,40` on any saved replay path, or `make view-mini-mars` to inspect completed matches in the browser. The competition field guide gives the event-day adaptation and emergency checklist.

## Remaining risks and decisions

- **Confirmed and unresolved:** A speculative four-gold detour can waste turns, but the tested universal marginal-return threshold harms average score. Keep the safe deadline guard; redesign partial-return economics only against fresh seeds and strong complete opponents.
- **Diagnostic, not necessarily failure:** Target changes and exploration with known deliverable gold can be useful when tasks are already assigned; inspect consecutive actions and score-changing events before treating a warning as a bug. The 69076 warning did not establish lost score.
- **Untested official mechanics:** Rover production, fuel, collision, combat, opponent interference, different scoring, and actual construction economics. Neither Mini Mars nor the event announcement establishes their rules.
- **Maintenance:** Experimental aliases add choices, but their switches remain localized in `StrategySettings`; do not port every variant on competition morning. `starter` has fewer moving parts. The JSON Lines schema is Mini Mars-specific and must be translated to the official sample.
- **Next worthwhile strategy experiment:** A narrow partial-cargo decision that compares the expected gold gain from one *known, reachable* detour against its added travel and deadline risk, while preserving target ownership. Require a fresh held-out validation set; the 73000–73099 seeds were already examined.
