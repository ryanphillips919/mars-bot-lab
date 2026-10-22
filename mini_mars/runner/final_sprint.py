"""Fresh paired-seed comparisons for assignment stability and partial cargo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .match import RESULTS, ROOT, source_hashes
from .research_loop import compact
from .tournament import run_tournament


CASES = {}


def add(name: str, scenario: str, baseline: str, candidate: str, hypothesis: str) -> None:
    CASES[name] = (name, 9, scenario, baseline, candidate, hypothesis)


for scenario in ("default", "obstacle-heavy", "scarce", "short-horizon"):
    add(f"starter_vs_greedy_{scenario}", scenario, "starter", "greedy",
        "Check the small independent scoring loop against the older greedy bot.")
    add(f"starter_vs_harvest_{scenario}", scenario, "starter", "coordinated-harvest-first",
        "Compare the complete coordinated package with a simple reliable starter.")
    add(f"greedy_vs_harvest_{scenario}", scenario, "greedy", "coordinated-harvest-first",
        "Check whether the prior resource-first gain generalizes to new seeds.")
    add(f"harvest_vs_reliable_{scenario}", scenario, "coordinated-harvest-first",
        "coordinated-harvest-reliable",
        "Combined stable assignment and marginal cargo return should avoid loops without losing score.")

for scenario in ("default", "scarce", "short-horizon", "full-info"):
    add(f"harvest_vs_stable_{scenario}", scenario, "coordinated-harvest-first",
        "coordinated-harvest-stable",
        "Retain feasible frontier ownership and reserve a busy resource during deposit.")

for scenario in ("default", "scarce", "short-horizon", "low-capacity"):
    add(f"harvest_vs_cargo_{scenario}", scenario, "coordinated-harvest-first",
        "coordinated-harvest-cargo",
        "Return partial gold when the incremental collection detour costs more than two turns per unit.")

for scenario in ("scarce", "short-horizon"):
    add(f"stable_vs_reliable_{scenario}", scenario, "coordinated-harvest-stable",
        "coordinated-harvest-reliable", "Isolate marginal cargo return after assignment stabilization.")

add("historical_vs_stable_full-info", "full-info", "coordinated", "coordinated-stable",
    "Test target ownership alone on the historical full-information loop.")

for scenario in ("limited-vision", "abundant", "iron-rich"):
    add(f"starter_vs_harvest_{scenario}", scenario, "starter", "coordinated-harvest-first",
        "Stress complete-bot ranking outside the four primary maps.")
    add(f"harvest_vs_reliable_{scenario}", scenario, "coordinated-harvest-first",
        "coordinated-harvest-reliable", "Stress both reliability rules outside the primary maps.")

EVIDENCE = ROOT / "mini_mars/docs/benchmarks/final-sprint-v1"


def run_stage(stage: str, names: list[str]) -> Path:
    seed, count = (72000, 20) if stage == "comparison" else (73000, 100)
    destination = EVIDENCE / f"{stage}.json"
    if destination.exists():
        raise FileExistsError(f"preserving existing evidence: {destination}")
    raw_root = RESULTS / "benchmarks" / "final-sprint-v1" / stage
    raw_root.mkdir(parents=True, exist_ok=True)
    rows = []
    first_report = None
    for name in names:
        case = CASES[name]
        _, _, scenario, a, b, _ = case
        folder = Path(tempfile.mkdtemp(prefix=name + "-", dir=raw_root))
        print(f"{stage}: {name}: {count} paired seeds", flush=True)
        report = run_tournament(a, b, count, seed, scenario=scenario, output_dir=folder)
        if first_report is None:
            first_report = report
        rows.append(compact(case, report, count, seed))
    evidence = {"format": "mini-mars-final-sprint-v1", "stage": stage,
                "python_version": sys.version.split()[0],
                "source_revision": first_report["source_revision"],
                "source_sha256": source_hashes(),
                "seed_sets": {"diagnostic": "64008, 67049, 69017, 69076",
                              "comparison": "72000-72019", "held_out": "73000-73099"},
                "bootstrap": "5000 deterministic percentile resamples by complete seed pair; RNG 20261021",
                "cases": rows}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("comparison", "validation"))
    parser.add_argument("--cases", nargs="+", choices=CASES)
    args = parser.parse_args()
    if args.stage == "validation" and not args.cases:
        parser.error("validation requires preselected --cases")
    print(run_stage(args.stage, args.cases or list(CASES)), flush=True)
