# Catan Research Lab

A private, interactive review site for the research and implementation blueprint of a four-player Catan AI: a full-game bot, a game companion, and a research workbench powered by one shared decision engine.

## Status

Research and website in development. The report is a source-backed assessment as of 11 September 2026. It contains published findings and proposed engineering choices; no trained bot, reproduced strength benchmark, or proof of game-theoretic optimality is claimed.

## Research

The complete report is in [research/catan-ai-research.md](research/catan-ai-research.md). It includes 12 chapters and 37 sources, covering prior agents, probabilistic card tracking, settlement evaluation, search, reinforcement learning, historical data, trading, architecture, testing, and implementation.

## Local development

Requires Node.js 22 or later. Run `npm start` and open the printed local URL. The website is served from `dist/`; static assets are deliberately tracked so the reviewed site can be reproduced from a commit.

This is an independent research project, unaffiliated with CATAN or any online Catan platform. Third-party repositories and papers retain their own terms and licenses. No third-party source code or game dataset is bundled.
