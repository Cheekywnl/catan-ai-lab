"""Replay an existing batch and test the public nine-point nonwin constraint."""

import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--replays", type=Path, required=True)
parser.add_argument(
    "--engine-root", type=Path, default=Path(__file__).resolve().parents[1]
)
parser.add_argument("--limit", type=int, default=40)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.engine_root.resolve()))

from engine import ENGINE_VERSION
from engine.arena import source_hashes
from engine.session import Session, decode_action
from engine.planning import development_beliefs
from catanatron.state_functions import player_key

paths = sorted(args.replays.glob("*.json"))[: args.limit]
if not paths:
    raise ValueError("No replay files found.")
cases, checked = [], []
turns = 0
for path in paths:
    replay = json.loads(path.read_text())
    session = Session(replay["seed"], False, replay["ruleset"])
    session.replay_version = replay["engine_version"]
    for intent in replay["intents"]:
        session.execute(decode_action(intent))
        if intent["type"] != "END_TURN" or session.game.winning_color():
            continue
        turns += 1
        view = session.observation(
            session.game.state.current_color().value, False, False
        )
        player = next(p for p in view["players"] if p["color"] == intent["color"])
        if player["public_points"] != 9 or not player["development_count"]:
            continue
        probability = development_beliefs(view)["hands"][player["color"]][
            "VICTORY_POINT"
        ]["probability_at_least_one"]
        key = player_key(session.game.state, decode_action(intent).color)
        assert session.game.state.player_state[key + "_VICTORY_POINT_IN_HAND"] == 0
        if probability > 0:
            cases.append(
                {
                    "replay": path.name,
                    "revision": len(session.intents),
                    "viewer": view["viewer"],
                    "player": player["color"],
                    "development_count": player["development_count"],
                    "impossible_vp_probability": probability,
                }
            )
    assert session.chain == replay["checksum"]
    checked.append({"replay": path.name, "checksum": session.chain})
result = {
    "engine_version": ENGINE_VERSION,
    "source_sha256": source_hashes(),
    "replays": len(paths),
    "completed_turns": turns,
    "contradictory_position_count": len(cases),
    "distinct_games": len({c["replay"] for c in cases}),
    "cases": cases,
    "verified_replays": checked,
    "interpretation": "Offline diagnosis on previously evaluated boards, not new strength evidence. Cases share games and are not independent. Hidden cards are used only in offline assertions; all model inputs come from the observation.",
}
args.output.write_text(json.dumps(result, indent=2) + "\n")
print(
    json.dumps(
        {
            k: v
            for k, v in result.items()
            if k not in ("cases", "source_sha256", "verified_replays")
        },
        indent=2,
    )
)
