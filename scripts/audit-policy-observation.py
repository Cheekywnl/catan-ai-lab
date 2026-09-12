"""Compare displayed tactical suggestions with the actual autoplay input boundary."""

import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--engine-root", type=Path, required=True)
parser.add_argument("--replays", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--limit", type=int, default=40)
args = parser.parse_args()
sys.path.insert(0, str(args.engine_root.resolve()))
from engine import ENGINE_VERSION
from engine.arena import source_hashes
from engine.session import Session, decode_action
from engine.tactics import rank_actions

paths = sorted(args.replays.glob("*.json"))[: args.limit]
if not paths:
    raise ValueError("No replays found.")
cases, verified = [], []
positions = 0
for path in paths:
    data = json.loads(path.read_text())
    session = Session(data["seed"], True, data["ruleset"])
    session.replay_version = data["engine_version"]
    for intent in data["intents"]:
        if any(a.action_type.value == "PLAY_MONOPOLY" for a in session.legal()):
            actor = session.game.state.current_color().value
            autoplay = (
                session.policy_observation(actor, "tactical")
                if hasattr(session, "policy_observation")
                else session.observation(actor, False, False, compact=True)
            )
            displayed = session.observation(actor, False, True, compact=True)
            a, b = rank_actions(autoplay)[0], rank_actions(displayed)[0]
            positions += 1
            if a["id"] != b["id"]:
                cases.append(
                    {
                        "replay": path.name,
                        "revision": len(session.intents),
                        "viewer": actor,
                        "tracker_status": displayed["belief"]["status"],
                        "autoplay": a,
                        "displayed_suggestion": b,
                    }
                )
        session.execute(decode_action(intent))
    assert session.chain == data["checksum"]
    verified.append({"replay": path.name, "checksum": session.chain})
report = {
    "engine_version": ENGINE_VERSION,
    "source_sha256": source_hashes(),
    "games": len(paths),
    "monopoly_decisions": positions,
    "different_top_action": len(cases),
    "cases": cases,
    "verified_replays": verified,
    "interpretation": "Reused replay diagnostic of the input boundary, not a strength estimate. Both policies use player observations. Each replay checksum is verified; different decisions in the same game are correlated.",
}
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(
    json.dumps(
        {
            k: v
            for k, v in report.items()
            if k not in ("cases", "source_sha256", "verified_replays")
        },
        indent=2,
    )
)
