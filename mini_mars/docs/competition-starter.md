# Competition starter: first valid Mars bot in 45 minutes

Lucid has named rovers, gold, iron, bases, and exploration, but has not published its rules or bot API. This is a **portable plan**, not a ready-to-submit Lucid program. Use the official sample bot's parser and action schema on event day. Mini Mars assumes banked gold scores, one action per rover per turn, known plain tiles for movement, and a separate deposit action; verify each assumption before using the policy.

## Four time boxes

| Time | Deliverable |
| --- | --- |
| First 10 minutes | Read scoring, legal actions, timing, visibility, sample input/output, runtime limits, and how to run a full local match. Identify whether cargo must be delivered. |
| Next 10 minutes | Adapt the sample bot into a process that reads one observation, emits a valid response for every turn, flushes stdout, and survives missing or surprising fields. Run one trivial match. |
| Next 15 minutes | Add the shortest safe route to a base, mine an immediate useful resource, navigate to a reachable known resource, and explore only when useful targets are absent. Check action legality before emission. |
| Final 10 minutes | Run a complete match. Inspect stderr, invalid actions, timeouts, score versus cargo, and a few rover paths. Fix one critical failure at a time. |

These are planning targets, not guarantees. If updates are allowed during qualifying, stage distinct-target assignment, better exploration, and economic construction **after** a valid scoring bot runs. Keep the last known working build available.

## Minimal decision loop

Use the real game's legal-action list if it provides one. The pseudocode below treats `safe_return` as a deadline invariant: after the proposed action, the rover must still have enough actions for a shortest **BFS** route to a scoring site and any required deposit action. Adapt it if carried cargo scores directly or movement consumes a different amount of time.

```python
from collections import deque
import json, sys

DIRS = (("N", 0, -1), ("S", 0, 1), ("E", 1, 0), ("W", -1, 0))

def paths(start, passable):
    """Known-cell BFS: distance and first step from start; O(V + E)."""
    distance, first = {start: 0}, {}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for direction, dx, dy in DIRS:
            nxt = (x + dx, y + dy)
            if nxt in passable and nxt not in distance:
                distance[nxt] = distance[(x, y)] + 1
                first[nxt] = first.get((x, y), direction)
                queue.append(nxt)
    return distance, first

targets = {}  # Per-rover state in a persistent process; omit if process restarts.

def choose(rover, obs, legal):
    here = rover_position(rover)
    passable = known_traversable_cells(obs)
    distance, first = paths(here, passable)
    base = nearest_reachable_base(obs, distance)
    cargo = scored_cargo(rover, obs)
    left = actions_remaining(obs)

    def legal_choice(action):
        return action if action in legal else wait_action(rover, legal)

    if cargo and here == base and deposit_action(rover) in legal:
        return deposit_action(rover)
    if cargo and base is not None and distance[base] + deposit_cost(obs) >= left:
        return legal_choice(move_action(rover, first.get(base)))

    current_resource = useful_resource_at(here, obs)
    if current_resource and mine_action(rover) in legal:
        proposal = mine_action(rover)
    else:
        target = targets.get(rover_id(rover))
        if target not in distance or not useful_resource_at(target, obs):
            target = best_reachable_resource(obs, rover, distance)
        if target is None:
            target = best_reachable_frontier(obs, distance)
        targets[rover_id(rover)] = target
        proposal = move_action(rover, first.get(target)) if target != here else wait_action(rover, legal)

    proposal = legal_choice(proposal)
    if cargo and base is not None and distance[base] + deposit_cost(obs) <= left:
        after = position_after(here, proposal)
        after_distance, _ = paths(after, passable)
        if after_distance.get(base, float("inf")) + deposit_cost(obs) > left - 1:
            proposal = legal_choice(move_action(rover, first.get(base)))
    return proposal

for line in sys.stdin:
    try:
        obs = json.loads(line)
        validate_essential_fields(obs)  # turn, own rovers, map, scoring sites
        actions = [choose(rover, obs, legal_actions(rover, obs)) for rover in own_rovers(obs)]
        response = real_protocol_response(obs, actions)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"input/decision error: {exc}", file=sys.stderr, flush=True)
        response = safe_protocol_fallback(line)  # Match the real API's required shape.
    print(json.dumps(response, separators=(",", ":")), flush=True)
```

The named helpers are deliberately placeholders for the organizers' schema. The tested Mini Mars BFS implementation is [`bots/strategies.py`](../bots/strategies.py); its bot protocol is in [`bots/entry.py`](../bots/entry.py). The fallback must know enough of the real protocol to return a valid turn and legal wait actions; test it against malformed and partial inputs. Keep stderr for diagnostics and stdout for responses only.

## Prevent oscillation with minimal state

Keep a rover's target until it is depleted, unreachable in the **current known** map, or a higher priority delivery becomes necessary. Recompute paths when new terrain is revealed. Do not alternate targets solely because their scores differ by a tiny amount; a modest persistence bonus or a fixed tie-break is enough. Track the last several positions and actions. If a rover repeats `A→B→A→B` without discovery, mining, deposit, construction, or reduced distance to a persistent target, log it and select a fresh reachable target. Do not call a deliberate wait or a long path a loop.

## If the real game differs sharply

Retain the parser, legal-action validator, safe fallback, output flush, and full-match smoke test. Rewrite the scoring and action priorities from the actual rules. If cargo scores immediately, remove deposit scheduling. If movement has energy costs or collisions, add them to legal movement and route estimates. If there is no grid, replace BFS with the official movement graph. If several actions are simultaneous, validate reservations and avoid duplicate tasks. A small valid bot that scores once is the first milestone; tune or port it only after that match finishes cleanly.

## Practice commands

```sh
make test
python3 -m mini_mars match --scenario short-horizon --bot-a greedy --bot-b coordinated --seed 42
python3 -m mini_mars replay mini_mars/results/matches/REPLAY_PATH/replay.json --turns 0,20,40
python3 -m mini_mars.runner.reliability_benchmark --matches 20 --seed 50000
```

The replay path is printed by `match`; substitute that exact path. Mini Mars reports invalid actions, protocol faults, scored gold, final cargo, and suspicious movement separately. It is an unofficial practice game, so none of its score weights establishes Lucid's best strategy.
