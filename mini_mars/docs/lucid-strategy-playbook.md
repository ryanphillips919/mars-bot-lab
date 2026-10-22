# Lucid strategy playbook — Mini Mars practice evidence

Mini Mars is an **unofficial** practice game. Lucid's announcement names rovers, iron, gold, bases, exploration, and competing colonies, but does not define scoring or the bot API. The measured results below test our invented rules, not Lucid's game.

## Quick reference for competition morning

1. **First, get a valid bot and a complete match.** Identify scoring, visibility, action timing, match length, and compute limits. Log seeds, scores, faults, and decision latency. Spend the first part of the three-hour contest on correctness.
2. **Plan delivery before mining.** If only deposited cargo scores, reserve the BFS route to a base plus one deposit action. The [40-turn validation](benchmarks/strategy-v2/validate.json) shows why mined gold and scored gold differ.
3. **Assign distinct tasks to rovers.** If deposits can deplete or be contested, avoid sending all workers to the same target. Test this with the same scorer and routes on both sides, as in the [allocation comparisons](benchmarks/strategy-v2/validate.json).
4. **Explore only if information is useful.** Under fog, try nearest frontier first, then expected newly revealed tiles per travel turn. With a known map, exploration for visibility is wasted; see the [full-info control](benchmarks/strategy-v2/smoke.json).
5. **Diagnose a loss before adding features.** Check faults, then gold mined versus deposited, final cargo, known deposits, movement and waits, iron spending, and whether bases were built. Read a replay when behavior is surprising.

**Three most useful transferable lessons for Saturday:** bank scored value before the deadline; coordinate shared workers; condition exploration on hidden information. Their measured sizes are Mini Mars-specific.

### Adapt to the real rules

Ask: What scores, and does carried cargo count? Are terrain or resources hidden? What are movement costs? Can rovers share tiles or collide? Can rovers be manufactured? Can bases be built, and at what cost? What ends the game? Are actions simultaneous? What are the runtime limits? Is the remaining horizon observable? Use the answers to choose which practice algorithms apply.

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
```

The benchmark commands save compact reports under `mini_mars/docs/benchmarks/strategy-v2/` and detailed outputs under ignored `mini_mars/results/`. Every case records its standalone tournament command. Both reports record Git HEAD **`221d61a37422e4762bc1d57586ee01959748dc5b`**, `git_dirty=true` during implementation, and matching SHA-256 hashes of the relevant Mini Mars sources. Smoke seeds are **30000–30019**, validation seeds **40000–40099**, each in both player slots. Intervals use **5000** deterministic bootstrap resamples of complete pairs (RNG seed **20261021**). Decision latency includes process scheduling and JSON overhead.

The symmetric map is 15×15. Only banked gold scores; bases cost eight banked iron; rovers may stack; there is no rover production, collision penalty, or combat. Those invented rules, fixed heuristic weights, and exploratory multiple comparisons limit transfer. Do not name an overall winner for Lucid's unpublished game.
