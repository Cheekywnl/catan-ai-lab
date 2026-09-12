"""Hidden-world sampling and bounded Monte Carlo continuation search.

The only entry point takes a JSON-serializable player observation. Real hands,
real deck order, and the game's seed/random state are never accepted.
"""

from collections import Counter, defaultdict
import copy
import math
import random
import time

from engine.policy import RESOURCES
from engine.strategy import position_value
from engine.fast_policy import choose_action
from catanatron.models.decks import starting_devcard_bank
from catanatron.models.enums import DEVELOPMENT_CARDS, ActionPrompt
from catanatron.models.player import Color, SimplePlayer
from catanatron.game import Game
from catanatron.state import State, PLAYER_INITIAL_STATE
from catanatron.models.actions import generate_playable_actions
from catanatron.serialization import map_from_json, board_from_json


def development_beliefs(o):
    pool = Counter(starting_devcard_bank())
    for p in o["players"]:
        pool.subtract(p["played_development"])
    pool.subtract(o["own_development"])
    if min(pool.values()) < 0:
        raise ValueError("Inconsistent development-card observations.")
    total = sum(pool.values())
    hands = {}
    for p in o["players"]:
        if p["color"] == o["viewer"]:
            continue
        n = p["development_count"]
        hands[p["color"]] = {
            card: {
                "expected": n * count / total if total else 0.0,
                "probability_at_least_one": (
                    1 - math.comb(total - count, n) / math.comb(total, n)
                    if total and n <= total - count
                    else float(n > 0 and count > 0)
                ),
            }
            for card, count in pool.items()
        }
    # Nonterminal turn owners cannot already hold enough hidden VP cards to win.
    owner = next(p for p in o["players"] if p["color"] == o["turn_owner"])
    if not o["initial"] and not o["winner"] and owner["color"] != o["viewer"]:
        n_owner = owner["development_count"]
        vp = pool["VICTORY_POINT"]
        limit = 9 - owner["public_points"]
        if limit < min(vp, n_owner):

            def choose(n, k):
                return math.comb(n, k) if 0 <= k <= n else 0

            weights = {
                j: choose(vp, j) * choose(total - vp, n_owner - j)
                for j in range(max(0, limit + 1))
            }
            mass = sum(weights.values())
            if not mass:
                raise ValueError(
                    "Development-card model contradicts the observed nonterminal game."
                )
            for p in o["players"]:
                if p["color"] == o["viewer"]:
                    continue
                for card, count in pool.items():
                    expected = present = 0.0
                    for j, w in weights.items():
                        if not w:
                            continue
                        if card == "VICTORY_POINT":
                            counts = {j: 1.0}
                        else:
                            draw = n_owner - j
                            den = choose(total - vp, draw)
                            counts = {
                                x: choose(count, x)
                                * choose(total - vp - count, draw - x)
                                / den
                                for x in range(min(count, draw) + 1)
                            }
                        for held, probability in counts.items():
                            weight = w / mass * probability
                            if p["color"] == owner["color"]:
                                expected += weight * held
                                present += weight * (held > 0)
                            else:
                                size = total - n_owner
                                remaining = count - held
                                n = p["development_count"]
                                expected += weight * n * remaining / size if size else 0
                                present += (
                                    weight
                                    * (
                                        1
                                        - choose(size - remaining, n) / choose(size, n)
                                    )
                                    if n
                                    else 0
                                )
                    hands[p["color"]][card] = {
                        "expected": expected,
                        "probability_at_least_one": max(0.0, min(1.0, present)),
                    }
    return {
        "status": "exchangeable-pool-model",
        "unknown_pool": dict(pool),
        "hands": hands,
        "assumption": "Unknown cards are exchangeable after known plays and your own cards. The model also conditions on the turn owner not already having enough hidden points to win. Strategic retention is not modeled.",
    }


def sample_hands(o, rng):
    colors = [p["color"] for p in o["players"]]
    totals = {p["color"]: p["resource_count"] for p in o["players"]}
    own_index = colors.index(o["viewer"])
    worlds = [
        w
        for w in o.get("joint_belief", [])
        if len(w["hands"]) == len(colors) * 5
        and w["weight"] > 0
        and all(n >= 0 for n in w["hands"])
        and w["hands"][own_index * 5 : own_index * 5 + 5] == list(o["own_hand"])
        and all(
            sum(w["hands"][i * 5 : i * 5 + 5]) == totals[c]
            for i, c in enumerate(colors)
        )
        and all(
            sum(w["hands"][i * 5 + r] for i in range(len(colors))) <= 19
            for r in range(5)
        )
    ]
    if worlds:
        world = rng.choices(worlds, [w["weight"] for w in worlds])[0]["hands"]
        return {c: list(world[i * 5 : i * 5 + 5]) for i, c in enumerate(colors)}
    # Reconstruct feasible joint inventories with hard public totals and supply limits.
    # The proposal is a bounded sequential sampler, not a uniform posterior.
    bounds = o.get("belief", {}).get("hands", {})
    totals = {p["color"]: p["resource_count"] for p in o["players"]}
    own = o["viewer"]
    for attempt in range(256):
        result = {own: list(o["own_hand"])}
        capacity = [19 - n for n in o["own_hand"]]
        remaining = [c for c in colors if c != own]
        rng.shuffle(remaining)
        valid = True
        for c in remaining:
            rows = bounds.get(
                c, [{"min": 0, "max": min(19, totals[c])} for _ in RESOURCES]
            )
            lo = [r["min"] for r in rows]
            hi = [min(r["max"], cap) for r, cap in zip(rows, capacity)]
            if any(a > b for a, b in zip(lo, hi)) or not sum(lo) <= totals[c] <= sum(
                hi
            ):
                valid = False
                break
            hand = lo[:]
            left = totals[c] - sum(hand)
            while left:
                choices = [r for r in range(5) if hand[r] < hi[r]]
                r = rng.choice(choices)
                hand[r] += 1
                left -= 1
            result[c] = hand
            capacity = [a - b for a, b in zip(capacity, hand)]
        if valid:
            return result
    raise ValueError(
        "Could not sample a hand consistent with the available resource bounds."
    )


def sample_game(o, rng):
    """Reconstruct simulation state from explicitly public data and a sampled world."""
    from engine.session import canonical, action_value

    public = o["simulation"]
    colors = tuple(Color(p["color"]) for p in o["players"])
    hands = sample_hands(o, rng)
    pool = development_beliefs(o)["unknown_pool"]
    deck = list(Counter(pool).elements())
    rng.shuffle(deck)
    dev = {o["viewer"]: dict(o["own_development"])}
    for p in o["players"]:
        if p["color"] == o["viewer"]:
            continue
        count = p["development_count"]
        dev[p["color"]] = dict(Counter(deck[:count]))
        del deck[:count]
    state = State([], initialize=False)
    state.random = random.Random(rng.getrandbits(64))
    state.players = [SimplePlayer(c) for c in colors]
    state.colors = colors
    state.color_to_index = {c: i for i, c in enumerate(colors)}
    state.discard_limit = 7
    state.friendly_robber = False
    state.board = board_from_json(public["board"], map_from_json(public["map"]))
    state.resource_freqdeck = [19 - sum(h[r] for h in hands.values()) for r in range(5)]
    if any(n < 0 for n in state.resource_freqdeck):
        raise ValueError("Sample violates the finite resource supply.")
    state.development_listdeck = deck
    state.player_state = {}
    for i, p in enumerate(o["players"]):
        key = f"P{i}"
        color = p["color"]
        own = color == o["viewer"]
        values = dict(PLAYER_INITIAL_STATE)
        for field, source in [
            ("VICTORY_POINTS", "public_points"),
            ("ROADS_AVAILABLE", "roads_available"),
            ("SETTLEMENTS_AVAILABLE", "settlements_available"),
            ("CITIES_AVAILABLE", "cities_available"),
            ("HAS_ROAD", "has_road"),
            ("HAS_ARMY", "has_army"),
            ("LONGEST_ROAD_LENGTH", "longest_road"),
        ]:
            values[field] = p[source]
        values["ACTUAL_VICTORY_POINTS"] = p["public_points"] + dev[color].get(
            "VICTORY_POINT", 0
        )
        values["HAS_ROLLED"] = p["has_rolled"]
        values["HAS_PLAYED_DEVELOPMENT_CARD_IN_TURN"] = p["has_played_development"]
        new_cards = (
            Counter(
                rng.sample(
                    list(Counter(dev[color]).elements()),
                    p["development_bought_this_turn"],
                )
            )
            if not own
            else Counter()
        )
        for r, n in zip(RESOURCES, hands[color]):
            values[r + "_IN_HAND"] = n
        for card in DEVELOPMENT_CARDS:
            values[card + "_IN_HAND"] = dev[color].get(card, 0)
            values["PLAYED_" + card] = p["played_development"][card]
            if card != "VICTORY_POINT":
                values[card + "_OWNED_AT_START"] = (
                    o["own_dev_playable_age"][card]
                    if own
                    else dev[color].get(card, 0) > new_cards[card]
                )
        state.player_state.update({key + "_" + field: v for field, v in values.items()})
    state.buildings_by_color = {
        Color(c): defaultdict(
            list,
            {
                kind: [tuple(x) if isinstance(x, list) else x for x in rows]
                for kind, rows in buildings.items()
            },
        )
        for c, buildings in public["buildings_by_color"].items()
    }
    state.action_records = []
    state.num_turns = public["num_turns"]
    state.current_player_index = colors.index(Color(o["actor"]))
    state.current_turn_index = colors.index(Color(o["turn_owner"]))
    state.current_prompt = ActionPrompt(o["phase"])
    state.is_initial_build_phase = o["initial"]
    for name in (
        "is_discarding",
        "is_moving_knight",
        "is_road_building",
        "is_resolving_trade",
    ):
        setattr(state, name, public[name])
    state.discard_counts = list(public["discard_counts"])
    state.free_roads_available = o["free_roads_available"]
    state.current_trade = tuple(public["current_trade"])
    state.acceptees = tuple(public["acceptees"])
    game = Game([], initialize=False)
    game.state = state
    game.random = state.random
    game.seed = 0
    game.id = "sampled-world"
    game.vps_to_win = 10
    game.friendly_robber = False
    game.playable_actions = generate_playable_actions(state)
    if (game.winning_color().value if game.winning_color() else None) != o["winner"]:
        raise ValueError("Sample contradicts the publicly observed game outcome.")
    # Legal actions are also observed information, including supply availability.
    actual = {
        canonical({k: a[k] for k in ("type", "color", "value")})
        for a in o["legal_actions"]
    }
    generated = {canonical(action_value(a)) for a in game.playable_actions}
    if o["viewer"] == o["actor"] and actual != generated:
        raise ValueError("Sample disagrees with the observed legal moves.")
    return game


def search(o, budget=32, horizon=64, max_candidates=6, search_seed=1701, progress=None):
    """UCB root allocation plus actual game continuations under observation-only policies.

    Finite-horizon samples get a heuristic leaf value. Terminal samples get 1/0.
    Report both counts, and never present mixed scores as win probabilities.
    """
    from engine.session import Session, decode_action

    if o["viewer"] != o["actor"] or not o["legal_actions"]:
        raise ValueError("Select the player who has the current decision.")
    budget = max(4, min(256, int(budget)))
    horizon = max(4, min(6000, int(horizon)))
    max_candidates = max(2, min(12, int(max_candidates)))
    from engine.tactics import rank_actions as tactical_rank

    rankings = tactical_rank(o)
    candidates = rankings[:max_candidates]
    # Preserve diverse action types when the root has many similar trades/builds.
    if not o["initial"]:
        seen = {a["type"] for a in candidates}
        for a in rankings:
            if a["type"] not in seen and a["type"] in (
                "END_TURN",
                "BUILD_CITY",
                "BUILD_SETTLEMENT",
                "BUY_DEVELOPMENT_CARD",
                "PLAY_MONOPOLY",
                "PLAY_YEAR_OF_PLENTY",
            ):
                candidates.append(a)
                seen.add(a["type"])
        candidates = candidates[:12]
    budget = max(budget, len(candidates) * 2)
    stats = [
        {"n": 0, "sum": 0.0, "sq": 0.0, "terminal": 0, "wins": 0} for _ in candidates
    ]
    rng = random.Random(search_seed)
    started = time.perf_counter()
    transitions = 0
    rejections = 0
    for trial in range(budget):
        unvisited = [i for i, s in enumerate(stats) if s["n"] < 2]
        index = (
            unvisited[0]
            if unvisited
            else max(
                range(len(stats)),
                key=lambda i: stats[i]["sum"] / stats[i]["n"]
                + 0.55 * math.sqrt(math.log(trial + 1) / stats[i]["n"]),
            )
        )
        game = None
        for attempt in range(64):
            try:
                game = sample_game(o, rng)
                break
            except ValueError as e:
                rejections += 1
                if attempt == 63:
                    raise ValueError(
                        "Beliefs could not produce a world matching the observed legal actions."
                    ) from e
        game.execute(decode_action(candidates[index]))
        transitions += 1
        # Lightweight observation shell: no real Session or historical RNG reaches it.
        sim = Session.__new__(Session)
        sim.game = game
        sim._geometry = {k: o["board"][k] for k in ("tiles", "nodes", "edges", "ports")}
        sim.intents = []
        sim.events = []
        sim.trackers = {}
        sim.track_beliefs = False
        for depth in range(horizon - 1):
            if game.winning_color():
                break
            actor = game.state.current_color().value
            view = sim.observation(actor, False, False, compact=True)
            game.execute(decode_action(choose_action(view)))
            transitions += 1
        winner = game.winning_color()
        value = (
            float(winner.value == o["viewer"])
            if winner
            else position_value(
                sim.observation(o["viewer"], False, False, compact=True)
            )
        )
        s = stats[index]
        s["n"] += 1
        s["sum"] += value
        s["sq"] += value * value
        s["terminal"] += winner is not None
        s["wins"] += bool(winner and winner.value == o["viewer"])
        if progress and ((trial + 1) % 4 == 0 or trial == budget - 1):
            progress(trial + 1, budget)
    results = []
    for action, s in zip(candidates, stats):
        mean = s["sum"] / s["n"]
        variance = max(0, (s["sq"] - s["n"] * mean * mean) / (s["n"] - 1))
        results.append(
            {
                **action,
                "search_score": round(mean, 5),
                "standard_error": round(math.sqrt(variance / s["n"]), 5),
                "samples": s["n"],
                "terminal_samples": s["terminal"],
                "terminal_wins": s["wins"],
            }
        )
    results.sort(key=lambda a: (-a["search_score"], -a["score"], a["id"]))
    return {
        "method": "belief-aware-root-monte-carlo-ucb",
        "candidates": results,
        "budget": budget,
        "horizon": horizon,
        "transitions": transitions,
        "elapsed_ms": round(1000 * (time.perf_counter() - started)),
        "rejected_worlds": rejections,
        "terminal_samples": sum(s["terminal"] for s in stats),
        "score_kind": (
            "rollout_win_rate"
            if all(s["terminal"] == s["n"] for s in stats)
            else "mixed_heuristic"
        ),
        "belief_status": o.get("belief", {}).get("status", "public-counts-only"),
        "objective": "Terminal win/loss or a bounded position score at the horizon. Scores are not calibrated win probabilities. Standard errors are descriptive under adaptive sampling.",
        "assumptions": [
            "Resource worlds follow the observation tracker; when absent, a constrained count sampler supplies approximate hands.",
            "Unknown development cards use an exchangeable remaining-pool model.",
            "Continuation players use their own sampled observations with the strategic heuristic; no player sees opponents’ sampled hands.",
            "Search screens candidate actions and truncates at the chosen horizon; it is not equilibrium solving.",
        ],
    }
