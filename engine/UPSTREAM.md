# Engine provenance and changes

The rules core in `vendor/catanatron` is a vendored subset of [Catanatron](https://github.com/bcollazo/catanatron), revision `ecf931181b9a65bb4116a2153fb78c16f1438e00` (8 September 2026). It and the selected upstream tests are distributed under GPL-3.0-or-later; see LICENSE. Catan Lab engine additions are also GPL-3.0-or-later. Original authors retain their copyrights. The six upstream test modules have local test utilities imports; the Year of Plenty case is updated for the two-card rule below.

Local core changes for ruleset `catan-base-4p-2025-v1`:

- Victory is checked for the active turn owner, after setup. Actions after a win are rejected.
- Game and State copies clone their RNG state, so planning cannot alter actual dice and theft randomness.
- Trade offers require exactly ten nonnegative integer counts, nonempty and disjoint sides, and sufficient offered resources. Trades are disallowed during a Road Building resolution.
- Trade replies skip the proposer, including when the proposer is seated after the first respondent.
- The sole player affected by a resource shortage receives the remaining supply, as specified in the 2025 rulebook. With multiple recipients the deficient resource is not paid.
- Year of Plenty takes two cards when available; a one-card draw is offered only when one card remains in the entire supply. The 2025 card instruction says to take two, not up to two.

Ruleset `catan-base-4p-2025-v2` additionally fixes road endpoint counting, road traversal through opponent buildings, tied or unclaimed road awards, and removal of points when an award becomes unclaimed. `engine/road_rules.py` computes an exact longest edge trail and rebuilds the small public road caches. The original core branches are retained only for checksum-compatible historical replay execution. New boards default to revision 2; board copies and serialization preserve the revision. See the [official Longest Road FAQ](https://www.catan.com/faq/basegame).

Rule source: [CATAN 2025 rulebook](https://www.catan.com/sites/default/files/2025-03/CN3081%20CATAN%E2%80%93The%20Game%20Rulebook%20secure%20%281%29.pdf).

The package includes a 2025-style base board with the official spiral token placement, four players, 10 victory points, ordinary dice, robber/discards, domestic and maritime trades, all development cards, Longest Road, and Largest Army. Expansions and tournament variants are not enabled. Correctness is tested, not formally proved.

The browser executes this same Python package in a dedicated Pyodide module worker. The native runner is suitable for simulation and future training adapters. References: [Pyodide workers](https://pyodide.org/en/stable/usage/webworker.html), [package loading](https://pyodide.org/en/stable/usage/loading-packages.html).

Engine v0.2 adds an observation-only strategic policy and root Monte Carlo search through legal game continuations. It samples hidden cards and reconstructs the simulator from explicitly public board/phase fields. It never receives the real game's hidden state or random generator. Candidate screening, heuristic leaf values, and modeled opponent behavior make this an approximation, not equilibrium solving. Winning forecasts use full-game outcomes and withhold probabilities on truncated samples. Neither automated policy proactively proposes trades; both can respond to and confirm offers. Manual proposals remain supported.

Resource beliefs are joint weighted states until capacity is reached, then sampled. Hidden discards use an explicitly labeled random-card model. If samples lose support, conservative interval bounds replace probabilities. Monopoly forces every other player's requested resource to zero, and trade commitments tighten minimum counts. Unknown development cards use a labeled exchangeable-pool model after public plays and the observer's own cards; strategic retention is not modeled.

Replay exports are research artifacts: the seed and complete intents permit recovering hidden information. They are kept out of player observations and policy inputs. The source is a local research sandbox, not an anti-cheat boundary against a browser owner inspecting memory.
