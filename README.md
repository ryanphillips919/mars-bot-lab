# Mars Bot Lab

Local experiments with autonomous agents for the upcoming Lucid Mars colony competition. [Halite III](https://github.com/HaliteChallenge/Halite-III) is the primary practice engine because its mining, routing, fleet allocation, dropoff expansion, and collision problems transfer well to this project. The Lucid rules are unpublished, so Halite is a practice environment rather than a model of that competition. The earlier Lux AI Season 2 workflow remains available for comparison.

## Mini Mars: independent practice game

`mini_mars/` is a separate, lightweight simulator based on the few mechanics named in the hackathon description. Its rules are **invented for practice**, not Lucid rules. It uses a 15×15 seeded grid, two resources, rovers, bases, fog of war, and 100 simultaneous turns. The existing Halite and Lux workflows remain available.

```sh
python3 -m mini_mars match --bot-a greedy --bot-b coordinated --seed 42
python3 -m mini_mars replay /path/printed/by/match/replay.json --turns 0,10,50,100 --view 0
python3 -m mini_mars tournament --bot-a greedy --bot-b coordinated --matches 10 --seed 42
make view-mini-mars
```

The match command prints the actual replay path; substitute it in the second command. Use `--step` to move through an ASCII replay interactively or `--view omniscient` to see the full map. For a quick browser demo, run `make demo-mini-mars` then `make view-mini-mars` and open **http://127.0.0.1:8766/**. The viewer loads completed matches with saved replays, lets you play or scrub turns, and switches the map between either player's fog of war and the full map. The score cards show replay-wide information in every map view. Run another match and click Refresh to load it; stop the viewer with Ctrl+C. The existing `make view` command remains the Halite viewer on port 8765. A tournament runs two games per seed with player slots swapped, then writes a JSON report under `mini_mars/results/tournaments/`. The bots run as persistent subprocesses using a [language-independent JSON Lines protocol](mini_mars/docs/README.md#bot-protocol); the [Mini Mars guide](mini_mars/docs/README.md) lists all Python reference bots and rules. Python 3.11+ and the standard library are sufficient.

Mini Mars also has four [experiment scenarios and strategy variants](mini_mars/docs/README.md#experiment-presets-and-evidence). Run `python3 -m mini_mars.runner.benchmark smoke`, then `python3 -m mini_mars.runner.benchmark validate` for the fixed paired-seed study. Its compact reports and [Lucid strategy playbook](mini_mars/docs/lucid-strategy-playbook.md) distinguish transferable ideas from our invented rules.

## Competition signals

The hackathon description supplied by the organizers says code will control rovers, gather **iron and gold**, build bases, explore Mars, and compete against other colonies. This makes rover allocation, resource-specific mining decisions, return routes, base placement, and exploration useful strategy targets. It does not specify scoring, resource uses, construction costs, map visibility, collision rules, or the bot API. In particular, “explore” does not establish that the map has hidden information.

Halite provides a working sandbox for mining logistics, expansion, and contested movement. It has one resource and a fully visible map, so it cannot by itself test choosing between iron and gold or any hidden-map exploration rule the organizers may later announce. Keep those gaps explicit when judging results; use the preserved Lux Season 2 workflow as a secondary reference for multi-resource and base decisions.

## Quick start (Linux or WSL Ubuntu)

Install Git, Python 3, a C++17 compiler, Make, and CMake. Go is optional; setup compiles its starter bot when Go is installed. The engine requires access to GitHub and the pinned dependency download hosts during a fresh setup.

```sh
make setup
make test
make demo
make view
```

`make setup` checks out official Halite III at the revision in `engine/halite/REVISION`, builds its engine in-source in a separate ignored source copy, and compiles the official C++ and optional Go starter bots. The engine uses pinned dependency archive hashes. `make demo` runs two official C++ starters on a 32×32 map with engine seed 42 and explicit bot seeds 101 and 202. Each invocation creates a unique directory under `results/halite/` containing `summary.json`, the raw `engine-result.json`, `engine-stderr.log`, bot logs, and a plain JSON `.hlt` replay. The runner prints the summary and its artifact paths.

`make view` starts a local replay viewer at **http://127.0.0.1:8765/**. Open that URL in your browser (including from Windows when running the server in WSL). Select a saved match, press Play, scrub turns, or click an event to jump to it. The map shows remaining halite, ships and their cargo, shipyards, dropoffs, and collisions. Bank balances and ship counts update with the replay. Run `make demo` in another terminal to create a new match, then click Refresh in the viewer. The viewer uses only Python's standard library and browser JavaScript; it reads completed matches and does not start bots. Stop it with Ctrl+C. Its visualization is a project-built overview, separate from the unbuilt official `libhaliteviz` and Halite in a Box source.

For an existing local source checkout and cached dependency archives, setup also accepts:

```sh
HALITE_SOURCE=/path/to/Halite-III \
HALITE_DEPS_CACHE=/path/to/archives \
CMAKE=/path/to/cmake make setup
```

`HALITE_DEPS_CACHE` must contain `v2.2.3.zip`, `include.zip`, `tclap-1.2.2.tar.gz`, and `v1.3.4.zip`. CMake checks their upstream SHA-256 hashes. The engine checkout and compiled outputs are ignored by Git.

## Run matches

```sh
python3 -m experiments.match --seed 43 --width 40 --height 40
python3 -m experiments.match \
  --player-0 "python3 $PWD/engine/halite/upstream/starter_kits/Python3/MyBot.py" \
  --player-1 "$PWD/engine/halite/bin/MyBotGo 202" --seed 77
```

`--player-0` and `--player-1` each accept one shell command; the official engine launches them with `/bin/sh -c` from the run's result directory. Use absolute paths for local bots and scripts. The upstream Python starter chooses random moves without an explicit RNG seed, so a map seed alone does not reproduce its actions. The official C++ and Go starters accept an RNG seed argument.

The runner requests `--results-as-json` and `--no-compression`, checks the replay against the result, and records engine and visible bot file hashes. It reports `scores` in the existing `player_0` / `player_1` shape and selects the winner by the engine's **rank**, including equal final scores. Keep the raw result and replay when comparing algorithms. For a fair tournament, run each map seed twice with player slots swapped, record bot RNG seeds in the command strings, and compare paired outcomes. Benchmark bot decision time separately from engine wall time and replay writing.

## Earlier Lux Season 2 workflow

The Lux runner is preserved at `experiments/lux_match.py`:

```sh
make setup-lux
make demo-lux
```

`make setup-lux` needs Python 3.10 and installs the pinned Lux Season 2 checkout at `engine/REVISION` into `.venv/`. The existing Lux match runner and its test remain available, but no real Lux match has yet been verified in this workspace. Its replay viewer is [s2vis.lux-ai.org](https://s2vis.lux-ai.org/).

## Project map

| Path | Purpose |
| --- | --- |
| `engine/halite/REVISION` | Pinned official Halite III revision |
| `engine/halite/upstream/` | Ignored Halite checkout created by setup |
| `engine/halite/build-source/halite` | Engine built in an ignored source copy |
| `experiments/match.py` | Primary Halite match runner and result validation |
| `experiments/replay_server.py` and `ui/halite/` | Local browser replay viewer |
| `mini_mars/viewer.py` and `mini_mars/ui/` | Separate Mini Mars browser replay viewer |
| `mini_mars/scenarios.py` and `mini_mars/runner/benchmark.py` | Fixed Mini Mars scenarios and paired experiment matrix |
| `mini_mars/docs/lucid-strategy-playbook.md` | Measured practice lessons and links to compact benchmark evidence |
| `experiments/lux_match.py` | Preserved Lux Season 2 match runner |
| `scripts/setup_halite.sh` | Halite checkout and starter kit builds |
| `docs/halite-iii-investigation-20261021.md` | Investigation, exact build commands, and engine comparison |
| `results/` | Ignored match artifacts |

Halite III's MIT source license and the four dependencies' license details are documented in the [investigation report](docs/halite-iii-investigation-20261021.md). This setup does not add or change the Mars Bot Lab Git remote.
