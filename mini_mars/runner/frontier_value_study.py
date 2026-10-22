"""Test per-frontier scoring after gold priority; keep earlier studies intact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .match import RESULTS, ROOT, source_hashes
from .research_loop import compact
from .tournament import run_tournament


SCENARIOS = ("default", "obstacle-heavy", "scarce", "short-horizon")
CASES = {
    f"frontier_value_{scenario}":
    (f"frontier_value_{scenario}", 8, scenario,
     "coordinated-harvest-first", "coordinated-harvest-scored",
     "Per-frontier values may reduce target switching after gold-first assignment.")
    for scenario in SCENARIOS
}
EVIDENCE = ROOT / "mini_mars/docs/benchmarks/frontier-value"


def run_stage(stage: str, names: list[str]) -> Path:
    seed, count = (68000, 20) if stage == "comparison" else (69000, 100)
    raw_root = RESULTS / "benchmarks" / "frontier-value" / stage
    raw_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        case = CASES[name]
        _, _, scenario, a, b, _ = case
        folder = Path(tempfile.mkdtemp(prefix=name + "-", dir=raw_root))
        print(f"{stage}: {name}: {count} paired seeds", flush=True)
        report = run_tournament(a, b, count, seed, scenario=scenario, output_dir=folder)
        rows.append(compact(case, report, count, seed))
    evidence = {"format": "mini-mars-frontier-value-v1", "stage": stage,
                "python_version": sys.version.split()[0],
                "source_revision": report["source_revision"], "source_sha256": source_hashes(),
                "seed_sets": {"diagnostic": "67049", "comparison": "68000-68019",
                              "held_out": "69000-69099"},
                "bootstrap": "5000 deterministic percentile resamples by complete seed pair; RNG 20261021",
                "cases": rows}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / f"{stage}.json"
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("comparison", "validation"))
    parser.add_argument("--cases", nargs="+", choices=CASES)
    args = parser.parse_args()
    if args.stage == "validation" and not args.cases:
        parser.error("validation requires an explicit preselected --cases list")
    print(run_stage(args.stage, args.cases or list(CASES)), flush=True)
