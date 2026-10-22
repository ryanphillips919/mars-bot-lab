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

**Transferable priorities:** valid protocol, legal actions, safe scoring before a deadline, reachable routes, and visible reliability metrics. Their exact thresholds and rewards depend on Lucid's unpublished rules. Start from the [working small JSON Lines starter](../bots/competition_starter.py) and its [adaptation guide](competition-starter.md). The [research notebook](research-loop-notebook.md) explains the failure and repair found after the earlier reliability smoke study.

### Adapt to the real rules

Ask: What scores, and does carried cargo count? Are terrain or resources hidden? What are movement costs? Can rovers share tiles or collide? Can rovers be manufactured? Can bases be built, and at what cost? What ends the game? Are actions simultaneous? What are the runtime limits? Is the remaining horizon observable? Use the answers to choose which practice algorithms apply.

## Current practice recommendation: score first, then coordinate

**Implement the small BFS scoring loop first when Lucid publishes its rules.** In [100 heldout paired seeds](benchmarks/research-loop/validation.json), the standalone `starter` beat the older greedy reference by **+6.26 [5.48, 7.03]** banked gold per seed on open terrain, **+7.81 [6.91, 8.69]** with vision radius one, and **+2.23 [1.57, 2.90]** in 40-turn games. These were **600 clean games**, with zero candidate invalid actions, timeouts, crashes, decision errors, zero scores, or movement warnings. Its persistent targets and return guard are portable ideas; its field names and scoring rules are Mini Mars-specific. The starter had no iron or base policy.

**If several rovers duplicate tasks, add coordination only after the scoring loop survives a full match.** The historical complete `coordinated` bot won a controlled target-allocation ablation yet lost to simple greedy on default, obstacle-heavy, and 40-turn maps because it kept scouting after deliverable gold was known. A one-rule `coordinated-harvest-first` variant prioritizes reachable gold that can be delivered before the deadline. Against greedy on [100 new paired seeds per scenario](benchmarks/exploration-fix/validation.json), it gained:

| Invented scenario | Candidate minus greedy banked gold [95% seed-pair interval] | Candidate win rate | Candidate zero-score games |
| --- | ---: | ---: | ---: |
| [Default](benchmarks/exploration-fix/validation.json) | +5.96 [+4.92, +6.98] | 86.0% | 0 / 200 |
| [Obstacle heavy](benchmarks/exploration-fix/validation.json) | +7.06 [+6.26, +7.90] | 93.0% | 0 / 200 |
| [Scarce](benchmarks/exploration-fix/validation.json) | +5.84 [+4.93, +6.80] | 85.3% | 0 / 200 |
| [40 turns](benchmarks/exploration-fix/validation.json) | +4.18 [+3.55, +4.81] | 87.5% | 0 / 200 |

All **800 candidate games** were clean. The scarce row contained one late back-and-forth warning and two target-switch warnings for resource-first coordination; none scored zero. Its mean decision latency was **1.60–2.16 ms** including process and JSON overhead, below the runner's one-second default timeout. The [focused 20-pair matrix](benchmarks/exploration-fix/comparison.json) found no candidate warnings, but heldout warnings matter more for reliability. The [seed 50004 trace](research-loop-notebook.md) explains why corrected per-frontier scoring alone still scored zero while resource-first scored 16 versus greedy's 12. The coordination result is a complete-bot comparison *under these invented rules*; it does not make coordination the first feature to build on competition morning.

A follow-up [per-frontier variant](benchmarks/frontier-value/validation.json) gave only **+0.59 scarce** and **+0.23 short-horizon** gold per paired seed versus resource-first on another heldout set, while still producing a real late back-and-forth episode. The [notebook](research-loop-notebook.md#follow-up-on-frontier-loops) traces it to target reassignment while a rover held four gold. Keep the small starter as the event-day reference and treat advanced coordination as a measured upgrade after the real rules and API are known.

### Scenario decision guide

| If the official game has… | First usable policy | Upgrade supported by Mini Mars evidence | Limit |
| --- | --- | --- | --- |
| A separate deposit step and deadline | BFS return plus deposit-turn guard | [40-turn endgame planning](benchmarks/strategy-v2/validate.json) | Remove this if carried cargo scores directly. |
| Fog and resources that must be discovered | Persistent reachable frontier when no bankable known work exists | [Resource-first versus scouting](benchmarks/exploration-fix/validation.json) | Exploration has different value if information scores directly. |
| Several rovers choosing the same finite deposit | Independent legal scoring loop | [Distinct-target allocation](benchmarks/strategy-v2/validate.json) after baseline works | This ablation did not validate the old complete bot. |
| Full visibility | Direct resource routing | [Full-info frontier control](benchmarks/research-loop/comparison.json) | No need to scout solely to reveal tiles. |
| Iron and buildable bases | Collect gold first until scoring works | [Iron/build diagnostics](benchmarks/strategy-v2/validate.json) | Mini Mars's iron package lost on scarce and iron-rich maps; Lucid's costs may differ. |

## Reliability smoke: simple first, sophisticated later

The earlier [reliability report](benchmarks/reliability-v1/smoke.json) uses seeds **50000–50019** in both player slots for each comparison, 20 complete pairs / 40 clean games per row. There were **zero invalid actions, crashes, timeouts, protocol faults, or movement warnings** across its 160 games. Candidate score differences below are candidate minus baseline banked gold per seed, averaged across slots; intervals resample whole seeds. These are historical head-to-head packages on invented rules, not isolated claims about coordination.

| Mini Mars scenario | Baseline → candidate | Candidate win rate | Mean scored gold, baseline → candidate | Paired difference [95% interval] |
| --- | --- | ---: | ---: | ---: |
| [Default](benchmarks/reliability-v1/smoke.json) | greedy → coordinated | 27.5% | 50.05 → 45.18 | −4.88 [−7.63, −2.07] |
| [Obstacle heavy](benchmarks/reliability-v1/smoke.json) | greedy → coordinated | 20.0% | 48.10 → 42.48 | −5.63 [−8.10, −2.90] |
| [40 turns](benchmarks/reliability-v1/smoke.json) | greedy → coordinated | 1.25% | 22.20 → 8.68 | −13.53 [−15.70, −11.10] |
| [40 turns](benchmarks/reliability-v1/smoke.json) | greedy without next-action guard → guarded greedy | 50.0% | 22.20 → 22.20 | 0.00 [0.00, 0.00] |

**Easy and reliable for the first qualifier:** a legal, BFS-based mining and delivery loop like the standalone `starter` is the practice starting point. The historical complete `coordinated` package lost this smoke comparison. Distinct-target allocation and information-gain frontier ordering improved their own controlled ablations below; that did not mean the historical complete bot beat simple greedy. The later [resource-first repair](benchmarks/exploration-fix/validation.json) changed the complete-bot outcome under Mini Mars rules. No Mini Mars policy is an overall Lucid winner.

The [score-checked 40-turn replay for seed 50004](../results/matches/reliability-short-horizon-greedy-coordinated-50004-normal/replay.json) ended **12–0**. Coordinated player 1 submitted **120 moves**, all accepted and all changing position, revealed **218 tiles**, discovered **29 resource deposits**, and **never mined or deposited**. The later [bid trace and repair study](research-loop-notebook.md) confirmed that frontier bids outranked reachable gold, then showed that giving every frontier its own value still left this seed at zero. The resource-first variant scored **16**. The original monitor emitted no cycling warning because movement was physically productive; economic diagnostics now flag zero score despite known deliverable gold. There were no other zero-score games or warnings in the historical smoke matrix.

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
python3 -m mini_mars match --scenario short-horizon --bot-a greedy --bot-b coordinated-harvest-first --seed 50004
python3 -m mini_mars.runner.exploration_study comparison
python3 -m mini_mars.runner.exploration_study validation --cases greedy_vs_harvest_default greedy_vs_harvest_obstacle-heavy greedy_vs_harvest_scarce greedy_vs_harvest_short-horizon
python3 -m mini_mars.runner.research_loop validation --cases starter_open starter_limited_vision starter_short
```

The historical strategy commands save compact reports under `mini_mars/docs/benchmarks/strategy-v2/`; the new smoke report is separate under `mini_mars/docs/benchmarks/reliability-v1/`. Detailed outputs stay under ignored `mini_mars/results/`. Every case records its standalone tournament command. Historical strategy reports record Git HEAD **`221d61a37422e4762bc1d57586ee01959748dc5b`**; the new reliability report records **`b3a3bd99350e610c70a38811c33e27732dc734fd`**, `git_dirty=true` during implementation, plus source SHA-256 hashes. The earlier smoke and validation seeds are **30000–30019** and **40000–40099**; reliability smoke seeds are **50000–50019**, each in both player slots. Intervals use **5000** deterministic bootstrap resamples of complete pairs (RNG seed **20261021**). Decision latency includes process scheduling and JSON overhead.

The symmetric map is 15×15. Only banked gold scores; bases cost eight banked iron; rovers may stack; there is no rover production, collision penalty, or combat. Those invented rules, fixed heuristic weights, and exploratory multiple comparisons limit transfer. Do not name an overall winner for Lucid's unpublished game.

The newer [research notebook](research-loop-notebook.md) links the historical and current snapshots. Its focused comparison uses seeds **66000–66019**, resource-first validation uses **67000–67099**, starter validation uses **65000–65099**, and the frontier follow-up uses **68000–68019** then **69000–69099**. These reports record Git HEAD **`229b7251e74c2a408e813d6c986020cf9c969887`**, `git_dirty=true`, Python **3.12.3**, and the exact source SHA-256 for each run. [Five score-checked replays](benchmarks/research-loop/score-checked-replays.json) include the original 12–0 failure, its 12–16 repair, a heldout candidate loss, and two loop diagnostics. No GitHub remote was created or pushed.
