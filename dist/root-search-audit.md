# Root search repeatability audit

12 September 2026. Engine 0.3.2 source snapshot; this is a tuning diagnostic, not a game-strength test.

Eleven eligible positions came from a fixed schedule on seeds 6400–6411: alternating opening, first playable decision at or after 100 actions, and at or after 220 actions. Seed 6408 ended before its scheduled position and is explicitly excluded. No position was selected based on whether search appeared good or bad. Existing tactical play generated positions with real resource trackers.

Each position was searched six times at budget 12 and six at budget 48 with separate search seeds, horizon 1600, and four initial candidates plus the existing action-type diversification. Independent reference simulations allocated 64 continuations to every screened candidate:43 candidate actions,2,752 reference continuations. The 132 search calls used 3,960 continuations. Reference estimates use the same frozen continuation-opponent model and have sampling error; they are not ground truth or human-opponent values.

| Diagnostic, averaged over positions | Budget 12 | Budget 48 |
| --- | ---: | ---: |
| Share choosing that position's most frequent recommendation |57.6%|54.5%|
| Share choosing the fast Tactical action |51.5%|27.3%|
| Selected action's independent reference score minus Tactical's |+0.0227|+0.0282|
| Reported score minus independent reference score for the selected action |+0.1186|+0.0509|

Recommendations vary across runs. More simulations reduced the reported-score optimism in this small set, but did not clearly stabilize the identity of the selected move. Different moves can have similar modeled values, so disagreement alone does not establish bad play. The positive independent-reference differences are small relative to the limited reference samples. Do not infer a winning-rate improvement from these diagnostics. All raw position results, seeds, settings, exclusions and source hashes are in [root-variance-v032.json](root-variance-v032.json). Reproduce with `scripts/audit-root-search.py` and the named frozen engine source.

The next algorithm experiment should target reliable final move selection, while preserving the existing search for comparison. [MCTS Based on Simple Regret](https://ojs.aaai.org/index.php/AAAI/article/view/8126) explains why the objective of the final chosen move differs from collecting rewards during sampling. [Sequential Halving applied to Trees](https://www.lamsade.dauphine.fr/~cazenave/papers/shot.pdf) allocates a fixed budget in rounds and eliminates less promising moves; its results in another game are motivation, not evidence of a Catan benefit. [Monte-Carlo Tree Search by Best Arm Identification](https://proceedings.neurips.cc/paper/2017/hash/a6d259bfbfa2062843ef543e21d7ec8e-Abstract.html) provides a related perspective on root choice. None of these new allocation methods is implemented by this audit.
