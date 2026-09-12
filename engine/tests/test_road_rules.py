import copy
import random
import json
from pathlib import Path

import pytest

from engine import RULESET
from engine.road_rules import longest_trail, award_owner, refresh_networks
from engine.tactics import tactical_values, rank_actions
from engine.planning import sample_hands, sample_game, search
from engine.session import Session, decode_action
from engine.tests.test_engine import ready, rolled, set_hand, give_dev
from catanatron.models.board import Board, STATIC_GRAPH
from catanatron.models.player import Color
from catanatron.models.actions import generate_playable_actions
from catanatron.state_functions import player_key, maintain_longest_road


@pytest.mark.parametrize(
    "edges,blocked,length",
    [
        ([(0, 1), (1, 2), (2, 3)], (0, 3), 3),
        ([(0, 1), (1, 2), (2, 3), (3, 4)], (2,), 2),
        ([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)], (), 6),
        ([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (0, 6)], (), 7),
        ([(0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (5, 6), (0, 7)], (), 6),
    ],
)
def test_road_endpoints_loops_and_branches(edges, blocked, length):
    trail = longest_trail(tuple(sorted(tuple(sorted(e)) for e in edges)), blocked)
    assert len(trail) == length and len(set(trail)) == length


def test_road_award_ties_preserve_only_an_eligible_incumbent():
    assert award_owner({"RED": 6, "BLUE": 6}, "RED") == "RED"
    assert award_owner({"RED": 6, "BLUE": 6, "WHITE": 4}, "WHITE") is None
    assert award_owner({"RED": 4, "BLUE": 3}, "RED") is None
    assert award_owner({"RED": 5, "BLUE": 6}, "RED") == "BLUE"


def test_unclaimed_road_award_removes_previous_holders_two_points():
    s = ready()
    owner = s.game.state.current_color()
    key = player_key(s.game.state, owner)
    p = s.game.state.player_state
    p[f"{key}_HAS_ROAD"] = True
    p[f"{key}_VICTORY_POINTS"] += 2
    p[f"{key}_ACTUAL_VICTORY_POINTS"] += 2
    before = p[f"{key}_ACTUAL_VICTORY_POINTS"]
    maintain_longest_road(s.game.state, owner, None, {owner: 4})
    assert not p[f"{key}_HAS_ROAD"]
    assert p[f"{key}_ACTUAL_VICTORY_POINTS"] == before - 2


def test_blocked_road_end_counts_but_cannot_be_used_for_expansion():
    board = Board()

    def path(nodes):
        if len(nodes) == 7:
            return nodes
        for n in sorted(STATIC_GRAPH.neighbors(nodes[-1])):
            if n not in nodes:
                result = path(nodes + [n])
                if result:
                    return result

    nodes = path([0])
    for a, b in zip(nodes, nodes[1:]):
        board.roads[a, b] = board.roads[b, a] = Color.RED
    board.buildings[nodes[0]] = (Color.BLUE, "SETTLEMENT")
    board.buildings[nodes[-1]] = (Color.WHITE, "SETTLEMENT")
    refresh_networks(board)
    assert board.road_lengths[Color.RED] == 6
    assert all(
        nodes[0] not in c and nodes[-1] not in c
        for c in board.connected_components[Color.RED]
    )
    sources = set(nodes[1:-1])
    for blocked in (nodes[0], nodes[-1]):
        for neighbor in STATIC_GRAPH.neighbors(blocked):
            edge = tuple(sorted((blocked, neighbor)))
            if neighbor not in sources and edge not in board.roads:
                assert edge not in board.buildable_edges(Color.RED)


def test_knight_that_wins_largest_army_takes_priority_over_an_available_city():
    s = ready()
    rolled(s)
    color = s.game.state.current_color()
    key = player_key(s.game.state, color)
    give_dev(s, color, "KNIGHT")
    for _ in range(2):
        s.game.state.development_listdeck.remove("KNIGHT")
    p = s.game.state.player_state
    p[f"{key}_PLAYED_KNIGHT"] = 2
    p[f"{key}_VICTORY_POINTS"] = p[f"{key}_ACTUAL_VICTORY_POINTS"] = 8
    set_hand(s, color, [0, 0, 0, 2, 3])
    s.game.playable_actions = generate_playable_actions(s.game.state)
    o = s.observation(color.value)
    assert any(a["type"] == "BUILD_CITY" for a in o["legal_actions"])
    ranked = rank_actions(o)
    assert ranked[0]["type"] == "PLAY_KNIGHT_CARD"
    assert ranked[0]["tactical"]["wins_now"]
    s.execute(decode_action(ranked[0]))
    assert s.game.winning_color() == color


def test_sampler_conditions_particle_worlds_on_finite_bank_supply():
    s = Session(42)
    o = s.observation(s.game.state.current_color().value, simulation=True)
    colors = [p["color"] for p in o["players"]]
    o["viewer"] = colors[0]
    o["own_hand"] = [8, 0, 0, 0, 0]
    for i, p in enumerate(o["players"]):
        p["resource_count"] = [8, 12, 0, 0][i]
    bad = [8, 0, 0, 0, 0, 12, 0, 0, 0, 0] + [0] * 10
    good = [8, 0, 0, 0, 0, 11, 1, 0, 0, 0] + [0] * 10
    o["joint_belief"] = [
        {"hands": bad, "weight": 0.999},
        {"hands": good, "weight": 0.001},
    ]
    before = copy.deepcopy(o)
    for seed in range(20):
        hands = sample_hands(o, random.Random(seed))
        assert sum(hand[0] for hand in hands.values()) == 19
    assert o == before


def test_captured_search_bank_failure_replays_and_now_samples_feasible_worlds():
    fixture = (
        Path(__file__).resolve().parents[2] / "tests/fixtures/search-bank-repro.json"
    )
    replay = json.loads(fixture.read_text())
    s = Session.from_replay(replay)
    assert s.export() == replay
    assert s.game.state.board.rules_revision == 1
    o = s.observation(s.game.state.current_color().value, simulation=True)
    for seed in range(20):
        game = sample_game(o, random.Random(seed))
        assert min(game.state.resource_freqdeck) >= 0
    result = search(o, budget=12, horizon=16, max_candidates=4)
    assert result["candidates"] and result["budget"] >= 12


@pytest.mark.parametrize("seed", range(3))
def test_tactical_award_predictions_agree_with_rules_in_complete_games(seed):
    s = Session(4100 + seed, False)
    checks = 0
    while not s.game.winning_color() and len(s.intents) < 2000:
        o = s.observation(
            s.game.state.current_color().value, False, False, compact=True
        )
        values = tactical_values(o)
        own = next(p for p in o["players"] if p["color"] == o["viewer"])
        if not o["initial"]:
            for action in o["legal_actions"]:
                if action["type"] not in (
                    "BUILD_ROAD",
                    "BUILD_SETTLEMENT",
                    "BUILD_CITY",
                    "PLAY_KNIGHT_CARD",
                ):
                    continue
                game = s.game.copy()
                game.execute(decode_action(action))
                key = player_key(game.state, game.state.current_color())
                assert (
                    values[action["id"]]["points_gained"]
                    == game.state.player_state[f"{key}_ACTUAL_VICTORY_POINTS"]
                    - own["own_points"]
                )
                assert values[action["id"]]["wins_now"] == (
                    game.winning_color() is not None
                )
                checks += 1
        s.execute(decode_action(rank_actions(o)[0]))
    assert s.game.winning_color() is not None and checks > 20
