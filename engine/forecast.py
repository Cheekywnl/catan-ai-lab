"""Exact dice exposure and model-conditional winning frequencies from full games."""

import math
import random
import time
from engine.policy import RESOURCES


def wilson(wins, n):
    if not n:
        return [0.0, 1.0]
    z = 1.959963984540054
    p = wins / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0, center - radius), min(1, center + radius)]


def dice_exposure(o):
    order = [p["color"] for p in o["players"]]
    owner = order.index(o["turn_owner"])
    viewer = order.index(o["viewer"])
    gap = (viewer - owner) % 4 or 4
    owner_has_rolled = next(
        p["has_rolled"] for p in o["players"] if p["color"] == o["turn_owner"]
    )
    rolls = 0 if o["initial"] else gap - int(owner_has_rolled)
    results = []
    for p in o["players"]:
        production = [0.0] * 5
        numbers = [set() for _ in range(5)]
        all_numbers = set()
        for b in o["board"]["buildings"]:
            if b["color"] != p["color"]:
                continue
            for t in o["board"]["tiles"]:
                if (
                    b["node"] not in t["nodes"]
                    or not t["resource"]
                    or t["coordinate"] == o["board"]["robber"]
                ):
                    continue
                r = RESOURCES.index(t["resource"])
                chance = (6 - abs(7 - t["number"])) / 36
                production[r] += chance * (2 if b["type"] == "CITY" else 1)
                numbers[r].add(t["number"])
                all_numbers.add(t["number"])
        probabilities = [sum((6 - abs(7 - n)) / 36 for n in nums) for nums in numbers]
        p_any = sum((6 - abs(7 - n)) / 36 for n in all_numbers)
        results.append(
            {
                "color": p["color"],
                "expected_cards": [round(x * rolls, 4) for x in production],
                "probability_resource": [
                    round(1 - (1 - q) ** rolls, 6) for q in probabilities
                ],
                "probability_any_income": round(1 - (1 - p_any) ** rolls, 6),
                "next_turn_in_seats": (order.index(p["color"]) - owner) % 4,
            }
        )
    return {
        "rolls_before_next_turn": rolls,
        "players": results,
        "assumption": "Exact independent-dice probabilities if buildings and robber stay fixed and supply is sufficient. Trading, spending, robber moves, and future builds can change the position.",
    }


def forecast(o, samples=12, horizon=1600, progress=None):
    from engine.planning import sample_game
    from engine.session import Session, decode_action
    from engine.fast_policy import choose_action

    samples = max(4, min(128, int(samples)))
    horizon = max(1, min(6000, int(horizon)))
    rng = random.Random(86321)
    wins = {p["color"]: 0 for p in o["players"]}
    completed = 0
    transitions = 0
    started = time.perf_counter()
    for i in range(samples):
        for attempt in range(64):
            try:
                game = sample_game(o, rng)
                break
            except ValueError:
                if attempt == 63:
                    raise ValueError(
                        "Could not sample a position consistent with the observed legal moves."
                    )
        sim = Session.__new__(Session)
        sim.game = game
        sim._geometry = {k: o["board"][k] for k in ("tiles", "nodes", "edges", "ports")}
        sim.intents = []
        sim.events = []
        sim.trackers = {}
        sim.track_beliefs = False
        for _ in range(horizon):
            if game.winning_color():
                break
            observation = sim.observation(
                game.state.current_color().value, False, False, compact=True
            )
            game.execute(decode_action(choose_action(observation)))
            transitions += 1
        winner = game.winning_color()
        if winner:
            completed += 1
            wins[winner.value] += 1
        if progress and ((i + 1) % 4 == 0 or i == samples - 1):
            progress(i + 1, samples)
    return {
        "samples": samples,
        "completed": completed,
        "truncated": samples - completed,
        "transitions": transitions,
        "elapsed_ms": round(1000 * (time.perf_counter() - started)),
        "players": [
            {
                "color": color,
                "wins": count,
                "win_probability": count / samples if completed == samples else None,
                "wilson_95_interval": (
                    wilson(count, samples) if completed == samples else None
                ),
                "censoring_bounds": [
                    count / samples,
                    (count + samples - completed) / samples,
                ],
            }
            for color, count in wins.items()
        ],
        "assumptions": [
            "Winning frequencies are conditional on sampled hidden cards and the strategic-v2 continuation policy for every player.",
            "The interval measures Monte Carlo sampling uncertainty; it does not cover opponent-model or belief-model error.",
            "When a continuation is truncated, probabilities are withheld and best/worst censoring bounds are returned.",
            "These are model-based forecasts, not equilibrium values or calibrated human-opponent predictions.",
        ],
    }
