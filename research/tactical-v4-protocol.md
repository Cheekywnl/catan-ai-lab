# Tactical v4: use the observed resource tracker in autoplay

12 September 2026, 01:35 UTC. Protocol fixed before this candidate's held-out results.

The displayed tactical suggestion included the player's resource belief summary, while autoplay and the arena omitted it. An audit of 40 existing replays found 43 different top actions in 77 positions with a playable Monopoly. These positions share games and are diagnostic, not strength evidence. At seed4500 / revision177 / Blue, the tracker was exact and identified eight available wheat cards; autoplay chose wood from a production-based guess instead.

The candidate changes the observation boundary, without changing the scoring weights in `tactics.py` or the reference `policy.py`, `strategy.py`, and `opening.py`. The current `tactical` policy receives tracked resource estimates. `tactical_v3` retains the previous input without that summary. Displayed recommendations, autoplay and the arena use the same policy-specific information. Unavailable trackers retain the existing production fallback. No actual opponent hand is provided to either policy.

Validation before the tournament:210 native tests pass, including the captured exact-tracker position, eight actual wheat cards collected, agreement between the display/autoplay/arena, the frozen wood choice, and fallback behavior. Historical replay checksums and rules remain unchanged.

Held-out protocol:800 games on seeds 6500–6699, all four challenger seats per board, current Tactical v4 against three frozen `tactical_v3` opponents. Corrected base-game rules, real resource tracking, max4000 actions, four workers. Every game retains a replay, status, source manifest and diagnostics. The arena runs an immutable source copy. Report wins, all failures/truncations, seat results, whole-board bootstrap interval and elapsed time. The equal-policy reference is25%; do not discard failures or promote a strength claim from intermediate results.

This is a fixed policy-information correction, not a neural training run or an equilibrium solution. A better immediate resource estimate does not guarantee a higher game winning rate. The full result will determine what playing-strength claim, if any, is justified.

## Completed result — 01:43 UTC

All 800 games completed without errors or truncations. Tactical v4 won 215 (26.875%); the whole-board bootstrap interval is 25.25–28.50%, compared with the 25% equal-policy reference. This supports a modest improvement against the specified opponents and rules. Full settings, source hashes, seat results and every outcome are in [strength-v4.json](strength-v4.json). No seeds or settings changed after the protocol was fixed.

## Secondary opponent populations — fixed before their outcomes

To check performance against earlier baselines, run two separate fresh batches with the unchanged Tactical v4 policy and corrected rules:800 games on seeds 6700–6899 against three strategic-v2 opponents (four workers), and400 games on seeds 6900–6999 against three original-v1 opponents (two workers). Both use all four seats, actual resource tracking and max4000 actions. Report each population separately, including failures and whole-board intervals. These are additional measurements, not pooled confirmation of the v3 comparison.

## Secondary results and pause

Both fixed batches completed with zero errors/truncations:223/800 wins against strategic-v2 (27.875%; board interval26–29.75%), and205/400 against original-v1 (51.25%; interval46.25–56%). Full results: [v2](strength-v4-v2.json) and [v1](strength-v4-original.json). The user paused further work at02:01UTC; the policy and these completed results are retained.
