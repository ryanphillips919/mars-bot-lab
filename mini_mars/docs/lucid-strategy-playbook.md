# Lucid strategy playbook — Mini Mars practice evidence

Mini Mars is an **unofficial** practice game. Lucid's announcement names rovers, iron, gold, bases, exploration, and competing colonies, but does not define scoring or the bot API. The measured results below test our invented rules, not Lucid's game.

## Survive the First Match

The schedule allows approximately **45 minutes before qualifying**. Follow the [small competition starter](competition-starter.md): inspect the real API, get valid output, add one safe scoring loop, then finish and inspect a complete match. Use the organizer's rules in place of every Mini Mars assumption below.

| Catastrophic failure | Prevention before qualifying |
| --- | --- |
| Parser or response failure | Start from the organizer's sample bot. Validate essential fields, emit one schema-correct response per turn, flush stdout, log to stderr, and test malformed/missing input. Mini Mars turns malformed, missing, and late responses into waits and records the faults. |
| Invalid or impossible actions | Check actions against the current observation and any official legal-action list. Include a safe wait fallback; test bounds, obstacles, depleted resources, base occupancy, and simultaneous conflicts. |
| Valuable cargo never scores | Verify whether cargo must be delivered. If it does, reserve BFS travel plus the separate deposit action. Recheck the **selected next action**, including its post-move position, before sending it. A deterministic Mini Mars regression now covers five actions left, a base three moves away, and a tempting wrong-way exploration move. |
| Rover cycling or stalled targeting | Keep a target until it is exhausted or truly unreachable; track recent positions, actions, progress, and map discoveries. Inspect [replay warnings](benchmarks/reliability-v1/smoke.json) before adding any automatic recovery. A long route and deliberate waiting are not themselves loops. |
| Running out of time without a complete match | Reserve the final ten minutes for a full match, faults, score versus cargo, and a replay. Keep the last working bot. Add allocation, exploration tuning, and construction only after this baseline works. |

**Transferable priorities:** valid protocol, legal actions, safe scoring before a deadline, reachable routes, and visible reliability metrics. Their exact thresholds and rewards depend on Lucid's unpublished rules. The measured Mini Mars smoke study is [here](benchmarks/reliability-v1/smoke.json); controlled algorithm comparisons remain below.

### Adapt to the real rules

Ask: What scores, and does carried cargo count? Are terrain or resources hidden? What are movement costs? Can rovers share tiles or collide? Can rovers be manufactured? Can bases be built, and at what cost? What ends the game? Are actions simultaneous? What are the runtime limits? Is the remaining horizon observable? Use the answers to choose which practice algorithms apply.

## Reliability smoke: simple first, sophisticated later

The new [reliability report](benchmarks/reliability-v1/smoke.json) uses seeds **50000–50019** in both player slots for each comparison, 20 complete pairs / 40 clean games per row. There were **zero invalid actions, crashes, timeouts, protocol faults, or movement warnings** across its 160 games. Candidate score differences below are candidate minus baseline banked gold per seed, averaged across slots; intervals resample whole seeds. These are head-to-head packages on invented rules, not isolated claims about coordination.

| Mini Mars scenario | Baseline → candidate | Candidate win rate | Mean scored gold, baseline → candidate | Paired difference [95% interval] |
| --- | --- | ---: | ---: | ---: |
| [Default](benchmarks/reliability-v1/smoke.json) | greedy → coordinated | 27.5% | 50.05 → 45.18 | −4.88 [−7.63, −2.07] |
| [Obstacle heavy](benchmarks/reliability-v1/smoke.json) | greedy → coordinated | 20.0% | 48.10 → 42.48 | −5.63 [−8.10, −2.90] |
| [40 turns](benchmarks/reliability-v1/smoke.json) | greedy → coordinated | 1.25% | 22.20 → 8.68 | −13.53 [−15.70, −11.10] |
| [40 turns](benchmarks/reliability-v1/smoke.json) | greedy without next-action guard → guarded greedy | 50.0% | 22.20 → 22.20 | 0.00 [0.00, 0.00] |

**Easy and reliable for the first qualifier:** a legal, BFS-based mining and delivery loop like `greedy` is the practice starting point. **Mathematically more involved:** coordinated bids, frontier value, and construction model more interactions, but this smoke comparison did not improve scores. **Previously measured in controlled comparisons:** distinct-target allocation and information-gain frontier ordering did improve over their own ablated baselines below. Those controlled gains do not imply the entire coordinated package beats simple greedy. No Mini Mars policy is an overall Lucid winner.

The [score-checked 40-turn replay for seed 50004](../results/matches/reliability-short-horizon-greedy-coordinated-50004-normal/replay.json) ended **12–0**. Coordinated player 1 submitted **120 moves**, all accepted and all changing position, revealed **218 tiles**, discovered **29 resource deposits**, and **never mined or deposited**. From the source bid rules and this action trace, exploration bids apparently beat resource bids even after deposits were known; the replay does not log every rejected bid. The movement monitor correctly emitted no cycling warning, and `no_effect_rover_turns` was zero; a move can change state without earning value. This is a remaining economic-policy risk, especially under a short deadline. It is a reason to prefer the smaller scoring loop initially, not evidence that routing or allocation is useless. There were no other zero-score games or warnings in this matrix.

The cargo guard compares each selected action's resulting position with BFS distance to a friendly base plus the separate deposit turn. A [deterministic regression](../tests/test_reliability.py) shows that an unsafe exploration move is replaced when five actions remain and the base is three moves away. The guard produced no score change against the old Greedy decision branch in this 20-seed smoke; Greedy's existing choices already returned safely on these maps. `ValueGreedy` also now uses BFS rather than Manhattan distance for return-value estimates; this targeted correctness fix was not benchmarked for score gain. The warning detector is conservative: it can miss a costly route that keeps revealing tiles or never revisits a tile, and goal-change warnings need optional target metadata. It does not repair a bot automatically.

## Experimental findings

Values are **candidate minus baseline banked gold per map seed**, averaged across both player slots. Brackets are deterministic seed-pair bootstrap 95% intervals; win rates count ties as half a win. Every validation row uses **100 complete pairs / 200 clean games** on seeds 40000–40099. The linked [validation](benchmarks/strategy-v2/validate.json) and [smoke](benchmarks/strategy-v2/smoke.json) reports contain configs, source hashes, exact commands, behavior, latency, and reliability.

| Scenario | Baseline → candidate; change tested | Gold difference [95% interval] | Candidate win rate |
| --- | --- | ---: | ---: |
| [Default fog](benchmarks/strategy-v2/validate.json) | nearest frontier → information gain | +1.660 [+0.795, +2.525] | 59.0% |
| [Obstacle heavy](benchmarks/strategy-v2/validate.json) | nearest frontier → information gain | +2.095 [+1.295, +2.890] | 61.8% |
| [Default fog](benchmarks/strategy-v2/validate.json) | no endgame → endgame planning | +1.695 [+1.390, +2.015] | 65.0% |
| [40-turn horizon](benchmarks/strategy-v2/validate.json) | no endgame → endgame planning | +1.470 [+1.145, +1.800] | 64.7% |
| [Scarce](benchmarks/strategy-v2/validate.json) | no endgame → endgame planning | +1.425 [+1.075, +1.775] | 61.5% |
| [Default fog](benchmarks/strategy-v2/validate.json) | independent → distinct-target allocation | +21.910 [+20.495, +23.300] | 100.0% |
| [Full info](benchmarks/strategy-v2/validate.json) | independent → distinct-target allocation | +6.780 [+5.650, +7.915] | 91.2% |
| [Scarce](benchmarks/strategy-v2/validate.json) | gold-only → existing iron/build package | −1.125 [−1.520, −0.765] | 40.7% |
| [Scarce](benchmarks/strategy-v2/validate.json) | existing builder → payback builder; same iron bids | +0.205 [+0.070, +0.380] | 52.0% |
| [Scarce](benchmarks/strategy-v2/validate.json) | gold-only → iron plus payback builder | −0.905 [−1.280, −0.545] | 42.5% |

The [20-pair / 40-game smoke report](benchmarks/strategy-v2/smoke.json) adds two useful controls: full-info nearest versus information gain tied exactly because no cells were unknown; scarce exploration gained +1.125 [−0.076, +2.450]. The default payback builder gained only +0.100 [0.000, +0.300] over the old builder, and the default iron/build package lost −0.975 [−1.775, −0.250] to gold-only. Smoke estimates are leads, not validation. The issue #1 [smoke](benchmarks/issue-1/smoke.json) and [validation](benchmarks/issue-1/validation.json) remain historical evidence from earlier code. Its no-exploration bot is a **negative control**: starting areas contain no resources, so it can remain stationary under fog.

### What the behavior metrics suggest

- **Endgame — transferable if cargo must be deposited.** On [40-turn maps](benchmarks/strategy-v2/validate.json), the planned bot mined **9.15** gold per game versus **14.49** without planning, yet deposited **5.08** versus **3.61** and ended with **4.07** versus **10.88** in cargo. The policy uses BFS route lengths, includes the deposit turn, and suppresses trips and iron investment that cannot plausibly score. The 40-turn preset changes only the turn limit; its physical map is identical to default for a seed.
- **Allocation — transferable when tasks can duplicate.** In [default validation](benchmarks/strategy-v2/validate.json), coordination deposited **45.55** gold per game versus **23.64** for independent assignment. Both variants share bids, exploration, endgame, and routes; only target reservation changes. Independent rovers also mined less, consistent with duplicated targeting. Task intent is not logged, so duplicated choices were not directly counted.
- **Exploration — conditional on fog.** Both policies use the same resource-versus-explore trigger. Information gain ranks frontiers by unseen tiles divided by BFS travel turns plus one; nearest ranks by distance. [Default and obstacle-heavy validation](benchmarks/strategy-v2/validate.json) favored information gain, although it revealed slightly **fewer** total tiles by game end. Better discovery timing or location is plausible, but total coverage alone does not explain the gain. Full-info reveals enemies as well as terrain, so it is not a terrain-only causal test.
- **Construction — dependent on the invented economy.** In [scarce validation](benchmarks/strategy-v2/validate.json), the existing iron/build bot mined **419 iron** but built only **one base across 200 games** against gold-only. Insufficient banked iron blocked **58,926 of 60,000 rover-turn checks**. Ignoring iron counterfactually, **5,695 visited positions** passed its site heuristic; when iron was available, gold thresholds, proximity, occupied tiles, and the turn cutoff also blocked builds. This audit checks visited locations, not all future sites. Neither policy deliberately navigates to a construction site. A deterministic funded, remote-gold test confirms that construction can happen; rare builds do not prove bases lack value.
- **Payback builder — a small controlled gain.** With identical iron bids, the [scarce validation](benchmarks/strategy-v2/validate.json) payback policy built **12** bases versus **one** for the existing builder across 200 games and gained **0.205** gold per pair. It counts one deliverable trip per known gold deposit and asks for at least nine saved one-way delivery turns, approximating eight iron mining actions plus one build. It omits much iron travel and assumes known deposits can be used. The full iron/payback policy still lost **0.905** gold per pair against gold-only. That combined comparison cannot isolate iron targeting from construction, and none of these results establish Lucid's iron value.

One surprising [obstacle-heavy replay, seed 40042](../results/matches/strategy-v2-candidate-loss-obstacle-heavy-seed-40042-normal/replay.json), shows nearest frontier winning **66–30** despite information gain revealing **216** tiles by turn 40 versus **166** for nearest. Nearest built a base on turn 53 and ultimately banked 66 gold; information gain built none and banked 30. One replay cannot explain the average result. The validation report lists a [candidate win, seed 40019](benchmarks/strategy-v2/validate.json), and a [tie, seed 40011](benchmarks/strategy-v2/validate.json); each saved replay was rerun and score-checked against its tournament record.

## Evidence, reliability, and reproduction

All **560 smoke games** and **2,000 validation games** completed in clean pairs, with **zero** invalid actions, timeouts, crashes, or protocol faults for the compared built-in bots. Score differences here were not improved by excluding failures. Future tournament reports keep reliability separate: score and win summaries use clean complete pairs, while attempted, clean, faulted, and exception game counts include every attempted game. An unreliable bot should not be presented as strong based only on its surviving games.

Match and tournament behavior sections distinguish **submitted** action types, **normalized** engine actions (including implicit waits), and actions with an actual **state effect**. Successful mine, deposit, and build activity comes from engine events; successful moves come from changed positions. `no_effect_rover_turns` includes waits and accepted actions that did nothing; it does not claim all transit moves were economically useful. Revealed tiles and deposits come from observed map state. Exploration-*task* turns are omitted because the unchanged JSON Lines protocol does not expose intent.

Run from the repository root on **Python 3.12.3**:

```sh
make test
python3 -m mini_mars match --scenario short-horizon --bot-a coordinated-no-endgame --bot-b coordinated --seed 42
python3 -m mini_mars tournament --scenario default --bot-a coordinated-nearest --bot-b coordinated --matches 20 --seed 30000
python3 -m mini_mars.runner.benchmark_v2 smoke
python3 -m mini_mars.runner.benchmark_v2 validate
make view-mini-mars
python3 -m unittest mini_mars.tests.test_reliability -v
python3 -m mini_mars.runner.reliability_benchmark --matches 20 --seed 50000
python3 -m mini_mars match --scenario short-horizon --bot-a greedy --bot-b coordinated --seed 50004
```

The historical strategy commands save compact reports under `mini_mars/docs/benchmarks/strategy-v2/`; the new smoke report is separate under `mini_mars/docs/benchmarks/reliability-v1/`. Detailed outputs stay under ignored `mini_mars/results/`. Every case records its standalone tournament command. Historical strategy reports record Git HEAD **`221d61a37422e4762bc1d57586ee01959748dc5b`**; the new reliability report records **`b3a3bd99350e610c70a38811c33e27732dc734fd`**, `git_dirty=true` during implementation, plus source SHA-256 hashes. The earlier smoke and validation seeds are **30000–30019** and **40000–40099**; reliability smoke seeds are **50000–50019**, each in both player slots. Intervals use **5000** deterministic bootstrap resamples of complete pairs (RNG seed **20261021**). Decision latency includes process scheduling and JSON overhead.

The symmetric map is 15×15. Only banked gold scores; bases cost eight banked iron; rovers may stack; there is no rover production, collision penalty, or combat. Those invented rules, fixed heuristic weights, and exploratory multiple comparisons limit transfer. Do not name an overall winner for Lucid's unpublished game.
