"""Opening economics and exact public snake-draft order. No generic port bonus."""

from engine.policy import RESOURCES, COSTS


def port_rates(o, own_nodes):
    rates = [4] * 5
    for port in o["board"]["ports"]:
        if own_nodes.intersection(port["nodes"]):
            if port["resource"] is None:
                rates = [min(r, 3) for r in rates]
            else:
                rates[RESOURCES.index(port["resource"])] = 2
    return rates


def tempo(production, rates, hand=None):
    from engine.strategy import eta

    hand = hand or [0] * 5
    times = {
        kind: eta(hand, COSTS[kind], production, rates)
        for kind in ("BUILD_SETTLEMENT", "BUILD_CITY", "BUY_DEVELOPMENT_CARD")
    }
    # Explicit preference, not an equilibrium utility: buildings grant a point;
    # development cards get a discount for uncertain points and army value.
    score = sum(
        w / (8 + times[kind])
        for kind, w in [
            ("BUILD_SETTLEMENT", 1.0),
            ("BUILD_CITY", 1.0),
            ("BUY_DEVELOPMENT_CARD", 0.35),
        ]
    )
    return score, times


def candidate(o, node):
    from engine.strategy import context

    color, nodes, owned, p, _, own = context(o)
    combined = [a + b for a, b in zip(p, nodes[node])]
    rates = port_rates(o, {b["node"] for b in owned} | {node})
    starting = list(o["own_hand"])
    if owned:
        for tile in o["board"]["tiles"]:
            if node in tile["nodes"] and tile["resource"]:
                starting[RESOURCES.index(tile["resource"])] += 1
    score, times = tempo(combined, rates, starting)
    _, without_port = tempo(combined, [4] * 5, starting)
    yields = {n: 0 for n in range(2, 13)}
    for tile in o["board"]["tiles"]:
        if tile["resource"]:
            yields[tile["number"]] += sum(
                (2 if b["type"] == "CITY" else 1)
                for b in owned
                if b["node"] in tile["nodes"]
            ) + int(node in tile["nodes"])
    prob = {n: (6 - abs(7 - n)) / 36 for n in range(2, 13) if n != 7}
    mean = sum(prob.get(n, 0) * v for n, v in yields.items())
    return {
        "node": node,
        "score": round(1000 * score, 4),
        "cards_per_36_rolls": [round(x * 36, 3) for x in combined],
        "candidate_pips": round(sum(nodes[node]) * 36, 3),
        "income_roll_probability": sum(prob.get(n, 0) for n, v in yields.items() if v),
        "income_variance": round(
            sum(prob.get(n, 0) * v * v for n, v in yields.items()) - mean * mean, 4
        ),
        "starting_resources": starting,
        "port_rates": rates,
        "build_tempo": {k: round(v, 2) for k, v in times.items()},
        "port_rolls_saved": {k: round(without_port[k] - times[k], 2) for k in times},
    }


def report(o):
    if not o["initial"]:
        return None
    order = [p["color"] for p in o["players"]]
    draft = order + list(reversed(order))
    current = max(
        0, len(o["board"]["buildings"]) - (o["phase"] == "BUILD_INITIAL_ROAD")
    )
    future = draft[current + 1 :]
    rows = [
        candidate(o, a["value"])
        for a in o["legal_actions"]
        if a["type"] == "BUILD_SETTLEMENT"
    ]
    return {
        "draft_order": draft,
        "current_pick": current,
        "rival_placements_before_next_pick": (
            future.index(o["viewer"]) if o["viewer"] in future else None
        ),
        "remaining_picks": future,
        "candidates": sorted(rows, key=lambda x: (-x["score"], x["node"])),
        "objective": "Prefer faster mean resource-flow access to settlements and cities, with discounted development-card access. Ports change conversion rates rather than adding a generic bonus.",
        "limits": "Pips and dice coverage are exact. Build tempo ignores dice variance and future bank shortages. Opponent decisions require continuation search; this score is not GTO.",
    }
