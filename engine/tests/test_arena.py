import copy
import json
from pathlib import Path

import pytest

from engine.arena import play_game, run, source_hashes, summarize, atomic_json
from engine.session import Session


def configuration():
    return {
        "challenger": "strategic",
        "opponents": "baseline",
        "boards": 1,
        "first_seed": 3099,
        "budget": 12,
        "horizon": 1600,
        "candidates": 4,
        "max_actions": 4000,
        "track_beliefs": False,
        "source_sha256": source_hashes(),
    }


def test_checkpoint_replace_recovers_from_a_transient_windows_reader_lock(
    tmp_path, monkeypatch
):
    original = Path.replace
    attempts = []

    def temporarily_locked(source, target):
        attempts.append(target)
        if len(attempts) == 1:
            raise PermissionError("Sharing violation")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", temporarily_locked)
    destination = tmp_path / "summary.json"
    atomic_json(destination, {"completed": 800})
    assert json.loads(destination.read_text()) == {"completed": 800}
    assert len(attempts) == 2


def test_arena_replay_reproduces_completed_game_and_refuses_changed_source(tmp_path):
    config = configuration()
    result = play_game((3099, 0, config, str(tmp_path)))
    assert result["status"] == "completed" and result["error"] is None
    replay = json.loads((tmp_path / "replays/3099-0.json").read_text())
    reproduced = Session.from_replay(replay, track_beliefs=False)
    assert reproduced.chain == result["checksum"]
    assert reproduced.game.winning_color().value == result["winner"]
    changed = copy.deepcopy(config)
    changed["source_sha256"]["strategy.py"] = "changed"
    with pytest.raises(RuntimeError, match="source changed"):
        play_game((3099, 1, changed, str(tmp_path)))


def test_arena_incomplete_games_are_censored_not_silently_counted_as_losses():
    rows = [
        {
            "seed": 1,
            "seat": i,
            "win": win,
            "status": status,
            "search": {},
            "elapsed_seconds": 1,
        }
        for i, (win, status) in enumerate(
            [
                (True, "completed"),
                (False, "completed"),
                (None, "error"),
                (None, "truncated"),
            ]
        )
    ]
    report = summarize(rows, configuration())
    assert report["win_rate"] is None
    assert report["censoring_bounds"] == [0.25, 0.75]
    assert report["complete_balanced_boards"] == 0
    assert report["board_bootstrap_95_interval"] is None


def test_arena_resume_preserves_completed_games_and_rejects_config_changes(tmp_path):
    config = configuration()
    first = run(config, tmp_path, workers=1)
    second = run(config, tmp_path, workers=1)
    assert first == second and first["games"] == 4
    assert len((tmp_path / "games.jsonl").read_text().splitlines()) == 4
    config["budget"] += 1
    with pytest.raises(ValueError, match="identical settings"):
        run(config, tmp_path)
