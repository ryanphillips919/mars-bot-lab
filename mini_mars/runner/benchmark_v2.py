"""Focused Mini Mars strategy study; issue #1 evidence remains untouched."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

from mini_mars.scenarios import SCENARIOS
from .match import RESULTS, ROOT, run_match, source_hashes
from .tournament import run_tournament


# Baseline A, candidate B; all comparisons are paired and slot-swapped.
MATRIX = (
    ("default", "coordinated-nearest", "coordinated"),
    ("full-info", "coordinated-nearest", "coordinated"),
    ("scarce", "coordinated-nearest", "coordinated"),
    ("obstacle-heavy", "coordinated-nearest", "coordinated"),
    ("default", "coordinated-no-endgame", "coordinated"),
    ("short-horizon", "coordinated-no-endgame", "coordinated"),
    ("scarce", "coordinated-no-endgame", "coordinated"),
    ("default", "independent", "coordinated"),
    ("full-info", "independent", "coordinated"),
    ("default", "coordinated-gold-only", "coordinated"),
    ("scarce", "coordinated-gold-only", "coordinated"),
    ("default", "coordinated", "coordinated-payback-build"),
    ("scarce", "coordinated", "coordinated-payback-build"),
    ("scarce", "coordinated-gold-only", "coordinated-payback-build"),
)
VALIDATE = (0, 3, 4, 5, 6, 7, 8, 10, 12, 13)
SMOKE_SEED, SMOKE_COUNT = 30000, 20
VALIDATE_SEED, VALIDATE_COUNT = 40000, 100
EVIDENCE = ROOT / "mini_mars" / "docs" / "benchmarks" / "strategy-v2"


def compact(case: tuple[str, str, str], report: dict, seed: int, count: int) -> dict:
    scenario, a, b = case
    return {
        "case": list(case), "seed_start": seed, "paired_seeds_requested": count,
        "complete_pairs": report["complete_pairs"], "failed_pairs": report["failed_pairs"],
        "attempted_games": report["attempted_games"], "games_played": report["games_played"],
        "wins": report["wins"], "win_rate_b_on_clean_pairs": report["win_rate_b"],
        "paired_mean_b_minus_a": (-report["paired_average_score_difference_a_minus_b"]
                                  if report["paired_average_score_difference_a_minus_b"] is not None else None),
        "paired_ci95_b_minus_a": ([-report["paired_bootstrap_ci95_a_minus_b"][1],
                                   -report["paired_bootstrap_ci95_a_minus_b"][0]]
                                  if report["paired_bootstrap_ci95_a_minus_b"] else None),
        "average_gold": report["average_gold"],
        "reliability": report["reliability"], "failed_matches": report["failed_matches"],
        "exception_matches": report["exception_matches"], "faulted_matches": report["faulted_matches"],
        "behavior_per_clean_game": report["behavior_per_game"],
        "behavior_totals_on_clean_pairs": report["behavior_totals"],
        "average_decision_latency_ms": report["average_decision_latency_ms"],
        "scenario_config": asdict(SCENARIOS[scenario]),
        "command": (f"python3 -m mini_mars tournament --scenario {scenario} --bot-a {a} "
                    f"--bot-b {b} --matches {count} --seed {seed}"),
    }


def representative_replays(reports: dict[int, dict]) -> list[dict]:
    candidates = [(index, record) for index, report in reports.items() for record in report["records"]
                  if "error" not in record and not record["excluded"]]
    selectors = (
        ("candidate-win", lambda item: item[1]["score_b"] - item[1]["score_a"] > 0,
         lambda item: -(item[1]["score_b"] - item[1]["score_a"])),
        ("candidate-loss", lambda item: item[1]["score_b"] - item[1]["score_a"] < 0,
         lambda item: item[1]["score_b"] - item[1]["score_a"]),
        ("close", lambda item: True,
         lambda item: abs(item[1]["score_b"] - item[1]["score_a"])),
    )
    saved = []
    used = set()
    for label, predicate, key in selectors:
        options = [(i, record) for i, record in candidates
                   if predicate((i, record)) and (i, record["seed"], record["swapped"]) not in used]
        if not options:
            continue
        index, record = min(options, key=lambda item: (key(item), item[0], item[1]["seed"], item[1]["swapped"]))
        used.add((index, record["seed"], record["swapped"]))
        scenario, a, b = MATRIX[index]
        swapped = record["swapped"]
        seed = record["seed"]
        identity_seeds = (seed * 1009, seed * 1009 + 1)
        folder = RESULTS / "matches" / f"strategy-v2-{label}-{scenario}-seed-{seed}-{'swapped' if swapped else 'normal'}"
        result = run_match((b, a) if swapped else (a, b), seed,
                           bot_seeds=identity_seeds[::-1] if swapped else identity_seeds,
                           output_dir=folder, scenario=scenario)
        scores = result["scores"][::-1] if swapped else result["scores"]
        if scores != [record["score_a"], record["score_b"]]:
            raise RuntimeError(f"replay differs from tournament: {folder}")
        saved.append({"category": label, "case": list(MATRIX[index]), "seed": seed,
                      "swapped": swapped, "scores_a_b": scores,
                      "local_replay": str((folder / "replay.json").relative_to(ROOT))})
    return saved


def run_stage(stage: str) -> Path:
    selected = tuple(range(len(MATRIX))) if stage == "smoke" else VALIDATE
    seed, count = (SMOKE_SEED, SMOKE_COUNT) if stage == "smoke" else (VALIDATE_SEED, VALIDATE_COUNT)
    raw = RESULTS / "benchmarks" / "strategy-v2"
    raw.mkdir(parents=True, exist_ok=True)
    cases = []
    reports = {}
    for index in selected:
        case = MATRIX[index]
        name = "--".join(case)
        folder = Path(tempfile.mkdtemp(prefix=f"{stage}-{name}-", dir=raw))
        print(f"{stage}: {name}: {count} paired seeds", flush=True)
        report = run_tournament(case[1], case[2], count, seed, scenario=case[0], output_dir=folder)
        reports[index] = report
        cases.append(compact(case, report, seed, count))
    first = next(iter(reports.values()))
    evidence = {"format": "mini-mars-strategy-v2", "stage": stage,
                "source_revision": first["source_revision"], "source_sha256": source_hashes(),
                "python_version": sys.version.split()[0], "seed_start": seed,
                "paired_seeds_per_case": count,
                "bootstrap": "5000 percentile resamples of complete seed pairs; RNG seed 20261021",
                "cases": cases}
    if stage == "smoke":
        builds = sum(case["behavior_totals_on_clean_pairs"]["b"]["economy"].get("bases_built", 0)
                     for case in cases if case["case"][1:] == ["coordinated-gold-only", "coordinated"])
        evidence["pilot_builds_default_and_scarce"] = builds
        evidence["payback_followup"] = "eligible" if builds else "deferred: no observed construction"
    else:
        evidence["representative_replays"] = representative_replays(reports)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / f"{stage}.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Compact evidence: {path}", flush=True)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("smoke", "validate"))
    run_stage(parser.parse_args().stage)


if __name__ == "__main__":
    main()
