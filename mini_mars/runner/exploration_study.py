"""Controlled study of Mini Mars exploration starvation and simple repairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .match import RESULTS, ROOT, run_match, source_hashes
from .research_loop import compact
from .tournament import run_tournament


SCENARIOS = ("default", "obstacle-heavy", "scarce", "short-horizon")
CASES = []
for scenario in SCENARIOS:
    CASES.extend((
        (f"greedy_vs_old_{scenario}", 7, scenario, "greedy", "coordinated",
         "The complete coordinated policy may lose to simple greedy due to exploration starvation."),
        (f"old_vs_harvest_{scenario}", 7, scenario, "coordinated", "coordinated-harvest-first",
         "Known deliverable gold should take priority over scouting."),
        (f"greedy_vs_harvest_{scenario}", 7, scenario, "greedy", "coordinated-harvest-first",
         "Coordination can retain its allocation benefit without losing practical scoring."),
        (f"harvest_vs_adaptive_{scenario}", 7, scenario, "coordinated-harvest-first", "coordinated-adaptive",
         "A time- and opportunity-aware frontier bid may rival hard gold priority."),
    ))
for scenario in ("default", "short-horizon"):
    CASES.extend((
        (f"old_vs_scored_{scenario}", 7, scenario, "coordinated", "coordinated-frontier-scored",
         "Per-frontier values alone may remove inflated exploration bids."),
        (f"greedy_vs_adaptive_{scenario}", 7, scenario, "greedy", "coordinated-adaptive",
         "Adaptive exploration should compete with the simple scoring baseline."),
    ))
BY_NAME = {case[0]: case for case in CASES}
EVIDENCE = ROOT / "mini_mars/docs/benchmarks/exploration-fix"


def diagnostic_seed_replays() -> list[dict]:
    saved = []
    for bot in ("coordinated", "coordinated-frontier-scored",
                "coordinated-adaptive", "coordinated-harvest-first"):
        folder = RESULTS / "matches" / f"exploration-diagnosis-50004-{bot}"
        result = run_match(("greedy", bot), 50004, scenario="short-horizon", output_dir=folder)
        saved.append({"bot": bot, "scores": result["scores"],
                      "milestones": result["behavior"][1]["milestones"],
                      "economic_diagnostics": result["behavior"][1]["economic_diagnostics"],
                      "movement_warnings": result["movement_warnings"][1],
                      "replay": str((folder / "replay.json").relative_to(ROOT))})
    return saved


def run_stage(stage: str, names: list[str]) -> Path:
    seed, count = (66000, 20) if stage == "comparison" else (67000, 100)
    raw_root = RESULTS / "benchmarks" / "exploration-fix" / stage
    raw_root.mkdir(parents=True, exist_ok=True)
    cases = []
    for name in names:
        if name not in BY_NAME:
            raise ValueError(f"unknown comparison: {name}")
        case = BY_NAME[name]
        _, _, scenario, a, b, _ = case
        folder = Path(tempfile.mkdtemp(prefix=name + "-", dir=raw_root))
        print(f"{stage}: {name}: {count} paired seeds", flush=True)
        report = run_tournament(a, b, count, seed, scenario=scenario, output_dir=folder)
        cases.append(compact(case, report, count, seed))
    evidence = {"format": "mini-mars-exploration-fix-v1", "stage": stage,
                "python_version": sys.version.split()[0],
                "source_revision": report["source_revision"], "source_sha256": source_hashes(),
                "seed_sets": {"debug": "50004", "comparison": "66000-66019",
                              "held_out": "67000-67099"},
                "bootstrap": "5000 deterministic percentile resamples by complete seed pair; RNG 20261021",
                "cases": cases}
    if stage == "comparison":
        evidence["diagnostic_seed_replays"] = diagnostic_seed_replays()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / f"{stage}.json"
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("comparison", "validation"))
    parser.add_argument("--cases", nargs="+", choices=BY_NAME)
    args = parser.parse_args()
    if args.stage == "validation" and not args.cases:
        parser.error("validation requires an explicit preselected --cases list")
    print(run_stage(args.stage, args.cases or list(BY_NAME)), flush=True)
