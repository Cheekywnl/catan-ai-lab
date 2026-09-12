"""Observation-only tactical policy over frozen strategic-v2 economics."""

from engine import RULESET
from engine.road_rules import longest_trail, award_owner as road_owner
from engine.fast_policy import rank_actions as base_rank


def longest_road(edges, blocked):
    return len(longest_trail(edges, blocked))


def road_lengths(o, added_edge=None, added_building=None):
    buildings = {b["node"]: b["color"] for b in o["board"]["buildings"]}
    if added_building is not None:
        buildings[added_building] = o["viewer"]
    values = {}
    for player in o["players"]:
        color = player["color"]
        edges = {
            tuple(sorted(r["edge"])) for r in o["board"]["roads"] if r["color"] == color
        }
        if added_edge is not None and color == o["viewer"]:
            edges.add(tuple(sorted(added_edge)))
        blocked = tuple(sorted(n for n, owner in buildings.items() if owner != color))
        values[color] = longest_road(tuple(sorted(edges)), blocked)
    return values


def tactical_values(o):
    """Immediate points and exact public award transfers for legal moves."""
    if o["initial"] or o["ruleset"] != RULESET:
        return {}
    viewer = o["viewer"]
    own = next(p for p in o["players"] if p["color"] == viewer)
    road_holder = next((p["color"] for p in o["players"] if p["has_road"]), None)
    rival_knights = max(
        p["played_knights"] for p in o["players"] if p["color"] != viewer
    )
    values = {}
    for a in o["legal_actions"]:
        kind = a["type"]
        points, gained, removed = 0, None, None
        if kind in ("BUILD_SETTLEMENT", "BUILD_CITY"):
            points = 1
        if kind == "BUILD_ROAD" or kind == "BUILD_SETTLEMENT":
            # Settlements can split an opponent's road, which can transfer the award.
            lengths = road_lengths(
                o,
                a["value"] if kind == "BUILD_ROAD" else None,
                a["value"] if kind == "BUILD_SETTLEMENT" else None,
            )
            holder = road_owner(lengths, road_holder)
            if holder == viewer and road_holder != viewer:
                points += 2
                gained = "Longest Road"
            if holder != road_holder and road_holder:
                removed = road_holder
        if (
            kind == "PLAY_KNIGHT_CARD"
            and not own["has_army"]
            and own["played_knights"] + 1 >= 3
            and own["played_knights"] + 1 > rival_knights
        ):
            points += 2
            gained = "Largest Army"
        values[a["id"]] = {
            "points_gained": points,
            "wins_now": viewer == o["turn_owner"] and own["own_points"] + points >= 10,
            "award_gained": gained,
            "road_award_removed_from": removed,
        }
    return values


def rank_actions(o):
    ranked = base_rank(o)
    tactical = tactical_values(o)
    for action in ranked:
        info = tactical.get(action["id"], {})
        if info.get("wins_now"):
            action["score"] = 100000 + info["points_gained"]
            action["reason"] = (
                "Win this turn: the public board and your own points guarantee at least ten points."
            )
        elif info.get("award_gained"):
            action["score"] += 35
            action["reason"] = (
                f"Gain {info['award_gained']} and two points with this move."
            )
        elif info.get("road_award_removed_from") != o["viewer"] and info.get(
            "road_award_removed_from"
        ):
            action["score"] += 12
            action["reason"] = (
                "Split the opponent's road and remove their two-point award."
            )
        if info:
            action["tactical"] = info
    return sorted(ranked, key=lambda a: (-a["score"], a["id"]))
