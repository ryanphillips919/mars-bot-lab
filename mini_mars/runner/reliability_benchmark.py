"""Small, reproducible paired-seed reliability smoke study."""

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


MATRIX = (
    ("default", "greedy", "coordinated"),
    ("obstacle-heavy", "greedy", "coordinated"),
    ("short-horizon", "greedy", "coordinated"),
    ("short-horizon", "greedy-no-cargo-guard", "greedy"),
)
EVIDENCE = ROOT / "mini_mars/docs/benchmarks/reliability-v1/smoke.json"


def compact(case: tuple[str, str, str], report: dict, seed: int, count: int) -> dict:
    scenario, a, b = case
    ci = report["paired_bootstrap_ci95_a_minus_b"]
    return {
        "case": list(case), "scenario_config": asdict(SCENARIOS[scenario]),
        "seed_start": seed, "paired_seeds_requested": count,
        "attempted_games": report["attempted_games"], "complete_pairs": report["complete_pairs"],
        "failed_pairs": report["failed_pairs"], "games_played_on_clean_pairs": report["games_played"],
        "wins_on_clean_pairs": report["wins"], "candidate_win_rate_on_clean_pairs": report["win_rate_b"],
        "paired_mean_gold_b_minus_a": (-report["paired_average_score_difference_a_minus_b"]
                                        if report["paired_average_score_difference_a_minus_b"] is not None else None),
        "paired_ci95_gold_b_minus_a": [-ci[1], -ci[0]] if ci else None,
        "average_scored_gold": report["average_gold"],
        "reliability_all_attempted_games": report["reliability"],
        "movement_warnings_on_clean_pairs": report["movement_warnings"],
        "behavior_per_clean_game": report["behavior_per_game"],
        "average_decision_latency_ms": report["average_decision_latency_ms"],
        "command": f"python3 -m mini_mars tournament --scenario {scenario} --bot-a {a} --bot-b {b} --matches {count} --seed {seed}",
    }


def run_smoke(seed: int = 50000, count: int = 20) -> Path:
    raw = RESULTS / "benchmarks/reliability-v1"
    raw.mkdir(parents=True, exist_ok=True)
    cases = []
    anomalies = []
    first = None
    for case in MATRIX:
        scenario, a, b = case
        folder = Path(tempfile.mkdtemp(prefix="--".join(case) + "-", dir=raw))
        print(f"Reliability smoke: {scenario}: {a} vs {b}; {count} paired seeds", flush=True)
        report = run_tournament(a, b, count, seed, scenario=scenario, output_dir=folder)
        first = first or report
        cases.append(compact(case, report, seed, count))
        records = [item for item in report["records"] if "error" not in item]
        for record in records:
            summary = json.loads(Path(record["summary"]).read_text())
            if (record["score_a"] == 0 or record["score_b"] == 0 or
                    any(summary["movement_warnings"][slot] for slot in (0, 1))):
                anomalies.append((case, record, summary))
    # Preserve a few complete, score-checked replays for warning/zero-score review.
    saved = []
    for case, record, summary in anomalies[:3]:
        scenario, a, b = case
        swapped, map_seed = record["swapped"], record["seed"]
        folder = RESULTS / "matches" / f"reliability-{scenario}-{a}-{b}-{map_seed}-{'swap' if swapped else 'normal'}"
        identity = (map_seed * 1009, map_seed * 1009 + 1)
        rerun = run_match((b, a) if swapped else (a, b), map_seed,
                          bot_seeds=identity[::-1] if swapped else identity,
                          scenario=scenario, output_dir=folder)
        scores = rerun["scores"][::-1] if swapped else rerun["scores"]
        if scores != [record["score_a"], record["score_b"]]:
            raise RuntimeError(f"replay score mismatch: {folder}")
        saved.append({"case": list(case), "seed": map_seed, "swapped": swapped,
                      "scores_a_b": scores, "movement_warnings": rerun["movement_warnings"],
                      "replay": str((folder / "replay.json").relative_to(ROOT))})
    evidence = {"format": "mini-mars-reliability-v1", "python_version": sys.version.split()[0],
                "source_revision": first["source_revision"], "source_sha256": source_hashes(),
                "seed_start": seed, "paired_seeds_per_case": count,
                "bootstrap": "5000 deterministic percentile resamples of complete seed pairs; RNG 20261021",
                "cases": cases, "anomaly_count": len(anomalies), "reviewed_replays": saved,
                "evidence_limit": "Warnings flag suspicious movement; absence of warnings is not proof of optimal routing."}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n")
    return EVIDENCE


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=50000)
    parser.add_argument("--matches", type=int, default=20)
    args = parser.parse_args()
    print(run_smoke(args.seed, args.matches))
