import copy
import json
import math
import random
import pytest

from engine.session import Session, action_value, decode_action
from engine.policy import rank_actions, draft_search
from engine.beliefs import ResourceBelief
from catanatron.game import Game, is_valid_trade
from catanatron.models.actions import (
    generate_playable_actions,
    year_of_plenty_possibilities,
    inner_maritime_trade_possibilities,
)
from catanatron.models.enums import (
    Action,
    ActionType,
    ActionRecord,
    ActionPrompt,
    RESOURCES,
    DEVELOPMENT_CARDS,
)
from catanatron.models.player import Color
from catanatron.state_functions import (
    player_key,
    get_player_freqdeck,
    player_clean_turn,
    play_dev_card,
    get_largest_army,
)
from catanatron.apply_action import yield_resources


def ready(seed=42):
    session = Session(seed, track_beliefs=False)
    while session.game.state.is_initial_build_phase:
        session.auto()
    return session


def set_hand(session, color, hand):
    state = session.game.state
    key = player_key(state, color)
    current = get_player_freqdeck(state, color)
    for i, (a, b) in enumerate(zip(current, hand)):
        state.resource_freqdeck[i] += a - b
        state.player_state[f"{key}_{RESOURCES[i]}_IN_HAND"] = b
    session.game.playable_actions = generate_playable_actions(state)


def rolled(session):
    session.game.state.player_state[
        f"{player_key(session.game.state,session.game.state.current_color())}_HAS_ROLLED"
    ] = True
    session.game.playable_actions = generate_playable_actions(session.game.state)


def test_seeded_setup_topology_and_snake_draft():
    a, b = Session(42), Session(42)
    assert a.observation() == b.observation()
    assert (
        len(a._geometry["nodes"]) == 54
        and len(a._geometry["edges"]) == 72
        and len(a._geometry["tiles"]) == 19
    )
    for edge in a._geometry["edges"]:
        p, q = [a._geometry["nodes"][i] for i in edge]
        assert math.hypot(p["x"] - q["x"], p["y"] - q["y"]) == pytest.approx(
            1, abs=1e-5
        )
    order = [c.value for c in a.game.state.colors]
    owners = []
    while a.game.state.is_initial_build_phase:
        if a.game.state.current_prompt == ActionPrompt.BUILD_INITIAL_SETTLEMENT:
            owners.append(a.game.state.current_color().value)
        a.auto()
    assert owners == order + list(reversed(order))
    assert len(a.game.state.board.buildings) == 8
    assert len(a.game.state.board.roads) // 2 == 8
    for color in a.game.state.colors:
        assert 0 <= sum(get_player_freqdeck(a.game.state, color)) <= 3
    a.check_invariants()


def test_clone_randomness_and_board_are_independent():
    s = ready()
    before = s.game.random.getstate()
    clone = s.game.copy()
    clone.random.random()
    assert s.game.random.getstate() == before
    assert clone.random is clone.state.random
    assert clone.random is not s.game.random
    state = s.game.state.copy()
    state.random.random()
    assert s.game.random.getstate() == before
    clone.state.resource_freqdeck[0] -= 1
    assert s.game.state.resource_freqdeck[0] != clone.state.resource_freqdeck[0]


def test_only_turn_owner_can_win_and_terminal_actions_are_rejected():
    s = ready()
    state = s.game.state
    other = state.colors[(state.current_turn_index + 1) % 4]
    state.player_state[f"{player_key(state,other)}_ACTUAL_VICTORY_POINTS"] = 10
    assert s.game.winning_color() is None
    rolled(s)
    s.game.execute(Action(state.current_color(), ActionType.END_TURN, None))
    assert s.game.winning_color() == other
    with pytest.raises(ValueError, match="already ended"):
        s.game.execute(s.game.playable_actions[0])


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        [1] * 9,
        [1] * 11,
        [-1, 1, 0, 0, 0, 0, 0, 1, 0, 0],
        [True, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        [1.5, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        [20, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 0],
        [0] * 10,
    ],
)
def test_malformed_and_gift_trade_offers_are_invalid(value):
    assert not is_valid_trade(value)


@pytest.mark.parametrize("offer_seat", range(4))
def test_trade_responses_skip_proposer_and_exchange_atomically(offer_seat):
    s = ready()
    state = s.game.state
    state.current_turn_index = state.current_player_index = offer_seat
    proposer = state.current_color()
    others = [c for c in state.colors if c != proposer]
    for color in state.colors:
        set_hand(s, color, [2, 0, 0, 0, 0] if color == proposer else [0, 2, 0, 0, 0])
    rolled(s)
    s.offer([1, 0, 0, 0, 0], [0, 1, 0, 0, 0], len(s.intents))
    replies = []
    while state.current_prompt == ActionPrompt.DECIDE_TRADE:
        replies.append(state.current_color())
        s.execute(
            next(a for a in s.legal() if a.action_type == ActionType.ACCEPT_TRADE)
        )
    assert sorted(c.value for c in replies) == sorted(c.value for c in others)
    assert state.current_color() == proposer
    action = next(a for a in s.legal() if a.action_type == ActionType.CONFIRM_TRADE)
    partner = action.value[10]
    s.execute(action)
    assert get_player_freqdeck(state, proposer) == [1, 1, 0, 0, 0]
    assert get_player_freqdeck(state, partner) == [1, 1, 0, 0, 0]
    assert state.current_prompt == ActionPrompt.PLAY_TURN
    s.check_invariants()


def test_offer_without_resources_rejected_without_state_change():
    s = ready()
    rolled(s)
    set_hand(s, s.game.state.current_color(), [0] * 5)
    before = s.export()
    with pytest.raises(ValueError):
        s.offer([1, 0, 0, 0, 0], [0, 1, 0, 0, 0], len(s.intents))
    assert s.export() == before


def test_supply_shortage_single_recipient_gets_remaining_multiple_get_none():
    s = Session(42)
    board = s.game.state.board
    tile = next(
        t for t in board.map.land_tiles.values() if t.resource and t.number != 7
    )
    board.robber_coordinate = next(
        c for c, t in board.map.land_tiles.items() if t.resource is None
    )
    node = list(tile.nodes.values())[0]
    board.buildings = {node: (Color.RED, "CITY")}
    bank = [19] * 5
    bank[RESOURCES.index(tile.resource)] = 1
    payout, depleted = yield_resources(board, bank, tile.number)
    assert (
        tile.resource in depleted
        and payout[Color.RED][RESOURCES.index(tile.resource)] == 1
    )
    board.buildings[list(tile.nodes.values())[3]] = (Color.BLUE, "SETTLEMENT")
    payout, _ = yield_resources(board, bank, tile.number)
    assert payout[Color.RED][RESOURCES.index(tile.resource)] == 0
    assert payout[Color.BLUE][RESOURCES.index(tile.resource)] == 0


def test_seven_discards_floor_half_only_above_seven():
    s = ready()
    state = s.game.state
    actor = state.current_color()
    for color, hand in zip(
        state.colors,
        [[7, 0, 0, 0, 0], [0, 8, 0, 0, 0], [0, 0, 9, 0, 0], [0, 0, 0, 3, 0]],
    ):
        set_hand(s, color, hand)
    action = Action(actor, ActionType.ROLL, None)
    s.game.execute(action, action_record=ActionRecord(action, (3, 4)))
    assert state.discard_counts == [0, 4, 4, 0]
    while state.is_discarding:
        s.game.execute(s.game.playable_actions[0])
    assert [sum(get_player_freqdeck(state, c)) for c in state.colors] == [7, 4, 5, 3]
    assert (
        state.current_color() == actor
        and state.current_prompt == ActionPrompt.MOVE_ROBBER
    )


def test_no_private_opponent_hand_deck_order_seed_or_rng_in_observation():
    s = ready()
    viewer = s.game.state.colors[0]
    opponents = [c for c in s.game.state.colors if c != viewer]
    for c in opponents:
        set_hand(s, c, [1, 1, 0, 0, 0])
    before = s.observation(viewer.value, include_belief=False)
    for c in opponents:
        set_hand(s, c, [0, 0, 1, 1, 0])
    s.game.state.development_listdeck.reverse()
    after = s.observation(viewer.value, include_belief=False)
    assert before == after
    assert rank_actions(before) == rank_actions(after)
    serialized = json.dumps(after)
    for key in [
        "random",
        "seed",
        "development_listdeck",
        "resource_freqdeck",
        "ACTUAL_VICTORY_POINTS",
    ]:
        assert key not in serialized
    assert all(
        "own_points" not in p for p in after["players"] if p["color"] != viewer.value
    )
    assert s.observation(opponents[0].value)["legal_actions"] == []


def test_replay_is_exact_and_invalid_import_does_not_mutate_original():
    s = Session(87)
    s.auto(200)
    t = Session.from_replay(s.export())
    assert t.export() == s.export()
    for color in Color:
        assert t.observation(color.value) == s.observation(color.value)
    t.auto(80)
    s.auto(80)
    assert t.chain == s.chain
    broken = s.export()
    broken["checksum"] = "tampered"
    before = s.export()
    with pytest.raises(ValueError, match="checksum"):
        Session.from_replay(broken)
    assert s.export() == before
    old = s.undo()
    old.execute(decode_action(s.intents[-1]))
    assert old.chain == s.chain


def test_stale_actions_rejected_and_observations_cannot_mutate_game():
    s = Session(42)
    obs = s.observation()
    s.auto()
    before = s.export()
    with pytest.raises(ValueError, match="earlier position"):
        s.apply(0, obs["revision"])
    assert s.export() == before
    obs = s.observation()
    obs["board"]["tiles"][0]["number"] = 99
    obs["own_hand"][0] = 99
    assert (
        s.observation()["board"]["tiles"][0]["number"] != 99
        and s.observation()["own_hand"][0] != 99
    )


def test_exact_correlated_theft_and_later_public_spending():
    b = ResourceBelief(["RED", "BLUE"])
    b.update(
        {"type": "ROLL", "color": "RED", "deltas": {"RED": [0, 0, 0, 1, 2]}},
        "BLUE",
        [0] * 5,
        {"RED": 3, "BLUE": 0},
    )
    b.update(
        {"type": "MOVE_ROBBER", "color": "BLUE", "victim": "RED", "resource": "ORE"},
        "BLUE",
        [0, 0, 0, 0, 1],
        {"RED": 2, "BLUE": 1},
    )
    assert len(b.worlds) == 1
    assert list(b.worlds)[0] == (0, 0, 0, 1, 1, 0, 0, 0, 0, 1)
    # A third observer sees a genuine 2/3–1/3 split.
    b = ResourceBelief(["RED", "BLUE", "ORANGE"])
    b.update(
        {"type": "ROLL", "color": "RED", "deltas": {"RED": [0, 0, 0, 1, 2]}},
        "ORANGE",
        [0] * 5,
        {"RED": 3, "BLUE": 0, "ORANGE": 0},
    )
    b.update(
        {"type": "MOVE_ROBBER", "color": "BLUE", "victim": "RED"},
        "ORANGE",
        [0] * 5,
        {"RED": 2, "BLUE": 1, "ORANGE": 0},
    )
    assert sorted(b.worlds.values()) == pytest.approx([1 / 3, 2 / 3])
    b.update(
        {
            "type": "MARITIME_TRADE",
            "color": "BLUE",
            "deltas": {"BLUE": [1, 0, 0, -1, 0]},
        },
        "ORANGE",
        [0] * 5,
        {"RED": 2, "BLUE": 1, "ORANGE": 0},
    )
    assert len(b.worlds) == 1 and b.summary()["hands"]["RED"][4]["min"] == 2


def test_draft_search_uses_observations_and_preserves_game_randomness():
    s = Session(42)
    obs = s.observation("RED")
    before = s.export()
    rng = s.game.random.getstate()
    result = draft_search(obs, 8)
    assert len(result["candidates"]) == 10
    assert result == draft_search(obs, 8)
    assert s.export() == before and s.game.random.getstate() == rng
    assert all(c["type"] == "BUILD_SETTLEMENT" for c in result["candidates"])


@pytest.mark.parametrize("seed", range(12))
def test_complete_games_and_conservation(seed):
    s = Session(seed, track_beliefs=False)
    for _ in range(30):
        s.auto(200)
        if s.game.winning_color():
            break
    assert s.game.winning_color() is not None
    s.check_invariants()


@pytest.mark.parametrize("seed", [1, 42, 87])
def test_belief_conservative_fallback_always_contains_actual_hands(seed):
    s = Session(seed)
    for _ in range(300):
        if s.game.winning_color():
            break
        s.auto()
        for tracker in s.trackers.values():
            for color in s.game.state.colors:
                actual = get_player_freqdeck(s.game.state, color)
                assert all(
                    low <= n <= high
                    for n, (low, high) in zip(actual, tracker.bounds[color.value])
                )


@pytest.mark.parametrize(
    "bank,expected",
    [
        ([0, 0, 0, 0, 0], set()),
        ([0, 0, 0, 0, 1], {("ORE",)}),
        ([0, 0, 0, 0, 2], {("ORE", "ORE")}),
        ([0, 0, 0, 1, 1], {("WHEAT", "ORE")}),
    ],
)
def test_year_of_plenty_draws_two_unless_only_one_remains(bank, expected):
    assert {a.value for a in year_of_plenty_possibilities(Color.RED, bank)} == expected


def give_dev(session, color, card, owned_at_start=True):
    state = session.game.state
    state.development_listdeck.remove(card)
    key = player_key(state, color)
    state.player_state[f"{key}_{card}_IN_HAND"] += 1
    if card != "VICTORY_POINT":
        state.player_state[f"{key}_{card}_OWNED_AT_START"] = owned_at_start
    session.game.playable_actions = generate_playable_actions(state)


def test_development_timing_pre_roll_one_per_turn_and_new_purchase_delay():
    s = ready()
    state = s.game.state
    color = state.current_color()
    give_dev(s, color, "YEAR_OF_PLENTY", False)
    assert not any(a.action_type == ActionType.PLAY_YEAR_OF_PLENTY for a in s.legal())
    player_clean_turn(state, color)
    give_dev(s, color, "MONOPOLY")
    assert any(a.action_type == ActionType.PLAY_YEAR_OF_PLENTY for a in s.legal())
    s.execute(
        next(a for a in s.legal() if a.action_type == ActionType.PLAY_YEAR_OF_PLENTY)
    )
    assert {a.action_type for a in s.legal()} == {ActionType.ROLL}
    s.game.execute(
        Action(color, ActionType.ROLL, None),
        action_record=ActionRecord(Action(color, ActionType.ROLL, None), (1, 1)),
    )
    assert not any(a.action_type == ActionType.PLAY_MONOPOLY for a in s.legal())
    s.check_invariants()


def test_knight_does_not_discard_and_theft_is_private_to_participants():
    s = ready()
    state = s.game.state
    actor = state.current_color()
    for color in state.colors:
        set_hand(s, color, [2, 2, 2, 2, 2])
    give_dev(s, actor, "KNIGHT")
    before = [sum(get_player_freqdeck(state, c)) for c in state.colors]
    s.execute(Action(actor, ActionType.PLAY_KNIGHT_CARD, None))
    assert state.current_prompt == ActionPrompt.MOVE_ROBBER
    assert [sum(get_player_freqdeck(state, c)) for c in state.colors] == before
    assert all(a.value[0] != state.board.robber_coordinate for a in s.legal())
    action = next(a for a in s.legal() if a.value[1])
    s.execute(action)
    for color in state.colors:
        event = s.observation(color.value)["events"][-1]
        assert ("resource" in event) == (color in (actor, action.value[1]))
        assert "deltas" not in event
    s.check_invariants()


def test_development_purchase_is_private_and_victory_point_wins_immediately():
    s = ready()
    state = s.game.state
    color = state.current_color()
    rolled(s)
    set_hand(s, color, [0, 0, 1, 1, 1])
    state.player_state[f"{player_key(state,color)}_ACTUAL_VICTORY_POINTS"] = 9
    # Put a VP in every draw position to avoid coupling this rule test to RNG implementation.
    state.development_listdeck = ["VICTORY_POINT"] * 25
    s.execute(Action(color, ActionType.BUY_DEVELOPMENT_CARD, None))
    assert s.game.winning_color() == color
    for viewer in state.colors:
        event = s.observation(viewer.value)["events"][-1]
        assert ("development_card" in event) == (viewer == color)


@pytest.mark.parametrize(
    "ports,amount", [([], 4), ([None], 3), (["WOOD"], 2), ([None, "WOOD"], 2)]
)
def test_maritime_trade_uses_best_port_and_requires_supply(ports, amount):
    trades = inner_maritime_trade_possibilities(
        [amount, 0, 0, 0, 0], [0, 1, 0, 0, 0], ports
    )
    assert trades == {tuple(["WOOD"] * amount + [None] * (4 - amount) + ["BRICK"])}
    assert (
        inner_maritime_trade_possibilities(
            [amount - 1, 0, 0, 0, 0], [0, 1, 0, 0, 0], ports
        )
        == set()
    )
    assert (
        inner_maritime_trade_possibilities([amount, 0, 0, 0, 0], [0] * 5, ports)
        == set()
    )


def test_largest_army_threshold_defending_tie_and_transfer():
    s = ready()
    state = s.game.state
    a, b = state.colors[:2]

    def knight(color):
        give_dev(s, color, "KNIGHT")
        play_dev_card(state, color, "KNIGHT")

    knight(a)
    knight(a)
    assert get_largest_army(state)[0] is None
    knight(a)
    assert get_largest_army(state) == (a, 3)
    for _ in range(3):
        knight(b)
    assert get_largest_army(state) == (a, 3)
    knight(b)
    assert get_largest_army(state) == (b, 4)
    assert not state.player_state[f"{player_key(state,a)}_HAS_ARMY"]
    assert state.player_state[f"{player_key(state,b)}_HAS_ARMY"]


def test_monopoly_recommendation_handles_bounds_without_invented_expectations():
    s = ready()
    color = s.game.state.current_color()
    give_dev(s, color, "MONOPOLY")
    observation = s.observation(color.value)
    observation["belief"] = {
        "status": "bounds_only",
        "hands": {
            c.value: [{"min": 0, "max": 5, "expected": None} for _ in RESOURCES]
            for c in Color
        },
    }
    ranked = rank_actions(observation)
    assert all(a["score"] == 25 for a in ranked if a["type"] == "PLAY_MONOPOLY")
