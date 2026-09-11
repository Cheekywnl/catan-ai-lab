# Catan Lab engine — implementation log

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
