# Five-hour refinement window

Requested 11 September 2026, 23:58 UTC. Stop starting experiments at **12 September 2026, 04:58 UTC** and finish the bounded release/report. Thread heartbeat `refine-catan-engine-for-five-hours` checks every 15 minutes; pause it after the final report. Its final permitted check is just after the deadline to allow wrap-up.

## Starting point

- Published source: `b5ac0c797e6ac69b370f164ed94641f97f9d430e`, engine 0.2.0, private Site version 3.
- Fast strategic-v2: 85/200 wins against three frozen v1 bots on seeds 2000–2049, four seats per board. Board-bootstrap interval 35–50%.
- Search strength is unmeasured. Its browser default is 12 requested root continuations (at least two per candidate), horizon 1600, four initial candidates with action-type diversification.
- 158 native tests, 20 browser checks, six content checks passed before this work window.

## Experiment discipline

Preserve `policy.py`, `strategy.py`, and `opening.py` as the v1/v2 reference policies. Put candidate policy changes in a new module until validation. Keep tuning boards and final evaluation boards separate. Do not label short or adaptively selected experiments as confirmed strength improvements. Keep errors and truncated games visible. Every run has a settings/source manifest, incremental results, full replays, and periodic progress files. Do not edit engine source used by an active tournament; the runner rejects a changed version rather than mixing policies.

## Queue

1. Measure current search against strategic-v2; inspect errors, weak choices, runtime, and sample variance.
2. Stress legal play and hidden-world reconstruction across more games. Turn any reproducible defect into a regression test.
3. Use diagnostics to choose a bounded improvement (search allocation, tactical winning actions, robber targets, development-card timing, or expansion economics).
4. Compare candidates against frozen v2 and original v1 on fresh seat-balanced boards. Validate retained changes and publish results in the existing website/repository.

## First cycle: observations and fixes

- Completed 400 further v2 games on seeds 3100–3199, all four seats. Strategic-v2 won 176 (44%); board-bootstrap interval 38.75–49.25%. No real-game errors or truncations. This uses the original road rules and is historical evidence only.
- Offline review of 287 completed games found eight decision positions in losing games where a legal road would have won immediately. The policy chose a different move. This motivated exact award and immediate-win calculations.
- Stopped the initial search batch after eight recorded games: seven completed, one errored. The error occurred at seed 3000 / seat 3 / action 280. A joint resource particle exceeded the bank's 19-card supply, producing a negative sampled bank and a failed maritime trade. Saved the complete reproducing replay as a regression fixture. The remaining games were intentionally aborted; this batch is not a strength estimate.
- Comparing a new public-board trail calculator against recorded positions exposed the existing rules core dropping roads ending at rival settlements. The related award code also mishandled tied or unclaimed awards. The [official CATAN FAQ](https://www.catan.com/faq/basegame) specifies endpoint interruption, incumbent ties, and unclaimed awards.
- Engine 0.3 corrects those rules, conserves finite resources in the belief/simulation boundary, and adds Tactical v3 over unchanged v2 economy code. New games use road-rule revision 2. Historical replay execution preserves revision 1 and is labeled in the website.
- All 176 native tests pass, including a captured failure, road endpoints/loops/branches, award removal, an immediate army win, and predicted tactical point changes compared with actual legal game transitions.
- The new arena runs each batch from an immutable copy of engine source. Future edits cannot alter a tournament in progress. It retains manifests, per-game checkpoints, replays, errors, and board-cluster uncertainty.

## First completed validation and ongoing experiments

- **Tactical v3 versus three frozen strategic-v2 players:** 800 games, seeds 4200–4399, all four seats, corrected rules and actual resource-belief tracking. This is a fresh validation set, separate from the losses used to identify the defect. Directory: `../../work/experiments/tactical-v3-4200`. Initial process PID 29860. **Complete: 222/800 wins (27.75%), 800 completed, zero errors/truncations. Board-bootstrap interval 26.125–29.50%.** Full results and source hashes are in `strength-v3.json`. The tournament recovered from a Windows file-sharing lock at game 796 by resuming its frozen snapshot; game results were retained. The main runner now retries transient checkpoint locks, with a regression test. That orchestration-only fix changes `arena.py` from the benchmark snapshot but leaves its policies and rules unchanged.
- **Corrected search reproduction batch:** 20 games, seeds 3000–3004, same search settings as the interrupted experiment, corrected rules and supply constraints. This reuses debugging seeds and is a correctness/reproduction check, not held-out acceptance evidence. Directory: `../../work/experiments/search-v3-repair-3000`. Initial process PID 24472.
- **Next:** inspect corrected-search outcomes and remaining failures, then measure search on fresh boards. Investigate allocation noise at only two or three full-game samples per candidate. Also inspect whether using tracked beliefs in fast Monopoly/robber choices improves decisions; keep the v2 reference modules unchanged.

## Handoff for later heartbeat runs

Inspect this log, `../../work/experiments/*/summary.json`, `manifest.json`, and `progress/` before launching more games. Resume only with identical engine hashes/settings. Review git status and active processes so an ongoing batch is not duplicated. The existing Site project is `appgprj_6aa466c08f78819185050189fb37433f`; preserve owner-only access. Publish through native Sites tools from the exact pushed commit. Never expose temporary source credentials.

## Next-cycle priorities

The 20-game corrected-search batch remains active from its immutable source snapshot. Inspect its stdout log and final summary before launching a duplicate. If a transient checkpoint lock interrupts this older snapshot, resume from its `source` directory using the original arguments and `--worker-snapshot`. Future arena runs include the retry fix. Investigate root sampling noise and profile full-game continuations: skipping heuristic ranking when there is exactly one legal move should preserve every chosen action and may reduce latency. Validate any speed optimization against fixed-seed search outputs before claiming equivalence. Keep new experiments separate from seeds 3000–3004 (debugging), 3100–3199 (old-rule validation), 4000 (smoke), and 4200–4399 (v3 validation).

## Second cycle — 00:44 UTC

- The corrected search batch is now **complete: 20 games, 7 wins, zero errors/truncations**, 11,520 terminal continuations and 1,867,605 simulated actions. It reused debugging boards; its 15–60% board-bootstrap interval is too wide to infer competitive strength. Full report: `search-repair-v3.json`.
- Tactical v3 versus three original bots under corrected rules is **complete: 193/400 wins (48.25%)**, zero errors/truncations, interval 43.25–53.50%. Seeds 4500–4599. Full report: `strength-v3-original.json`.
- Profiling located the main cost in repeated mean-flow affordability calculations. `fast_policy.py` uses a piecewise-linear crossing plus exact reference-grid verification, a bounded memoization cache, and a forced-action shortcut. `policy.py`, `strategy.py`, and `opening.py` remain unchanged.
- The optimized policy matched all ranked actions/scores in eight full games, 10,000 randomized resource cases and boundary tests, and identical search outputs. All 188 native tests pass. Six-position, unprofiled timing: aggregate 3.77× faster; median 3.85×; 2.46–4.09× range. Report: `speed-v3.json`. This measures local runtime only.
- **Active matched search-budget trials:** each arm has 100 games, seeds 5500–5524, all seats, opponents strategic-v2, tracking on, horizon 1600, max initial candidates 4. Directories `../../work/experiments/search12-v031-5500` (budget 12, initial PID 25352) and `../../work/experiments/search48-v031-5500` (budget 48, initial PID 22876). Four workers per arm. Both execute immutable source snapshots. Wait for complete results; compare paired board outcomes and runtime without treating intermediate rates as final.
- Seeds 5200–5207 were used for equivalence tests and must not be treated as fresh strength evaluation. The six timing positions use seeds 42, 17, 71, 86, and 91.
- A matched Tactical v3 control uses the same 25 boards and four seats, three strategic-v2 opponents, and actual belief tracking. It was added after the search arms started, before their final outcomes, without changing or selecting boards. Directory `../../work/experiments/tactical-control-v031-5500`, initial PID 29304. It completed all 100 games with 26 wins and zero errors/truncations. Retain this small control for paired comparisons after both search arms finish; it is not a replacement for the larger tactical validation.
- Browser validation completed successfully: 20 passing tests, with two desktop-only checks intentionally skipped on mobile. Six content checks also passed.
- While those trials run, investigate the next bounded improvement independently: belief-aware robber/Monopoly decisions, root sampling variance, or value-estimate calibration. Keep the baselines and active experiment snapshots unchanged. Stop starting new experiments at 04:58 UTC.
