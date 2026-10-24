"""Observation-only site planning for Mini Mars; historical bots are unchanged."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, inf

from .strategies import (CoordinatedGreedy, StrategySettings, bfs, home_distances,
                         known_cells, move, remaining_turns, shortest_base, simple)

Point = tuple[int, int]


@dataclass
class ConstructionPlan:
    site: Point
    projected_saved_turns: float
    acquisition_turns: float
    created_turn: int


class PlannedConstructionBot(CoordinatedGreedy):
    """Resource-first coordinator with one optional colony-wide investment plan.

    All rovers have identical abilities; a worker is assigned dynamically.
    Plans use visible and remembered terrain only. Estimates are heuristics,
    not claims about the true optimal policy or unknown resource deposits.
    """
    def __init__(self) -> None:
        super().__init__(StrategySettings(gold_priority=True, iron_enabled=False,
                                         build_enabled=False, stable_targets=True,
                                         horizon_scaled=True))
        self.plan: ConstructionPlan | None = None
        self.worker_id: str | None = None
        self.diagnostic_plan: dict | None = None

    @staticmethod
    def _site_value(site: Point, obs: dict, cells: dict, home: dict) -> float:
        distances, _ = bfs(site, cells)
        capacity = obs["constants"]["cargo_capacity"]
        remaining = remaining_turns(obs)
        gain = 0.0
        for point, cell in cells.items():
            if cell["resource"] != "gold" or cell["quantity"] <= 0:
                continue
            old = home.get(point, inf)
            new = distances.get(point, inf)
            if new >= old or new == inf:
                continue
            # Count complete cargo trips, bounded by the actual time horizon.
            trips = ceil(cell["quantity"] / capacity)
            trip_cost = 2 * new + min(capacity, cell["quantity"]) + 1
            trips = min(trips, max(0, remaining // max(1, trip_cost)))
            gain += trips * (old - new)  # Conservative one-way saving.
        return gain

    def _choose_plan(self, obs: dict, cells: dict) -> ConstructionPlan | None:
        left = remaining_turns(obs)
        if left < 20:
            return None
        capacity = obs["constants"]["cargo_capacity"]
        cost = obs["constants"]["base_cost_iron"]
        bank = obs["bank"]["iron"]
        deficit = max(0, cost - bank)
        home = home_distances(obs["bases"], cells)
        gold = [(p, c) for p, c in cells.items()
                if c["resource"] == "gold" and c["quantity"] > 0 and p in home]
        if not gold:
            return None
        bases = {(b["x"], b["y"]) for b in obs["bases"]}
        enemy_bases = {(b["x"], b["y"]) for b in obs.get("enemies", {}).get("bases", [])}
        # Expansion requires known reachable iron unless already funded.
        iron = [(p, c) for p, c in cells.items()
                if c["resource"] == "iron" and c["quantity"] > 0 and p in home]
        if deficit and not iron:
            return None
        acquisition = 0.0
        if deficit:
            # Approximate the best accessible iron round trips, including mining
            # and unloading. Do not confuse banked with carried iron.
            rounds = ceil(deficit / capacity)
            cheapest = min(2 * home[p] + 1 for p, _ in iron)
            acquisition = deficit / obs["constants"]["mine_rate"] + rounds * cheapest
        # Candidate sites come from discovered gold and their adjacent known
        # traversable tiles, NOT the whole hidden map.
        candidates = set()
        for point, _ in gold:
            x, y = point
            for p in ((x, y), (x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                if cells.get(p, {}).get("terrain") == "plain" and p not in bases and p not in enemy_bases:
                    candidates.add(p)
        # Cheap coarse ranking bounds the cost of detailed per-site BFS.
        scored = sorted(candidates, key=lambda p: (
            -sum(max(0, home.get(g, 0) - (abs(p[0]-g[0])+abs(p[1]-g[1])))
                 * min(c["quantity"], capacity) for g, c in gold),
            p))
        rover_routes = [bfs((r["x"], r["y"]), cells)[0] for r in obs["rovers"]]
        best = None
        for site in scored[:12]:
            gain = self._site_value(site, obs, cells, home)
            travel = min((route.get(site, inf) for route in rover_routes), default=inf)
            investment = acquisition + travel + 1
            if investment >= left or gain <= investment * 1.25:
                continue
            if best is None or gain - investment > best[0]:
                best = (gain - investment, ConstructionPlan(site, gain, acquisition, obs["turn"]))
        return best[1] if best else None

    def decide(self, obs: dict) -> list[dict]:
        # Ordinary gold collection and safe return remain the fallback.
        actions = super().decide(obs)
        cells = known_cells(obs)
        bases = {(b["x"], b["y"]) for b in obs["bases"]}
        self.diagnostic_plan = None
        if self.plan is not None and (self.plan.site in bases or
                                      cells.get(self.plan.site, {}).get("terrain") != "plain"):
            self.plan, self.worker_id = None, None
        if self.plan is None and obs["turn"] % 5 == 0:
            self.plan = self._choose_plan(obs, cells)
        if self.plan is None:
            return actions
        site = self.plan.site
        if obs["turn"] % 10 == 0:
            home = home_distances(obs["bases"], cells)
            if self._site_value(site, obs, cells, home) <= 0:
                self.plan, self.worker_id = None, None
                return actions
        rover_by_id = {r["id"]: r for r in obs["rovers"]}
        if self.worker_id not in rover_by_id:
            candidates = [r for r in obs["rovers"] if r["cargo"]["gold"] == 0]
            if not candidates:
                return actions
            self.worker_id = min(candidates, key=lambda r: (
                abs(r["x"]-site[0])+abs(r["y"]-site[1]), r["id"]))["id"]
        worker = rover_by_id[self.worker_id]
        rid = worker["id"]
        here = (worker["x"], worker["y"])
        cost = obs["constants"]["base_cost_iron"]
        bank = obs["bank"]["iron"]
        bases_list = obs["bases"]
        base, base_steps, base_move = shortest_base(worker, bases_list, cells)
        chosen = None
        stage = "build"
        if worker["cargo"]["gold"]:
            # Gold already in hand has priority over speculative infrastructure.
            chosen = simple(rid, "DEPOSIT") if here in bases else move(rid, base_move)
            stage = "deliver_gold"
        elif bank < cost:
            stage = "acquire_iron"
            needed = min(obs["constants"]["cargo_capacity"], cost - bank)
            carried = worker["cargo"]["iron"]
            if here in bases and carried:
                chosen = simple(rid, "DEPOSIT")
            elif carried >= needed or carried == obs["constants"]["cargo_capacity"]:
                chosen = move(rid, base_move)
            else:
                distances, first = bfs(here, cells)
                options = [p for p, c in cells.items() if c["resource"] == "iron"
                           and c["quantity"] > 0 and p in distances]
                if options:
                    home = home_distances(bases_list, cells)
                    target = min(options, key=lambda p: (
                        distances[p] + home.get(p, inf), p))
                    chosen = simple(rid, "MINE") if target == here else move(rid, first[target])
                elif carried:
                    chosen = move(rid, base_move)
                else:
                    # No visible iron remains; let the colony explore and recover.
                    self.plan, self.worker_id = None, None
                    return actions
        elif here == site:
            chosen = simple(rid, "BUILD")
        else:
            distances, first = bfs(here, cells)
            if site not in distances:
                self.plan, self.worker_id = None, None
                return actions
            chosen = move(rid, first[site])
        # Never override the basic scoring deadline with speculative construction.
        if worker["cargo"]["gold"] and base_steps + 1 >= remaining_turns(obs):
            chosen = simple(rid, "DEPOSIT") if here in bases else move(rid, base_move)
        index = next(i for i, r in enumerate(obs["rovers"]) if r["id"] == rid)
        actions[index] = chosen
        self.targets.pop(rid, None)
        self.target_kinds.pop(rid, None)
        if chosen["type"] == "MOVE":
            self.diagnostic_targets[rid] = site if stage == "build" else base if stage == "deliver_gold" else here
        self.diagnostic_plan = {"site": list(site), "worker": rid, "stage": stage,
                                "projected_saved_turns": self.plan.projected_saved_turns}
        return actions
