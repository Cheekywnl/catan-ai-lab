"""Economy/expansion policy v2. Every function consumes player observations only."""

from collections import deque
from functools import lru_cache
import math

from engine.policy import RESOURCES, COSTS


@lru_cache(maxsize=128)
def _nodes(tiles):
    values = [[0.0] * 5 for _ in range(54)]
    for resource, number, nodes in tiles:
        if resource:
            for node in nodes:
                values[node][RESOURCES.index(resource)] += (6 - abs(7 - number)) / 36
    return tuple(tuple(v) for v in values)


def context(o):
    color = o["viewer"]
    nodes = _nodes(
        tuple(
            (t["resource"], t["number"], tuple(t["nodes"])) for t in o["board"]["tiles"]
        )
    )
    owned = [b for b in o["board"]["buildings"] if b["color"] == color]
    p = [
        sum(nodes[b["node"]][r] * (2 if b["type"] == "CITY" else 1) for b in owned)
        for r in range(5)
    ]
    rates = [4] * 5
    for port in o["board"]["ports"]:
        if any(b["node"] in port["nodes"] for b in owned):
            if port["resource"] is None:
                rates = [min(3, x) for x in rates]
            else:
                rates[RESOURCES.index(port["resource"])] = 2
    own = next(x for x in o["players"] if x["color"] == color)
    return color, nodes, owned, p, rates, own


def economy(p):
    return (
        sum(w * x for w, x in zip([1.0, 0.9, 0.8, 1.3, 1.35], p))
        + 0.15 * sum(math.sqrt(x) for x in p)
        + 0.6 * min(p[3], p[4])
    )


def eta(hand, cost, production, rates):
    """Mean-flow affordability in future dice rolls, including maritime conversion.

    This deterministic estimate ignores dice variance and finite bank supply.
    """

    def feasible(t):
        balance = [h + p * t - c for h, p, c in zip(hand, production, cost)]
        return (
            sum(max(0, b) / r for b, r in zip(balance, rates))
            >= sum(max(0, -b) for b in balance) - 1e-9
        )

    if feasible(0):
        return 0.0
    if not feasible(120):
        return 120.0
    low, high = 0.0, 120.0
    for _ in range(9):
        mid = (low + high) / 2
        if feasible(mid):
            high = mid
        else:
            low = mid
    return high


def expansion(o):
    """Minimum new roads to each unblocked settlement node. Opponents block travel."""
    color = o["viewer"]
    board = o["board"]
    neighbors = {n["id"]: n["neighbors"] for n in board["nodes"]}
    buildings = {b["node"]: b["color"] for b in board["buildings"]}
    roads = {tuple(sorted(r["edge"])): r["color"] for r in board["roads"]}
    distance = {}
    first = {}
    queue = deque()
    sources = {b["node"] for b in board["buildings"] if b["color"] == color}
    for edge, owner in roads.items():
        if owner == color:
            sources.update(n for n in edge if buildings.get(n, color) == color)
    for node in sorted(sources):
        distance[node] = 0
        first[node] = None
        queue.append(node)
    while queue:
        node = queue.popleft()
        if buildings.get(node, color) != color:
            continue
        for other in sorted(neighbors[node]):
            edge = tuple(sorted((node, other)))
            owner = roads.get(edge)
            if owner and owner != color:
                continue
            weight = 0 if owner == color else 1
            cost = distance[node] + weight
            if cost > 3 or cost >= distance.get(other, 999):
                continue
            distance[other] = cost
            first[other] = first[node] or (edge if weight else None)
            if weight:
                queue.append(other)
            else:
                queue.appendleft(other)
    return [
        (n, d, first[n])
        for n, d in distance.items()
        if n not in buildings and not any(x in buildings for x in neighbors[n])
    ]


def analyze(o):
    color, nodes, owned, p, rates, own = context(o)
    goals = []
    if own["cities_available"]:
        for b in owned:
            if b["type"] == "SETTLEMENT":
                goals.append(
                    {
                        "kind": "BUILD_CITY",
                        "node": b["node"],
                        "cost": COSTS["BUILD_CITY"],
                        "utility": 1.05 + 2.6 * economy(nodes[b["node"]]),
                        "first_edge": None,
                    }
                )
    if own["settlements_available"]:
        for node, d, edge in expansion(o):
            if d <= own["roads_available"]:
                goals.append(
                    {
                        "kind": "BUILD_SETTLEMENT",
                        "node": node,
                        "cost": [1 + d, 1 + d, 1, 1, 0],
                        "utility": 1 + 2.6 * economy(nodes[node]),
                        "first_edge": edge,
                        "roads": d,
                    }
                )
    # Development cards become a point/army route when building opportunities diminish.
    if o["development_bank_count"]:
        army = max(x["played_knights"] for x in o["players"])
        utility = 0.42 + (
            0.3
            if own["played_knights"] >= max(1, army - 1) and not own["has_army"]
            else 0
        )
        goals.append(
            {
                "kind": "BUY_DEVELOPMENT_CARD",
                "node": None,
                "cost": COSTS["BUY_DEVELOPMENT_CARD"],
                "utility": utility,
                "first_edge": None,
            }
        )
    for goal in goals:
        goal["eta_rolls"] = round(eta(o["own_hand"], goal["cost"], p, rates), 2)
        goal["priority"] = goal["utility"] / (5 + goal["eta_rolls"])
    goals.sort(key=lambda g: (-g["priority"], g["eta_rolls"]))
    return {
        "production_per_roll": p,
        "port_rates": rates,
        "goals": goals,
        "production_score": economy(p),
        "eta_note": "Mean resource flow with port conversion; not an expected stopping time or guarantee.",
    }


def rank_actions(o, analysis=None):
    if not o["legal_actions"]:
        return []
    color, nodes, owned, p, rates, own = context(o)
    initial = o["initial"]
    if initial:
        goals = []
    else:
        analysis = analysis or analyze(o)
        goals = analysis["goals"]
    hand = o["own_hand"]
    occupied = {b["node"] for b in o["board"]["buildings"]}

    def potential(h):
        return max(
            (
                g["utility"]
                / (
                    5
                    + eta(h, g["cost"], p, rates)
                    + 0.5 * sum(max(0, c - n) for c, n in zip(g["cost"], h))
                )
                for g in goals
            ),
            default=0,
        )

    before = potential(hand) if not initial else 0
    ranked = []
    for a in o["legal_actions"]:
        kind, value = a["type"], a["value"]
        score = -10.0
        reason = "Preserve resources for a useful build."
        if kind == "ROLL":
            score = 1
            reason = "Roll to collect resources."
        elif kind == "END_TURN":
            score = 0
            reason = "Save cards for the next productive build."
        elif kind in ("BUILD_SETTLEMENT", "BUILD_CITY"):
            if initial:
                from engine.opening import candidate

                opening = candidate(o, value)
                score = opening["score"]
                reason = f"{opening['candidate_pips']:g} site pips; combined production, starting cards, and port conversion give a city tempo of {opening['build_tempo']['BUILD_CITY']:g} rolls."
            else:
                goal = next(
                    (g for g in goals if g["kind"] == kind and g["node"] == value), None
                )
                score = 30 + 100 * (goal["priority"] if goal else 0.2)
                if own["own_points"] >= 9:
                    score = 10000
                reason = "Gain a point and productive capacity; prioritize builds near victory."
        elif kind == "BUILD_ROAD":
            if initial:
                hypothetical = {
                    **o,
                    "board": {
                        **o["board"],
                        "roads": o["board"]["roads"]
                        + [{"edge": value, "color": color}],
                    },
                }
                targets = expansion(hypothetical)
                scored = [
                    (
                        100
                        * (1 + 2.6 * economy(nodes[n]))
                        / (5 + eta(hand, [1 + d, 1 + d, 1, 1, 0], p, rates) + 2 * d),
                        n,
                        d,
                    )
                    for n, d, _ in targets
                ]
                best = max(scored, default=(0, None, None))
                score = best[0]
                reason = (
                    f"Reachable expansion: intersection {best[1]}, requiring {best[2]} more roads. Opponents block paths."
                    if best[1] is not None
                    else "No settlement within three further roads; search can compare road-award routes."
                )
            else:
                edge = tuple(sorted(value))
                targets = [g for g in goals if g["first_edge"] == edge]
                score = max([100 * g["priority"] - 3 for g in targets] or [-2])
                if own["longest_road"] >= 4 and not own["has_road"]:
                    score = max(score, 7)
                if o.get("free_roads_available", 0):
                    score += 20
                reason = "Build toward a reachable settlement; avoid roads with no expansion value."
        elif kind == "BUY_DEVELOPMENT_CARD":
            g = next((g for g in goals if g["kind"] == kind), None)
            score = 100 * g["priority"] if g else -1
            reason = "Pursue hidden points and army when this competes with the best build plan."
        elif kind in (
            "MARITIME_TRADE",
            "PLAY_YEAR_OF_PLENTY",
            "DISCARD_RESOURCE",
            "ACCEPT_TRADE",
            "CONFIRM_TRADE",
        ):
            h = list(hand)
            if kind == "MARITIME_TRADE":
                for r in value[:-1]:
                    if r:
                        h[RESOURCES.index(r)] -= 1
                h[RESOURCES.index(value[-1])] += 1
            elif kind == "PLAY_YEAR_OF_PLENTY":
                for r in value:
                    h[RESOURCES.index(r)] += 1
            elif kind == "DISCARD_RESOURCE":
                h[RESOURCES.index(value)] -= 1
            else:
                give, take = (
                    (value[5:10], value[:5])
                    if kind == "ACCEPT_TRADE"
                    else (value[:5], value[5:10])
                )
                h = [n - g + t for n, g, t in zip(h, give, take)]
            gain = potential(h) - before
            score = 500 * gain
            if kind == "MARITIME_TRADE":
                score -= 0.3
            if kind in ("ACCEPT_TRADE", "CONFIRM_TRADE"):
                score -= 0.15
            if kind == "PLAY_YEAR_OF_PLENTY":
                score -= 1
            if kind == "DISCARD_RESOURCE":
                score += 0.002 * hand[RESOURCES.index(value)]
            reason = "Compare this hand with the resource needs of reachable settlements, cities, and cards."
        elif kind == "PLAY_KNIGHT_CARD":
            blocked = next(
                (
                    t
                    for t in o["board"]["tiles"]
                    if t["coordinate"] == o["board"]["robber"]
                ),
                None,
            )
            hurts = bool(blocked and any(b["node"] in blocked["nodes"] for b in owned))
            score = 32 if hurts or not own["has_army"] else 2
            reason = "Unblock production or compete for Largest Army."
        elif kind == "PLAY_ROAD_BUILDING":
            score = 18
            reason = "Use free roads toward expansion and road awards."
        elif kind == "PLAY_MONOPOLY":
            r = RESOURCES.index(value)
            expected = 0.0
            for opponent in o["players"]:
                if opponent["color"] == color:
                    continue
                beliefs = o.get("belief", {}).get("hands", {}).get(opponent["color"])
                if beliefs and beliefs[r]["expected"] is not None:
                    expected += beliefs[r]["expected"]
                else:
                    production = [
                        sum(
                            nodes[b["node"]][j] * (2 if b["type"] == "CITY" else 1)
                            for b in o["board"]["buildings"]
                            if b["color"] == opponent["color"]
                        )
                        for j in range(5)
                    ]
                    expected += (
                        opponent["resource_count"]
                        * (production[r] + 0.02)
                        / (sum(production) + 0.1)
                    )
            score = 4 * expected - 5
            reason = "Estimate available cards from observed beliefs, or public production when beliefs are unavailable."
        elif kind == "MOVE_ROBBER":
            coordinate, victim = value
            tile = next(t for t in o["board"]["tiles"] if t["coordinate"] == coordinate)
            score = 0
            for b in o["board"]["buildings"]:
                if b["node"] in tile["nodes"]:
                    opponent = next(x for x in o["players"] if x["color"] == b["color"])
                    score += (
                        (6 - abs(7 - (tile["number"] or 7)))
                        * (2 if b["type"] == "CITY" else 1)
                        * (
                            -3
                            if b["color"] == color
                            else 1 + opponent["public_points"] / 5
                        )
                    )
            if victim:
                score += 2 + next(
                    x["public_points"] for x in o["players"] if x["color"] == victim
                )
            reason = "Reduce the leader’s production while preserving our own income."
        elif kind in ("REJECT_TRADE", "CANCEL_TRADE"):
            score = 0
        ranked.append({**a, "score": round(score, 5), "reason": reason})
    return sorted(ranked, key=lambda a: (-a["score"], a["id"]))


def position_value(o):
    """Bounded heuristic leaf value, deliberately not labeled win probability."""
    color, nodes, owned, p, rates, own = context(o)
    values = []
    for player in o["players"]:
        c = player["color"]
        production = [
            sum(
                nodes[b["node"]][r] * (2 if b["type"] == "CITY" else 1)
                for b in o["board"]["buildings"]
                if b["color"] == c
            )
            for r in range(5)
        ]
        points = player.get("own_points", player["public_points"])
        values.append(
            (
                c,
                points
                + 1.5 * economy(production)
                + 0.04 * min(12, player["resource_count"])
                + 0.12 * player["development_count"],
            )
        )
    own_value = next(v for c, v in values if c == color)
    exps = [math.exp((v - own_value) / 2) for c, v in values]
    return 1 / sum(exps)
