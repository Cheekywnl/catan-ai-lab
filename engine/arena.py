"""Resumable, seat-balanced policy tournaments with replay and source provenance.

Run as ``python -m engine.arena``. Result checkpoints are append-only. A resume
refuses changed policy code or experiment settings rather than mixing versions.
"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import traceback

from engine import ENGINE_VERSION, RULESET
from engine.session import Session
from engine.policy import rank_actions as baseline
from engine.strategy import rank_actions as strategic


def source_hashes(root=None):
    root = Path(root) if root is not None else Path(__file__).parent
    return {
        str(p.relative_to(root))
        .replace("\\", "/"): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n"))
        .hexdigest()
        for p in sorted(root.rglob("*.py"))
        if "tests" not in p.parts and "__pycache__" not in p.parts
    }


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8")
    # Windows readers can briefly hold a sharing lock while inspecting progress.
    for attempt in range(40):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.05)


def select(session, policy, config):
    actor = session.game.state.current_color().value
    view = session.policy_observation(actor, policy)
    if len(view["legal_actions"]) == 1:
        return view["legal_actions"][0], None
    if policy == "baseline":
        return baseline(view)[0], None
    if policy == "strategic":
        return strategic(view)[0], None
    if policy in ("tactical", "tactical_v3"):
        from engine.tactics import rank_actions

        return rank_actions(view)[0], None
    if policy == "search":
        from engine.planning import search

        report = search(
            session.observation(actor, False, True, compact=True, simulation=True),
            budget=config["budget"],
            horizon=config["horizon"],
            max_candidates=config["candidates"],
            search_seed=1701,
        )
        return report["candidates"][0], report
    raise ValueError(f"Unknown policy: {policy}")


def play_game(task):
    seed, seat, config, directory = task
    root = Path(directory)
    key = f"{seed}-{seat}"
    started = time.perf_counter()
    if source_hashes() != config["source_sha256"]:
        raise RuntimeError("Engine source changed while the tournament was running.")
    session = Session(seed, track_beliefs=config["track_beliefs"])
    challenger = session.game.state.colors[seat]
    decisions = Counter()
    search_stats = Counter()
    error = None
    last_view = None
    last_searches = []
    try:
        while (
            not session.game.winning_color()
            and len(session.intents) < config["max_actions"]
        ):
            actor = session.game.state.current_color()
            policy = (
                config["challenger"] if actor == challenger else config["opponents"]
            )
            action, report = select(session, policy, config)
            if actor == challenger:
                decisions[action["type"]] += 1
            if report:
                search_stats.update(
                    {
                        "decisions": 1,
                        "continuations": report["budget"],
                        "transitions": report["transitions"],
                        "terminal_samples": report["terminal_samples"],
                        "rejected_worlds": report["rejected_worlds"],
                        "elapsed_ms": report["elapsed_ms"],
                    }
                )
                last_searches.append(
                    {
                        "revision": len(session.intents),
                        "actor": actor.value,
                        "score_kind": report["score_kind"],
                        "candidates": report["candidates"],
                    }
                )
                last_searches = last_searches[-12:]
            session.apply(action["id"], len(session.intents))
            if len(session.intents) % 50 == 0:
                atomic_json(
                    root / "progress" / f"{key}.json",
                    {
                        "seed": seed,
                        "seat": seat,
                        "actions": len(session.intents),
                        "elapsed_seconds": round(time.perf_counter() - started, 2),
                        "search": dict(search_stats),
                        "status": "running",
                    },
                )
    except Exception:
        error = traceback.format_exc()
        last_view = session.observation(
            session.game.state.current_color().value, simulation=True
        )
    winner = session.game.winning_color()
    # This is diagnostic after play; hidden actual points never inform a policy.
    final_view = session.observation(challenger.value, False, False, compact=True)
    result = {
        "seed": seed,
        "seat": seat,
        "challenger_color": challenger.value,
        "winner": winner.value if winner else None,
        "win": winner == challenger if winner else None,
        "status": "error" if error else "completed" if winner else "truncated",
        "actions": len(session.intents),
        "turns": final_view["turn"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "challenger_public_points": next(
            p["public_points"]
            for p in final_view["players"]
            if p["color"] == challenger.value
        ),
        "challenger_actual_points": next(
            p["own_points"]
            for p in final_view["players"]
            if p["color"] == challenger.value
        ),
        "decisions": dict(decisions),
        "search": dict(search_stats),
        "checksum": session.chain,
        "error": error,
    }
    atomic_json(root / "replays" / f"{key}.json", session.export())
    if last_searches or error:
        atomic_json(
            root / "diagnostics" / f"{key}.json",
            {
                "result": result,
                "last_searches": last_searches,
                "error_observation": last_view,
            },
        )
    atomic_json(root / "progress" / f"{key}.json", result)
    return result


def summarize(results, config):
    completed = [r for r in results if r["status"] == "completed"]
    seeds = sorted({r["seed"] for r in results})
    balanced = []
    for seed in seeds:
        rows = [r for r in results if r["seed"] == seed]
        if len(rows) == 4 and all(r["status"] == "completed" for r in rows):
            balanced.append(sum(r["win"] for r in rows) / 4)
    rng = random.Random(921)
    interval = None
    if len(balanced) >= 5:
        draws = sorted(
            sum(rng.choices(balanced, k=len(balanced))) / len(balanced)
            for _ in range(5000)
        )
        interval = [draws[125], draws[4874]]
    totals = Counter()
    for r in results:
        totals.update(r["search"])
    n = len(results)
    wins = sum(bool(r["win"]) for r in results)
    unresolved = n - len(completed)
    return {
        "engine_version": ENGINE_VERSION,
        "ruleset": RULESET,
        "config": config,
        "games": n,
        "planned_games": config["boards"] * 4,
        "completed": len(completed),
        "errors": sum(r["status"] == "error" for r in results),
        "truncated": sum(r["status"] == "truncated" for r in results),
        "wins": wins,
        "win_rate": wins / n if n and not unresolved else None,
        "censoring_bounds": [wins / n, (wins + unresolved) / n] if n else [0, 1],
        "complete_balanced_boards": len(balanced),
        "balanced_board_win_rate": sum(balanced) / len(balanced) if balanced else None,
        "board_bootstrap_95_interval": interval,
        "seat_results": [
            {
                "seat": seat,
                "games": sum(r["seat"] == seat for r in results),
                "wins": sum(r["seat"] == seat and r["win"] is True for r in results),
            }
            for seat in range(4)
        ],
        "search": dict(totals),
        "elapsed_game_seconds": round(sum(r["elapsed_seconds"] for r in results), 2),
        "interpretation": "Conditional on the named opponents. Incomplete games are censored. The bootstrap uses completed four-seat boards; it is exploratory until the preregistered batch completes. No GTO or human-strength claim.",
        "results": sorted(results, key=lambda r: (r["seed"], r["seat"])),
    }


def run(config, directory, workers=1):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "manifest.json"
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf8"))
        if previous["config"] != config:
            raise ValueError(
                "Resume requires identical settings and source hashes. Use a new directory."
            )
    else:
        atomic_json(
            manifest,
            {"started_utc": datetime.now(timezone.utc).isoformat(), "config": config},
        )
    results_path = directory / "games.jsonl"
    results = (
        [
            json.loads(line)
            for line in results_path.read_text(encoding="utf8").splitlines()
        ]
        if results_path.exists()
        else []
    )
    done = {(r["seed"], r["seat"]) for r in results}
    tasks = [
        (seed, seat, config, str(directory))
        for seed in range(config["first_seed"], config["first_seed"] + config["boards"])
        for seat in range(4)
        if (seed, seat) not in done
    ]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(play_game, task): task[:2] for task in tasks}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            with results_path.open("a", encoding="utf8") as f:
                f.write(json.dumps(result) + "\n")
                f.flush()
            report = summarize(results, config)
            atomic_json(directory / "summary.json", report)
            print(
                f"{len(results)}/{config['boards']*4} games; wins={report['wins']}; "
                f"errors={report['errors']}; last={result['seed']}/{result['seat']} "
                f"{result['status']} {result['elapsed_seconds']}s",
                flush=True,
            )
    report = summarize(results, config)
    atomic_json(directory / "summary.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--challenger",
        choices=("baseline", "strategic", "tactical", "tactical_v3", "search"),
        default="search",
    )
    p.add_argument(
        "--opponents",
        choices=("baseline", "strategic", "tactical", "tactical_v3", "search"),
        default="strategic",
    )
    p.add_argument("--boards", type=int, default=5)
    p.add_argument("--seed", type=int, default=3000)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--budget", type=int, default=12)
    p.add_argument("--horizon", type=int, default=1600)
    p.add_argument("--candidates", type=int, default=4)
    p.add_argument("--max-actions", type=int, default=4000)
    p.add_argument("--track-beliefs", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--worker-snapshot", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    if not 1 <= args.boards <= 1000 or not 1 <= args.workers <= 8:
        p.error("Use 1–1000 boards and 1–8 workers.")
    if not args.worker_snapshot:
        # Workers use an immutable copy, allowing subsequent work in the checkout.
        output = args.output.resolve()
        snapshot = output / "source"
        if not (snapshot / "engine").exists():
            snapshot.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                Path(__file__).parent,
                snapshot / "engine",
                ignore=shutil.ignore_patterns("__pycache__", "tests"),
            )
        elif source_hashes(snapshot / "engine") != source_hashes():
            p.error(
                "This snapshot has different source. Resume from its source directory or choose a new output directory."
            )
        argv = list(sys.argv[1:])
        argv[argv.index("--output") + 1] = str(output)
        subprocess.run(
            [sys.executable, "-m", "engine.arena", "--worker-snapshot", *argv],
            cwd=snapshot,
            check=True,
        )
        return
    config = {
        k: v
        for k, v in vars(args).items()
        if k not in ("output", "workers", "seed", "worker_snapshot")
    }
    config.update(first_seed=args.seed, source_sha256=source_hashes())
    report = run(config, args.output, args.workers)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ("results", "config")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
