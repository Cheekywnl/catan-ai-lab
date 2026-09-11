import { insights, planMarkup, forecastMarkup } from "./engine-insights.js";
const colors = {
  RED: "#ac4c39",
  BLUE: "#3f6f9a",
  ORANGE: "#ad671e",
  WHITE: "#f4eee0",
};
const resourceColors = {
  WOOD: "#78966c",
  BRICK: "#be8366",
  SHEEP: "#adbe83",
  WHEAT: "#d6bc71",
  ORE: "#93a6a4",
  DESERT: "#d4c5a5",
};
const resources = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"];
const names = {
  BUILD_INITIAL_SETTLEMENT: "Place an opening settlement",
  BUILD_INITIAL_ROAD: "Choose its road",
  PLAY_TURN: "Play your turn",
  DISCARD: "Choose cards to discard",
  MOVE_ROBBER: "Move the robber",
  DECIDE_TRADE: "Respond to the trade",
  DECIDE_ACCEPTEES: "Choose a trade partner",
};
const esc = (v) =>
  String(v).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const tradeCounts = (counts) =>
  counts
    .map((n, i) => (n ? `${n} ${title(resources[i])}` : ""))
    .filter(Boolean)
    .join(", ");
const title = (v) =>
  v
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
let worker,
  requestId = 0,
  snapshot,
  viewer = "RED",
  seed = 42,
  policy = "strategic";
const pending = new Map();
let statusListener = () => {};
function call(command, args = {}) {
  if (!worker) {
    worker = new Worker(new URL("./engine-worker.js", import.meta.url), {
      type: "module",
    });
    worker.onmessage = ({ data }) => {
      if (data.status) {
        statusListener(data.status);
        return;
      }
      const handlers = pending.get(data.id);
      if (!handlers) return;
      pending.delete(data.id);
      if (data.error) handlers.reject(new Error(data.error));
      else handlers.resolve(data.result);
    };
    worker.onerror = () => {
      for (const { reject } of pending.values())
        reject(
          new Error(
            "The engine worker stopped. Reload this page to restart it.",
          ),
        );
      pending.clear();
    };
  }
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, command, viewer, policy, ...args });
  });
}

function boardSVG(s, selected) {
  const nodeMap = Object.fromEntries(s.board.nodes.map((n) => [n.id, n]));
  const xy = (n) => [n.x * 59, n.y * 59];
  const buildings = Object.fromEntries(
    s.board.buildings.map((b) => [b.node, b]),
  );
  const possible = new Map();
  for (const a of s.legal_actions) {
    if (a.type === "BUILD_SETTLEMENT" || a.type === "BUILD_CITY")
      possible.set("n" + a.value, a.id);
    if (a.type === "BUILD_ROAD")
      possible.set(
        "e" +
          a.value
            .slice()
            .sort((a, b) => a - b)
            .join("-"),
        a.id,
      );
    if (a.type === "MOVE_ROBBER" && !possible.has("t" + a.value[0].join(",")))
      possible.set("t" + a.value[0].join(","), a.id);
  }
  let svg =
    '<svg viewBox="-350 -285 700 570" class="catan-board" role="group" aria-label="Catan board. Use the legal move list or select a highlighted location."><rect x="-350" y="-285" width="700" height="570" rx="18" fill="#e4ece6"/><circle r="273" fill="#d4e2de" opacity=".55"/>';
  for (const tile of s.board.tiles) {
    const x = tile.x * 59,
      y = tile.y * 59;
    const points = Array.from({ length: 6 }, (_, i) => {
      const a = ((i * 60 - 90) * Math.PI) / 180;
      return `${x + 58 * Math.cos(a)},${y + 58 * Math.sin(a)}`;
    }).join(" ");
    const id = possible.get("t" + tile.coordinate.join(","));
    svg += `<g ${id !== undefined ? `class="board-target" role="button" tabindex="0" data-action="${id}" aria-label="Move robber to tile ${tile.id}"` : ""}><polygon points="${points}" fill="${resourceColors[tile.resource || "DESERT"]}" stroke="#f5f3e7" stroke-width="3"/>`;
    svg += `<text x="${x}" y="${y - 22}" class="tile-resource">${tile.resource || "DESERT"}</text>`;
    if (tile.number) {
      svg += `<circle cx="${x}" cy="${y + 4}" r="17" fill="#fbf5df"/><text x="${x}" y="${y + 10}" class="tile-number ${tile.number === 6 || tile.number === 8 ? "red-number" : ""}">${tile.number}</text><text x="${x}" y="${y + 34}" class="tile-pips">${"•".repeat(6 - Math.abs(7 - tile.number))}</text>`;
    }
    if (tile.coordinate.join(",") === s.board.robber.join(","))
      svg += `<g transform="translate(${x + 27},${y - 4})"><circle cy="-7" r="7" fill="#253831"/><path d="M-5 0H5L10 18H-10Z" fill="#253831"/><title>Robber</title></g>`;
    svg += "</g>";
  }
  for (const port of s.board.ports) {
    if (port.nodes.length !== 2) continue;
    const a = nodeMap[port.nodes[0]],
      b = nodeMap[port.nodes[1]];
    if (!a || !b) continue;
    let x = (a.x + b.x) * 29.5,
      y = (a.y + b.y) * 29.5;
    const len = Math.hypot(x, y);
    const px = x + (x / len) * 31,
      py = y + (y / len) * 31;
    svg += `<path d="M${a.x * 59} ${a.y * 59}L${px} ${py}L${b.x * 59} ${b.y * 59}" fill="none" stroke="#637e72" stroke-width="2"/><rect x="${px - 25}" y="${py - 12}" width="50" height="24" rx="6" fill="#f7f5eb" stroke="#c2d1c3"/><text x="${px}" y="${py + 4}" class="port-label">${port.resource ? title(port.resource).slice(0, 3) + " 2:1" : "Any 3:1"}</text>`;
  }
  for (const road of s.board.roads) {
    const [a, b] = road.edge.map((n) => nodeMap[n]);
    svg += `<line x1="${a.x * 59}" y1="${a.y * 59}" x2="${b.x * 59}" y2="${b.y * 59}" stroke="#263b32" stroke-width="9" stroke-linecap="round"/><line x1="${a.x * 59}" y1="${a.y * 59}" x2="${b.x * 59}" y2="${b.y * 59}" stroke="${colors[road.color]}" stroke-width="6" stroke-linecap="round"/>`;
  }
  for (const edge of s.board.edges) {
    const id = possible.get("e" + edge.join("-"));
    if (id === undefined) continue;
    const [a, b] = edge.map((n) => nodeMap[n]);
    svg += `<g class="board-target" role="button" tabindex="0" data-action="${id}" aria-label="Build road ${edge[0]} to ${edge[1]}"><line x1="${a.x * 59}" y1="${a.y * 59}" x2="${b.x * 59}" y2="${b.y * 59}" stroke="${id === selected ? "#233e2c" : "#f7fff0"}" stroke-width="12" opacity=".85"/><line x1="${a.x * 59}" y1="${a.y * 59}" x2="${b.x * 59}" y2="${b.y * 59}" stroke="#537741" stroke-width="3" stroke-dasharray="5 4"/></g>`;
  }
  for (const n of s.board.nodes) {
    const [x, y] = xy(n),
      b = buildings[n.id],
      id = possible.get("n" + n.id);
    if (id !== undefined)
      svg += `<g class="board-target" role="button" tabindex="0" data-action="${id}" aria-label="Select intersection ${n.id}"><circle cx="${x}" cy="${y}" r="12" fill="${id === selected ? "#233e2c" : "#f7fce9"}" stroke="#49683e" stroke-width="2"/><text x="${x}" y="${y + 3.5}" class="node-id" fill="${id === selected ? "#fff" : "#233e2c"}">${n.id}</text></g>`;
    if (b)
      svg += `<g transform="translate(${x},${y})"><path d="${b.type === "CITY" ? "M-13 8V-4L-6-11 1-4V-1L7-8 14-1V8Z" : "M-10 8V-3L0-12 10-3V8Z"}" fill="${colors[b.color]}" stroke="#263b32" stroke-width="2"/><title>${title(b.color)} ${title(b.type)} at ${n.id}</title></g>`;
  }
  return svg + "</svg>";
}

function eventText(e) {
  let text = title(e.color) + " · " + title(e.type);
  if (e.type === "ROLL")
    text += ` ${e.dice.join(" + ")} = ${e.dice[0] + e.dice[1]}`;
  else if (e.type === "BUILD_SETTLEMENT" || e.type === "BUILD_CITY")
    text += " at " + e.value;
  else if (e.type === "BUILD_ROAD") text += " " + e.value.join("–");
  else if (e.type === "MOVE_ROBBER" && e.victim)
    text +=
      " from " +
      title(e.victim) +
      (e.resource ? " · " + title(e.resource) : " · hidden card");
  else if (e.type === "DISCARD_RESOURCE")
    text += e.resource ? " · " + title(e.resource) : " · hidden card";
  else if (e.development_card) text += " · " + title(e.development_card);
  return text;
}

export function mountEngine(root) {
  let disposed = false,
    busy = false,
    running = false,
    selected = null,
    search = null,
    plan = null,
    forecast = null;
  root.innerHTML = `<div class="page-heading engine-heading"><div><div class="eyebrow">ENGINE 0.2 · FOUR-PLAYER BASE CATAN</div><h1>Play. Inspect. Simulate.</h1><p class="lede">Resource planning, hidden-world search, and turn-by-turn winning forecasts.</p></div><span class="pill green">Strategic policy + search</span></div><div class="engine-toolbar"><div class="field"><label for="game-seed">Game seed</label><input id="game-seed" type="number" min="0" max="4294967295" step="1" value="${seed}"></div><button class="button" id="new-game">New game</button><div class="field"><label for="game-viewer">View as</label><select id="game-viewer">${Object.keys(
    colors,
  )
    .map((c) => `<option ${c === viewer ? "selected" : ""}>${c}</option>`)
    .join(
      "",
    )}</select></div><div class="field"><label for="bot-policy">Bot policy</label><select id="bot-policy"><option value="strategic">Strategic v2</option><option value="baseline">Original baseline</option><option value="search">Win search · experimental / slow</option></select></div><button class="button" id="undo-game">Undo move</button><button class="button" id="export-game">Export replay ↓</button><label class="button import-replay">Import replay<input id="import-game" type="file" accept=".json,application/json" aria-label="Import replay file"></label></div><p class="engine-status" role="status" id="engine-status">Loading the game engine…</p><div id="engine-position"><div class="engine-loading"><span class="loading-orbit" aria-hidden="true">⬡</span><h2>Preparing the board</h2><p>The engine runs on your device. The first load downloads the Python runtime.</p></div></div><section class="card engine-validation"><span class="eyebrow">VALIDATION · ENGINE 0.2</span><h2>Built to be inspected.</h2><p>The final strategic policy won 85 of 200 games (42.5%) against three copies of the original bot, across all four seats on 50 held-out boards. The board-bootstrap 95% interval is 35–50%. This measures strength against our original bot, not humans or GTO. The rules, sampling, probability, and replay tests run in GitHub CI.</p><div class="detail-links"><a href="strength-v2.json" download>Download opponent benchmark ↓</a><a href="solver-mathematics.md" target="_blank" rel="noopener noreferrer">Math & solver assumptions ↗</a><a href="implementation.md" target="_blank" rel="noopener noreferrer">Implementation & limitations ↗</a><a href="https://github.com/Cheekywnl/catan-ai-lab" target="_blank" rel="noopener noreferrer">Open GitHub ↗</a></div></section><div class="engine-footnote"><a href="engine-source.zip" download>Python engine source ↓</a><a href="THIRD_PARTY.md" target="_blank" rel="noopener noreferrer">Runtime & license notices ↗</a><span>Research sandbox · Replay exports include hidden information.</span></div>`;
  const $ = (sel) => root.querySelector(sel);
  const status = (text) => {
    if (!disposed) $("#engine-status").textContent = text;
  };
  statusListener = status;
  const setBusy = (value) => {
    busy = value;
    root.setAttribute("aria-busy", String(value));
    root.querySelectorAll("button,input,select").forEach((el) => {
      if (el.id !== "stop-auto") el.disabled = value;
    });
    if (!value && snapshot) applyDisabled();
  };
  function applyDisabled() {
    if (!snapshot) return;
    const disable = (id, value) => {
      const el = $(id);
      if (el) el.disabled = value;
    };
    for (const id of [
      "#new-game",
      "#game-seed",
      "#game-viewer",
      "#import-game",
      "#export-game",
      "#bot-policy",
    ])
      disable(id, running);
    disable("#undo-game", !snapshot.revision || running);
    disable(
      "#apply-move",
      selected === null ||
        !snapshot.legal_actions.length ||
        !!snapshot.winner ||
        running,
    );
    disable("#legal-moves", !snapshot.legal_actions.length || running);
    disable(
      "#search-draft",
      snapshot.phase !== "BUILD_INITIAL_SETTLEMENT" ||
        snapshot.actor !== viewer ||
        !!snapshot.winner ||
        running,
    );
    for (const id of ["#bot-step", "#bot-batch", "#auto-game"])
      disable(id, !!snapshot.winner || running);
    disable("#stop-auto", !running);
    disable(
      "#plan-move",
      running ||
        snapshot.actor !== viewer ||
        snapshot.legal_actions.length < 2 ||
        !!snapshot.winner,
    );
    disable("#forecast-win", running || !!snapshot.winner);
  }
  function draw() {
    if (disposed || !snapshot) return;
    const s = snapshot;
    if (!s.legal_actions.some((a) => a.id === selected))
      selected = s.recommendations[0]?.id ?? null;
    const chosen = s.legal_actions.find((a) => a.id === selected);
    const phase = s.winner
      ? `${title(s.winner)} wins!`
      : names[s.phase] || title(s.phase);
    const myTurn = s.actor === viewer;
    $("#engine-position").innerHTML =
      `<div class="player-strip">${s.players.map((p) => `<div class="player-tile ${p.color === s.actor ? "acting" : ""}"><div><span class="player-swatch" style="background:${colors[p.color]}"></span><strong>${title(p.color)}</strong>${p.color === viewer ? '<span class="you-label">Your view</span>' : ""}</div><div class="player-points"><strong>${p.own_points ?? p.public_points}</strong><span>${p.own_points !== undefined ? "your" : "public"} points</span></div><p>${p.resource_count} resources · ${p.development_count} dev cards</p><small>Road ${p.longest_road}${p.has_road ? " ★" : ""} · Knights ${p.played_knights}${p.has_army ? " ★" : ""}</small></div>`).join("")}</div><div class="game-grid"><section class="game-board-panel" aria-label="Game board"><div class="board-topline"><strong>${esc(phase)}</strong><span>${s.initial ? "Opening draft" : "Turn " + s.turn} · Move ${s.revision}</span></div>${boardSVG(s, selected)}<div class="board-caption">${s.winner ? "Game complete. Export the replay or start another seed." : myTurn ? "Select a highlighted location or a legal move, then play it." : `${title(s.actor)} is deciding. Advance the bot or switch perspective.`}</div><div class="hand-panel"><div><span class="eyebrow">${viewer} · YOUR HAND</span><div class="hand-resources">${resources.map((r, i) => `<span class="hand-token"><i style="background:${resourceColors[r]}"></i>${title(r)} <strong>${s.own_hand[i]}</strong></span>`).join("")}</div></div><div class="own-dev"><span class="eyebrow">YOUR DEVELOPMENT CARDS</span><p>${
        Object.entries(s.own_development)
          .filter(([, n]) => n)
          .map(([c, n]) => `${title(c)} × ${n}`)
          .join(" · ") || "None"
      }</p></div></div></section><aside class="move-panel"><span class="eyebrow">${esc(title(s.actor))} TO ACT</span><h2>${s.winner ? "Game finished" : myTurn ? "Choose a move" : "Observe this turn"}</h2>${s.trade ? `<div class="active-trade"><strong>${title(s.turn_owner)} offers</strong><p>${tradeCounts(s.trade.slice(0, 5))} for ${tradeCounts(s.trade.slice(5, 10))}</p></div>` : ""}${s.discard_remaining ? `<p>Discard ${s.discard_remaining} more card${s.discard_remaining === 1 ? "" : "s"} from your hand.</p>` : ""}<div class="field"><label for="legal-moves">Legal moves (${s.legal_actions.length})</label><select id="legal-moves" size="7" ${!s.legal_actions.length ? "disabled" : ""}>${s.legal_actions.map((a) => `<option value="${a.id}" ${a.id === selected ? "selected" : ""}>${esc(a.label)}</option>`).join("")}</select></div><button class="button primary" id="apply-move" ${!chosen ? "disabled" : ""}>Play selected move</button><div class="bot-controls"><button class="button" id="bot-step" ${s.winner ? "disabled" : ""}>Bot: next move</button><button class="button" id="bot-batch" ${s.winner ? "disabled" : ""}>${policy === "search" ? "Search one move" : "Run 50 moves"}</button><button class="button" id="auto-game" ${s.winner ? "disabled" : ""}>Run to a winner</button><button class="button" id="stop-auto" ${!running ? "disabled" : ""}>Pause</button></div><div class="move-recommendations"><div class="section-heading"><h3>Policy suggestions</h3></div>${
        s.recommendations
          .slice(0, 3)
          .map(
            (a, i) =>
              `<button class="recommendation" data-action="${a.id}"><span>${i + 1}</span><div><strong>${esc(a.label)}</strong><small>${esc(a.reason)}</small></div></button>`,
          )
          .join("") ||
        "<p>Suggestions appear when the selected player has a decision.</p>"
      }</div><button class="button" id="search-draft">Compare opening futures</button><div id="draft-results"></div></aside></div><div class="engine-lower"><section class="card"><div class="section-heading"><h2>Resource beliefs</h2><span class="pill neutral">${esc(s.belief?.status?.replaceAll("_", " ") || "Unavailable")}</span></div><p class="belief-description">${s.belief?.assumptions?.map(esc).join(" ") || "Joint possibilities inferred from this player’s observed events. A single number is deduced; a range is uncertain."}</p><div class="table-scroll" tabindex="0" role="region" aria-label="Resource belief counts"><table class="engine-beliefs"><thead><tr><th scope="col">Player</th>${resources.map((r) => `<th scope="col">${title(r)}</th>`).join("")}</tr></thead><tbody>${s.players.map((p) => `<tr><th scope="row">${title(p.color)}</th>${(s.belief?.hands?.[p.color] || resources.map(() => ({ min: 0, max: p.resource_count }))).map((r) => `<td title="${r.expected == null ? "Conservative bounds" : `Expected count: ${r.expected.toFixed(2)}`}">${r.min === r.max ? r.min : `${r.min}–${r.max}`}</td>`).join("")}</tr>`).join("")}</tbody></table></div><p class="micro">${s.belief?.worlds || 0} retained joint states · Opponents’ actual hands are excluded from this view.</p>${s.can_offer ? `<details class="trade-form"><summary>Propose a player trade</summary><p>Offer resources you hold. Other players respond before you choose a partner.</p><div class="trade-grid"><span></span><strong>Give</strong><strong>Receive</strong>${resources.map((r, i) => `<label for="give-${i}">${title(r)}</label><input id="give-${i}" type="number" min="0" max="19" value="0" aria-label="Give ${r.toLowerCase()}"><input id="receive-${i}" type="number" min="0" max="19" value="0" aria-label="Receive ${r.toLowerCase()}">`).join("")}</div><button class="button" id="offer-trade">Send trade offer</button></details>` : ""}</section><section class="card event-panel"><div class="section-heading"><h2>Observed events</h2><span class="pill neutral">${s.events.length} latest</span></div><ol class="event-list">${
        s.events
          .slice()
          .reverse()
          .map((e) => `<li><span>${e.sequence}</span>${esc(eventText(e))}</li>`)
          .join("") ||
        "<li>The board is ready. Place the first settlement to begin.</li>"
      }</ol></section></div>`;
    $("#engine-position").insertAdjacentHTML(
      "beforeend",
      '<div id="solver-insights">' +
        insights(s, selected, plan, forecast) +
        "</div>",
    );
    bindPlanned();
    $("#plan-move").onclick = async () => {
      const depth = $("#search-depth").value;
      const settings =
        depth === "full"
          ? { budget: 32, horizon: 1600 }
          : depth === "deep"
            ? { budget: 48, horizon: 128 }
            : { budget: 24, horizon: 48 };
      setBusy(true);
      status("Comparing hidden-card worlds and legal continuations…");
      try {
        plan = await call("plan", settings);
        $("#plan-results").innerHTML = planMarkup(plan);
        bindPlanned();
        status(
          "Decision comparison ready. Review the sample counts and assumptions.",
        );
      } catch (e) {
        showError(e);
      } finally {
        setBusy(false);
      }
    };
    $("#forecast-win").onclick = async () => {
      setBusy(true);
      status(
        "Playing sampled games to estimate each player’s winning chances…",
      );
      try {
        forecast = await call("forecast", { samples: 12 });
        $("#win-forecast").innerHTML = forecastMarkup(forecast);
        status("Winning forecast ready. Intervals show sampling uncertainty.");
      } catch (e) {
        showError(e);
      } finally {
        setBusy(false);
      }
    };
    $("#legal-moves").onchange = (e) => choose(Number(e.target.value));
    root.querySelectorAll("[data-action]").forEach((el) => {
      const activate = () => choose(Number(el.dataset.action));
      el.onclick = activate;
      el.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      };
    });
    $("#apply-move").onclick = () =>
      run("act", { action: selected, revision: snapshot.revision });
    $("#bot-step").onclick = () => run("auto", { count: 1 });
    $("#bot-batch").onclick = () =>
      run("auto", { count: policy === "search" ? 1 : 50 });
    $("#auto-game").onclick = async () => {
      running = true;
      let batches = 0;
      while (running && !disposed && !snapshot.winner && batches++ < 4000) {
        await run("auto", { count: policy === "search" ? 1 : 25 });
        await new Promise((r) => setTimeout(r, 0));
      }
      running = false;
      if (!disposed) {
        draw();
        status(
          snapshot.winner
            ? `${title(snapshot.winner)} won after ${snapshot.revision} moves.`
            : "Simulation paused.",
        );
      }
    };
    $("#stop-auto").onclick = () => {
      running = false;
      status("Pausing after the current batch…");
    };
    $("#search-draft").onclick = async () => {
      setBusy(true);
      status("Comparing public opening drafts…");
      try {
        search = await call("plan", { budget: 30, horizon: 48 });
        showSearch();
        status(
          "Opening continuations compared in the real snake-draft order. Short-horizon scores are not win probabilities.",
        );
      } catch (e) {
        showError(e);
      } finally {
        setBusy(false);
      }
    };
    if ($("#offer-trade"))
      $("#offer-trade").onclick = () =>
        run("offer", {
          give: resources.map((_, i) => $(`#give-${i}`).valueAsNumber),
          receive: resources.map((_, i) => $(`#receive-${i}`).valueAsNumber),
          revision: snapshot.revision,
        });
    showSearch();
    applyDisabled();
  }
  function bindPlanned() {
    root
      .querySelectorAll("[data-planned]")
      .forEach((el) => (el.onclick = () => choose(Number(el.dataset.planned))));
  }
  function choose(id) {
    if (busy || running) return;
    selected = id;
    draw();
  }
  function showSearch() {
    if (!search || !$("#draft-results")) return;
    $("#draft-results").innerHTML =
      `<p class="micro">${esc(search.objective)}</p><ol class="draft-comparison">${search.candidates
        .slice(0, 5)
        .map(
          (a) =>
            `<li><button class="draft-choice" data-draft="${a.id}"><strong>Intersection ${a.value}</strong><span>${(a.search_score ?? a.draft_score).toFixed(3)} <small>± ${a.standard_error.toFixed(1)} SE</small></span></button></li>`,
        )
        .join(
          "",
        )}</ol><p class="micro">${search.budget ?? search.trials_per_candidate} total samples · ${search.candidates.length} screened candidates</p>`;
    root
      .querySelectorAll("[data-draft]")
      .forEach((el) => (el.onclick = () => choose(Number(el.dataset.draft))));
  }
  function showError(error) {
    running = false;
    status(
      "Could not complete that action: " +
        String(error.message).split("\n").filter(Boolean).at(-1),
    );
  }
  async function run(command, args = {}) {
    if (busy) return false;
    setBusy(true);
    status(
      command === "auto" ? "Simulating legal moves…" : "Updating the game…",
    );
    try {
      snapshot = await call(command, args);
      selected = null;
      search = null;
      plan = null;
      forecast = null;
      draw();
      status(
        snapshot.winner
          ? `${title(snapshot.winner)} wins. Game complete after ${snapshot.revision} moves.`
          : `${title(snapshot.actor)} to act · ${snapshot.revision} moves recorded.`,
      );
      return true;
    } catch (e) {
      showError(e);
      return false;
    } finally {
      if (!disposed) setBusy(false);
    }
  }
  $("#new-game").onclick = () => {
    running = false;
    const value = $("#game-seed").valueAsNumber;
    if (!Number.isInteger(value) || value < 0 || value >= 4294967296) {
      status("Enter a whole-number seed from 0 to 4294967295.");
      return;
    }
    seed = value;
    run("new", { seed });
  };
  $("#bot-policy").value = policy;
  $("#bot-policy").onchange = (e) => {
    policy = e.target.value;
    run("observe");
  };
  $("#game-viewer").onchange = (e) => {
    viewer = e.target.value;
    search = null;
    run("observe");
  };
  $("#undo-game").onclick = () => run("undo");
  $("#export-game").onclick = async () => {
    try {
      const replay = await call("export");
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(replay, null, 2)], {
          type: "application/json",
        }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `catan-${seed}-${snapshot.revision}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status(
        "Research replay exported, including the seed and private action history.",
      );
    } catch (e) {
      showError(e);
    }
  };
  $("#import-game").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 5_000_000) {
      status("Choose a replay smaller than 5 MB.");
      return;
    }
    try {
      const replay = JSON.parse(await file.text());
      if (await run("import", { replay })) {
        seed = replay.seed;
        $("#game-seed").value = seed;
      }
    } catch (error) {
      showError(error);
    } finally {
      e.target.value = "";
    }
  };
  run(snapshot ? "observe" : "new", snapshot ? {} : { seed });
  return () => {
    disposed = true;
    running = false;
    statusListener = () => {};
  };
}
