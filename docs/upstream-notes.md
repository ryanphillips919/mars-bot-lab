# Upstream integration notes

Inspected source: [Lux-Design-S2 at `5bcb3c7`](https://github.com/Lux-AI-Challenge/Lux-Design-S2/tree/5bcb3c775d536cecda32a3c041a9814279b79c5b). The checkout is a pinned dependency and is not copied into this repository.

## Rules and protocol

The [official specifications](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/specs.md) describe a two-player game: factories and light/heavy robots collect ice and ore, produce water and metal, and grow lichen. Final lichen determines the score. The [kit API](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/kits/README.md) distinguishes bidding/factory placement from normal turns. Each normal-turn observation includes board, units, factories, teams, and `real_env_steps`; actions map factory or unit IDs to commands, with unit commands submitted as queues. Replacing a queue costs power, so later strategy work should avoid needless updates.

The [Python kit's `main.py`](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/kits/python/main.py) reads one JSON message per line from stdin and prints one JSON action per line. It maintains the observation and calls `Agent.early_setup` or `Agent.act` in `agent.py`. The starter agent bids zero, chooses a valid factory spawn, builds heavy robots when affordable, mines ice, and returns ice to a factory. Its factory placement uses NumPy randomness with a fixed seed inside the agent; the match seed controls map generation.

The [official CLI](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/luxai_s2/luxai_runner/cli.py) accepts two bot paths, `-s` for a seed, and `-o` for a replay. Its [episode runner](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/luxai_s2/luxai_runner/episode.py) returns terminal rewards, which `experiments.match` records without reimplementing scoring. The official CLI also offers a tournament mode and Elo or win ranking. A paired-seed tournament with player swaps and structured results is later work.

## Language kits and versions

The [upstream README](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/README.md) calls for Python >=3.8 and <3.11. The packaging file states only >=3.8, so this project follows the stricter README range. The checked revision contains [Python](https://github.com/Lux-AI-Challenge/Lux-Design-S2/tree/5bcb3c775d536cecda32a3c041a9814279b79c5b/kits/python) and [C++](https://github.com/Lux-AI-Challenge/Lux-Design-S2/tree/5bcb3c775d536cecda32a3c041a9814279b79c5b/kits/cpp) starter directories. Its README links a Go kit, but `kits/go/` is absent at this revision; Go integration needs an independently verified source and protocol check.

## Attribution

The repository root [LICENSE](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/5bcb3c775d536cecda32a3c041a9814279b79c5b/LICENSE) is Apache 2.0. Its `luxai_s2/setup.py` metadata says MIT, which conflicts with the root license; retain the upstream checkout's license and attribution if distributing its code. The upstream README also requests citation of the Lux AI Season 2 NeurIPS 2023 paper when using the environment in published work.

## Current verification limit

This workspace has Python 3.12 but no Python 3.10, and shell DNS cannot resolve GitHub. The match command and replay workflow have been checked against upstream source, but a real match cannot be run here until Python 3.10 and network access are available. A local test covers the command's result and replay wiring with a simulated episode; it does not validate the actual simulator.

