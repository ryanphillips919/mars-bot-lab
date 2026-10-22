# Mini Mars practice game

Mini Mars is a deliberately small, **unofficial** game for comparing bot algorithms. The Lucid competition description names rovers, iron, gold, bases, and exploration; it does not supply rules or an API. Every rule below is a Mini Mars design choice. The Halite III integration in the repository is independent.

## Run it

From the repository root in Linux or WSL, with Python 3.11 or newer:

```sh
python3 -m mini_mars match --bot-a greedy --bot-b coordinated --seed 42
python3 -m mini_mars replay /path/printed/by/match/replay.json --turns 0,10,50,100 --view 0
python3 -m mini_mars replay /path/printed/by/match/replay.json --step --view omniscient
python3 -m mini_mars tournament --bot-a greedy --bot-b coordinated --matches 10 --seed 42
make test
```

The match command saves `summary.json`, `replay.json` by default, and one stderr log per bot in a unique ignored `mini_mars/results/matches/` directory. `--no-replay` skips the replay. Summaries record the seed, bot commands and seeds, Python version, and hashes of the local engine and reference bot source. For custom bots, also retain the bot's own executable or source version. A tournament's `--matches` is the number of **map seeds**; each seed runs twice with the bots in opposite player slots. Its report and individual match summaries are under `mini_mars/results/tournaments/`. Add `--save-replays` to retain every tournament replay. No frontend or installed package is needed.

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

The replay has frame 0 for the initial state and one frame after each resolved turn, so a standard game has 101 frames. It includes the complete map for **analysis**; bot observations are generated separately and include only known cells. The ASCII viewer defaults to one player's limited view: `?` means unexplored, `,` remembered empty terrain, lowercase `g/i` remembered deposits, uppercase `G/I` currently visible deposits, `#` rock, `A/B` bases, `a/b` rovers, and `*` a stack. Use `--view 1` for the other player or `--view omniscient` for the full replay. The viewer is not the Halite browser viewer.

## Bot protocol

The runner keeps each bot process alive for the entire match and sends one UTF-8 JSON object followed by `\n` on stdin per turn. The bot must print exactly one JSON object followed by `\n` on stdout per turn and flush. Logs belong on stderr. Bot processes run from the repository root. The response deadline defaults to one second (`--timeout`). Bot commands are split into arguments, not run through a shell. For custom commands, `{seed}` is replaced with the bot's deterministic seed; use it to seed the bot's own RNG. Built-in aliases are `random`, `greedy`, and `coordinated`.

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
- **Coordinated greedy:** Computes deposit and frontier bids for all available rovers. A bid estimates useful units divided by travel, mining, and return time, with a modest penalty if a visible opponent is closer. It sorts bids and assigns each rover to a distinct target, retaining a small preference for last turn's target. It considers iron before turn 60 and can build a base when enough nearby known gold lies far from existing bases. This can outperform independent selection when several rovers would otherwise chase the same deposit, but it is a heuristic, not a guarantee.

BFS is `O(V + E)` on known tiles (at most 225 here). Greedy runs one BFS per rover per turn, `O(R(V + E))`. Coordinated greedy also scores up to `R × (D + F)` deposit/frontier candidates and sorts the bids: `O(R(V + E) + RD log(RD))` when `F ≤ V` and `D ≤ V`. The frontier scan checks a constant-size vision neighborhood for each known tile. The task-selection functions are in `mini_mars/bots/strategies.py`, separate from protocol I/O in `bots/entry.py`; swapping BFS or bid scoring needs no engine change.

## Read tournament results

The tournament report records wins, losses via the opponent's wins, ties, tie-adjusted win rates, average banked gold, average A-minus-B score, invalid actions, bot timeouts/crashes, and total wall time. Every seed has a normal and swapped result. Built-in bot RNG seeds stay with bot identity through that swap. The average decision latency measures subprocess request-to-response time, including JSON and scheduling overhead; it is **not** pure algorithm compute time. Evaluate strategic quality with paired scores/wins, then inspect latency separately. A handful of matches can reveal bugs and rough direction, not statistical significance.

Future comparisons that fit this platform: (1) BFS versus A* or cached paths, (2) independent versus coordinated assignment with value-per-turn bids, and (3) exploration policies that weigh unknown cells against known gold. Weighted Dijkstra, min-cost flow, cross-language equivalents, and parallel candidate evaluation can follow only if these simpler comparisons show value.
