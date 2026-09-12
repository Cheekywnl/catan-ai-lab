"""Joint development-card beliefs conditional on public turn history.

Enumerate placements of at most five hidden VP cards in old/new hand slots and
the deck. Non-VP types remain exchangeable; strategic retention is not modeled.
Only observation fields enter this module, never the authoritative game state.
"""

from collections import Counter
from functools import lru_cache
from itertools import product
from math import comb

from catanatron.models.decks import starting_devcard_bank

VP = "VICTORY_POINT"


def choose(n, k):
    return comb(n, k) if 0 <= k <= n else 0


@lru_cache(maxsize=1024)
def _allocations(vp, deck_size, specs):
    # spec: color, total cards, newly bought cards, old VP cap, total VP min/max.
    options = []
    for _, n, new, old_cap, lower, upper in specs:
        rows = []
        for held in range(lower, min(n, vp, upper) + 1):
            ages = tuple(
                (k, choose(n - new, held - k) * choose(new, k))
                for k in range(min(new, held) + 1)
                if held - k <= old_cap and choose(n - new, held - k) * choose(new, k)
            )
            weight = sum(w for _, w in ages)
            if weight:
                rows.append((held, weight, ages))
        options.append(rows)
    worlds = []
    for rows in product(*options):
        remaining = vp - sum(row[0] for row in rows)
        weight = choose(deck_size, remaining)
        for row in rows:
            weight *= row[1]
        if weight:
            worlds.append(
                (tuple(row[0] for row in rows), weight, tuple(row[2] for row in rows))
            )
    if not worlds:
        raise ValueError(
            "Development-card observations contradict public turn history or the game outcome."
        )
    return tuple(worlds)


def joint_model(o):
    pool = Counter(starting_devcard_bank())
    for player in o["players"]:
        pool.subtract(player["played_development"])
    pool.subtract(o["own_development"])
    if min(pool.values()) < 0:
        raise ValueError("Inconsistent development-card observations.")
    specs = []
    for player in o["players"]:
        color = player["color"]
        if color == o["viewer"]:
            continue
        n = player["development_count"]
        new = player["development_bought_this_turn"]
        if not 0 <= new <= n:
            raise ValueError("Invalid development-card purchase count.")
        previous = player.get("last_completed_turn_public_points")
        old_cap = n if previous is None else 9 - previous
        lower, upper = 0, n
        if o["winner"] == color:
            lower = max(0, 10 - player["public_points"])
        elif not o["winner"] and not o["initial"] and color == o["turn_owner"]:
            upper = 9 - player["public_points"]
        specs.append((color, n, new, old_cap, lower, upper))
    deck_size = sum(pool.values()) - sum(spec[1] for spec in specs)
    if deck_size < 0 or deck_size != o["development_bank_count"]:
        raise ValueError("Development-card hand totals contradict the remaining deck.")
    specs = tuple(specs)
    return pool, specs, _allocations(pool[VP], deck_size, specs)


def development_beliefs(o):
    pool, specs, worlds = joint_model(o)
    mass = sum(world[1] for world in worlds)
    non_vp = sum(pool.values()) - pool[VP]
    hands, constraints = {}, {}
    for i, (color, n, new, old_cap, lower, upper) in enumerate(specs):
        marginal = Counter()
        for held, weight, _ in worlds:
            marginal[held[i]] += weight
        hands[color] = {}
        for card, count in pool.items():
            expected = present = 0.0
            for held, weight in marginal.items():
                probability = weight / mass
                if card == VP:
                    expected += probability * held
                    present += probability * (held > 0)
                else:
                    draw = n - held
                    expected += probability * draw * count / non_vp if non_vp else 0
                    present += probability * (
                        1 - choose(non_vp - count, draw) / choose(non_vp, draw)
                    )
            hands[color][card] = {
                "expected": expected,
                "probability_at_least_one": max(0.0, min(1.0, present)),
            }
        constraints[color] = {
            "vp_min": min(marginal),
            "vp_max": max(marginal),
            "old_vp_max": min(n - new, old_cap),
            "new_cards": new,
        }
    return {
        "status": "history-conditioned-exchangeable-pool-model",
        "unknown_pool": dict(pool),
        "hands": hands,
        "constraints": constraints,
        "assumption": "Joint card placements condition on public completed turns, purchases, and the observed game outcome. Old and newly bought cards are sampled together. Non-VP types remain exchangeable; strategic retention is not modeled.",
    }


def sample_development(o, rng):
    pool, specs, worlds = joint_model(o)
    held, _, ages = rng.choices(worlds, weights=[world[1] for world in worlds])[0]
    non_vp = list(
        Counter({card: n for card, n in pool.items() if card != VP}).elements()
    )
    rng.shuffle(non_vp)
    hands = {o["viewer"]: dict(o["own_development"])}
    new_cards = {}
    for i, (color, n, new, _, _, _) in enumerate(specs):
        new_vp = rng.choices(ages[i], weights=[weight for _, weight in ages[i]])[0][0]
        new_non_vp = new - new_vp
        draw = n - held[i]
        new_cards[color] = Counter(non_vp[:new_non_vp])
        new_cards[color][VP] = new_vp
        hand = Counter(non_vp[:draw])
        hand[VP] = held[i]
        hands[color] = dict(hand)
        del non_vp[:draw]
    deck = non_vp + [VP] * (pool[VP] - sum(held))
    rng.shuffle(deck)
    return hands, new_cards, deck
