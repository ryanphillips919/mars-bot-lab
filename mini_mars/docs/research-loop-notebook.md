# Mini Mars research notebook — 21 October 2026

Mini Mars is an **unofficial**, invented practice economy. Lucid has announced rovers, gold, iron, bases, exploration, and competing colonies, but has not published scoring or an API. Every score here is banked gold under Mini Mars rules. The [exploration study](benchmarks/exploration-fix/comparison.json) and [broader comparison](benchmarks/research-loop/comparison.json) contain the exact configs, bot commands, source hashes, revision, latency, reliability, and per-game behavior. Raw tournament logs and replays are in ignored `mini_mars/results/`.

## The 12–0 failure: decision trace before the fix

In short-horizon seed **50004**, simple greedy scored 12 and historical coordinated scored 0. The latter made 120 accepted moves, revealed 218 tiles and 29 deposits, and did not mine or deposit. Its first gold discovery was turn 5. Across the game it had **45 rover-turns with deliverable known gold**, yet made **43 moves assigned to other targets** while such gold was known. This is economic starvation, not a protocol or pathfinding failure. See the [score-checked diagnostic replay](../results/matches/exploration-diagnosis-50004-coordinated/replay.json) and its [report entry](benchmarks/exploration-fix/comparison.json).

At turn 5, all three coordinated rovers could reach the same gold deposit at (11, 8). Their best gold bids were approximately **0.238, 0.333, and 0.263**; their best frontier bids were **0.30, 0.42, and 0.42**. All three chose frontiers. `task_candidates()` computed the best frontier bid and assigned that same value to every reachable frontier, including inferior ones. Per-target values actually ranged from roughly **0.018 to 0.42**. The inflated bids crowded out feasible gold across the global assignment. A 1.2 resource-target persistence multiplier could not reliably overcome that gap, and frontier targets had no corresponding persistence. Near the 40-turn deadline the fixed exploration weight still competed with bankable gold.

The controlled repairs share BFS, return-horizon filtering, resource bid calculation, and distinct-target assignment:

| Variant | Single policy change | Seed 50004 score against greedy's 12 |
| --- | --- | ---: |
| Historical `coordinated` | Shared maximum frontier bid | 0 |
| `coordinated-frontier-scored` | Give each frontier its own bid | 0 |
| `coordinated-adaptive` | Per-frontier bid times remaining-turn fraction divided by `1 + min(feasible gold tasks, rover count)` | 11 |
| `coordinated-harvest-first` | Rank **reachable gold with a feasible scoring return** before exploration bids | 16 |

Per-frontier scoring fixes a real arithmetic error but does not by itself solve the resource versus scouting choice. The adaptive formula partly does; its opportunity proxy is still weaker than an explicit bankable-gold priority when deposits are scarce or time is short. The resource-first control is one ordering rule and is the smallest reliable repair found here. It still explores when no feasible known gold is available and retains the existing iron, base, routing, and target-allocation policy. `greedy` is unchanged.

## Focused 20-pair comparison

Each row uses seeds **66000–66019** in both player slots, so 40 games. Difference and 95% deterministic bootstrap interval are candidate minus baseline banked gold per paired seed. The [full compact report](benchmarks/exploration-fix/comparison.json) also separates attempted and faulted games, win/loss/tie counts, decision latency, zero-score games, activity metrics, and warning counts. All 20 rows had 20 complete seed pairs and zero bot faults.

| Scenario | Baseline → candidate | Candidate difference [95% interval] | Candidate win rate | Zero-score games |
| --- | --- | ---: | ---: | ---: |
| Default | greedy → historical coordinated | −4.20 [−5.90, −2.52] | 22.5% | 0 |
| Default | greedy → resource-first coordinated | +6.15 [+4.43, +7.93] | 92.5% | 0 |
| Obstacle heavy | greedy → historical coordinated | −6.35 [−8.70, −3.88] | 10.0% | 0 |
| Obstacle heavy | greedy → resource-first coordinated | +6.43 [+4.25, +8.68] | 86.3% | 0 |
| Scarce | greedy → historical coordinated | +0.18 [−2.25, +2.70] | 50.0% | 0 |
| Scarce | greedy → resource-first coordinated | +7.90 [+5.60, +10.35] | 83.8% | 0 |
| 40 turns | greedy → historical coordinated | −12.33 [−14.53, −10.05] | 3.8% | 0 |
| 40 turns | greedy → resource-first coordinated | +5.30 [+4.28, +6.38] | 97.5% | 0 |

The paired opponents affect absolute scores, so differences from distinct rows are not additive. Direct historical-coordinated → resource-first comparisons gained **+9.53 default, +13.15 obstacle heavy, +7.00 scarce, and +17.58 short**. The per-frontier-only repair gained **−0.10 default** and **+1.45 short**, with one zero-score game in the short comparison. Adaptive versus resource-first was **+0.40 default**, **+0.55 obstacle heavy**, **−3.05 scarce**, and **−3.13 short**. Adaptive also generated movement-loop warnings in two comparisons; resource-first generated none in these four direct rows. These are exploratory 20-pair estimates, not evidence of the upcoming competition's rules.

### Independent heldout checks

The resource-first variant faced greedy on **67000–67099**, again in both slots, without parameter tuning on these seeds. The [heldout report](benchmarks/exploration-fix/validation.json) records **100 complete pairs and 200 clean games per row**, with zero invalid actions, crashes, timeouts, decision errors, and zero-score games for either bot:

| Scenario | Mean scored gold, greedy → resource-first | Candidate paired gain [95% interval] | Candidate win rate |
| --- | ---: | ---: | ---: |
| Default | 51.74 → 57.69 | +5.96 [+4.92, +6.98] | 86.0% |
| Obstacle heavy | 46.44 → 53.49 | +7.06 [+6.26, +7.90] | 93.0% |
| Scarce | 36.07 → 41.91 | +5.84 [+4.93, +6.80] | 85.3% |
| 40 turns | 23.09 → 27.26 | +4.18 [+3.55, +4.81] | 87.5% |

The scarce row exposed one **back-and-forth**, two **goal-switching**, and one **small-tile-cycle** warning for resource-first in one game, seed 67049. These labels describe one late rover episode rather than four independent failures. The bot still scored 37 against greedy's 35. A [score-checked replay](benchmarks/research-loop/score-checked-replays.json) preserves it. The worst default game in this heldout matrix was a **53–43** loss, also score-checked; a positive average does not guarantee every map. Strategy performance and reliability are separate: no faulted game was excluded from these paired-score results, but the movement warning remains a genuine concern.

The standalone starter was separately tested on **65000–65099** against greedy. Its [heldout report](benchmarks/research-loop/validation.json) has 100 complete pairs per scenario: **+6.26 [5.48, 7.03]** on open terrain, **+7.81 [6.91, 8.69]** with vision radius one, and **+2.23 [1.57, 2.90]** on 40-turn maps. Across **600 games**, it had no faults, zero-score games, or movement warnings. It is the simpler competition-day reference because its protocol, pathfinding, target persistence, legality checks, and scoring loop can be adapted independently of the global assignment model.

### Follow-up on frontier loops

The seed 67049 warning showed that historical shared-maximum frontier bids can also cause repeated retargeting **after known gold is exhausted**. A combined `coordinated-harvest-scored` variant keeps gold priority and gives each frontier its own value. On seed 67049 it removed the back-and-forth and small-tile-cycle warnings, with the same **37** gold, though it still logged one goal-switch warning. This is a deterministic regression test, not an independent performance result.

On fresh comparison seeds **68000–68019**, the combined variant versus resource-first differed by **−0.28 default, −0.08 obstacle heavy, −0.20 scarce, and −0.30 short** gold per pair; all games were clean, with no zero scores or warnings. The preselected [second heldout set](benchmarks/frontier-value/validation.json), seeds **69000–69099**, gave **+0.59 [0.09, 1.10]** on scarce and **+0.23 [0.06, 0.40]** on 40-turn maps. However, the combined variant still generated a back-and-forth and goal-switch warning on scarce seed 69017, plus another goal-switch warning on 69076. The [score-checked 69017 replay](benchmarks/research-loop/score-checked-replays.json) ended **49–45** against the combined variant. At turn 56, one rover carried four gold and moved away from a base toward a distant task; changing reservations then made it alternate between (1, 8) and (1, 9). Per-frontier arithmetic alone cannot fix assignment changes or a rover that scouts while holding valuable cargo. This small measured score difference is not enough to make the extra variant the default starter.

This is a **remaining failure mode**, not a claim that the whole bot catastrophically failed: both candidates continued to score and all games completed cleanly. A possible next controlled change is to return partial gold before speculative exploration or reserve occupied resource targets during a teammate's deposit, but neither is validated here. Further heuristic tuning would go beyond the useful evidence from this session. The [replay manifest](benchmarks/research-loop/score-checked-replays.json) records source hashes, exact bot and map seeds, scores, and generated replay paths for five representative cases.

## Six broader iterations, including unsuccessful ideas

The [predeclared broader matrix](benchmarks/research-loop/comparison.json) used 20 paired seeds **64000–64019** per row, 18 rows total, with zero protocol, action, crash, timeout, or reported decision errors. It used an earlier source snapshot than the focused study; each report records its own SHA-256 source hashes. Differences below are candidate minus baseline and intervals resample complete seeds.

1. **Resource-first and deadline:** historical coordinated → resource-first gained **+19.00 [17.08, 20.90]** on 40-turn maps, **+12.95 [11.20, 14.55]** on default maps, and **+19.20 [17.58, 20.88]** with abundant gold. Against simple greedy on short maps it gained **+3.73 [2.55, 4.83]**. This motivated the focused matrix above.
2. **Small starter:** simple greedy → [standalone `starter` implementation](../bots/competition_starter.py) gained **+4.30 [2.65, 5.95]** on open terrain, **+8.75 [6.55, 11.03]** under vision radius one, **+0.93 [−0.15, 2.28]** with cargo capacity two, and **+1.65 [0.38, 2.95]** at 40 turns. A preliminary version tried to route a full rover to gold on its current tile, causing a `KeyError` and faults in **20 of 40** games of an early smoke run. It now excludes gold targets when cargo is full; this was fixed before the reported matrix. Runner reports now expose bot-reported decision exceptions as faults instead of silently treating them as clean waits.
3. **Value per trip:** `value` versus simple greedy was **+0.25 [−0.93, 1.40]** with abundant deposits, **−0.95 [−2.63, +0.33]** with obstacles, and **+0.23 [−0.25, +0.68]** at low capacity. The more detailed value ranking has no clear practical gain here.
4. **Frontier destination ordering:** information gain versus nearest frontier was **+0.05 [−1.63, 1.80]** at limited vision, **+1.95 [+0.28, +3.83]** with abundant resources, and an exact **0** with full information, where no exploration task exists. The full-information case still revealed a separate assignment oscillation: on seed 64008, a rover alternated between (8, 9) and (8, 10) while another deposited and mined at (6, 10) on alternating turns. The global assignment allowed the first rover to target that occupied deposit on deposit turns, then took it away when the other rover could mine. Resource-first did not warn on the same seed in a targeted full-information self-match, but that does not prove loops are impossible. The warning is retained; no extra coordination machinery was added on this evidence alone.
5. **Iron and construction:** the current iron/build package versus gold-only lost **−1.93 [−3.02, −0.95]** on iron-rich maps and **−0.83 [−1.58, −0.12]** on scarce maps. This is an invented-economic-rule result, not a reason to remove iron logic before Lucid publishes scoring. Existing [construction diagnostics](benchmarks/strategy-v2/validate.json) distinguish insufficient banked iron, visited-site rejection, and actual build events; bots do not deliberately travel to build sites.
6. **Allocation:** coordinated versus independent bids gained **+22.83 [18.73, 26.75]** with abundant resources and **+9.65 [7.65, 11.80]** at low capacity. Distinct target reservation remains useful in a controlled ablation, even though the historical complete coordinated bot lost to simple greedy in several scenarios. **Winning an ablation is not the same as being the best practical complete bot.**

The broader study found no zero-score games and a few movement warnings; the [report](benchmarks/research-loop/comparison.json) lists them separately from bot faults. A warning is a diagnostic flag, not proof of a lost match. Low-capacity value ranking and limited-vision frontier ordering did not justify more policy complexity.

## Reproduce and interpret

Run from repository root with **Python 3.12.3**. The comparison scripts save compact JSON under `mini_mars/docs/benchmarks/` and raw details under ignored `mini_mars/results/`:

```sh
make test
python3 -m mini_mars match --scenario short-horizon --bot-a greedy --bot-b coordinated --seed 50004
python3 -m mini_mars match --scenario short-horizon --bot-a greedy --bot-b coordinated-harvest-first --seed 50004
python3 -m mini_mars.runner.research_loop comparison
python3 -m mini_mars.runner.exploration_study comparison
python3 -m mini_mars.runner.exploration_study validation --cases greedy_vs_harvest_default greedy_vs_harvest_obstacle-heavy greedy_vs_harvest_scarce greedy_vs_harvest_short-horizon
python3 -m mini_mars.runner.research_loop validation --cases starter_open starter_limited_vision starter_short
python3 -m mini_mars.runner.frontier_value_study comparison
python3 -m mini_mars.runner.frontier_value_study validation --cases frontier_value_scarce frontier_value_short-horizon
```

The complete configurations, Git HEAD **`229b7251e74c2a408e813d6c986020cf9c969887`**, dirty state, Python version, and exact source hashes are embedded in each report. The first comparative data were collected before the new economics metrics were added; the focused study includes the new fields. No model was tuned on the heldout **67000–67099** seeds. Multiple exploratory comparisons make apparent gains easy to overread, so practical recommendations require independent validation and clean-game reliability. Only banked gold scores in Mini Mars; construction, collision, combat, and rover manufacturing differ from or may not exist in Lucid's eventual rules.

## 22 October follow-up: assignment, cargo, and complete bots

The [final sprint report](final-sprint-20261022.md) and [new versioned evidence](benchmarks/final-sprint-v1/validation.json) extend this notebook without replacing any historical report. The four warning seeds above were rerun and preserved in a [diagnostic manifest](benchmarks/final-sprint-v2/diagnostic-seeds.json). Seed **64008** exposed a resource reservation released while its owner deposited; **67049** exposed a changing frontier owner; **69017** combined a four-gold speculative trip with reassignment; **69076** produced a goal-switch flag without confirmed lost score. Stable target ownership and a resource reservation through deposit remove the two directly controlled loops. A partial-cargo return heuristic removes outward movement with gold but failed a fresh score test: **−1.66 [−2.27, −1.04]** gold per paired scarce seed against resource-first on seeds **73000–73099**. Keep it experimental.

The strongest complete-bot comparison now places the small `starter` approximately level with resource-first coordination on default, obstacle-heavy, and scarce 100-turn maps. Resource-first gains **+1.99 [1.46, 2.53]** on the 40-turn map. All 2,000 held-out games completed cleanly and none scored zero; warning counts remain separate from faults. The starter is the first bot to adapt to official rules, while resource-first is an advanced option after a valid scoring loop exists. See the [competition field guide](competition-day-field-guide.md) for event-day actions. These are still Mini Mars findings, with no claim about Lucid's unpublished scoring.
