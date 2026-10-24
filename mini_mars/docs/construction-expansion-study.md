# Mini Mars construction and expansion study — 23 October 2026

These are results for the **invented Mini Mars practice rules**, not Lucid. The objective is banked gold. The compact [evidence file](benchmarks/construction-expansion-20261023/evidence.json) stores configuration, source hashes, paired seed differences, scores, behavior, faults, and latency for every completed report. Raw subprocess logs remain ignored under mini_mars/results/.

## Design and completed work

The expansion matrix contains 15×15, 30×30, and 50×50 maps; 100, 200, and 400 turns; costs of 4, 6, and 8 iron; and uniform or clustered resources. Deposit and rock counts scale with map area: 15×15 has 9 gold, 6 iron, and 8 rock **pairs**; 50×50 has 100, 67, and 89. Each map is connected, seeded, and rotationally symmetric. Both colonies start with the same rovers and banked iron. Swapped matches preserve bot identity seeds. A cluster map now uses exactly the same total gold and iron quantities as its uniform counterpart at a given seed; only placement changes. The original uniform map sequence is locked by a regression hash.

The runner accepts explicit size, duration, cost, layout, rover count, starting bank, baseline, candidate, and seed selections. Screening used development seeds 81000 or 82000. Held-out validation used fresh blocks beginning at 91000, 92000, 94000, and 95000; no validation seed was used to tune the planner. Every reported seed produced two swapped games. In total, **2,272 complete, clean games** appear in 17 completed reports (1,800 validation games and 472 screening/smoke games). Some exploratory reports repeat configurations and seeds, so 2,272 is an execution count, not an independent sample size. Two interrupted screens, stopped after code changes to avoid mixed-version evidence, are excluded. All completed reports have zero faulted matches and zero failed pairs.

The comparison that isolates construction is coordinated-planned-build versus coordinated-planned-no-build. Both use the same gold priority, stable targets, and other collection settings; the control has construction disabled. Coordinated-gold-only, historical coordinated heuristic building, historical payback building, and the scaled payback variant were also screened. A paired difference is candidate minus baseline gold, averaging the two player slots for each seed. The reported 95% intervals bootstrap whole seed pairs (5,000 fixed-seed resamples). Screening intervals with two to five seeds are descriptive only.

## Confirmed held-out findings

All rows below have **100 clean paired seeds / 200 games** each. “New-base gold” counts gold actually deposited at a constructed base, and “build turn” averages the turn of each successful build, weighted by builds. These are behavior measures, not estimates of the base's causal score contribution.

| Map / turns / cost / layout / starting iron | Seed block | Gold, no-build → planner | Planner gain, 95% paired interval | Bases per game; mean build turn | Iron mined; new-base gold per game |
| --- | ---: | ---: | ---: | ---: | ---: |
| 15×15 / 100 / 4 / uniform / 0 | 91000–91099 | 56.57 → 63.99 | **+7.42** [6.29, 8.59] | 1.99; 55.9 | 8.46; 40.37 |
| 15×15 / 100 / 4 / uniform / 4 | 91000–91099 | 56.16 → 69.00 | **+12.84** [11.51, 14.15] | 2.68; 41.4 | 7.55; 60.31 |
| 15×15 / 400 / 4 / uniform / 0 | 95000–95099 | 72.36 → 80.45 | **+8.09** [6.66, 9.54] | 2.90; 79.6 | 12.37; 54.13 |
| 50×50 / 100 / 4 / uniform / 0 | 95000–95099 | 55.10 → 64.52 | **+9.42** [8.14, 10.68] | 1.99; 57.4 | 8.56; 40.70 |
| 50×50 / 400 / 4 / uniform / 0 | 92000–92099 | 159.04 → 271.79 | **+112.75** [109.16, 116.28] | 9.97; 211.1 | 40.49; 248.35 |

The 50×50/400 result is a repeated Mini Mars result: 100 complete pairs, no faults, nearly ten builds per game, and most planner gold deposited at new bases. Only 20 of 1,994 built bases in those games received no gold delivery. The 15×15/100 funded validation had 10 unused bases among 535; the unfunded version had 8 among 397. Gold delivered there is not a counterfactual measure of value.

At cost four, the **five-seed same-seed factorial screen** gave planner gains of +4.8 (15×15/100), +9.0 (15×15/400), +9.2 (50×50/100), and +119.2 (50×50/400). The larger held-out runs above support the pattern: increasing either size or duration alone gave only a modest gain, while combining a large map and long horizon produced a much larger one. Because the held-out cells use different seed blocks, the exact size-by-duration interaction was not given its own paired interval. The five-seed factorial is the direct matched-seed comparison for that interaction.

## Iron price, layout, and starting resources

The following four cells use **the same 100 held-out seeds, 94000–94099**, with three rovers, 100 turns, and zero starting iron. Uniform and clustered maps have equal total gold and iron quantities for each seed. All pairs completed without faults.

| Cost / layout | Gold, no-build → planner | Planner gain, 95% paired interval | Bases; iron mined; new-base gold per game |
| --- | ---: | ---: | ---: |
| 4 / uniform | 56.34 → 64.82 | **+8.49** [7.18, 9.75] | 2.00; 8.48; 41.77 |
| 4 / clustered | 59.54 → 75.48 | **+15.94** [13.13, 18.81] | 1.17; 4.93; 46.56 |
| 8 / uniform | 56.79 → 57.43 | **+0.64** [−0.19, 1.49] | 0.73; 7.29; 14.81 |
| 8 / clustered | 59.79 → 70.14 | **+10.35** [8.31, 12.36] | 0.77; 6.52; 33.84 |

Comparing **per-seed planner gains** within this four-cell block, cost four beat cost eight by +7.85 [6.80, 8.98] gold on uniform maps and +5.59 [4.11, 7.19] on clustered maps. Clustering increased the planner's gain by +7.45 [4.53, 10.41] at cost four and +9.71 [7.62, 11.78] at cost eight. These contrast intervals use 5,000 seed-level bootstrap resamples with RNG seed 20261023; they are exploratory and not adjusted for multiple comparisons. Resource *placement* matters here. The current generator clusters both gold and iron, so this study does not isolate which resource's clustering drives the effect.

The initially funded control grants the same base cost to **both** players. On 15×15/100/cost-four uniform maps it raised the planner's held-out gain from +7.42 to +12.84 and moved successful builds earlier (mean turn 55.9 to 41.4). This separates the value of immediately available infrastructure from the time spent acquiring its iron. It does not mean free iron would be available in Lucid.

The 30×30/200/cost-six clustered **three-seed screen** gave +31.83 with three rovers and +73.33 with ten, both initially unfunded. With free starting iron those gains were +72.83 and +139.50. More rovers increased absolute gold scores for both bots; this small screen does not establish an optimal rover count or per-rover benefit. The ten-rover decisions averaged about 10–13 ms in these games and produced no timeout.

## Historical policies and the comparison trap

On 15×15/100/cost-four uniform maps, a five-seed screen against historical coordinated-gold-only gave these candidate gains (unfunded / initially funded): historical coordinated heuristic **−0.2 / +20.4**, payback **+0.1 / +7.5**, scaled payback **+0.1 / +7.5**, and the planner **+14.0 / +27.1**. The historical policies remain registered for comparison.

Those full-policy comparisons **do not isolate construction**. The planner also turns on gold priority and stable targets. In a two-seed 50×50/100 screen, gold-only averaged just 8 gold, while the matched no-build control averaged 67 and the planner 77.75 when initially unfunded. The planner's +69.75 gap to gold-only therefore mostly reflected collection-policy differences; the matched construction increment was +10.75 on those seeds. The matched no-build control was added before all held-out causal comparisons.

## Engineering findings and performance

- The initial suite failed because a 120-turn cutoff test used turn 80, already past the correctly scaled cutoff of 78, and tournament aggregation omitted new-base usage despite per-match telemetry. Both were corrected. Base usage now counts **gold** deliveries, and construction timing is aggregated.
- Validation previously accepted only a prefix of the 54-condition matrix. Explicit filters now select arbitrary cases and starting-bank controls. A matching no-build alias removes the collection-policy confound.
- The planner could begin an unfunded plan when all known accessible iron summed to less than the cost. It now rejects that plan until enough iron is known. A deterministic full lifecycle test covers remote gold discovery, iron mining and deposit, construction, delivery through the new base, and higher final banked gold; rejection cases are also tested.
- Profiled first decisions on fully visible 50×50 maps with ten rovers fell from a 548 ms median to 164 ms after sharing rover and base distance maps during site and iron evaluation (three repetitions before, five after). The final five-run maximum was 185 ms; the profiling process peaked at 25.8 MB resident memory. A cProfile run now attributes most first-turn cost to 45 BFS calls, coarse site ranking, and regular gold-task selection. In the 100-seed 50×50/400 validation, actual planner decisions averaged 3.90 ms and there were no simulated one-second timeouts. These profiles are local Python measurements, not official Lucid timing guarantees.
- The quantity-matching change affects clustered maps only. A regression locks the historical uniform-map hash; connectivity, rotational symmetry, equal resource totals, and old scenario behavior passed tests.

## Reproduce and interpret

    make test
    python3 -m mini_mars.runner.construction_study screen --size 15 --turns 100 --cost 4 --layout uniform --matches 5 --seed 81000 --output /tmp/construction-historical-screen.json
    python3 -m mini_mars.runner.construction_study validate --size 15 --turns 100 --cost 4 --layout uniform --candidate coordinated-planned-build --baseline coordinated-planned-no-build --matches 100 --seed 91000 --output /tmp/construction-short-validation.json
    python3 -m mini_mars.runner.construction_study validate --size 50 --turns 400 --cost 4 --layout uniform --candidate coordinated-planned-build --baseline coordinated-planned-no-build --bank 0 --matches 100 --seed 92000 --output /tmp/construction-large-validation.json
    python3 -m mini_mars.runner.construction_study validate --size 15 --turns 100 --cost 4 --cost 8 --layout uniform --layout clustered --candidate coordinated-planned-build --baseline coordinated-planned-no-build --bank 0 --matches 100 --seed 94000 --output /tmp/construction-price-layout-validation.json
    python3 -m mini_mars.runner.construction_study validate --size 15 --turns 400 --cost 4 --layout uniform --candidate coordinated-planned-build --baseline coordinated-planned-no-build --bank 0 --matches 100 --seed 95000 --output /tmp/construction-long-small-validation.json
    python3 -m mini_mars.runner.construction_study validate --size 50 --turns 100 --cost 4 --layout uniform --candidate coordinated-planned-build --baseline coordinated-planned-no-build --bank 0 --matches 100 --seed 95000 --output /tmp/construction-short-large-validation.json
    python3 -m mini_mars.runner.profile_decisions --repetitions 5 --output /tmp/construction-profile.json

No GitHub Actions workflows are configured for this research project; run the tests and experiments locally.

The tracked evidence includes all completed screen cases, including earlier code snapshots and repeated smoke configurations. Use its source hashes when comparing them. The original 100-seed uniform validations preceded the clustered quantity fix; the uniform-map regression demonstrates their physical maps are unchanged. Repeating a command with a new output path is required because the CLI will not overwrite a report.

**Strategic guidance for this invented economy:** build when a reachable, sufficiently rich remote region can support repeated deliveries before the deadline and iron can be acquired without consuming most of that payoff. A long horizon on a large map made repeated expansion exceptionally productive. On short uniform maps with eight-iron bases and no starting iron, the gain was indistinguishable from zero; prioritize bankable gold instead. Clustered placement and free initial iron shifted that boundary toward construction. These are tested Mini Mars conditions and hypotheses to check against official rules, not a recommendation to port this planner before a legal Lucid scoring match exists.
