# Catan Lab engine — implementation log

## Engine 0.3.1 — faster equivalent continuations

The resource-affordability estimate is a monotone piecewise-linear function. The optimized adapter solves its crossing analytically, then verifies the same 120/512-roll grid and 1e-9 tolerance used by the frozen policy. A bounded cache avoids repeated identical calculations. Forced decisions skip ranking. The reference policy modules remain unchanged; the adapter binds their functions to separate globals instead of mutating them or maintaining another scoring implementation.

Across six fixed positions, alternating reference/optimized run order and clearing the cache before each run, full-game search was **3.77× faster in aggregate** (median **3.85×**, individual range **2.46–4.09×**). All candidate scores, choices, sample counts, and simulated transitions matched exactly after excluding elapsed time. This is a local runtime measurement, not a playing-strength claim. Reproduce it with `python scripts/benchmark-search.py`; full timings and hashes are in [speed-v3.json](speed-v3.json).

All **188 native tests** pass. New cases compare 10,000 varied resource states, grid-boundary cases, every ranked action through eight complete games, and fixed-seed search outputs. Browser validation covers the Python adapter running in the deployed runtime.

The corrected search reproduction batch completed **20/20 games**, with **7 wins**, no errors, and 11,520 terminal continuations. These debugging seeds give a wide 15–60% board-bootstrap interval and do not establish search strength. Tactical v3 separately completed **400/400 fresh games against three original v1 bots**, winning **193 (48.25%)**, interval **43.25–53.50%**, under corrected rules. These are separate opponent populations and must not be combined with its 27.75% result against strategic-v2.

Two fresh, preregistered search-budget batches now compare 12 versus 48 requested continuations per decision on seeds 5500–5524, all four seats, against three strategic-v2 opponents. Both use the same corrected rules, resource tracking, horizon 1600, and four initial candidates. Outcomes will be compared by board, with failures and runtime retained. No budget is promoted before those results are reviewed.

A Tactical v3 control was added on the same boards before the search arms finished. It completed 100 games with 26 wins and no errors or truncations. The matched comparison will be reported when both search arms complete. The release passed 20 browser tests and six content checks; two desktop-only browser checks are intentionally skipped on mobile.

## Engine 0.3 — refinement window, 12 September 2026

Repeated play found two correctness defects and missed immediate wins. New games now use `catan-base-4p-2025-v2`: a road ending at an opponent's settlement counts toward its length, while traversal stops at that settlement. Road awards retain an eligible incumbent on ties, transfer to a unique eligible leader, and become unclaimed when nobody qualifies. Losing an unclaimed award removes its two points. These cases follow the [official CATAN FAQ](https://www.catan.com/faq/basegame).

The new tactical policy layers exact public-board award calculations over the frozen v2 economy. It prioritizes immediate wins from settlements, cities, Longest Road, and Largest Army. Root search includes this tactical screening; its continuation opponents still use strategic-v2. Sampled resource worlds now enforce the 19-card supply for every resource, fixing a captured search failure caused by a negative sampled bank.

Historical 0.1/0.2 replays retain their original road rules, checksums, and exports. They are explicitly marked in the interface. New games and their sampled continuations use the corrected rules. The new rules do not rewrite historical benchmark claims.

The suite now passes 176 native tests, including the captured failing replay, finite-supply sampling, road endpoint/loop/branch cases, award ties and removal, guaranteed army wins, and tactical predictions compared with legal actions in complete games. The tournament runner saves settings, normalized source hashes, periodic progress, results, and replays. It executes a frozen source snapshot, so later edits cannot change an experiment in progress.

An additional 400 games under the previous rules completed without real-game errors: strategic-v2 won 176 (44%) against three original bots; the board-bootstrap interval is 38.75–49.25%. The initial search tournament was stopped after discovering a sampler error: eight recorded games, seven completed, one error. Its incomplete results are not a strength estimate. Current experiments and results are recorded in [refinement-log.md](refinement-log.md) and [strength-v3.json](strength-v3.json).

Tactical v3 completed its fresh 800-game validation against three frozen strategic-v2 players: **222 wins (27.75%)**, board-bootstrap interval **26.125–29.50%**, zero errors or truncations. All players used corrected rule revision 2. The 25% equal-policy reference lies below this interval. The change is retained on this evidence and the immediate-win regressions; this does not measure search strength or human performance.

## Engine 0.2 — 12 September 2026

The new strategic policy evaluates resource plans, reachable road destinations, exact opening pips and dice coverage, second-settlement cards, actual port conversion rates, and snake-draft order. The browser exposes an opening audit, resource plans, turn-order exposure, and development-card probabilities.

The decision laboratory now reconstructs sampled hidden worlds from player observations and compares legal continuations with adaptive root Monte Carlo search. Quick search uses bounded heuristic leaf scores. Win-objective search attempts full games and labels winning rates only when all samples finish. The separate forecast control returns each player's modeled winning frequency with sampling intervals, or censoring bounds when continuations truncate. Every simulated player receives only its own observation.

Autoplay can use the original baseline, the faster strategic policy, or experimental win-search. The latter starts with 12 full-game attempts per decision, increasing that minimum when needed to sample every screened candidate twice. It can be slow; manual analysis provides additional budgets. Search is screened and approximate, not a certified GTO solution. No neural model is trained.

The final fast strategic policy won 85/200 games against three original bots, across all seats on 50 held-out boards. The board-bootstrap interval is 35–50%. All 200 games completed. This is evidence about the strategic policy against that opponent; search strength has not yet been established. Source hashes and every game result are published in `strength-v2.json`.

The 158 passing Python tests include regressions for sampled-world reconstruction, hidden-information independence, immediate winning moves, port economics, opening order, dice exposure, development beliefs, truncated forecasts, and old replay compatibility. Full derivations, assumptions, and limitations are in [solver-mathematics.md](solver-mathematics.md).

## Historical engine 0.1 release

11 September 2026. The original research report remains a dated research snapshot; this log records the implementation that followed it.

## What is working

- **Four-player base game.** Seeded board and spiral number-token setup, the eight-settlement snake draft and its roads, dice and production, robber and private theft, discard decisions, settlements, roads and cities, all five development-card types, maritime and player trades, Longest Road, Largest Army, and victory on the player's own turn.
- **A playable browser interface.** Select highlighted legal locations or use the move list. View your own cards and other players' public information; switch viewpoints for research. Step the bot, run batches or complete games, compare opening drafts, propose trades, undo, and import/export a replay. Python runs inside a dedicated browser worker so simulations do not occupy the UI thread.
- **A native simulator.** The browser and Python CLI execute the same rules source. Source, dependencies, ruleset, random seed, action history, and replay checksum are versioned. The native CLI can export observation/action/outcome JSONL for future imitation-learning experiments.
- **Resource tracking from observations.** Joint states retain correlations after hidden thefts; public production and spending constrain those possibilities. The display distinguishes exact enumeration, a model of hidden discards, sampled states, and conservative interval fallback. Own-hand observations and public hand totals condition the tracker.
- **An observation-only baseline.** Resource production, diversity, ore/wheat balance, build availability, expansion, public robber targets, and resource exchanges determine heuristic scores. Policy functions never receive the authoritative game state, opponent hands, deck order, or RNG seed.
- **Opening Monte Carlo evaluation.** Up to ten candidates are compared against sampled remaining settlement drafts. The displayed objective is final resource economy, with Monte Carlo standard error. It is not a win probability. Roads, full-game continuation, strategic negotiation, and learned opponent behavior are outside this initial search.

## Core audit and local corrections

The project vendors the GPL-3.0-or-later Catanatron rules core at revision `ecf931181b9a65bb4116a2153fb78c16f1438e00`. Engine additions use the same license. The source download includes the complete local engine, upstream notices, tests, and NetworkX source. Detailed provenance and local modifications are in `engine/UPSTREAM.md` in the repository and source archive.

Six areas were corrected: victory timing and post-game moves; independent random-number generators in game/state copies; malformed, unaffordable, and out-of-phase trade offers; trade response order; single-recipient resource shortages; and Year of Plenty drawing two cards when two are available. Rules target the [2025 official base-game rulebook](https://www.catan.com/sites/default/files/2025-03/CN3081%20CATAN%E2%80%93The%20Game%20Rulebook%20secure%20%281%29.pdf) and [official FAQ](https://www.catan.com/faq/basegame). The Year of Plenty interpretation follows the instruction to take two, with a single-card exception only when the entire supply has one card remaining.

## Evidence and how to reproduce it

**126 Python tests** pass: 73 selected upstream tests (with the documented Year of Plenty expectation updated) and 53 local cases. Coverage includes topology and setup order, road behavior, malformed and valid trades, resource shortages, development timing, private observations, replay and clone independence, stale-action rejection, correlated theft probabilities, conservative bounds, ports, Largest Army, and complete games.

**100/100 native games completed**, seeds 0–99, four copies of the same heuristic policy, with no truncations. Each transition checks conservation of all 95 resource cards, 25 development cards, and player piece inventories. The downloadable `engine-validation.json` records every seed, winner, action count, and final checksum, plus measured runtime and environment. These are completion and consistency checks. They do not establish competitive strength or rule completeness.

Browser regression tests cover legal placement, draft comparison, undo, a game played to completion, switching views, native-to-browser replay identity, rejected corrupt imports, local-only runtime requests, accessibility checks, and narrow-screen layout. The existing research-reader tests run alongside them. Chromium desktop and mobile emulation are covered; other browser engines have not been certified.

```sh
python -m venv .venv
# Activate .venv using the command for your shell.
pip install -r engine/requirements.txt
python -m pytest -q
python -m engine.simulate --games 100 --output research/engine-validation.json
python -m engine.simulate --games 5 --trajectories work/teacher.jsonl
npm ci
python scripts/build-engine.py
npx playwright install chromium
npm test
npm run test:browser
npm start
```

Open `http://127.0.0.1:4173/#engine`. Node.js 22 and native Python 3.12 are the tested setup. The bundled Pyodide release supplies browser Python. GitHub Actions reruns Python and browser tests and checks that the committed browser engine matches its source.

## Limits and next engineering work

This is a functioning engine foundation, not a solved strategy or a trained GTO agent. No neural network has been trained and no historical human-game dataset has been imported. The baseline has not been tested against strong external opponents. It responds to offers but does not initiate them; manual proposals are supported.

Hidden discards are strategic choices, so their probabilities depend on an imperfect model. Particle depletion can trigger bounds-only display; this is explicit, and the UI does not invent expected values. Development-card identities stay private, but their probabilistic tracker is not yet built. Arbitrary board editing and ingestion of outside game events are also pending.

Replay files intentionally contain the seed and complete intents, which recover hidden information. They are research artifacts, separate from player observations. A browser owner can inspect their own worker memory; this local sandbox is not an adversarial multiplayer server.

Next priorities are an independent rules conformance suite with larger randomized action coverage; calibrated beliefs on held-out histories; full-game, belief-aware root search with observation-correct opponent policies; a frozen opponent evaluation suite with all seat rotations; and only then imitation learning and self-play with measured gains. Training-data splits must be by whole games and board seeds. Heuristic teacher data provides a bootstrap, not evidence of expert decisions.

The private GitHub repository is [Cheekywnl/catan-ai-lab](https://github.com/Cheekywnl/catan-ai-lab). This is an independent project, unaffiliated with CATAN GmbH.
