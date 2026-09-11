"""Joint resource beliefs from a single player's observations; never from hidden state."""

from collections import defaultdict
import random

RESOURCES = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]


class ResourceBelief:
    def __init__(self, colors, capacity=256):
        self.colors = list(colors)
        self.capacity = capacity
        self.worlds = {(0,) * (5 * len(colors)): 1.0}
        self.sampled = False
        self.discard_model_used = False
        self.inconsistent = False
        self.random = random.Random(41019)
        self.bounds = {color: [[0, 0] for _ in RESOURCES] for color in colors}

    def update(self, event, observer, own_hand, totals):
        self.update_bounds(event, observer, own_hand, totals)
        if self.inconsistent:
            return
        result = defaultdict(float)
        actor = self.colors.index(event["color"]) * 5
        kind = event["type"]
        for world, weight in self.worlds.items():
            base = list(world)
            for color, delta in event.get("deltas", {}).items():
                start = self.colors.index(color) * 5
                for r, amount in enumerate(delta):
                    base[start + r] += amount
            candidates = [(base, weight)]
            if kind == "MOVE_ROBBER" and event.get("victim"):
                victim = self.colors.index(event["victim"]) * 5
                count = sum(world[victim : victim + 5])
                candidates = []
                for r in range(5):
                    if not world[victim + r] or (
                        event.get("resource") is not None
                        and RESOURCES[r] != event["resource"]
                    ):
                        continue
                    copy = base.copy()
                    copy[victim + r] -= 1
                    copy[actor + r] += 1
                    candidates.append((copy, weight * world[victim + r] / count))
            elif kind == "DISCARD_RESOURCE":
                candidates = []
                known = event.get("resource")
                count = sum(world[actor : actor + 5])
                if known is None:
                    self.discard_model_used = True
                for r in range(5):
                    if not world[actor + r] or (
                        known is not None and RESOURCES[r] != known
                    ):
                        continue
                    copy = base.copy()
                    copy[actor + r] -= 1
                    # A strategic discard is NOT a random event. This optional model
                    # is explicitly labeled, and its posterior is not claimed exact.
                    candidates.append(
                        (copy, weight if known else weight * world[actor + r] / count)
                    )
            for candidate, probability in candidates:
                if min(candidate) < 0:
                    continue
                if kind == "PLAY_MONOPOLY":
                    resource = RESOURCES.index(event["value"])
                    if any(
                        candidate[i * 5 + resource]
                        for i, c in enumerate(self.colors)
                        if c != event["color"]
                    ):
                        continue
                if any(
                    sum(candidate[i * 5 : i * 5 + 5]) != totals[c]
                    for i, c in enumerate(self.colors)
                ):
                    continue
                own = self.colors.index(observer) * 5
                if candidate[own : own + 5] != list(own_hand):
                    continue
                if kind in ("OFFER_TRADE", "ACCEPT_TRADE"):
                    need = (
                        event["value"][:5]
                        if kind == "OFFER_TRADE"
                        else event["value"][5:10]
                    )
                    if any(candidate[actor + r] < need[r] for r in range(5)):
                        continue
                result[tuple(candidate)] += probability
        mass = sum(result.values())
        if not mass:
            self.worlds = {}
            self.inconsistent = True
            return
        self.worlds = {world: weight / mass for world, weight in result.items()}
        if len(self.worlds) > self.capacity:
            self.sampled = True
            states, weights = list(self.worlds), list(self.worlds.values())
            sampled = self.random.choices(states, weights, k=self.capacity)
            counts = defaultdict(float)
            for state in sampled:
                counts[state] += 1 / self.capacity
            self.worlds = dict(counts)

    def summary(self):
        if self.inconsistent:
            return {
                "status": "bounds_only",
                "worlds": 0,
                "hands": {
                    color: [
                        {
                            "resource": r,
                            "min": pair[0],
                            "max": pair[1],
                            "expected": None,
                            "distribution": {},
                        }
                        for r, pair in zip(RESOURCES, rows)
                    ]
                    for color, rows in self.bounds.items()
                },
                "assumptions": [
                    "Particle support was exhausted. Displaying conservative count bounds; no probability estimates."
                ],
            }
        hands = {}
        for i, color in enumerate(self.colors):
            rows = []
            for r, resource in enumerate(RESOURCES):
                probabilities = defaultdict(float)
                for world, weight in self.worlds.items():
                    probabilities[world[i * 5 + r]] += weight
                rows.append(
                    {
                        "resource": resource,
                        "min": min(probabilities),
                        "max": max(probabilities),
                        "expected": sum(n * p for n, p in probabilities.items()),
                        "distribution": dict(sorted(probabilities.items())),
                    }
                )
            hands[color] = rows
        return {
            "status": (
                "sampled"
                if self.sampled
                else "model_based" if self.discard_model_used else "exact"
            ),
            "worlds": len(self.worlds),
            "hands": hands,
            "assumptions": (
                [
                    "Hidden discards use a random-card approximation; real choices are strategic."
                ]
                if self.discard_model_used
                else []
            )
            + (
                ["Particle approximation can omit feasible hands."]
                if self.sampled
                else []
            ),
        }

    def update_bounds(self, event, observer, own_hand, totals):
        for color, delta in event.get("deltas", {}).items():
            for pair, change in zip(self.bounds[color], delta):
                pair[0] = max(0, pair[0] + change)
                pair[1] = max(0, pair[1] + change)
        if event["type"] == "PLAY_MONOPOLY":
            resource = RESOURCES.index(event["value"])
            for color in self.colors:
                if color != event["color"]:
                    self.bounds[color][resource] = [0, 0]
        if event["type"] in ("OFFER_TRADE", "ACCEPT_TRADE"):
            need = (
                event["value"][:5]
                if event["type"] == "OFFER_TRADE"
                else event["value"][5:10]
            )
            for pair, count in zip(self.bounds[event["color"]], need):
                pair[0] = max(pair[0], count)
        if event["type"] in ("MOVE_ROBBER", "DISCARD_RESOURCE"):
            source = (
                event.get("victim")
                if event["type"] == "MOVE_ROBBER"
                else event["color"]
            )
            if source:
                known = event.get("resource")
                feasible = [
                    i
                    for i, r in enumerate(RESOURCES)
                    if self.bounds[source][i][1] > 0 and (known is None or r == known)
                ]
                for i in feasible:
                    low, high = self.bounds[source][i]
                    self.bounds[source][i] = [
                        max(0, low - 1),
                        max(0, high - (1 if len(feasible) == 1 else 0)),
                    ]
                    if event["type"] == "MOVE_ROBBER":
                        pair = self.bounds[event["color"]][i]
                        self.bounds[event["color"]][i] = [
                            pair[0] + (1 if len(feasible) == 1 else 0),
                            pair[1] + 1,
                        ]
        self.bounds[observer] = [[n, n] for n in own_hand]
        # Tighten each hand with its observed card count, without inventing a distribution.
        for _ in range(5):
            for color, rows in self.bounds.items():
                count = totals[color]
                for i, pair in enumerate(rows):
                    pair[0] = max(
                        pair[0],
                        count - sum(p[1] for j, p in enumerate(rows) if j != i),
                        0,
                    )
                    pair[1] = min(
                        pair[1],
                        count - sum(p[0] for j, p in enumerate(rows) if j != i),
                        19,
                    )
