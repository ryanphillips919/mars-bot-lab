# Mars Bot Lab

Local experiments with autonomous agents for [Lux AI Season 2](https://github.com/Lux-AI-Challenge/Lux-Design-S2). This repository currently provides the first match workflow; strategies, tournaments, and cross-language benchmarks are future milestones.

## Quick start (Linux or WSL Ubuntu)

Install Git and Python 3.10 with its `venv` module. The [upstream setup guide](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/README.md) supports Python 3.8–3.10; this project selects 3.10. Network access to GitHub and PyPI is needed for setup.

```sh
make setup
make test
make demo
```

`make setup` checks out upstream commit `5bcb3c775d536cecda32a3c041a9814279b79c5b` into ignored `engine/upstream/`, creates `.venv/`, installs the upstream simulator, and saves the resolved package list to `.venv/installed-packages.txt`. Set `PYTHON=/path/to/python3.10 make setup` if needed. The engine revision is fixed; Python transitive dependencies are not yet locked, so retain `installed-packages.txt` when comparing runs.

`make demo` runs the pinned upstream Python starter agent against itself with seed 42. It writes `results/demo/replay.json` and `results/demo/summary.json`. Upload the replay JSON to the [official viewer](https://s2vis.lux-ai.org/) to watch it. The local CLI can also run the same two agents directly:

```sh
.venv/bin/luxai-s2 engine/upstream/kits/python/main.py engine/upstream/kits/python/main.py -s 42 -o results/demo/cli-replay.json
```

Run a different pair with:

```sh
.venv/bin/python -m experiments.match --player-0 path/to/first/main.py --player-1 path/to/second/main.py --seed 42
```

The runner uses the engine's `Episode` and terminal rewards. `summary.json` records the engine revision, seed, two scores, and winning player; the official replay remains the full record of the game. Keep each Python bot's `main.py`, `agent.py`, and `lux/` helpers together as described in the [starter kit](https://github.com/Lux-AI-Challenge/Lux-Design-S2/tree/5bcb3c775d536cecda32a3c041a9814279b79c5b/kits/python).

## Project map

| Path | Purpose |
| --- | --- |
| `engine/REVISION` | Exact upstream Git revision |
| `engine/upstream/` | Ignored local checkout, created by setup |
| `experiments/match.py` | Seeded two-agent match and result JSON |
| `scripts/setup.sh` | Local simulator installation |
| `docs/upstream-notes.md` | Rules, protocol, licensing, and current limits |
| `results/` | Ignored replays and experiment output |

The competition rules and API for the upcoming Lucid event are unpublished. Lux is a practice environment, not an implementation of those rules.

