import json
from pathlib import Path

import pytest

from engine.session import Session, dispatch
from engine.arena import select
from catanatron.models.enums import RESOURCES
from catanatron.state_functions import get_player_freqdeck
from catanatron.models.player import Color


def fixture():
    return json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "tests/fixtures/policy-observation-repro.json"
        ).read_text()
    )


def test_autoplay_uses_exact_tracked_monopoly_cards_and_keeps_frozen_v3():
    data = fixture()
    s = Session.from_replay(data["replay"])
    view = s.policy_observation(data["viewer"], "tactical")
    assert view["belief"]["status"] == "exact"
    wheat = RESOURCES.index("WHEAT")
    expected = sum(
        rows[wheat]["expected"]
        for color, rows in view["belief"]["hands"].items()
        if color != data["viewer"]
    )
    assert expected == 8
    before = get_player_freqdeck(s.game.state, Color(data["viewer"]))
    s.auto(policy="tactical")
    assert s.intents[-1]["type"] == "PLAY_MONOPOLY"
    assert s.intents[-1]["value"] == "WHEAT"
    after = get_player_freqdeck(s.game.state, Color(data["viewer"]))
    assert after[wheat] - before[wheat] == 8
    old = Session.from_replay(data["replay"])
    old.auto(policy="tactical_v3")
    assert old.intents[-1]["value"] == "WOOD"


@pytest.mark.parametrize("policy", ["baseline", "strategic", "tactical_v3", "tactical"])
def test_displayed_recommendation_autoplay_and_arena_use_same_information(policy):
    data = fixture()
    view = json.loads(
        dispatch(
            json.dumps(
                {
                    "command": "import",
                    "replay": data["replay"],
                    "viewer": data["viewer"],
                    "policy": policy,
                }
            )
        )
    )
    expected = {k: view["recommendations"][0][k] for k in ("type", "color", "value")}
    dispatch(
        json.dumps(
            {"command": "auto", "viewer": data["viewer"], "policy": policy, "count": 1}
        )
    )
    replay = json.loads(dispatch(json.dumps({"command": "export"})))
    assert replay["intents"][-1] == expected
    s = Session.from_replay(data["replay"])
    action, report = select(s, policy, {})
    assert report is None
    assert {k: action[k] for k in expected} == expected
    if policy == "tactical":
        assert expected["value"] == "WHEAT"
    elif policy == "tactical_v3":
        assert expected["value"] == "WOOD"


def test_unavailable_tracker_retains_the_existing_production_fallback():
    data = fixture()
    current = Session.from_replay(data["replay"], False)
    legacy = Session.from_replay(data["replay"], False)
    current.auto(policy="tactical")
    legacy.auto(policy="tactical_v3")
    assert current.intents == legacy.intents


def test_the_policy_observation_exposes_no_other_players_actual_hands():
    data = fixture()
    s = Session.from_replay(data["replay"])
    view = s.policy_observation(data["viewer"], "tactical")
    assert "simulation" not in view
    assert "seed" not in view
    assert "joint_belief" not in view
    assert all(
        "own_points" not in p for p in view["players"] if p["color"] != data["viewer"]
    )
    assert "belief" not in s.policy_observation(data["viewer"], "tactical_v3")
    assert "belief" not in s.policy_observation(data["viewer"], "strategic")
