# Competition Day Field Guide

Lucid has announced rovers, iron, gold, bases, and exploration, but has not published the scoring rules or bot API. Treat [Mini Mars](README.md) as practice. On event day, read the official rules and adapt the organizer's sample program first. Keep a copy of every version that completes a match.

## First 45 minutes

| Clock | Deliverable | Check |
| --- | --- | --- |
| 0–8 min | Read the official scoring, action, visibility, collision, timing, and submission rules. Run the organizer's sample unchanged. | Identify precisely when resources count as points and whether a return or deposit action is required. |
| 8–18 min | Make a protocol-safe bot: parse one observation, emit one legal response, flush stdout, log only to stderr. | Run a complete game; inspect invalid actions, crashes, timeouts, and the official score. |
| 18–32 min | Add the smallest scoring loop: mine a usable resource here, travel by shortest known route to one, return when required, deposit. Explore only when no useful known task exists. | Verify at least one actual score-changing event in a complete game. |
| 32–40 min | Protect delivery near the deadline; handle full cargo, depleted targets, blocked routes, and malformed input. | Check a late-game replay and one bad-input probe. |
| 40–45 min | Run a second complete match and submit the last working build. | Confirm the submitted command, working directory, language version, and output framing. |

If the real protocol restarts the program each turn, serialize only essential target state if allowed; otherwise use a deterministic rule. Add coordination or building only after a valid scoring bot has passed full matches.

## Small algorithm toolkit

Let `V` be known passable cells, `E` their movement edges, `R` rovers, and `D` known deposits. Recompute routes when the observation changes; a newly revealed obstacle can invalidate a route.

| Tool | Implementation sketch | Cost | Use when |
| --- | --- | --- | --- |
| Shortest route | BFS queue from rover; store `distance[next] = distance[cur] + 1` and the first direction. Do not step into unknown or known rock unless the real rules permit it. | `O(V + E)` per rover | Uniform-cost grid movement. Use Dijkstra if movement costs differ. |
| Resource-first choice | For each reachable deposit, estimate `deliverable units / (travel + mining + return + deposit)`. Filter by cargo room and remaining time; choose a deterministic tie break. | `O(R(V + E + D))` with one BFS per rover and cached return distances | Simple scoring loop with a required return. |
| Stable target | Keep `target[rover]` while reachable, useful, and still the assigned task. Clear it when delivery overrides the task or the task is exhausted. | `O(R)` state; scoring still dominates | When task scores fluctuate and rovers reverse course. A target must match the action actually pursued. |
| Distinct assignment | Sort rover–task bids by value, then assign each rover and deposit at most once; reserve a deposit during a worker's one-turn delivery action if another rover would otherwise take it. | `O(RD log(RD))` after route computation | Several rovers compete for scarce tasks. Validate against an entire independent greedy bot, since coordination has costs. |
| Safe deadline return | Before moving or mining with cargo, ensure `shortest distance from resulting position to scoring site + required deposit actions <= turns remaining after this action`. | One cached distance lookup per proposal | Cargo needs delivery and the horizon is finite. Account for fuel or hazards if present. |
| Investment payback | Build only if reachable future deliveries are expected to save more turns or gain more points than iron collection, construction, and delayed scoring cost. Include time remaining. | `O(D)` for a small candidate set, plus route maps | Only if real rules make bases useful; Mini Mars does not create rovers. |
| Explore or exploit | Estimate whether known resource supply can keep available rovers busy. Send a scout to a reachable frontier only if finding new tasks is worth delaying known scoring. | Frontier scan `O(V)` plus route lookup | Fog with insufficient known resources. Stop speculative scouting near the deadline. |

For example, if a rover holds four gold with capacity five, a remote fifth unit may cost three travel turns, one mining turn, and three turns back toward a base. Returning the four already held may be better. There is no universal cargo threshold: compare the **extra** detour with the marginal reward and preserve a feasible delivery path. The Mini Mars experimental return rule is a heuristic, not an official Lucid rule.

## Translate to the actual game

| If the official rules add… | Change the model |
| --- | --- |
| Rover production | Compare a new rover's cost and creation delay with the work it can complete before the deadline. Reserve spawn sites and commands. |
| Fuel, energy, or refueling | Add resource state to pathfinding and ensure every proposed route can reach a refill or scoring site. Uniform BFS may no longer suffice. |
| Different scoring or resource values | Rank tasks by **official score gained**, including conversion costs, not by Mini Mars gold units. If cargo scores immediately, remove return scheduling. |
| Multiple bases | Choose the reachable base with lowest real delivery cost; recompute after a new base appears. |
| Collisions or simultaneous actions | Predict teammate destinations, reserve contested cells, and check swaps and opponent interaction under the actual resolution order. Mini Mars lets rovers overlap. |
| Opponent blocking or theft | Value a deposit by what can be collected before the opponent reaches it; use only visible information. |
| Strict runtime limits | Profile one decision at the maximum map size and rover count. Cache immutable per-turn maps; remove expensive ranking before compromising legality. |

## Emergency debugging

| Symptom | First checks |
| --- | --- |
| Crash or local success only | Confirm executable path, Python/Go/C++ version, working directory, JSON framing, stderr versus stdout, and flush. Feed the sample observation and a partial one. |
| All `WAIT` | Inspect parsed rover IDs, legal-action syntax, action normalization, and exception logs. |
| No mining or no score | Confirm resources are actually visible, cargo has room, mine action succeeds, and scoring requires delivery. Inspect **state transitions**, not submitted commands. |
| Back-and-forth movement | Print rover position, actual action, target, target owner, and score for consecutive turns; clear stale targets and reserve a worker's task during delivery. |
| Endless exploration | Count known deliverable resources and active miners; lower scouting priority while known scoring is available. |
| Stranded cargo | Print remaining turns and shortest path to a scoring site after each action. Check full and partial cargo. |
| Sudden poor score | Replay the first divergence from the previous working build with the same seed and player slot. Count faults and zero-score games before comparing averages. |
| Timeout | Measure maximum decision latency on a crowded late observation; cache route maps and avoid one BFS per candidate. |

## Practice in this repository

```sh
make test
python3 -m mini_mars match --scenario short-horizon --bot-a starter --bot-b coordinated-harvest-first --seed 42
python3 -m mini_mars replay /path/printed/by/match/replay.json --turns 0,20,40
python3 -m mini_mars tournament --scenario scarce --bot-a starter --bot-b greedy --matches 20 --seed 72000
```

See the [starter source](../bots/competition_starter.py), [strategy source](../bots/strategies.py), and [measured playbook](lucid-strategy-playbook.md). These are unofficial Mini Mars experiments; no outcome proves a Lucid strategy will win.
