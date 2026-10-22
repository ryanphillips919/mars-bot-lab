"""Focused, paired Mini Mars research runs with compact tracked evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile

from mini_mars.scenarios import SCENARIOS
from .match import RESULTS, ROOT, run_match, source_hashes
from .tournament import run_tournament


# Separate comparison seeds from previous debugging (50000, 62000) and the
# final held-out set (65000). A case changes one policy whenever possible.
CASES = (
    ("harvest_short", 1, "short-horizon", "coordinated", "coordinated-harvest-first",
     "Known bankable gold should outrank visibility work before a short deadline."),
    ("harvest_default", 1, "default", "coordinated", "coordinated-harvest-first",
     "Gold priority should not sacrifice the standard fog map."),
    ("harvest_abundant", 1, "abundant", "coordinated", "coordinated-harvest-first",
     "Gold priority should hold when many deposits are available."),
    ("harvest_vs_greedy_short", 1, "short-horizon", "greedy", "coordinated-harvest-first",
     "The repaired complex policy should be competitive with a simple scoring loop."),
    ("starter_open", 2, "open", "greedy", "starter",
     "A compact state machine can score reliably on open terrain."),
    ("starter_limited_vision", 2, "limited-vision", "greedy", "starter",
     "Persistent frontier goals help a simple starter under narrow vision."),
    ("starter_low_capacity", 2, "low-capacity", "greedy", "starter",
     "A simple full-cargo return loop remains reliable with small cargo."),
    ("starter_short", 2, "short-horizon", "greedy", "starter",
     "The starter's deadline guard avoids stranded gold in short games."),
    ("value_abundant", 3, "abundant", "greedy", "value",
     "Value-per-turn target ranking should help when deposit quantities vary."),
    ("value_obstacles", 3, "obstacle-heavy", "greedy", "value",
     "BFS return estimates should select better targets around obstacles."),
    ("value_low_capacity", 3, "low-capacity", "greedy", "value",
     "Value ranking should avoid long trips for small cargo."),
    ("frontier_limited_vision", 4, "limited-vision", "coordinated-nearest", "coordinated",
     "Information gain may beat nearest frontier under severe fog."),
    ("frontier_abundant", 4, "abundant", "coordinated-nearest", "coordinated",
     "Abundant deposits may reduce the value of information-gain scouting."),
    ("frontier_full_info", 4, "full-info", "coordinated-nearest", "coordinated",
     "A pure scouting-order change should tie when nothing is hidden."),
    ("iron_iron_rich", 5, "iron-rich", "coordinated-gold-only", "coordinated",
     "Iron-rich maps might make base investment worthwhile."),
    ("iron_scarce", 5, "scarce", "coordinated-gold-only", "coordinated",
     "The iron/build package should be stress-tested where gold is scarce."),
    ("allocation_abundant", 6, "abundant", "independent", "coordinated",
     "Distinct task reservations may help even with many deposits."),
    ("allocation_low_capacity", 6, "low-capacity", "independent", "coordinated",
     "Distinct reservations may matter when frequent trips increase congestion."),
)
BY_NAME = {case[0]: case for case in CASES}
EVIDENCE = ROOT / "mini_mars/docs/benchmarks/research-loop"


def compact(case: tuple, report: dict, count: int, seed: int) -> dict:
    name, iteration, scenario, a, b, hypothesis = case
    differences = report["paired_score_differences_a_minus_b"]
    interval = report["paired_bootstrap_ci95_a_minus_b"]
    records = [record for record in report["records"] if "error" not in record]
    zero_games = [{"seed": record["seed"], "swapped": record["swapped"],
                   "scores_a_b": [record["score_a"], record["score_b"]]}
                  for record in records if 0 in (record["score_a"], record["score_b"])]
    return {
        "name": name, "iteration": iteration, "hypothesis": hypothesis,
        "scenario": scenario, "config": report["config"], "bot_a": a, "bot_b": b,
        "seed_start": seed, "paired_seeds_requested": count,
        "complete_pairs": report["complete_pairs"], "failed_pairs": report["failed_pairs"],
        "attempted_games": report["attempted_games"], "clean_games_in_pairs": report["games_played"],
        "reliability_all_attempted_games": report["reliability"],
        "warnings_on_clean_pairs": report["movement_warnings"],
        "wins_on_clean_pairs": report["wins"], "candidate_win_rate": report["win_rate_b"],
        "average_scored_gold": report["average_gold"],
        "paired_mean_b_minus_a": -report["paired_average_score_difference_a_minus_b"]
            if report["paired_average_score_difference_a_minus_b"] is not None else None,
        "paired_ci95_b_minus_a": [-interval[1], -interval[0]] if interval else None,
        "paired_seed_sd": statistics.pstdev(differences) if differences else None,
        "worst_seed_b_minus_a": -max(differences) if differences else None,
        "best_seed_b_minus_a": -min(differences) if differences else None,
        "zero_score_games": zero_games,
        "behavior_per_clean_game": report["behavior_per_game"],
        "mean_decision_latency_ms": report["average_decision_latency_ms"],
        "command": (f"python3 -m mini_mars tournament --scenario {scenario} --bot-a {a} "
                    f"--bot-b {b} --matches {count} --seed {seed}"),
    }


def selected_replays(raw_reports: dict[str, dict], limit: int = 4) -> list[dict]:
    candidates = []
    for name, report in raw_reports.items():
        for record in report["records"]:
            if "error" in record or record.get("excluded"):
                continue
            summary = json.loads(Path(record["summary"]).read_text())
            warning = any(summary["movement_warnings"])
            zero = 0 in (record["score_a"], record["score_b"])
            if warning or zero:
                candidates.append((not warning, not zero, name, record))
    saved = []
    for _, _, name, record in sorted(candidates, key=lambda item: (item[0], item[1], item[2], item[3]["seed"]))[:limit]:
        _, _, scenario, a, b, _ = BY_NAME[name]
        seed, swapped = record["seed"], record["swapped"]
        identity = (seed * 1009, seed * 1009 + 1)
        folder = RESULTS / "matches" / f"research-{name}-{seed}-{'swap' if swapped else 'normal'}"
        result = run_match((b, a) if swapped else (a, b), seed,
                           bot_seeds=identity[::-1] if swapped else identity,
                           scenario=scenario, output_dir=folder)
        scores = result["scores"][::-1] if swapped else result["scores"]
        if scores != [record["score_a"], record["score_b"]]:
            raise RuntimeError(f"replay does not match tournament score: {folder}")
        saved.append({"case": name, "seed": seed, "swapped": swapped,
                      "scores_a_b": scores, "warnings": result["movement_warnings"],
                      "replay": str((folder / "replay.json").relative_to(ROOT))})
    return saved


def run_stage(stage: str, names: list[str]) -> Path:
    seed, count = (64000, 20) if stage == "comparison" else (65000, 100)
    raw_root = RESULTS / "benchmarks" / "research-loop" / stage
    raw_root.mkdir(parents=True, exist_ok=True)
    cases = []
    reports = {}
    for name in names:
        if name not in BY_NAME:
            raise ValueError(f"unknown case: {name}")
        case = BY_NAME[name]
        _, _, scenario, a, b, _ = case
        folder = Path(tempfile.mkdtemp(prefix=name + "-", dir=raw_root))
        print(f"{stage}: {name}: {count} paired seeds", flush=True)
        report = run_tournament(a, b, count, seed, scenario=scenario, output_dir=folder)
        reports[name] = report
        cases.append(compact(case, report, count, seed))
    evidence = {"format": "mini-mars-research-loop-v1", "stage": stage,
                "seed_sets": {"development": "50000 and 62000 ranges",
                              "comparison": "64000-64019", "held_out": "65000-65099"},
                "python_version": sys.version.split()[0],
                "source_revision": next(iter(reports.values()))["source_revision"],
                "source_sha256": source_hashes(),
                "bootstrap": "5000 deterministic percentile resamples by complete seed pair; RNG 20261021",
                "cases": cases, "selected_replays": selected_replays(reports)}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / f"{stage}.json"
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("comparison", "validation"))
    parser.add_argument("--cases", nargs="+", choices=BY_NAME)
    args = parser.parse_args()
    if args.stage == "validation" and not args.cases:
        parser.error("validation requires an explicit preselected --cases list")
    print(run_stage(args.stage, args.cases or list(BY_NAME)), flush=True)


if __name__ == "__main__":
    main()
