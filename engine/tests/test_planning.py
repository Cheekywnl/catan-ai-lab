import copy
import json
import random
from pathlib import Path
import pytest
from engine.session import Session, canonical, action_value, decode_action
from engine.planning import sample_game, sample_hands, search, development_beliefs
from engine.strategy import analyze, rank_actions, eta, expansion
from engine.tests.test_engine import set_hand, ready, rolled, give_dev
from catanatron.models.enums import ActionType, RESOURCES
from catanatron.state_functions import get_player_freqdeck


@pytest.mark.parametrize("step", [0, 1, 7, 15, 16, 35, 90, 160])
def test_sampled_world_preserves_public_position_legal_moves_and_conservation(step):
    s = Session(42)
    while len(s.intents) < step:
        s.auto(policy="strategic")
    o = s.observation(s.game.state.current_color().value, simulation=True)
    game = sample_game(o, random.Random(3))
    shell = Session.__new__(Session)
    shell.game = game
    shell.check_invariants()
    assert game.state.board.buildings == s.game.state.board.buildings
    assert game.state.board.roads == s.game.state.board.roads
    assert get_player_freqdeck(game.state, game.state.current_color()) == o["own_hand"]
    assert {canonical(action_value(a)) for a in game.playable_actions} == {
        canonical(action_value(a)) for a in s.legal()
    }
    assert game.random is game.state.random and game.random is not s.game.random


def test_planning_packet_and_search_do_not_reveal_real_hidden_world():
    s = ready()
    viewer = s.game.state.current_color()
    for color in s.game.state.colors:
        if color != viewer:
            set_hand(s, color, [1, 1, 0, 0, 0])
    a = s.observation(viewer.value, simulation=True)
    for color in s.game.state.colors:
        if color != viewer:
            set_hand(s, color, [0, 0, 1, 1, 0])
    s.game.state.development_listdeck.reverse()
    s.game.random.random()
    b = s.observation(viewer.value, simulation=True)
    assert a == b
    for word in ("random_state", "development_listdeck", "resource_freqdeck", '"seed"'):
        assert word not in json.dumps(a)
    x = search(a, 4, 8, 2)
    y = search(b, 4, 8, 2)
    x.pop("elapsed_ms")
    y.pop("elapsed_ms")
    assert x == y


def test_search_is_reproducible_and_cannot_mutate_real_game():
    s = Session(17)
    s.auto(70, policy="strategic")
    before = s.export()
    rng = s.game.random.getstate()
    o = s.observation(s.game.state.current_color().value, simulation=True)
    backup = copy.deepcopy(o)
    a = search(o, 12, 20, 4)
    b = search(o, 12, 20, 4)
    assert s.export() == before and s.game.random.getstate() == rng and o == backup
    a.pop("elapsed_ms")
    b.pop("elapsed_ms")
    assert a == b
    assert sum(x["samples"] for x in a["candidates"]) == a["budget"]
    assert a["transitions"] <= a["budget"] * a["horizon"]
    assert all(0 <= x["search_score"] <= 1 for x in a["candidates"])


def test_joint_sampling_retains_correlated_hands_and_capacity():
    s = Session(42)
    o = s.observation("RED", simulation=True)
    colors = [p["color"] for p in o["players"]]
    a = [0] * 20
    b = [0] * 20
    a[5] = 1
    a[11] = 1
    b[6] = 1
    b[10] = 1
    o["joint_belief"] = [{"hands": a, "weight": 0.7}, {"hands": b, "weight": 0.3}]
    for i in range(50):
        sampled = sample_hands(o, random.Random(i))
        assert [v for c in colors for v in sampled[c]] in (a, b)


def test_bounds_sampling_respects_own_hand_totals_and_global_resource_limits():
    s = ready()
    o = s.observation(s.game.state.current_color().value, simulation=True)
    o["joint_belief"] = []
    for p in o["players"]:
        if p["color"] != o["viewer"]:
            p["resource_count"] = 20
    o["belief"] = {
        "hands": {
            p["color"]: [{"min": 0, "max": 19} for _ in RESOURCES] for p in o["players"]
        }
    }
    for i in range(30):
        hands = sample_hands(o, random.Random(i))
        assert hands[o["viewer"]] == o["own_hand"]
        assert all(sum(hands[p["color"]]) == p["resource_count"] for p in o["players"])
        assert all(sum(h[r] for h in hands.values()) <= 19 for r in range(5))


def test_development_estimates_remove_own_and_played_cards():
    s = ready()
    color = s.game.state.current_color()
    give_dev(s, color, "KNIGHT")
    o = s.observation(color.value)
    model = development_beliefs(o)
    assert model["unknown_pool"]["KNIGHT"] == 13
    assert sum(model["unknown_pool"].values()) == 24
    assert "exchangeable" in model["status"]


def test_mean_flow_eta_handles_trade_conversion_and_no_production():
    assert eta([4, 0, 0, 0, 0], [0, 1, 0, 0, 0], [0] * 5, [4] * 5) == 0
    assert eta([0] * 5, [0, 1, 0, 0, 0], [0] * 5, [4] * 5) == 120
    assert eta([0] * 5, [1, 0, 0, 0, 0], [0.1, 0, 0, 0, 0], [4] * 5) == pytest.approx(
        10, abs=0.25
    )


def test_strategic_policy_trades_toward_city_instead_of_hoarding_convertible_cards():
    s = ready()
    rolled(s)
    color = s.game.state.current_color()
    set_hand(s, color, [4, 0, 0, 2, 2])
    o = s.observation(color.value)
    ranked = rank_actions(o)
    assert ranked[0]["type"] == "MARITIME_TRADE" and ranked[0]["value"][-1] == "ORE"


@pytest.mark.parametrize("seed", range(6))
def test_strategic_full_games_finish(seed):
    s = Session(seed, False)
    for _ in range(20):
        s.auto(200, policy="strategic")
        if s.game.winning_color():
            break
    assert s.game.winning_color()
    s.check_invariants()


def test_old_replays_remain_identical_after_upgrade():
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[2] / "tests/fixtures/native-replay.json"
        ).read_text()
    )
    s = Session.from_replay(fixture)
    assert s.export() == fixture
    assert s.undo().export()["engine_version"] == "0.1.0"


@pytest.mark.parametrize("seed", [314, 2718, 1618])
def test_mixed_random_and_strategic_actions_preserve_rules_invariants(seed):
    s = Session(seed, False)
    rng = random.Random(seed)
    for _ in range(1000):
        if s.game.winning_color():
            break
        if rng.random() < 0.2:
            s.execute(rng.choice(s.legal()))
        else:
            s.auto(policy="strategic")
    s.check_invariants()


def test_opening_audit_exact_pips_snake_order_and_actual_port_rates():
    from engine.opening import report, candidate

    s = Session(42)
    o = s.observation("RED")
    audit = report(o)
    assert audit["draft_order"] == [
        "RED",
        "WHITE",
        "BLUE",
        "ORANGE",
        "ORANGE",
        "BLUE",
        "WHITE",
        "RED",
    ]
    assert audit["rival_placements_before_next_pick"] == 6
    for row in audit["candidates"]:
        tiles = [
            t
            for t in o["board"]["tiles"]
            if row["node"] in t["nodes"] and t["resource"]
        ]
        assert row["candidate_pips"] == sum(6 - abs(7 - t["number"]) for t in tiles)
        unique = {t["number"] for t in tiles}
        assert row["income_roll_probability"] == pytest.approx(
            sum((6 - abs(7 - n)) / 36 for n in unique)
        )
        assert all(x in (2, 3, 4) for x in row["port_rates"])


def test_port_without_resource_supply_has_no_arbitrary_bonus():
    from engine.opening import candidate

    s = Session(42)
    o = s.observation("RED")
    node = next(
        n["id"]
        for n in o["board"]["nodes"]
        if not any(
            t["resource"] == "ORE" and n["id"] in t["nodes"]
            for t in o["board"]["tiles"]
        )
    )
    o["board"]["ports"] = []
    a = candidate(o, node)
    o["board"]["ports"] = [{"nodes": [node], "resource": "ORE"}]
    b = candidate(o, node)
    assert b["port_rates"][4] == 2 and a["score"] == b["score"]
    assert all(x == 0 for x in b["port_rolls_saved"].values())


def test_dice_exposure_uses_unique_dice_events_and_turn_order():
    from engine.forecast import dice_exposure

    s = ready()
    rolled(s)
    o = s.observation(s.game.state.current_color().value)
    forecast = dice_exposure(o)
    assert forecast["rolls_before_next_turn"] == 3
    for p in forecast["players"]:
        nums = {
            t["number"]
            for t in o["board"]["tiles"]
            if t["resource"]
            and t["coordinate"] != o["board"]["robber"]
            and any(
                b["color"] == p["color"] and b["node"] in t["nodes"]
                for b in o["board"]["buildings"]
            )
        }
        chance = sum((6 - abs(7 - n)) / 36 for n in nums)
        assert p["probability_any_income"] == pytest.approx(
            1 - (1 - chance) ** 3, abs=1e-6
        )


def test_truncated_forecasts_withhold_win_probabilities():
    from engine.forecast import forecast, wilson

    s = Session(42)
    o = s.observation("BLUE", simulation=True)
    before = s.export()
    f = forecast(o, 4, 1)
    assert f["completed"] == 0 and f["truncated"] == 4
    assert all(
        p["win_probability"] is None and p["censoring_bounds"] == [0, 1]
        for p in f["players"]
    )
    assert s.export() == before and wilson(0, 4)[1] > 0.4


def test_search_recognizes_immediate_winning_build():
    from catanatron.state_functions import player_key

    s = ready()
    rolled(s)
    color = s.game.state.current_color()
    set_hand(s, color, [0, 0, 0, 2, 3])
    key = player_key(s.game.state, color)
    s.game.state.player_state[key + "_VICTORY_POINTS"] = 9
    s.game.state.player_state[key + "_ACTUAL_VICTORY_POINTS"] = 9
    o = s.observation(color.value, simulation=True)
    result = search(o, 8, 8, 2)
    best = result["candidates"][0]
    assert best["type"] == "BUILD_CITY" and best["search_score"] == 1
    assert best["terminal_wins"] == best["samples"]


def test_monopoly_eliminates_impossible_residual_cards_in_beliefs():
    from engine.beliefs import ResourceBelief

    b = ResourceBelief(["RED", "BLUE", "ORANGE"])
    b.worlds = {
        (0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0): 0.5,
        (0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0): 0.5,
    }
    b.bounds = {c: [[0, 1], [0, 1], [0, 0], [0, 0], [0, 0]] for c in b.colors}
    event = {
        "type": "PLAY_MONOPOLY",
        "color": "RED",
        "value": "WOOD",
        "deltas": {"RED": [1, 0, 0, 0, 0], "BLUE": [-1, 0, 0, 0, 0]},
    }
    b.update(event, "RED", [1, 0, 0, 0, 0], {"RED": 1, "BLUE": 0, "ORANGE": 1})
    assert b.bounds["BLUE"][0] == b.bounds["ORANGE"][0] == [0, 0]
    assert len(b.worlds) == 1


def test_nonterminal_turn_owner_cannot_have_a_hidden_winning_point():
    s = ready()
    owner = s.game.state.current_color()
    give_dev(s, owner, "KNIGHT")
    viewer = next(c for c in s.game.state.colors if c != owner)
    o = s.observation(viewer.value)
    p = next(p for p in o["players"] if p["color"] == owner.value)
    p["public_points"] = 9
    model = development_beliefs(o)
    assert model["hands"][owner.value]["VICTORY_POINT"]["probability_at_least_one"] == 0
    assert sum(
        c["expected"] for c in model["hands"][owner.value].values()
    ) == pytest.approx(1)
