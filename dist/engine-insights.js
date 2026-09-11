const resources = ["Wood", "Brick", "Sheep", "Wheat", "Ore"];
const names = {
  BUILD_SETTLEMENT: "Settlement",
  BUILD_CITY: "City",
  BUY_DEVELOPMENT_CARD: "Development card",
};
const title = (s) =>
  s
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
const percent = (n) => `${(100 * n).toFixed(1)}%`;
const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export function insights(s, selected, plan, forecast) {
  const opening = s.opening;
  const node = s.legal_actions.find((a) => a.id === selected)?.value;
  const candidate = opening?.candidates.find((c) => c.node === node);
  const goals = s.analysis?.goals.slice(0, 3) || [];
  return `<section class="card solver-panel"><div class="section-heading"><div><span class="eyebrow">DECISION LABORATORY</span><h2>Compare the futures.</h2></div><span class="pill neutral">Model-based search</span></div><p>Search samples possible hands and development cards, then plays legal continuations in turn order. Each simulated player sees only their own information.</p><div class="solver-controls"><div class="field"><label for="search-depth">Search depth</label><select id="search-depth"><option value="quick">Quick · 24 short continuations</option><option value="deep">Deeper · 48 longer continuations</option><option value="full">Win objective · 32 full-game attempts</option></select></div><button class="button primary" id="plan-move">Analyze this decision</button><button class="button" id="forecast-win">Estimate win chances</button></div><p class="micro">Full-game analysis takes longer. Small samples have wide uncertainty. A winning forecast is conditional on the simulated opponents; it is not a GTO value.</p><div id="plan-results">${planMarkup(plan)}</div><div id="win-forecast">${forecastMarkup(forecast)}</div></section>
 ${opening ? `<section class="card opening-audit"><span class="eyebrow">OPENING AUDIT</span><h2>Production, timing, and access.</h2><div class="draft-sequence" aria-label="Opening settlement order">${opening.draft_order.map((c, i) => `<span class="${i === opening.current_pick ? "current-pick" : ""}">${i + 1}. ${title(c)}</span>`).join('<span aria-hidden="true">→</span>')}</div><p>${opening.rival_placements_before_next_pick === null ? "This player has no later opening settlement pick." : `${opening.rival_placements_before_next_pick} rival settlement picks occur before this player’s next placement.`} Intervening road choices are included in continuation search.</p>${candidate ? `<div class="opening-metrics"><div><strong>${candidate.candidate_pips}</strong><span>Pips at intersection ${candidate.node}</span></div><div><strong>${percent(candidate.income_roll_probability)}</strong><span>Chance of income on one roll</span></div><div><strong>${candidate.build_tempo.BUILD_CITY.toFixed(1)}</strong><span>City tempo in future rolls</span></div></div><p>Combined holdings after this placement, including your earlier settlement:</p><div class="resource-projection">${resources.map((r, i) => `<div><strong>${r}</strong><span>${candidate.cards_per_36_rolls[i]} cards / 36 rolls</span><small>Trade ${candidate.port_rates[i]}:1</small></div>`).join("")}</div><p class="micro">The port saves approximately ${candidate.port_rolls_saved.BUILD_CITY.toFixed(1)} rolls toward a city in the mean-flow model. A port with no useful surplus receives no bonus. Second-settlement starting resources are included.</p>` : "<p>Select a legal settlement to inspect its production. Road suggestions name a reachable expansion and the roads still needed.</p>"}<p class="micro">${esc(opening.limits)}</p></section>` : ""}
 <div class="solver-grid"><section class="card"><span class="eyebrow">RESOURCE PLAN</span><h2>What the hand is working toward.</h2>${goals.map((g) => `<div class="goal-row"><strong>${names[g.kind]}${g.node === null ? "" : ` at ${g.node}`}</strong><span>≈ ${g.eta_rolls.toFixed(1)} rolls${g.roads ? ` · ${g.roads} new roads` : ""}</span></div>`).join("") || "<p>Resource plans become useful after the first placement.</p>"}<p class="micro">${esc(s.analysis?.eta_note || "")}</p></section><section class="card"><span class="eyebrow">TURN-ORDER EXPOSURE</span><h2>Before your next turn.</h2><p>${s.dice_exposure.rolls_before_next_turn} future dice rolls in the current turn schedule.</p>${s.dice_exposure.players.map((p) => `<div class="exposure-row"><strong>${title(p.color)}</strong><span>${percent(p.probability_any_income)} chance of income</span><small>${p.expected_cards.reduce((a, b) => a + b, 0).toFixed(2)} expected cards · ${resources.map((r, i) => `${r} ${percent(p.probability_resource[i])}`).join(" / ")}</small></div>`).join("")}<p class="micro">${esc(s.dice_exposure.assumption)}</p></section></div>
 <details class="card development-model"><summary>Development-card possibilities</summary><p>${esc(s.development_belief.assumption)}</p><div class="table-scroll" tabindex="0" role="region" aria-label="Development card probabilities"><table><thead><tr><th>Opponent</th><th>Has a knight</th><th>Has a victory point</th><th>Has a monopoly</th></tr></thead><tbody>${Object.entries(
   s.development_belief.hands,
 )
   .map(
     ([color, cards]) =>
       `<tr><th>${title(color)}</th>${["KNIGHT", "VICTORY_POINT", "MONOPOLY"].map((card) => `<td>${percent(cards[card].probability_at_least_one)}</td>`).join("")}</tr>`,
   )
   .join(
     "",
   )}</tbody></table></div><p class="micro">Hypergeometric probabilities under an exchangeable unknown-card model. Strategic card retention is not modeled.</p></details>`;
}
export function planMarkup(plan) {
  if (!plan) return "";
  const probabilities = plan.score_kind === "rollout_win_rate";
  return `<div class="search-summary"><h3>${probabilities ? "Simulated winning rates" : "Continuation position scores"}</h3><p>${plan.budget} continuations · ${plan.transitions.toLocaleString()} legal actions · ${plan.terminal_samples} reached a winner · ${(plan.elapsed_ms / 1000).toFixed(1)} seconds</p><p class="micro">${esc(plan.objective)}</p><ol class="solver-ranking">${plan.candidates.map((a) => `<li><button class="search-choice" data-planned="${a.id}"><strong>${esc(a.label)}</strong><span>${probabilities ? percent(a.search_score) : a.search_score.toFixed(3)} <small>± ${probabilities ? percent(a.standard_error) : a.standard_error.toFixed(3)} SE · ${a.samples} samples</small></span></button></li>`).join("")}</ol><details><summary>Assumptions behind this search</summary><ul>${plan.assumptions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details></div>`;
}
export function forecastMarkup(forecast) {
  if (!forecast) return "";
  return `<div class="forecast-result"><h3>Winning forecasts</h3><p>${forecast.completed}/${forecast.samples} continuations reached a winner. ${(forecast.elapsed_ms / 1000).toFixed(1)} seconds. Your own cards inform this view.</p>${forecast.players.map((p) => `<div class="forecast-row"><strong>${title(p.color)}</strong><div><span class="forecast-bar" style="width:${100 * (p.win_probability ?? p.censoring_bounds[0])}%"></span></div><span>${p.win_probability === null ? "Unresolved" : percent(p.win_probability)}</span><small>${p.wilson_95_interval ? `95% sampling interval ${percent(p.wilson_95_interval[0])}–${percent(p.wilson_95_interval[1])}` : `Censoring bounds ${percent(p.censoring_bounds[0])}–${percent(p.censoring_bounds[1])}`}</small></div>`).join("")}<p class="micro">${forecast.assumptions.map(esc).join(" ")}</p></div>`;
}
