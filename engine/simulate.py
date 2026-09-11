"""Reproducible baseline evaluation and optional observation/action training data.

python -m engine.simulate --games 100 --output research/engine-validation.json
python -m engine.simulate --games 5 --trajectories work/teacher.jsonl
"""

import argparse
from collections import Counter
from pathlib import Path
import json
import platform
import time
from engine import ENGINE_VERSION, RULESET
from engine.session import Session
from engine.policy import rank_actions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trajectories", type=Path)
    args = parser.parse_args()
    if not 1 <= args.games <= 100000:
        parser.error("games must be between 1 and 100000")
    stream = None
    if args.trajectories:
        args.trajectories.parent.mkdir(parents=True, exist_ok=True)
        stream = args.trajectories.open("w", encoding="utf8")
    results = []
    wins = Counter()
    started = time.perf_counter()
    try:
        for i in range(args.games):
            s = Session(args.seed + i, track_beliefs=False)
            rows = []
            while not s.game.winning_color() and len(s.intents) < 6000:
                color = s.game.state.current_color().value
                observation = s.observation(
                    color, include_history=bool(stream), include_belief=False
                )
                recommendation = rank_actions(observation)[0]
                if stream:
                    rows.append(
                        {
                            "schema": "catan-observation-action-v1",
                            "engine_version": ENGINE_VERSION,
                            "ruleset": RULESET,
                            "episode": i,
                            "step": len(s.intents),
                            "actor": color,
                            "observation": observation,
                            "action": {
                                k: recommendation[k] for k in ["type", "value", "color"]
                            },
                            "teacher": "heuristic-v1",
                        }
                    )
                s.apply(recommendation["id"], len(s.intents))
            winner = s.game.winning_color()
            if winner:
                wins[winner.value] += 1
            results.append(
                {
                    "seed": args.seed + i,
                    "winner": winner.value if winner else None,
                    "actions": len(s.intents),
                    "turns": s.observation(include_history=False)["turn"],
                    "checksum": s.chain,
                }
            )
            if stream:
                for row in rows:
                    row["outcome"] = (
                        int(row["actor"] == winner.value) if winner else None
                    )
                    stream.write(json.dumps(row, separators=(",", ":")) + "\n")
            if (i + 1) % 20 == 0:
                print(f"{i+1}/{args.games} games complete", flush=True)
    finally:
        if stream:
            stream.close()
    seconds = time.perf_counter() - started
    report = {
        "engine_version": ENGINE_VERSION,
        "ruleset": RULESET,
        "suite": "four identical observation-only heuristic policies; deterministic seeds; not a playing-strength benchmark",
        "games": args.games,
        "completed": sum(r["winner"] is not None for r in results),
        "truncated": sum(r["winner"] is None for r in results),
        "actions": sum(r["actions"] for r in results),
        "wins_by_color": dict(sorted(wins.items())),
        "elapsed_seconds": round(seconds, 3),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "processor": platform.machine(),
        },
        "invariants": "19 cards per resource, 25 development cards, player piece counts; checked after every action",
        "results": results,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
