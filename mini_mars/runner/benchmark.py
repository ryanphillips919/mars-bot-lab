"""Run the fixed issue #1 Mini Mars experiment matrix and save compact evidence."""

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


# Each pair is baseline A versus candidate B. Order also breaks selection ties.
MATRIX = (
    ("default", "greedy", "value"),
    ("default", "independent", "coordinated"),
    ("default", "coordinated-no-explore", "coordinated"),
    ("default", "coordinated-gold-only", "coordinated"),
    ("full-info", "greedy", "value"),
    ("full-info", "independent", "coordinated"),
    ("full-info", "coordinated-no-explore", "coordinated"),
    ("scarce", "greedy", "value"),
    ("scarce", "coordinated-gold-only", "coordinated"),
    ("obstacle-heavy", "independent", "coordinated"),
    ("obstacle-heavy", "coordinated-no-explore", "coordinated"),
)
PRIMARY = (1, 5, 8, 10)
FULL_INFO_EXPLORATION_CONTROL = 6
SMOKE_START, SMOKE_COUNT = 10000, 20
VALIDATION_START, VALIDATION_COUNT = 20000, 100
EVIDENCE_DIR = ROOT / "mini_mars" / "docs" / "benchmarks" / "issue-1"


def case_id(case: tuple[str, str, str]) -> str:
    return "--".join(case)


def select_validation_cases(smoke: dict) -> list[int]:
    """Four fixed comparisons, then one close and one positive surprise, in matrix order."""
    if smoke.get("stage") != "smoke" or len(smoke.get("cases", [])) != len(MATRIX):
        raise ValueError("expected a complete issue #1 smoke summary")
    if smoke.get("source_sha256") != source_hashes():
        raise ValueError("source changed since smoke run; rerun smoke before validation")
    for index, item in enumerate(smoke["cases"]):
        if tuple(item["case"]) != MATRIX[index] or item["complete_pairs"] != SMOKE_COUNT:
            raise ValueError("smoke matrix or paired seed count does not match the fixed plan")
    selected = set(PRIMARY)
    eligible = [i for i in range(len(MATRIX)) if i not in selected and i != FULL_INFO_EXPLORATION_CONTROL]
    close = min(eligible, key=lambda i: (abs(smoke["cases"][i]["paired_mean_b_minus_a"]), i))
    selected.add(close)
    positive = [i for i in eligible if i not in selected and smoke["cases"][i]["paired_mean_b_minus_a"] > 0]
    if positive:
        selected.add(max(positive, key=lambda i: (smoke["cases"][i]["paired_mean_b_minus_a"], -i)))
    return sorted(selected)


def compact_case(case: tuple[str, str, str], report: dict, seed: int, count: int) -> dict:
    scenario, bot_a, bot_b = case
    return {
        "case": list(case), "scenario_config": asdict(SCENARIOS[scenario]),
        "seed_start": seed, "paired_seeds_requested": count,
        "complete_pairs": report["complete_pairs"], "games_played": report["games_played"],
        "failed_matches": report["failed_matches"], "failed_pairs": report["failed_pairs"],
        "wins": report["wins"], "win_rate_b": report["win_rate_b"],
        "average_gold": report["average_gold"],
        "paired_mean_b_minus_a": -report["paired_average_score_difference_a_minus_b"],
        "paired_ci95_b_minus_a": [-report["paired_bootstrap_ci95_a_minus_b"][1],
                                   -report["paired_bootstrap_ci95_a_minus_b"][0]],
        "invalid_actions": report["invalid_actions"], "timeouts": report["timeouts"],
        "bot_crashes": report["bot_crashes"],
        "average_decision_latency_ms": report["average_decision_latency_ms"],
        "command": (f"python3 -m mini_mars tournament --scenario {scenario} --bot-a {bot_a} "
                    f"--bot-b {bot_b} --matches {count} --seed {seed}"),
    }


def representative_replays(reports: dict[int, dict]) -> tuple[list[dict], list[str]]:
    """Rerun three informative games with the original bot seeds and verify scores."""
    candidates = []
    for index, report in reports.items():
        for record in report["records"]:
            if "error" not in record:
                candidates.append((index, record))
    choices: list[tuple[str, int, dict]] = []
    used: set[tuple[int, int, bool]] = set()
    selectors = (
        ("candidate-win", lambda item: -(item[1]["score_b"] - item[1]["score_a"]),
         lambda item: item[1]["score_b"] > item[1]["score_a"]),
        ("candidate-loss", lambda item: item[1]["score_b"] - item[1]["score_a"],
         lambda item: item[1]["score_b"] < item[1]["score_a"]),
        ("close", lambda item: abs(item[1]["score_b"] - item[1]["score_a"]),
         lambda item: True),
    )
    missing = []
    for label, score, predicate in selectors:
        options = [(i, record) for i, record in candidates
                   if predicate((i, record)) and (i, record["seed"], record["swapped"]) not in used]
        if not options:
            missing.append(label)
            continue
        index, record = min(options, key=lambda item: (score(item), item[0], item[1]["seed"], item[1]["swapped"]))
        used.add((index, record["seed"], record["swapped"]))
        choices.append((label, index, record))

    saved = []
    for label, index, record in choices:
        scenario, bot_a, bot_b = MATRIX[index]
        seed, swapped = record["seed"], record["swapped"]
        identity_seeds = (seed * 1009, seed * 1009 + 1)
        specs = (bot_b, bot_a) if swapped else (bot_a, bot_b)
        bot_seeds = identity_seeds[::-1] if swapped else identity_seeds
        folder = RESULTS / "matches" / f"issue-1-{label}-{scenario}-seed-{seed}-{'swapped' if swapped else 'normal'}"
        result = run_match(specs, seed, bot_seeds=bot_seeds, output_dir=folder, scenario=scenario)
        scores = result["scores"][::-1] if swapped else result["scores"]
        if scores != [record["score_a"], record["score_b"]]:
            raise RuntimeError(f"replay rerun disagreed with tournament: {folder}")
        saved.append({"category": label, "case": list(MATRIX[index]), "seed": seed,
                      "swapped": swapped, "score_a": scores[0], "score_b": scores[1],
                      "local_replay": str((folder / "replay.json").relative_to(ROOT))})
    return saved, missing


def run_stage(stage: str, smoke_path: Path | None = None) -> Path:
    if stage == "smoke":
        selected = list(range(len(MATRIX)))
        start, count = SMOKE_START, SMOKE_COUNT
    else:
        smoke_path = smoke_path or EVIDENCE_DIR / "smoke.json"
        selected = select_validation_cases(json.loads(smoke_path.read_text(encoding="utf-8")))
        start, count = VALIDATION_START, VALIDATION_COUNT
    raw_root = RESULTS / "benchmarks" / "issue-1"
    raw_root.mkdir(parents=True, exist_ok=True)
    cases = []
    reports = {}
    for index in selected:
        case = MATRIX[index]
        folder = Path(tempfile.mkdtemp(prefix=f"{stage}-{case_id(case)}-", dir=raw_root))
        print(f"{stage}: {case_id(case)} ({count} paired seeds)", flush=True)
        report = run_tournament(case[1], case[2], count, start, output_dir=folder, scenario=case[0])
        if report["failed_pairs"] or any(sum(report[name].values()) for name in
                                         ("invalid_actions", "timeouts", "bot_crashes")):
            raise RuntimeError(f"built-in bot fault; inspect {folder / 'tournament.json'}")
        reports[index] = report
        cases.append(compact_case(case, report, start, count))
    first = next(iter(reports.values()))
    evidence = {
        "format": "mini-mars-issue-1-benchmark-v1", "stage": stage,
        "seed_start": start, "paired_seeds_per_case": count,
        "source_revision": first["source_revision"], "source_sha256": first["source_sha256"],
        "python_version": sys.version.split()[0],
        "bootstrap": "5000 percentile resamples of complete seed pairs, RNG seed 20261021",
        "cases": cases,
    }
    if stage == "validate":
        evidence["selected_matrix_indices"] = selected
        evidence["representative_replays"], evidence["missing_replay_categories"] = representative_replays(reports)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / ("smoke.json" if stage == "smoke" else "validation.json")
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Compact evidence: {path}", flush=True)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("smoke", "validate"))
    parser.add_argument("--smoke", type=Path, help="smoke.json path (defaults to tracked issue #1 evidence)")
    args = parser.parse_args()
    run_stage(args.stage, args.smoke)


if __name__ == "__main__":
    main()
