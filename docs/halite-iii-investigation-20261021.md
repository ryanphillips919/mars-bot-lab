# Halite III engine investigation — 2026-10-21

> Follow-up: after this investigation, Halite III became the default local match workflow. The implementation and usage are in the [project README](../README.md). The findings and temporary artifact paths below record the investigation as it happened.

> Viewer follow-up: Mars Bot Lab now has its own local browser replay viewer (`make view`). It rendered a saved 402-frame match in headless Chrome. The official `libhaliteviz` and Halite in a Box builds remain unverified.

## Recommendation

Adopt Halite III as the **primary practice engine for the next iteration**, after a small, reversible runner adaptation. Keep the existing Lux Season 2 runner and results as a comparison baseline. No engine migration was made in this investigation.

Halite III directly exercises mining, routing, fleet allocation, dropoff placement, and collision avoidance. Its single resource and single ship type remove much of Lux Season 2's factory, power, lichen, bid, and action queue work. A complete seeded match and a repeated, semantically identical match worked with the current toolchains. The main cost is maintaining a local C++ engine build with old pinned dependencies. That cost is real, but bounded and outweighed by the closer algorithm fit and three working language kits. The [official game overview](https://github.com/HaliteChallenge/Halite-III/blob/e1050ee924292997b3a446b4be4c821848944fd8/website/learn-programming-challenge/game-overview.md) describes the rules; the match evidence below comes from running the engine.

This is a practice engine, not evidence about the unpublished Lucid competition rules. The game’s sea setting, toroidal map, inspiration bonus, and ship collision rules are domain-specific; algorithms should be expressed independently of these details.

## Update from the hackathon description

The user supplied the organizers' brief description after this investigation: competitors will control rovers, gather **iron and gold**, build bases, explore Mars, and compete against other colonies. It confirms two named resources and base construction, but gives no scoring rules, resource uses, costs, map visibility, collision rules, or bot interface. “Explore” alone does not imply fog of war.

Halite III still works as the primary practice engine for rover dispatch, mining routes, return timing, infrastructure payoff, and contested movement. Its ships and dropoffs are proxies for rovers and bases, and its one resource and fully visible map leave two clear coverage gaps: iron-versus-gold allocation and possible information-gathering decisions. Lux Season 2 can serve as a secondary reference for multiple resources and base operations, though its extra mechanics are not confirmed Lucid rules. The recommendation above remains conditional on learning the actual competition rules; keep strategies independent of either engine's protocol.

## Source, environment, and licenses

- Official source: <https://github.com/HaliteChallenge/Halite-III>, checkout `/tmp/halite-iii-investigation-20261021`, revision `e1050ee924292997b3a446b4be4c821848944fd8` (2026-10-05). The replay identifies engine version `1.2.2.finals` and replay format version `3`.
- Toolchains observed: Python `3.12.3`; Go `go1.27.1 linux/amd64`; GCC/G++ `13.3.0`; GNU Make `4.3`; CMake `3.31.10` at `/tmp/halite-iii-tooling-20261021/bin/cmake`. Node `20.19.2` is present for possible viewer work.
- The repository root `LICENSE` is MIT. The engine’s pinned downloads are Catch2 `2.2.3` (Boost Software License 1.0), nlohmann/json `3.1.2` (MIT), TCLAP `1.2.2` (MIT), and zstd `1.3.4` (BSD or GPLv2; its BSD license was inspected). Preserve the relevant notices if vendoring or redistributing binaries/source.
- The engine requires C++17, CMake, Make, and access to the four archive URLs in `game_engine/CMakeLists.txt.in`. It has no Python runtime dependency. The Python3 kit uses standard library modules; the C++ kit requires C++14; the Go kit uses legacy relative imports.

## Build and kit verification

The requested `/tmp/halite-iii-sourcebuild-20261021` directory did not exist before this work. An earlier **out-of-source** configure at `/tmp/halite-iii-build-20261021` had downloaded the pinned archives but failed because `add_subdirectory` uses external source paths without binary paths. The first **in-source** configure in the copied engine reached downloads but failed with `Could not resolve host: github.com` (shell DNS unavailable). The four archives already in the earlier temporary build matched the pinned SHA-256 hashes, so they were copied into the new build’s `external/src/`; the repeat configure and engine build succeeded. A fresh online dependency download remains unverified in this environment. No files in the official source checkout were modified.

```sh
cp -a /tmp/halite-iii-investigation-20261021/game_engine /tmp/halite-iii-sourcebuild-20261021
/tmp/halite-iii-tooling-20261021/bin/cmake -S /tmp/halite-iii-sourcebuild-20261021 -B /tmp/halite-iii-sourcebuild-20261021 -DCMAKE_BUILD_TYPE=Release
# The first command failed at dependency download; then reuse verified cached archives:
mkdir -p /tmp/halite-iii-sourcebuild-20261021/external/src
cp -a /tmp/halite-iii-build-20261021/external/src/{v2.2.3.zip,include.zip,tclap-1.2.2.tar.gz,v1.3.4.zip} /tmp/halite-iii-sourcebuild-20261021/external/src/
sha256sum /tmp/halite-iii-sourcebuild-20261021/external/src/{v2.2.3.zip,include.zip,tclap-1.2.2.tar.gz,v1.3.4.zip}
/tmp/halite-iii-tooling-20261021/bin/cmake -S /tmp/halite-iii-sourcebuild-20261021 -B /tmp/halite-iii-sourcebuild-20261021 -DCMAKE_BUILD_TYPE=Release
/tmp/halite-iii-tooling-20261021/bin/cmake --build /tmp/halite-iii-sourcebuild-20261021 --target halite -j 4
```

The archive hashes, in the order above, are `659679a47edb72f0bdc535770368d5fac4abd115f02376e3c5990fdd6fac4629`, `495362ee1b9d03d9526ba9ccf1b4a9c37691abe3a642ddbced13e5778c16660c`, `f5013be7fcaafc69ba0ce2d1710f693f61e9c336b6292ae4f57554f59fde5837`, and `76f3e6cadd9e1714cad7b550e53b82d4a5a5f9e08fbc0b3eb54abd0d0ebeb42d`.

```sh
mkdir -p /tmp/halite-iii-kits-20261021
cp -a /tmp/halite-iii-investigation-20261021/starter_kits/{Python3,Go,C++} /tmp/halite-iii-kits-20261021/
python3 -m py_compile /tmp/halite-iii-kits-20261021/Python3/MyBot.py /tmp/halite-iii-kits-20261021/Python3/hlt/*.py
/tmp/halite-iii-tooling-20261021/bin/cmake -S /tmp/halite-iii-kits-20261021/C++ -B /tmp/halite-iii-kits-20261021/C++/build
/tmp/halite-iii-tooling-20261021/bin/cmake --build /tmp/halite-iii-kits-20261021/C++/build -j 4
go build -o /tmp/halite-iii-kits-20261021/Go/MyBot ./src # failed: no go.mod
GO111MODULE=off go build -o /tmp/halite-iii-kits-20261021/Go/MyBot ./src # succeeds, from the Go kit directory
```

The C++ kit compiled with a CMake compatibility deprecation warning. The Go kit needs `GO111MODULE=off` or a modern module/import-path conversion. Its bundled `run_game.sh` uses `go build main` and `go run main`, which do not match this directory layout on Go 1.27. The Python3 starter header says Python 3.6, but the complete match below verifies it runs on Python 3.12. The bundled kit `run_game.sh` scripts also assume a `./halite` executable alongside the kit; use the built engine path instead.

Build logs: `/tmp/halite-iii-configure-20261021.log` (DNS failure), `/tmp/halite-iii-configure-cached-20261021.log`, `/tmp/halite-iii-build-engine-20261021.log`, `/tmp/halite-iii-cpp-configure-20261021.log`, and `/tmp/halite-iii-cpp-build-20261021.log`. Built executables: `/tmp/halite-iii-sourcebuild-20261021/halite`, `/tmp/halite-iii-kits-20261021/C++/build/MyBot`, `/tmp/halite-iii-kits-20261021/Go/MyBot`.

## Complete matches, results, and replays

Run the engine from a temporary working directory because starter bots write `bot-*.log` to the process working directory. The first run used the project working directory; its generated bot logs were removed afterward. This command invokes two **unmodified official C++ starter bots**, each with an explicit RNG seed:

```sh
mkdir -p /tmp/halite-iii-matches-20261021/cpp-a
/tmp/halite-iii-sourcebuild-20261021/halite --results-as-json --seed 42 --width 32 --height 32 \
  --replay-directory /tmp/halite-iii-matches-20261021/cpp-a \
  '/tmp/halite-iii-kits-20261021/C++/build/MyBot 101' \
  '/tmp/halite-iii-kits-20261021/C++/build/MyBot 202' \
  > /tmp/halite-iii-matches-20261021/cpp-a/result.json \
  2> /tmp/halite-iii-matches-20261021/cpp-a/engine.stderr
```

Result: map seed `42`, map `32×32`, 401 recorded turns / 402 replay frames, player 0 score `51` rank `2`, player 1 score `583` rank `1`; both `terminated: false`. The winner is **player 1** by the engine's rank. The compressed replay is `/tmp/halite-iii-matches-20261021/cpp-a/replay-20261021-094437-0600-42-32-32.hlt` (14,153 bytes). `result.json` includes `stats` keyed by player ID, `map_seed`, dimensions, `replay`, `error_logs`, `terminated`, `final_snapshot`, and `execution_time`.

The exact command was repeated with replay directory `cpp-b`. `stats`, `final_snapshot`, map details, and termination flags matched. `execution_time`, timestamped paths, and compressed replay bytes differed. Repeating with `--no-compression` into `cpp-plain` and `cpp-plain-b` produced replay JSON that compared equal after removing `game_statistics.execution_time`. Each plain replay has 401 turns and 402 frames. The engine's compressed replay was independently decoded with system `libzstd.so.1` to valid JSON of replay format version 3 and the same scores/turn count. This establishes replay generation and semantic reproducibility for these fixed bots; it does not establish identical bytes or general reproducibility of arbitrary bots.

A second complete match used the unmodified Python and Go starter sources/executables. It ran with `/tmp/halite-iii-matches-20261021` as the working directory:

```sh
mkdir -p /tmp/halite-iii-matches-20261021/py-go-plain
/tmp/halite-iii-sourcebuild-20261021/halite --results-as-json --no-compression --seed 77 --width 32 --height 32 \
  --replay-directory /tmp/halite-iii-matches-20261021/py-go-plain \
  'python3 /tmp/halite-iii-kits-20261021/Python3/MyBot.py' \
  '/tmp/halite-iii-kits-20261021/Go/MyBot 202' \
  > /tmp/halite-iii-matches-20261021/py-go-plain/result.json \
  2> /tmp/halite-iii-matches-20261021/py-go-plain/engine.stderr
```

That run also reached 401 turns, with neither bot terminated. It produced player 0 (Python) score `1340`, rank `1`, and player 1 (Go) score `788`, rank `2`. Its replay is under `/tmp/halite-iii-matches-20261021/py-go-plain/` as named by `result.json`. Python's official starter does not seed its RNG; Go and C++ default to time/PID based seeds unless arguments are provided. An engine map seed alone therefore does not make all starter matches reproducible. Also, `stats[*].rank` is the authoritative winner field: `core/Statistics.cpp` breaks equal final scores by earlier score history and then a seed-derived random ID. A separate Python–Go run yielded `0–0` with distinct ranks.

Replay **playback** was not verified. `libhaliteviz` has source and a `yarn.lock`, but no built `dist/bundle.js` or installed `node_modules`; the shell cannot resolve package hosts. The historic `halite.io` URL now redirects to Two Sigma's home page. A future runner should keep replay JSON readable with `--no-compression` when visualization tooling is unavailable, and verify the returned replay path exists (the engine's fallback write path is not reflected in its `results["replay"]`). Its `terminated` keys are written only when the engine has bot log output, so the runner should also detect missing keys and inspect replay/game completion.

## Fit for Mars Bot Lab

| Priority | Halite III | Lux Season 1 | Lux Season 2 (current) |
| --- | --- | --- | --- |
| Transferable work | Direct mining, movement cost, return trips, ship allocation, dropoff expansion, collisions | Mining, routing, research, city expansion, day/night fuel, roads | Mining, routing, factory placement, power/refining, lichen growth, queues, collisions |
| Implementation scope | One resource, one ship type, simple per-turn orders; inspiration and toroidal wrap add game-specific details | Three resources, tech unlocks, day/night survival, city/fuel planning | Most mechanics: bid/placement, light/heavy bots, ice/ore/water/metal, rubble, power, lichen, action queues |
| Local tournaments | Verified full matches, JSON ranks/scores, CLI seeds, replay files; needs small Python wrapper | CLI and replays documented, but not run here | Existing `experiments/match.py` and mock test; no real match verified in this workspace |
| Reproducible benchmarks | Fixed engine and bot seeds produced identical replay state; timestamps and execution time differ | Seed support documented, not verified here | Pinned engine commit and runner seed, but simulator dependencies and real run still unverified |
| Python/Go/C++ equivalence | All three official kits executed or compiled with current toolchains; Go needs legacy mode | Official Python and C++ listed; no official Go kit listed in the inspected README | Pinned checkout has Python and C++; linked Go kit is outside that checkout and unverified |

Lux Season 1 and Season 2 comparisons use their official [Season 1 specifications](https://github.com/Lux-AI-Challenge/Lux-Design-S1/blob/master/specs.md), [Season 1 README](https://github.com/Lux-AI-Challenge/Lux-Design-S1), [Season 2 specifications](https://github.com/Lux-AI-Challenge/Lux-Design-S2/blob/main/specs.md), and [Season 2 README](https://github.com/Lux-AI-Challenge/Lux-Design-S2). The current project’s pinned Season 2 integration is described in `README.md` and `docs/upstream-notes.md`; its Python 3.10 requirement and missing pinned Go kit remain setup costs.

## Suggested runner adaptation (not implemented)

1. Keep the existing CLI arguments and result schema where useful, but make the engine invocation an adapter: launch the Halite binary as a subprocess with two bot command strings, `--results-as-json`, explicit seed/width/height, and a unique output directory. Keep the current Lux adapter for baseline comparisons.
2. Parse only the engine's stdout JSON; preserve raw `result.json`, stderr, bot logs, and `.hlt` replay. Validate that the replay path exists, the game reached its expected turn limit, and neither bot terminated. Map `stats["0"].score` and `stats["1"].score` to the existing score keys, and choose winner from lower `rank`, including equal-score tiebreaks.
3. Store the engine Git revision, binary hash, build type/toolchain, dependency archive hashes, map generator and size, game seed, bot source/binary hashes, bot RNG seeds, command lines, and ordered player slots with every match. Use paired seeds with swapped player order in tournaments.
4. Move tournament scheduling and benchmark summaries above the engine adapter. Compare the same strategy and protocol decisions across Python, Go, and C++ with deterministic tie-breaking and RNG streams. Benchmark bot decision time separately from engine wall time and replay compression, and retain raw replays for strategy audits.

At the time of this investigation, no project architecture, match runner, Git remote, or upstream checkout was changed. This file was its only Mars Bot Lab artifact; the subsequent runner implementation is documented in the README.
