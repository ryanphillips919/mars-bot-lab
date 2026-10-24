"""Paired screening and held-out validation of Mini Mars construction economics."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from itertools import product
import json
from pathlib import Path
import tempfile

from mini_mars.scenarios import expansion_config
from .match import RESULTS, ROOT, source_hashes, source_revision
from .tournament import run_tournament

SCREEN_SEED = 81000
VALIDATION_SEED = 91000
BOTS = (
    ("coordinated-gold-only", "coordinated"),
    ("coordinated-gold-only", "coordinated-payback-build"),
    ("coordinated-gold-only", "coordinated-scaling-build"),
    ("coordinated-gold-only", "coordinated-planned-build"),
)


def configurations():
    for size, turns, cost, layout in product((15, 30, 50), (100, 200, 400),
                                              (4, 6, 8), ("uniform", "clustered")):
        yield expansion_config(size, turns, cost, layout)


def case_name(config, candidate, initial_iron):
    return (f"{config.width}x{config.height}-t{config.turns}-i{config.base_cost_iron}-"
            f"{config.resource_layout}-{candidate}-bank{initial_iron}")


def run_study(stage: str, case_limit: int | None = None, candidates: list[str] | None = None,
              count: int | None = None, output_root: Path | None = None,
              seed: int | None = None) -> dict:
    count = count or (20 if stage == "screen" else 100)
    seed = seed if seed is not None else (SCREEN_SEED if stage == "screen" else VALIDATION_SEED)
    output_root = output_root or RESULTS / "benchmarks" / "construction-expansion-v1" / stage
    output_root.mkdir(parents=True, exist_ok=True)
    combos = list(configurations())
    if stage == "validate" and case_limit is None:
        raise ValueError("validation must be restricted to preselected configurations")
    if case_limit is not None:
        combos = combos[:case_limit]
    comparisons = [pair for pair in BOTS if candidates is None or pair[1] in candidates]
    if not comparisons:
        raise ValueError("no candidate bots selected")
    rows = []
    for config in combos:
        for baseline, candidate in comparisons:
            for bank in (0, config.base_cost_iron):
                name = case_name(config, candidate, bank)
                current_config = expansion_config(config.width, config.turns,
                                                  config.base_cost_iron, config.resource_layout,
                                                  initial_banked_iron=bank)
                folder = Path(tempfile.mkdtemp(prefix=name + "-", dir=output_root))
                report = run_tournament(baseline, candidate, count, seed,
                                        config=current_config, output_dir=folder,
                                        save_replays=False)
                rows.append({
                    "name": name, "config": asdict(current_config), "baseline": baseline,
                    "candidate": candidate, "seeds": [seed, seed + count - 1],
                    "attempted_games": report["attempted_games"],
                    "complete_pairs": report["complete_pairs"],
                    "failed_pairs": report["failed_pairs"],
                    "faulted_matches": report["faulted_matches"],
                    "paired_gold_difference_candidate_minus_baseline":
                        -report["paired_average_score_difference_a_minus_b"]
                        if report["paired_average_score_difference_a_minus_b"] is not None else None,
                    "paired_ci95_candidate_minus_baseline":
                        [-report["paired_bootstrap_ci95_a_minus_b"][1],
                         -report["paired_bootstrap_ci95_a_minus_b"][0]]
                        if report["paired_bootstrap_ci95_a_minus_b"] is not None else None,
                    "win_rate_candidate": report["win_rate_b"],
                    "behavior_per_game": report["behavior_per_game"],
                    "invalid_actions": report["invalid_actions"],
                    "timeouts": report["timeouts"], "crashes": report["bot_crashes"],
                    "raw_report": str(folder / "tournament.json"),
                })
                print(f"{name}: {rows[-1]['paired_gold_difference_candidate_minus_baseline']}", flush=True)
    return {"format": "mini-mars-construction-expansion-v1", "stage": stage,
            "source_revision": source_revision(), "source_sha256": source_hashes(),
            "paired_seed_swap": True, "seed_start": seed, "paired_seeds_per_case": count,
            "cases": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("screen", "validate"))
    parser.add_argument("--case-limit", type=int, help="initial subset of matrix, in fixed order")
    parser.add_argument("--candidate", action="append",
                        choices=[candidate for _, candidate in BOTS])
    parser.add_argument("--matches", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", type=Path, required=True,
                        help="new JSON report path, never overwrites")
    args = parser.parse_args()
    evidence = run_study(args.stage, args.case_limit, args.candidate, args.matches, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
