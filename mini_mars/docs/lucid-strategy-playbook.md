# Lucid competition strategy playbook — Mini Mars practice evidence

Mini Mars is an **unofficial** practice game. Lucid has described rovers, iron, gold, bases, exploration, and competing colonies, but has not published scoring, visibility, action rules, or a bot API. The measured results below apply to our invented Mini Mars economy. Treat the practical ideas as hypotheses to test once Lucid publishes its real rules.

## Competition morning: what to do first

1. **Transferable idea:** Read the actual scoring and action rules before optimizing. Write down what earns points, when carried resources count, how bases pay back, and whether the map is hidden. Mini Mars awards only **banked gold**, gives a base an **8 banked iron** cost, and uses **100 turns**; those are **Mini Mars-dependent** details.
2. **Transferable idea:** Get one valid, deterministic bot and one complete local match working. Log seeds, version, bot faults, final scores, and action timing. A clever policy that times out or emits an invalid action is not a useful competition baseline.
3. **Transferable idea:** Assign multiple rovers to complementary targets when deposits can be depleted or contested. Compare distinct-target assignment with independent decisions using the **same** scorer and pathfinder; the Mini Mars paired evidence below tests exactly that change.
4. **Transferable idea:** If terrain or resources are hidden, spend some rover time revealing valuable unknown areas. If the official map is fully visible, that scouting incentive may be useless. The default versus full-info Mini Mars contrast below tests this boundary.
5. **Transferable idea:** Price mining and construction in expected *scored value per remaining turn*. Keep ore collection, return travel, cargo capacity, and the game horizon in the estimate. **Mini Mars-dependent:** iron itself scores zero, and its only planned use is a base; the results below do not establish the value of Lucid's iron.
6. **Transferable idea:** Evaluate on paired map seeds with player slots swapped, then validate on different seeds. Read win rate and paired score difference together. A short smoke run is for finding defects and leads, not declaring a champion.

## Strategies tested

| Bot | What it does | Controlled question |
| --- | --- | --- |
| `greedy` | Independent nearest known gold, iron fallback, BFS routes, frontier exploration; no construction | Existing baseline |
| `value` | Same policy, but ranks deposits by useful units per estimated outbound, mining, return, and deposit turns | Does value per turn improve target choice? |
| `independent` | Same bids, persistence, iron policy, and building as `coordinated`, but rovers may duplicate targets | Does distinct-target allocation help? |
| `coordinated` | Shared bids, distinct targets, frontier scoring, iron and optional base building | Reference coordinated policy |
| `coordinated-no-explore` | Same as `coordinated` with frontier bid weight zero | Does active exploration help? |
| `coordinated-gold-only` | Same as `coordinated` with iron bids and building disabled | Does iron/base investment pay back? |

All variants use BFS over known traversable cells. The coordinated family uses an outbound BFS distance, a Manhattan return-distance estimate, exploration weight `0.24`, prior-target multiplier `1.2`, early/late iron weights `0.65`/`0.05`, and visible-opponent multiplier `0.8`. These fixed numbers are practice heuristics, not Lucid recommendations.

## Results and evidence quality

The table uses **candidate minus baseline banked gold per swapped seed pair**. Positive favors the candidate. Brackets are paired-bootstrap 95% intervals in gold units. Every smoke cell uses **20 pairs / 40 games** from the committed [smoke report](benchmarks/issue-1/smoke.json); every validation cell uses **100 disjoint pairs / 200 games** from the committed [validation report](benchmarks/issue-1/validation.json). “Smoke only” means the result has weaker evidence and was not promoted to the larger set.

| Scenario | Baseline → candidate | Smoke: gold difference [95% interval] | Validation: gold difference [95% interval]; candidate win rate |
| --- | --- | ---: | ---: |
| Default | `greedy → value` | −0.40 [−1.73, +0.93] | Smoke only |
| Default | `independent → coordinated` | +23.45 [+20.38, +26.38] | **+22.30 [+20.89, +23.68]; 100%** |
| Default | `coordinated-no-explore → coordinated` | +43.65 [+42.00, +45.27] | **+42.83 [+41.72, +43.95]; 100%** |
| Default | `coordinated-gold-only → coordinated` | −1.25 [−2.33, −0.38] | Smoke only |
| Full info | `greedy → value` | +0.40 [−1.35, +2.12] | Smoke only |
| Full info | `independent → coordinated` | +9.00 [+6.55, +11.57] | **+8.55 [+7.06, +10.07]; 85.5%** |
| Full info | `coordinated-no-explore → coordinated` | 0.00 [0.00, 0.00] | Smoke only; visibility control |
| Scarce | `greedy → value` | −0.12 [−0.60, +0.40] | **+0.03 [−0.57, +0.64]; 51.5%** |
| Scarce | `coordinated-gold-only → coordinated` | −1.32 [−2.60, −0.33] | **−0.64 [−1.10, −0.18]; 44.0%** |
| Obstacle heavy | `independent → coordinated` | +27.62 [+23.93, +31.33] | Smoke only |
| Obstacle heavy | `coordinated-no-explore → coordinated` | +41.92 [+38.87, +44.67] | **+39.90 [+38.92, +40.84]; 100%** |

The win rates count each game, with ties worth half a win; the score intervals resample whole **seed pairs**. All **440 smoke games** and **1,200 validation games** finished with zero invalid actions, timeouts, crashes, or incomplete pairs. Validation decision latency averaged about **1.8–6.6 ms** per response across these bots, including process and JSON overhead; it is not pure algorithm time.

### Lessons to carry forward

- **Transferable idea — coordinated allocation:** With identical bids and routes, reserving distinct targets beat independent assignment by **22.30 gold per pair** in default Mini Mars and **8.55** with full information on disjoint validation seeds. The obstacle-heavy smoke result also favored coordination, but lacks 100-seed validation. Start with a clear assignment policy when several rovers can duplicate or exhaust the same work.
- **Transferable idea, conditional on hidden information — explore deliberately:** Frontier bids beat no frontier bids by **42.83 gold** in default and **39.90** with heavy obstacles. In the full-info control, both policies had exactly the same paired mean score. **Mini Mars-dependent:** the size of this effect comes from our radius-two fog, map size, deposit layout, and 100-turn horizon. Check Lucid's actual visibility rule before allocating scouting effort.
- **Mini Mars-dependent — iron/base investment:** In scarce maps, the combined iron-and-base policy scored **0.64 less gold per pair** than gold-only, with a validation interval below zero. The default 20-pair smoke test pointed the same way. This tests a *package* of iron targeting and base building; it does not isolate whether mining iron, where bases were built, or the eight-iron cost caused the shortfall. Do not translate it into a claim about Lucid's iron.
- **Transferable idea — estimate delivered value per turn, then test it:** The `value` variant changes only greedy's deposit ranking. On scarce validation seeds its difference was **+0.03 gold per pair**, with an interval spanning zero; default and full-info smoke results also span zero. This implementation has no demonstrated advantage here. Allocation and information gathering mattered more in this fixed simulator; a different scoring economy may change that.
- **Transferable idea — keep pathfinding comparisons separate:** All tested policies use the same BFS. These reports say nothing about A*, Dijkstra, caching, collision avoidance, or language performance. Change one of those separately after Lucid's map and action rules are known.

## How the evidence was made

The smoke matrix used **20 seeds, 10000–10019**, in both player slots for each of 11 focused comparisons across default, full-info, scarce-resource, and obstacle-heavy scenarios. The disjoint validation set uses **100 seeds, 20000–20099**, in both slots for four primary comparisons plus up to two chosen by a fixed smoke-result rule: closest paired score difference and largest positive candidate gain. The full-info exploration control is excluded from promotion. A game failure invalidates its whole seed pair. Each reported 95% interval uses **5000 deterministic bootstrap resamples of seed pairs**, not individual games. Bot decision latency includes process and JSON overhead.

For the same seed, `default` and `full-info` have the identical physical map and starting positions. Full-info updates all cells and enemy positions each turn. Scarce has **5 gold and 3 iron pairs** instead of 9 and 6. Obstacle-heavy has **20 rock pairs** instead of 8 while retaining connected open terrain. Each scenario is symmetric between starting players; symmetry does not model whatever fairness Lucid may choose.

Run the saved protocol and matrix again from the repository root:

```sh
make test
python3 -m mini_mars match --scenario default --bot-a greedy --bot-b coordinated --seed 42
python3 -m mini_mars tournament --scenario default --bot-a independent --bot-b coordinated --matches 20 --seed 10000
python3 -m mini_mars.runner.benchmark smoke
python3 -m mini_mars.runner.benchmark validate
```

The matrix commands save detailed tournament outputs and representative replays under ignored `mini_mars/results/`. The compact [smoke](benchmarks/issue-1/smoke.json) and [validation](benchmarks/issue-1/validation.json) JSON files are versioned evidence. Each case records its exact standalone tournament command, scenario config, source hashes, paired counts, scores, uncertainty, faults, and latency. Reproduce a case from its recorded command; `--save-replays` retains every tournament replay if needed, while the matrix normally saves only a few verified examples.

The recorded environment was **Python 3.12.3**, source Git HEAD **`4232e2ca903ab82d6092549bf7a5aaaca0c23022`**, with `git_dirty=true` while the implementation was being prepared. The reports contain SHA-256 hashes of every relevant Mini Mars source file, so the exact measured code can be identified despite the dirty working tree. The validation report records three locally saved, score-checked replay examples: a candidate win (default seed 20014), a candidate loss (scarce seed 20046), and a tie (full-info seed 20000, swapped). Those large replay files remain ignored; their seed and player-slot details are in the JSON for recreation.
