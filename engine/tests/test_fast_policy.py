import copy
import random

import pytest

from engine import fast_policy
from engine import strategy as reference
from engine.session import Session, decode_action


def test_piecewise_solver_matches_reference_quantization_over_diverse_hands():
    rng = random.Random(20871)
    for _ in range(10000):
        hand = [rng.randrange(20) for _ in range(5)]
        cost = [rng.randrange(7) for _ in range(5)]
        production = [rng.randrange(13) / 36 for _ in range(5)]
        rates = [rng.choice([2, 3, 4]) for _ in range(5)]
        assert fast_policy.eta(hand, cost, production, rates) == reference.eta(
            hand, cost, production, rates
        )


def test_piecewise_solver_preserves_near_boundary_and_capped_results():
    for index in range(1, 513):
        for factor in (1 - 1e-10, 1, 1 + 1e-10):
            production = [factor / (index * fast_policy.STEP), 0, 0, 0, 0]
            assert fast_policy.eta(
                [0] * 5, [1, 0, 0, 0, 0], production, [4] * 5
            ) == reference.eta([0] * 5, [1, 0, 0, 0, 0], production, [4] * 5)
    assert fast_policy.eta([0] * 5, [1] * 5, [0] * 5, [4] * 5) == 120
    assert fast_policy.eta([4, 0, 0, 0, 0], [0, 1, 0, 0, 0], [0] * 5, [4] * 5) == 0


@pytest.mark.parametrize("seed", range(8))
def test_every_ranked_move_and_score_matches_reference_through_full_games(seed):
    s = Session(5200 + seed, False)
    original_eta = reference.eta
    while not s.game.winning_color() and len(s.intents) < 2000:
        o = s.observation(
            s.game.state.current_color().value, False, False, compact=True
        )
        before = copy.deepcopy(o)
        old = reference.rank_actions(o)
        new = fast_policy.rank_actions(o)
        assert new == old
        assert fast_policy.choose_action(o)["id"] == old[0]["id"]
        assert o == before and reference.eta is original_eta
        s.execute(decode_action(new[0]))
    assert s.game.winning_color() is not None


@pytest.mark.parametrize("seed,step", [(42, 60), (17, 180)])
def test_optimized_search_produces_identical_candidates_scores_and_simulated_transitions(
    seed, step, monkeypatch
):
    from engine import planning

    s = Session(seed, False)
    s.auto(step, policy="tactical")
    o = s.observation(s.game.state.current_color().value, simulation=True)
    optimized = planning.search(o, budget=12, horizon=80, max_candidates=4)
    monkeypatch.setattr(
        planning, "choose_action", lambda view: reference.rank_actions(view)[0]
    )
    original = planning.search(o, budget=12, horizon=80, max_candidates=4)
    optimized.pop("elapsed_ms")
    original.pop("elapsed_ms")
    assert optimized == original
