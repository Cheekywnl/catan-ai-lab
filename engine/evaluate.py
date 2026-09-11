"""Seat-rotated, board-held-out evaluation against the frozen v1 policy."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import time
from engine import ENGINE_VERSION, RULESET
from engine.session import Session
from engine.policy import rank_actions as baseline
from engine.strategy import rank_actions as strategic


def evaluate(boards=25, first_seed=1000):
    started = time.perf_counter()
    results = []
    for seed in range(first_seed, first_seed + boards):
        for seat in range(4):
            session = Session(seed, False)
            challenger = session.game.state.colors[seat]
            while not session.game.winning_color() and len(session.intents) < 4000:
                actor = session.game.state.current_color()
                view = session.observation(actor.value, False, False, compact=True)
                action = (strategic if actor == challenger else baseline)(view)[0]
                session.apply(action["id"], len(session.intents))
            winner = session.game.winning_color()
            results.append(
                {
                    "seed": seed,
                    "seat": seat,
                    "challenger": challenger.value,
                    "winner": winner.value if winner else None,
                    "win": winner == challenger,
                    "actions": len(session.intents),
                    "checksum": session.chain,
                }
            )
        if (seed - first_seed + 1) % 5 == 0:
            print(f"{seed-first_seed+1}/{boards} boards evaluated", flush=True)
    means = [
        sum(r["win"] for r in results if r["seed"] == seed) / 4
        for seed in range(first_seed, first_seed + boards)
    ]
    rng = random.Random(93871)
    bootstrap = sorted(sum(rng.choices(means, k=boards)) / boards for _ in range(5000))
    source = Path(__file__).parent
    return {
        "engine_version": ENGINE_VERSION,
        "ruleset": RULESET,
        "challenger": "strategic-v2",
        "opponents": ["frozen-heuristic-v1"] * 3,
        "protocol": "Four starting seats per board, held-out seeds. All policies receive their own observations only. No adaptive tuning during this evaluation.",
        "first_seed": first_seed,
        "boards": boards,
        "games": len(results),
        "completed": sum(r["winner"] is not None for r in results),
        "wins": sum(r["win"] for r in results),
        "win_rate": sum(means) / boards,
        "board_bootstrap_95_interval": [bootstrap[125], bootstrap[4874]],
        "seat_win_rates": [
            sum(r["win"] for r in results if r["seat"] == seat) / boards
            for seat in range(4)
        ],
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "policy_sha256": {
            name: hashlib.sha256(
                (source / name).read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for name in ("policy.py", "strategy.py", "opening.py")
        },
        "interpretation": "Strength against the original project bot only. Confidence interval resamples whole boards to retain seat correlation. This is not a human, external-agent, or GTO benchmark.",
        "results": results,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--boards", type=int, default=25)
    p.add_argument("--seed", type=int, default=1000)
    p.add_argument("--output", type=Path, default=Path("research/strength-v2.json"))
    a = p.parse_args()
    if not 5 <= a.boards <= 1000:
        p.error("Use 5 to 1000 boards.")
    report = evaluate(a.boards, a.seed)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
