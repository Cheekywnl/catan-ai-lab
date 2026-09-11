"""Transparent baseline and public-information opening draft search. No hidden game argument."""

import math
import random

RESOURCES = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
COSTS = {
    "BUILD_ROAD": [1, 1, 0, 0, 0],
    "BUILD_SETTLEMENT": [1, 1, 1, 1, 0],
    "BUILD_CITY": [0, 0, 0, 2, 3],
    "BUY_DEVELOPMENT_CARD": [0, 0, 1, 1, 1],
}


def production(observation, color, extra=None):
    result = [0.0] * 5
    buildings = [b for b in observation["board"]["buildings"] if b["color"] == color]
    if extra is not None:
        buildings = buildings + [{"node": extra, "type": "SETTLEMENT"}]
    for building in buildings:
        for tile in observation["board"]["tiles"]:
            if building["node"] in tile["nodes"] and tile["resource"]:
                r = RESOURCES.index(tile["resource"])
                result[r] += (6 - abs(7 - tile["number"])) * (
                    2 if building["type"] == "CITY" else 1
                )
    return result


def economy_score(pips):
    # Preference scale, not a win probability. Ore/wheat enable cities and cards.
    weights = [1.0, 0.9, 0.8, 1.25, 1.2]
    return (
        sum(weights[i] * v for i, v in enumerate(pips))
        + sum(2.0 * math.sqrt(v) for v in pips)
        + 2 * min(pips[3], pips[4])
    )


def rank_actions(observation):
    color = observation["viewer"]
    hand = observation["own_hand"]
    actions = observation["legal_actions"]
    own = next(p for p in observation["players"] if p["color"] == color)
    score_before = economy_score(production(observation, color))
    rankings = []
    for action in actions:
        kind, value = action["type"], action["value"]
        reason = "Keep the turn moving."
        score = {
            "END_TURN": 0,
            "ROLL": 10,
            "BUY_DEVELOPMENT_CARD": 45,
            "PLAY_KNIGHT_CARD": 46,
            "PLAY_ROAD_BUILDING": 60,
            "PLAY_MONOPOLY": 25,
            "PLAY_YEAR_OF_PLENTY": 55,
            "ACCEPT_TRADE": -1,
            "REJECT_TRADE": 0,
            "CANCEL_TRADE": 0,
            "CONFIRM_TRADE": 20,
        }.get(kind, 0)
        if kind == "BUILD_SETTLEMENT":
            gain = economy_score(production(observation, color, value)) - score_before
            score = 100 + gain
            reason = f"Adds {gain:.1f} resource-balance score; includes production, diversity, and ore–wheat balance."
        elif kind == "BUILD_CITY":
            score = (
                95 + economy_score(production(observation, color, value)) - score_before
            )
            reason = "One point and doubled production at an existing settlement."
        elif kind == "BUILD_ROAD":
            neighbors = {n["id"]: n["neighbors"] for n in observation["board"]["nodes"]}
            occupied = {b["node"] for b in observation["board"]["buildings"]}
            candidates = set(value)
            for node in value:
                candidates.update(neighbors[node])
            potential = max(
                [
                    economy_score(production(observation, color, n)) - score_before
                    for n in candidates
                    if n not in occupied
                    and not any(x in occupied for x in neighbors[n])
                ]
                or [0]
            )
            # Avoid exhausting roads when settlement sites are unavailable; pursue longest road too.
            score = 12 + potential * 0.6 + (5 if own["roads_available"] < 9 else 0)
            if own["settlements_available"] == 0:
                score = 4 if own["roads_available"] else -1
            reason = "Connect toward productive legal expansion sites; modest value for road length."
        elif kind == "DISCARD_RESOURCE":
            r = RESOURCES.index(value)
            score = hand[r] - [1, 1, 1, 2, 3][r]
            reason = "Discard the largest surplus above the next-build reserve."
        elif kind == "MOVE_ROBBER":
            coordinate, victim = value
            tile = next(
                t
                for t in observation["board"]["tiles"]
                if t["coordinate"] == coordinate
            )
            score = 0
            for building in observation["board"]["buildings"]:
                if building["node"] in tile["nodes"]:
                    points = next(
                        p["public_points"]
                        for p in observation["players"]
                        if p["color"] == building["color"]
                    )
                    score += (
                        (6 - abs(7 - (tile["number"] or 7)))
                        * (2 if building["type"] == "CITY" else 1)
                        * (-3 if building["color"] == color else 1 + points / 10)
                    )
            if victim:
                score += 2
            reason = (
                "Block visible opponent production while avoiding our own settlements."
            )
        elif kind == "MARITIME_TRADE":
            updated = hand.copy()
            for resource in value[:-1]:
                if resource:
                    updated[RESOURCES.index(resource)] -= 1
            updated[RESOURCES.index(value[-1])] += 1
            score = -2
            for target, cost in COSTS.items():
                if target == "BUILD_CITY" and not any(
                    b["color"] == color and b["type"] == "SETTLEMENT"
                    for b in observation["board"]["buildings"]
                ):
                    continue
                if target == "BUILD_SETTLEMENT" and not own["settlements_available"]:
                    continue
                if target == "BUILD_ROAD" and not own["roads_available"]:
                    continue
                before = sum(max(0, c - h) for c, h in zip(cost, hand))
                after = sum(max(0, c - h) for c, h in zip(cost, updated))
                if after < before:
                    score = max(score, (22 if after == 0 else 2) + (before - after))
            reason = "Trade only when it reduces the resource shortfall for a build."
        elif kind in ("ACCEPT_TRADE", "CONFIRM_TRADE"):
            giving, receiving = (
                (value[5:10], value[:5])
                if kind == "ACCEPT_TRADE"
                else (value[:5], value[5:10])
            )
            weights = [1, 1, 0.8, 1.2, 1.2]
            gain = sum((b - a) * w for a, b, w in zip(giving, receiving, weights))
            score = 5 + gain if gain >= 0 else -5
            reason = "Accept only a nonnegative weighted resource exchange."
        elif kind == "PLAY_MONOPOLY":
            # Use tracked beliefs only if available. Never read opponents' real cards.
            r = RESOURCES.index(value)
            hands = observation.get("belief", {}).get("hands", {})
            score += sum(
                (hands.get(p["color"], [{"expected": 0}] * 5)[r]["expected"] or 0)
                for p in observation["players"]
                if p["color"] != color
            )
            reason = "Use observed-history resource expectations, when available."
        rankings.append({**action, "score": round(score, 4), "reason": reason})
    return sorted(rankings, key=lambda a: (-a["score"], a["id"]))


def draft_search(observation, trials=32):
    """Root Monte Carlo over remaining opening settlements; roads are separate.

    Samples rank-weighted opponent choices from public geometry. Evaluates the eventual
    resource economy, NOT wins or a complete game rollout. It does not access a Game.
    """
    if observation["phase"] != "BUILD_INITIAL_SETTLEMENT":
        raise ValueError(
            "Draft search is available when placing an opening settlement."
        )
    trials = max(4, min(128, int(trials)))
    color = observation["viewer"]
    neighbors = {n["id"]: set(n["neighbors"]) for n in observation["board"]["nodes"]}
    occupied = {b["node"] for b in observation["board"]["buildings"]}
    order = [p["color"] for p in observation["players"]]
    placements = len(occupied)
    remaining = (order + list(reversed(order)))[placements + 1 :]
    candidates = rank_actions(observation)[:10]
    output = []
    for candidate in candidates:
        values = []
        for trial in range(trials):
            rng = random.Random(
                971 + trial
            )  # common scenario randomness, independent of game RNG
            used = set(occupied) | {candidate["value"]}
            added = {c: [] for c in order}
            added[color].append(candidate["value"])
            for player in remaining:
                feasible = [
                    n
                    for n in sorted(neighbors)
                    if n not in used and not (neighbors[n] & used)
                ]
                if not feasible:
                    break
                ranks = sorted(
                    feasible,
                    key=lambda n: (
                        -economy_score(production(observation, player, n)),
                        n,
                    ),
                )[:5]
                node = rng.choices(ranks, weights=[5, 4, 3, 2, 1][: len(ranks)])[0]
                used.add(node)
                added[player].append(node)
            pips = production(observation, color)
            for n in added[color]:
                extra = production(observation, color, n)
                old = production(observation, color)
                pips = [a + b - c for a, b, c in zip(pips, extra, old)]
            values.append(economy_score(pips))
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
        output.append(
            {
                **candidate,
                "draft_score": round(mean, 2),
                "standard_error": round(math.sqrt(variance / len(values)), 2),
                "samples": trials,
            }
        )
    return {
        "method": "public-opening-draft-monte-carlo",
        "objective": "Heuristic resource economy after the draft; not win probability. Opponents use sampled production preferences. Roads and continuation play are not rolled out.",
        "candidates": sorted(output, key=lambda a: (-a["draft_score"], a["id"])),
        "trials_per_candidate": trials,
    }
