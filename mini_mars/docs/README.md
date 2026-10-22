# Mini Mars practice game

Mini Mars is a deliberately small, **unofficial** game for comparing bot algorithms. The Lucid competition description names rovers, iron, gold, bases, and exploration; it does not supply rules or an API. Every rule below is a Mini Mars design choice. The Halite III integration in the repository is independent.

For the 45-minute event window, start with the [competition starter](competition-starter.md) and the [strategy playbook](lucid-strategy-playbook.md).

## Run it

From the repository root in Linux or WSL, with Python 3.11 or newer:

```sh
python3 -m mini_mars match --bot-a greedy --bot-b coordinated --seed 42
python3 -m mini_mars replay /path/printed/by/match/replay.json --turns 0,10,50,100 --view 0
python3 -m mini_mars replay /path/printed/by/match/replay.json --step --view omniscient
python3 -m mini_mars tournament --bot-a greedy --bot-b coordinated --matches 10 --seed 42
python3 -m mini_mars tournament --scenario scarce --bot-a coordinated-gold-only --bot-b coordinated --matches 10 --seed 42
make view-mini-mars
make test
```

For a quick saved match, use `make demo-mini-mars` before starting the browser viewer.

The match command saves `summary.json`, `replay.json` by default, and one stderr log per bot in a unique ignored `mini_mars/results/matches/` directory. `--no-replay` skips the replay. Summaries record the seed, bot commands and seeds, Python version, and hashes of the local engine and reference bot source. For custom bots, also retain the bot's own executable or source version. A tournament's `--matches` is the number of **map seeds**; each seed runs twice with the bots in opposite player slots. Its report and individual match summaries are under `mini_mars/results/tournaments/`. Add `--save-replays` to retain every tournament replay. No installed frontend package is needed.

The runner counts suspicious movement patterns per bot. Saved replay JSON includes `movement_warnings` with rover ID, turn range, recent positions/actions, and an optional current target. The monitor reports possible stalls; it does not change bot actions. Built-in bots may add an optional `targets` field to help diagnosis. Custom bots can omit it; required JSON Lines fields stay the same.

The browser viewer at **http://127.0.0.1:8766/** reads completed Mini Mars replays from `mini_mars/results/matches/`. Select a match, play or scrub, inspect a cell by hovering, and switch the map between player 0, player 1, and full visibility. Player views hide unexplored terrain and enemies outside current vision; remembered deposits are dimmed and may have stale quantities. The score cards and event log show complete replay information in all map views. The viewer does not run bots or show a match live. Run a new match in another terminal and click Refresh. The Halite browser viewer is separate (`make view`, port 8765).

## Experiment presets and evidence

`--scenario` accepts five fixed presets on `match` and `tournament`; omitting it preserves the default rules. These are **invented practice variations**, not organizer rules.

| Preset | Change from default |
| --- | --- |
| `default` | 8 mirrored rock pairs, 9 gold pairs, 6 iron pairs, fog of war |
| `full-info` | Identical physical map for the same seed as `default`; every current tile, deposit quantity, rover, and base is visible to both bots |
| `scarce` | 5 gold and 3 iron pairs, with the same 5–12 units per deposit |
| `obstacle-heavy` | 20 rock pairs; map generation still checks that open tiles are connected |
| `short-horizon` | Same physical map as `default` for a seed, with 40 instead of 100 turns |

Named scenarios, their complete configurations, Git revision and dirty state, and source hashes are saved in match/replay/tournament metadata. Explicit Python `Config` callers still work and are labeled `custom` when they do not match a preset. The map seed fixes symmetric terrain and deposits; a bot's RNG seed stays with its identity when tournament slots swap.

The issue #1 reports under `benchmarks/issue-1/` are historical results from the earlier bot code. The current controlled study runs with:

```sh
python3 -m mini_mars.runner.benchmark_v2 smoke
python3 -m mini_mars.runner.benchmark_v2 validate
python3 -m mini_mars.runner.reliability_benchmark --matches 20 --seed 50000
```

The strategy-v2 study uses 20 paired smoke seeds starting at 30000 and 100 disjoint validation seeds starting at 40000. The focused reliability study uses 20 paired seeds starting at 50000. Each pair has a normal and swapped game. Compact reports are under `mini_mars/docs/benchmarks/strategy-v2/` and `mini_mars/docs/benchmarks/reliability-v1/`; detailed outputs and score-checked example replays stay under ignored `mini_mars/results/`. The 95% paired bootstrap interval resamples whole map seeds (5000 deterministic resamples). Faulted games invalidate their seed pair for score analysis, while reliability counts all attempted games separately.

## Complete game rules

| Item | Rule / default |
| --- | --- |
| Map | 15×15 grid, four-direction movement, 8 pairs of impassable rocks |
| Players | Two; bases at `(1,1)` and `(13,13)`, three rovers each, multiple rovers may share a tile |
| Deposits | 9 mirrored gold pairs and 6 mirrored iron pairs; each contains 5–12 finite units |
| Game length | 100 turns; both bots respond before a turn is resolved |
| Actions | Each rover has one action: `MOVE`, `MINE`, `DEPOSIT`, `BUILD`, or `WAIT` |
| Cargo | Five combined iron and gold units per rover |
| Mine | One unit from the rover's tile, if a deposit remains and cargo has room |
| Deposit | On a friendly base, unload all cargo; gold adds one point per unit, iron enters the construction bank |
| Build | On a traversable tile with no base, spend eight **banked** iron for a friendly deposit base |
| Win | Highest banked gold after turn 100; equal scores tie |
| Vision | Each friendly rover reveals Manhattan radius two; explored cells stay known, but resource quantity is refreshed only when observed again |

All constants live in `mini_mars/engine/game.py` as `Config`. The seed determines rock and deposit placement. The map is rotationally symmetric so both starting positions have matching access to resources; open ground is checked for connectivity. The bot observation does not contain the map seed or unexplored cells. The symmetry is an artificial balancing choice, so it should not be mistaken for a Lucid rule.

### Turn transition

1. Each player receives its own observation for turn `t`. The engine writes both JSON lines before reading either bot response. A missing rover action means `WAIT`.
2. Every supplied action is validated against the **pre-turn** state. Unknown actions, duplicate rover commands, bad directions, blocked moves, impossible mines, invalid deposits, and unaffordable or occupied builds become `WAIT` and appear in replay diagnostics. A malformed or timed-out bot response also results in waits.
3. Valid moves occur together. Rovers may stack and pass through one another; no collision or combat rule exists.
4. Mining on each tile is resolved together. Contenders are ordered by player and rover ID, then rotated by `(turn + x + y) mod contender_count`. Each takes at most one unit until the deposit empties. A losing contender receives a `mine_contested` event, not an invalid-action penalty. This deterministic rotation prevents a fixed player-zero advantage on the last unit.
5. Builds resolve before deposits, so iron deposited on this turn cannot fund a build until the next turn. If multiple builds compete for one tile or a colony overspends, the loser waits and gets a diagnostic. Player priority for a contested tile alternates with turn parity; same-player ties use rover ID.
6. Valid deposits unload cargo. The turn advances, rover vision refreshes knowledge, and the next observations are ready. New bases can receive deposits from the following turn.

The replay has frame 0 for the initial state and one frame after each resolved turn, so a standard game has 101 frames. It includes the complete map for **analysis**; bot observations are generated separately and include only known cells. The ASCII viewer defaults to one player's limited view: `?` means unexplored, `,` remembered empty terrain, lowercase `g/i` remembered deposits, uppercase `G/I` currently visible deposits, `#` rock, `A/B` bases, `a/b` rovers, and `*` a stack. Use `--view 1` for the other player or `--view omniscient` for the full replay.

## Bot protocol

The runner keeps each bot process alive for the entire match and sends one UTF-8 JSON object followed by `\n` on stdin per turn. The bot must print exactly one JSON object followed by `\n` on stdout per turn and flush. Logs belong on stderr. Bot processes run from the repository root. The response deadline defaults to one second (`--timeout`). Bot commands are split into arguments, not run through a shell. For custom commands, `{seed}` is replaced with the bot's deterministic seed; use it to seed the bot's own RNG. Built-in aliases include `random`, `greedy`, `greedy-no-cargo-guard` (a controlled unsafe baseline), `value`, `independent`, `coordinated`, `coordinated-nearest`, `coordinated-no-endgame`, `coordinated-gold-only`, and `coordinated-payback-build`.

Example observation, abridged to two known cells and one rover:

```json
{"turn":0,"player":0,"width":15,"height":15,"cells":[{"x":1,"y":1,"terrain":"plain","resource":null,"quantity":0,"last_seen":0,"visible":true},{"x":2,"y":1,"terrain":"plain","resource":"gold","quantity":6,"last_seen":0,"visible":true}],"rovers":[{"id":"p0-r0","x":1,"y":1,"cargo":{"iron":0,"gold":0}}],"bases":[{"x":1,"y":1}],"bank":{"iron":0,"gold":0},"score":0,"enemies":{"rovers":[],"bases":[]},"constants":{"width":15,"height":15,"turns":100,"starting_rovers":3,"cargo_capacity":5,"mine_rate":1,"base_cost_iron":8,"vision_radius":2}}
```

The real observation has all three friendly rovers and every explored cell. A known cell's `visible` flag says whether it is inside current rover vision. `resource` and `quantity` may be stale when `visible` is false. Enemy rovers and bases appear only while currently visible. Friendly bases and all friendly rover positions are always present. There is no hidden terrain, deposit, enemy, or seed field elsewhere in the observation.

Example response:

```json
{"turn":0,"actions":[{"rover_id":"p0-r0","type":"MOVE","direction":"E"},{"rover_id":"p0-r1","type":"MINE"},{"rover_id":"p0-r2","type":"WAIT"}]}
```

Directions are uppercase `N`, `S`, `E`, `W`; action types are uppercase. `MINE`, `DEPOSIT`, `BUILD`, and `WAIT` need no other fields. An action can omit `WAIT` rovers entirely. The response `turn` must match the observation `turn`. This protocol uses JSON types and newline framing only, so Python, Go, and C++ bots can use their standard JSON libraries without changing the engine.

## Reference strategies and algorithm costs

- **Random:** A seeded Python RNG chooses among known legal moves, mine, deposit, build, and wait. It checks local legality but ignores long-term value. The RNG instance persists across turns, so fixed map and bot seeds reproduce its choices.
- **Greedy miner:** Each rover independently computes BFS over explored traversable tiles, prefers a reachable gold deposit, mines until full, follows BFS to the nearest base, deposits, and explores a known frontier when no reachable deposit is known. Independent choices can duplicate effort on a small deposit.
- **Coordinated greedy:** Computes deposit and frontier bids for all available rovers. A bid estimates useful units divided by travel, mining, and BFS return time, with a modest penalty if a visible opponent is closer. It assigns distinct targets, retaining a small preference for last turn's resource target. `coordinated` ranks frontiers by expected new tiles per travel turn; `coordinated-nearest` differs only in frontier destination ranking. Both share the same exploration trigger.
- **Value greedy (`value`):** Keeps greedy's gold-first, iron-fallback and frontier behavior, but ranks known deposits by useful units divided by outbound BFS steps, mining turns, estimated return distance, and one deposit turn. It does not build bases.
- **Independent bids (`independent`):** Uses the coordinated scorer, exploration, iron/build policy, and target persistence; each rover may choose the same highest-value task. Compare it with `coordinated` to isolate distinct-target allocation.
- **No exploration bids (`coordinated-no-explore`):** Negative control only. Starting areas contain no deposits, so this bot can remain stationary throughout a fog match.
- **Gold only (`coordinated-gold-only`):** Uses the coordinated policy without iron bids or base construction; otherwise identical. Compare it with `coordinated` to test iron/base investment as a package.
- **No endgame (`coordinated-no-endgame`):** Same paths, bids, and construction heuristic as `coordinated`, but disables the horizon filter and mandatory return decision.
- **Payback build (`coordinated-payback-build`):** Same iron targeting as `coordinated`, but builds only when known, deliverable gold suggests at least nine saved one-way delivery turns. It does not deliberately travel to a build site.

Coordinated bid weights live in `StrategySettings`: exploration `0.24` per newly revealed cell, prior resource-target multiplier `1.2`, early iron `0.65`, late iron `0.05`, and visible-opponent penalty `0.8`. These are fixed practice heuristics, not tuned Lucid values. Candidate return routes and endgame feasibility use BFS over known traversable cells.

BFS is `O(V + E)` on known tiles (at most 225 here). Greedy runs one BFS per rover per turn, `O(R(V + E))`. Coordinated greedy also scores up to `R × (D + F)` deposit/frontier candidates and sorts the bids: `O(R(V + E) + RD log(RD))` when `F ≤ V` and `D ≤ V`. The frontier scan checks a constant-size vision neighborhood for each known tile. The task-selection functions are in `mini_mars/bots/strategies.py`, separate from protocol I/O in `bots/entry.py`; swapping BFS or bid scoring needs no engine change.

## Read tournament results

The tournament report records paired scores and intervals from clean, complete seed pairs. A separate reliability section counts every attempted game, faults, invalid actions, and exceptions, including games excluded from paired scoring. Match and tournament behavior sections distinguish submitted action types, normalized engine actions (including implicit waits), and actions that changed state. Successful mining, deposits, and builds come from engine events. An effect-free rover turn includes waits and accepted actions that did nothing; movement is counted separately and is not labeled economically productive. Exploration-intent turns are omitted because the bot protocol does not report intent. Decision latency includes subprocess and JSON overhead, not just algorithm time.

Future comparisons that fit this platform include BFS versus A* or cached paths, but pathfinder changes should be tested separately from the allocation and exploration experiments above. Weighted Dijkstra, min-cost flow, cross-language equivalents, and parallel candidate evaluation can follow only if these simpler comparisons show value.
