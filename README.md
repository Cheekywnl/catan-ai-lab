# Catan Research Lab

A playable four-player Catan engine with hidden-card beliefs, turn-aware opening economics, continuation search, and winning forecasts. The same Python engine runs natively and in a browser worker. Open [Play & simulate](https://catan-research-lab-cheekywnl.founders622811.chatgpt.site/#engine).

Engine 0.4's current Tactical v4 policy consistently uses tracked resource cards in displayed suggestions and autoplay. It won **215/800 games (26.875%)** against three frozen Tactical-v3 opponents on fresh seat-balanced boards, with no errors/truncations; whole-board bootstrap interval **25.25–28.50%**. This is a modest gain against that population. [Results](research/strength-v4.json), [information-use audit](research/policy-observation-v4.json), [search-repeatability audit](research/root-search-audit.md). All 210 native tests and 24 browser checks pass. Old policies remain selectable; search remains experimental.

**Paused at the user's request on 12 September 2026.** Scheduled work and game workers are stopped. Tactical v4 also completed **223/800 wins against v2** and **205/400 against v1**, with no errors/truncations. The larger search trial is preserved at 62/100 games with a portable checkpoint. See the [progress report and resume instructions](research/progress-2026-09-12.md).

Engine 0.3's Tactical v3 won **222/800 games (27.75%)** against three frozen strategic-v2 opponents on fresh seat-balanced boards, with no errors or truncations; the board-bootstrap 95% interval is **26.125–29.50%**. See [results](research/strength-v3.json).

Engine 0.3.1 accelerates equivalent full-game continuations: **3.77× aggregate local speedup** across six fixed positions, with identical search results. It also records a second opponent test: Tactical v3 won **193/400 (48.25%)** against original v1 bots under corrected rules. See [timings](research/speed-v3.json) and [opponent results](research/strength-v3-original.json). Larger search-budget trials are in progress.

## Implemented

Engine 0.3.2 conditions hidden development cards on public completed turns and purchase ages. It fixes seven contradictory positions found in a 40-game replay audit and exposes hidden VP ranges in the website. All 203 native tests pass; [audit and provenance](research/development-history-v032.json).

- Legal full games with setup, production, robber/discards, building, development cards, ports, player trades, awards, and victory.
- Interactive SVG board, legal-action selection, manual trading, bot simulation, viewpoints, undo, and deterministic replay import/export.
- Joint resource beliefs with explicit exact, modeled, sampled, and conservative-bound states.
- Strategic policy with resource plans, reachable road destinations, and port conversion economics.
- Tactical v3 checks immediate building and award wins, with corrected road endpoints, blocking, and award ties.
- Exact opening pips, dice coverage, starting cards, and snake-draft order shown in the interface.
- Belief-aware root Monte Carlo search through legal continuations, including full-game attempts.
- Winning forecasts with sampling intervals; fixed-board resource probabilities before the next turn; exchangeable-model development-card estimates.
- Native simulation and observation/action/outcome JSONL export for future training.
- Twelve research chapters, 37 sources, project comparison, architecture, roadmap, search, and an exact theft-probability explainer.

Engine 0.2's fast strategic policy won **85/200 games (42.5%)** against three original bots on 50 held-out boards across all seats; the board-bootstrap 95% interval is 35–50%. This measures that policy against our baseline, not human or equilibrium strength. **No neural training, full information-set tree, or GTO guarantee is claimed.** See [solver mathematics](research/solver-mathematics.md), [implementation](research/implementation.md), [research](research/catan-ai-research.md), and [provenance](engine/UPSTREAM.md).

Use **Analyze this decision** to compare moves. Select **Win objective** for full-game attempts, or **Estimate win chances** for a forecast conditional on simulated opponents. Autoplay defaults to Tactical v3, with frozen strategic-v2, the original baseline, and slower win-search also available. Short-horizon scores are labeled as heuristic values, not probabilities. See the [refinement log](research/refinement-log.md) for the five-hour experiment window and current results.

## Run locally

Requires Node.js 22. Static assets, including the Python runtime, are committed, so running the website requires no native Python installation.

```sh
npm ci
npm start
```

Open `http://127.0.0.1:4173/#engine`. All runtime assets and fonts are self-hosted. Research pages load without starting Python; the engine initializes when opened.

## Simulate and develop the engine

Tested with Python 3.12. Create and activate a virtual environment, then:

```sh
pip install -r engine/requirements.txt
python -m pytest -q
python -m engine.simulate --games 100 --output research/engine-validation.json
python -m engine.simulate --games 5 --trajectories work/teacher.jsonl
python -m engine.evaluate --boards 50 --seed 2000 --output research/strength-v2.json
python -m engine.arena --challenger tactical --opponents strategic --boards 200 --seed 4200 --workers 4 --track-beliefs --output work/experiments/tactical-v3
python scripts/benchmark-search.py work/search-speed.json
python scripts/build-engine.py
```

`engine/session.py` owns transitions, observations, events, replay, and invariants. `policy.py`, `strategy.py`, and `opening.py` preserve the v1/v2 policies. `tactics.py` adds immediate-win checks; `road_rules.py` handles corrected road trails and awards. `planning.py` reconstructs sampled worlds and searches continuations; `forecast.py` computes dice exposure and winning forecasts. `beliefs.py` updates correlated resource possibilities and finite-supply constraints. `engine/vendor/catanatron` is the pinned rules core with documented patches. Build the browser bundle after changing engine source. Version 0.1/0.2 replays remain compatible using their original road-rule revision; new games use corrected revision 2.

The arena executes an immutable source copy in each experiment directory and records a manifest, incremental results, replays, and progress. Rerunning an identical command resumes completed games; changed settings/source are rejected. To resume an older experiment after editing the checkout, run its copied `engine.arena` from that experiment's `source` directory with `--worker-snapshot` and the original arguments. Do not launch duplicate processes for the same directory. Experiments with errors or unfinished games report censoring bounds rather than pretending those games were losses.

The [historical validation run](research/engine-validation.json) completed 100/100 baseline games; the [v2 evaluation](research/strength-v2.json) records 200 completed opponent games with policy hashes, seeds, seats, and replay checksums. The Python suite includes rules, information boundaries, replay, probability, and search regressions. These establish tested behavior, not a proof of rule completeness or optimality.

## Website checks and editing

```sh
npm test
npx playwright install chromium
npm run test:browser
```

Browser checks exercise gameplay, exact native/browser replay agreement, research flows, keyboard navigation, mobile layout, and automated accessibility. GitHub Actions repeats these checks and Python tests, regenerates engine and report artifacts, and rejects stale generated output.

Edit the canonical report in `research/catan-ai-research.md`, then run `npm run content`. The implementation log is separate so original research remains a dated snapshot. UI files live in `dist/`; `engine-ui.js` and `engine.css` implement the playable workspace. `catalog.js` holds curated project, architecture, and roadmap entries. Source archives are reproducibly generated by `scripts/build-engine.py`.

## Publishing and licenses

GitHub and the Sites deployment are private. `.openai/hosting.json` selects the existing website. Reviewed source is pushed to both repositories, then the exact commit's static `dist/` directory is packaged and privately published. GitHub pushes run CI; they do not deploy the site by themselves.

Catanatron and Catan Lab engine additions are GPL-3.0-or-later, with corresponding source and notices in `dist/engine-source.zip` and [engine/LICENSE](engine/LICENSE). NetworkX is BSD-3-Clause. Pyodide, CPython, and fonts retain their own notices; see [runtime notices](dist/THIRD_PARTY.md). This independent project is unaffiliated with CATAN or online Catan platforms. No proprietary artwork or historical game dataset is bundled.
