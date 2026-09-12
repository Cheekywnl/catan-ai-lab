import copy
import json
import random
from collections import Counter
from itertools import combinations
from pathlib import Path

import pytest

from engine.development import VP, _allocations, development_beliefs, sample_development
from engine.session import Session, decode_action
from engine.planning import sample_game
from engine.fast_policy import choose_action
from catanatron.state_functions import player_key


def captured():
    fixture = (
        Path(__file__).resolve().parents[2]
        / "tests/fixtures/development-history-repro.json"
    )
    data = json.loads(fixture.read_text())
    s = Session.from_replay(data["replay"], False)
    assert s.export() == data["replay"]
    return s, data


def tiny_observation():
    # Unknown cards: one VP, one Knight, one Monopoly. Red holds one old and
    # one new card; the last turn at 9 points rules out VP in the old slot.
    o = Session(81, False).observation("BLUE", False, False)
    o["initial"] = False
    o["turn_owner"] = "RED"
    o["development_bank_count"] = 1
    o["own_development"] = {"VICTORY_POINT": 4}
    for p in o["players"]:
        p["development_count"] = 4 if p["color"] == "BLUE" else 0
        p["public_points"] = 2
    own = next(p for p in o["players"] if p["color"] == "BLUE")
    own["played_development"].update(
        KNIGHT=13, MONOPOLY=1, ROAD_BUILDING=2, YEAR_OF_PLENTY=2
    )
    red = next(p for p in o["players"] if p["color"] == "RED")
    red.update(
        development_count=2,
        development_bought_this_turn=1,
        public_points=7,
        last_completed_turn_public_points=9,
    )
    return o


def test_captured_impossible_hidden_vp_is_excluded_and_replay_is_unchanged():
    s, data = captured()
    o = s.observation(data["viewer"], simulation=True)
    target = data["case"]["player"]
    row = next(p for p in o["players"] if p["color"] == target)
    assert row["last_completed_turn_public_points"] == 9
    model = development_beliefs(o)
    assert model["hands"][target][VP]["probability_at_least_one"] == 0
    assert model["constraints"][target]["vp_max"] == 0
    for seed in range(24):
        game = sample_game(o, random.Random(seed))
        key = player_key(game.state, decode_action(s.intents[-1]).color)
        assert game.state.player_state[key + "_VICTORY_POINT_IN_HAND"] == 0


@pytest.mark.parametrize("public_points", [7, 9, 11])
def test_off_turn_road_points_do_not_erase_previous_nonwin(public_points):
    o = tiny_observation()
    o["turn_owner"] = "BLUE"
    o["development_bank_count"] = 2
    red = next(p for p in o["players"] if p["color"] == "RED")
    red.update(
        development_count=1, development_bought_this_turn=0, public_points=public_points
    )
    assert development_beliefs(o)["hands"]["RED"][VP]["expected"] == 0


def test_new_purchase_after_road_loss_has_correct_probability_and_age():
    o = tiny_observation()
    before = copy.deepcopy(o)
    model = development_beliefs(o)
    assert model["hands"]["RED"][VP]["expected"] == pytest.approx(0.5)
    assert model["hands"]["RED"]["KNIGHT"]["expected"] == pytest.approx(0.75)
    assert model["hands"]["RED"]["MONOPOLY"][
        "probability_at_least_one"
    ] == pytest.approx(0.75)
    rng = random.Random(17)
    held_vp = 0
    for _ in range(4000):
        hands, new, deck = sample_development(o, rng)
        held_vp += hands["RED"][VP]
        assert sum(hands["RED"].values()) == 2
        assert sum(new["RED"].values()) == 1
        assert new["RED"][VP] == hands["RED"][VP]
        assert Counter(hands["RED"]) + Counter(deck) == Counter(
            {VP: 1, "KNIGHT": 1, "MONOPOLY": 1}
        )
        assert all(new["RED"][card] <= count for card, count in hands["RED"].items())
        assert hands["BLUE"] == o["own_development"]
    assert held_vp / 4000 == pytest.approx(0.5, abs=0.03)
    assert o == before


def test_joint_weights_equal_exhaustive_labeled_slot_enumeration():
    # A owns old slot0/new slot1 and has old cap0. B owns slots2,3. Deck4,5.
    specs = (("A", 2, 1, 0, 0, 2), ("B", 2, 0, 2, 0, 2))
    brute = Counter()
    for slots in combinations(range(6), 2):
        if 0 in slots:
            continue
        brute[(sum(x in slots for x in (0, 1)), sum(x in slots for x in (2, 3)))] += 1
    actual = Counter({held: weight for held, weight, _ in _allocations(2, 2, specs)})
    assert actual == brute
    assert sum(actual.values()) == 10


def test_joint_posterior_changes_other_opponents_and_deck_together():
    o = tiny_observation()
    red = next(p for p in o["players"] if p["color"] == "RED")
    white = next(p for p in o["players"] if p["color"] == "WHITE")
    red.update(development_count=1, development_bought_this_turn=0)
    white["development_count"] = 1
    model = development_beliefs(o)
    assert model["hands"]["RED"][VP]["expected"] == 0
    assert model["hands"]["WHITE"][VP]["expected"] == pytest.approx(0.5)


def test_terminal_winner_evidence_and_impossible_counts():
    o = tiny_observation()
    o["winner"] = "RED"
    next(p for p in o["players"] if p["color"] == "RED")["public_points"] = 9
    model = development_beliefs(o)
    assert model["hands"]["RED"][VP]["expected"] == 1
    for seed in range(10):
        hands, new, _ = sample_development(o, random.Random(seed))
        assert hands["RED"][VP] == new["RED"][VP] == 1
    o["development_bank_count"] = 2
    with pytest.raises(ValueError, match="totals"):
        development_beliefs(o)


def test_history_survives_undo_and_does_not_read_real_hidden_cards():
    s, data = captured()
    undone = s.undo()
    fresh = Session(s.seed, False)
    for intent in s.intents[:-1]:
        fresh.execute(decode_action(intent))
    assert (
        undone.last_completed_turn_public_points
        == fresh.last_completed_turn_public_points
    )
    o = s.observation(data["viewer"], simulation=True)
    target = decode_action(s.intents[-1]).color
    key = player_key(s.game.state, target)
    # Deliberately mutate an inaccessible opponent card, retaining public totals.
    existing = next(
        card
        for card in ("KNIGHT", "MONOPOLY", "ROAD_BUILDING", "YEAR_OF_PLENTY")
        if s.game.state.player_state[key + "_" + card + "_IN_HAND"]
    )
    s.game.state.player_state[key + "_" + existing + "_IN_HAND"] -= 1
    s.game.state.player_state[key + "_VICTORY_POINT_IN_HAND"] += 1
    s.game.state.player_state[key + "_ACTUAL_VICTORY_POINTS"] += 1
    if VP in s.game.state.development_listdeck:
        s.game.state.development_listdeck.remove(VP)
        s.game.state.development_listdeck.append(existing)
    else:
        donor = next(
            color
            for color in s.game.state.colors
            if color != target
            and color.value != data["viewer"]
            and s.game.state.player_state[
                player_key(s.game.state, color) + "_VICTORY_POINT_IN_HAND"
            ]
        )
        donor_key = player_key(s.game.state, donor)
        s.game.state.player_state[donor_key + "_VICTORY_POINT_IN_HAND"] -= 1
        s.game.state.player_state[donor_key + "_" + existing + "_IN_HAND"] += 1
        s.game.state.player_state[donor_key + "_ACTUAL_VICTORY_POINTS"] -= 1
    s.game.state.development_listdeck.reverse()
    s.game.random.random()
    changed = s.observation(data["viewer"], simulation=True)
    assert changed == o
    assert development_beliefs(changed) == development_beliefs(o)


@pytest.mark.parametrize("seed", range(6100, 6106))
def test_real_hidden_points_remain_in_model_support_through_full_games(seed):
    s = Session(seed, False)
    for step in range(2000):
        actor = s.game.state.current_color()
        view = s.observation(actor.value, False, False, compact=True)
        if step % 9 == 0 or s.game.winning_color():
            for viewer in s.game.state.colors:
                o = s.observation(viewer.value, False, False, compact=True)
                model = development_beliefs(o)
                for color in s.game.state.colors:
                    if color == viewer:
                        continue
                    key = player_key(s.game.state, color)
                    real_vp = s.game.state.player_state[key + "_VICTORY_POINT_IN_HAND"]
                    bounds = model["constraints"][color.value]
                    assert bounds["vp_min"] <= real_vp <= bounds["vp_max"]
        if s.game.winning_color():
            break
        s.execute(decode_action(choose_action(view)))
    assert s.game.winning_color()
