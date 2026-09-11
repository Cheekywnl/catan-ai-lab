# Catan Research Lab

A private, interactive review site for the research and implementation blueprint of a four-player Catan AI: a full-game bot, a game companion, and a research workbench powered by one shared decision engine.

## Status

The research review website is implemented. The report is a source-backed assessment as of 11 September 2026. It contains published findings and proposed engineering choices; no trained bot, reproduced strength benchmark, or proof of game-theoretic optimality is claimed. The belief lab is a working exact-probability explainer, not a full game tracker.

The workspace includes the complete chapter reader, global search, searchable project comparisons, a filterable evidence register, interactive architecture, the correlated-hand explainer, and the staged implementation roadmap. Every chapter is directly linkable, and the original report can be downloaded on desktop or mobile. All website assets, including fonts, are served locally; no external service is required to use the workspace once served.

## Research

The complete report is in [research/catan-ai-research.md](research/catan-ai-research.md). It includes 12 chapters and 37 sources, covering prior agents, probabilistic card tracking, settlement evaluation, search, reinforcement learning, historical data, trading, architecture, testing, and implementation.

## Local development

Requires Node.js 22 or later. Run `npm ci`, then `npm start`, and open the printed local URL. The website is served from `dist/`; static assets are deliberately tracked so the reviewed site can be reproduced from a commit.

## Editing and verification

- Edit the canonical report in `research/catan-ai-research.md`, then run `npm run content` to rebuild the reader data and download. Commit both the original and generated files.
- Edit the curated project, architecture, and roadmap views in `dist/catalog.js`. Their citations reference the same numbered evidence register.
- Edit interaction code in `dist/app.js`; exact theft probabilities live in `dist/lab-math.js`.
- Run `npm test` for content completeness, citation integrity, resource conservation, and exact probability checks.
- Run `npx playwright install chromium`, then `npm run test:browser` for desktop/mobile flows, downloads, keyboard focus, responsive layouts, and automated accessibility checks. The test runner starts a local server when needed.
- With the local server running, `node scripts/capture-review.mjs` writes visual-review screenshots to the ignored `test-results/review/` folder.

GitHub Actions repeats content regeneration and both test suites on pushes and pull requests. Generated data must match the committed research. Browser checks use Chromium desktop and mobile emulation; they do not certify all browsers or replace manual accessibility review.

## Publishing

The GitHub repository is private. The website uses an owner-private Sites deployment, configured by `.openai/hosting.json`. A reviewed commit is pushed to both repositories and its static `dist/` output is packaged for publication. Source credentials are temporary and never committed. A GitHub push runs tests; it does not itself publish the website.

This is an independent research project, unaffiliated with CATAN or any online Catan platform. Third-party repositories and papers retain their own terms and licenses. No third-party agent source code or game dataset is bundled. DM Sans and Manrope font files retain their SIL Open Font License notices in `dist/fonts/`.
