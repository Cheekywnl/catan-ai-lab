"""Fixed-position repeatability audit, using an explicitly frozen engine checkout.

This is a tuning diagnostic. Independent, uniformly allocated reference rollouts
estimate the same opponent-model values; they are neither ground truth nor GTO.
"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import traceback


def init_worker(engine_root):
    sys.path.insert(0, str(engine_root))


def write_json(path, data):
    from engine.arena import atomic_json

    atomic_json(path, data)


def reference_rollout(observation, action, rng, horizon):
    from engine.planning import sample_game
    from engine.session import Session, decode_action
    from engine.fast_policy import choose_action
    from engine.strategy import position_value

    rejected = 0
    for attempt in range(64):
        try:
            game = sample_game(observation, rng)
            break
        except ValueError:
            rejected += 1
            if attempt == 63:
                raise
    game.execute(decode_action(action))
    shell = Session.__new__(Session)
    shell.game = game
    shell._geometry = {
        k: observation["board"][k] for k in ("tiles", "nodes", "edges", "ports")
    }
    shell.intents, shell.events, shell.trackers = [], [], {}
    shell.track_beliefs = False
    transitions = 1
    for _ in range(horizon - 1):
        if game.winning_color():
            break
        view = shell.observation(
            game.state.current_color().value, False, False, compact=True
        )
        game.execute(decode_action(choose_action(view)))
        transitions += 1
    winner = game.winning_color()
    score = (
        float(winner.value == observation["viewer"])
        if winner
        else position_value(
            shell.observation(observation["viewer"], False, False, compact=True)
        )
    )
    return score, winner is not None, transitions, rejected


def audit_position(task):
    from engine.planning import search
    from engine.tactics import rank_actions

    packet, config, output = task
    observation = packet["observation"]
    index = packet["index"]
    started = time.perf_counter()
    result = {
        "index": index,
        "seed": packet["seed"],
        "revision": packet["revision"],
        "runs": [],
        "reference": [],
        "error": None,
    }
    path = Path(output) / "positions" / f"{index}.json"
    try:
        rankings = rank_actions(observation)
        result["tactical_action"] = rankings[0]["id"]
        candidates = None
        for budget in config["budgets"]:
            for repetition in range(config["replicates"]):
                search_seed = 820000 + index * 1000 + budget * 10 + repetition
                report = search(observation, budget, config["horizon"], 4, search_seed)
                ids = {a["id"] for a in report["candidates"]}
                if candidates is None:
                    candidates = [a for a in rankings if a["id"] in ids]
                elif ids != {a["id"] for a in candidates}:
                    raise ValueError("Candidate screening changed between repetitions.")
                result["runs"].append(
                    {
                        "requested_budget": budget,
                        "repetition": repetition,
                        "search_seed": search_seed,
                        "report": report,
                    }
                )
                write_json(path, result)
        for action in candidates:
            rng_seed = 91000000 + index * 1000 + action["id"]
            rng = random.Random(rng_seed)
            values = []
            terminal = transitions = rejections = 0
            for _ in range(config["reference_per_action"]):
                value, complete, steps, rejected = reference_rollout(
                    observation, action, rng, config["horizon"]
                )
                values.append(value)
                terminal += complete
                transitions += steps
                rejections += rejected
            result["reference"].append(
                {
                    "action": action,
                    "rng_seed": rng_seed,
                    "samples": len(values),
                    "terminal": terminal,
                    "values": values,
                    "mean": sum(values) / len(values),
                    "transitions": transitions,
                    "rejected_worlds": rejections,
                }
            )
            write_json(path, result)
        result["status"] = "completed"
    except Exception:
        result["status"] = "error"
        result["error"] = traceback.format_exc()
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    write_json(path, result)
    return result


def prepare(config, output):
    from engine.session import Session, decode_action
    from engine.tactics import rank_actions

    packets, missing = [], []
    for index in range(config["positions"]):
        seed = config["first_seed"] + index
        threshold = (0, 100, 220)[index % 3]
        s = Session(seed, True)
        for _ in range(2000):
            if s.game.winning_color():
                break
            observation = s.observation(
                s.game.state.current_color().value, False, False, compact=True
            )
            eligible = threshold == 0 or observation["phase"] == "PLAY_TURN"
            if (
                len(s.intents) >= threshold
                and eligible
                and len(observation["legal_actions"]) >= 2
            ):
                packet = {
                    "index": index,
                    "seed": seed,
                    "revision_threshold": threshold,
                    "revision": len(s.intents),
                    "observation": s.observation(
                        s.game.state.current_color().value, simulation=True
                    ),
                }
                packets.append(packet)
                write_json(output / "packets" / f"{index}.json", packet)
                break
            s.execute(decode_action(rank_actions(observation)[0]))
        else:
            raise ValueError("Position generation exceeded action cap.")
        if not packets or packets[-1]["index"] != index:
            missing.append(
                {
                    "index": index,
                    "seed": seed,
                    "reason": "Game ended before an eligible position.",
                }
            )
    return packets, missing


def summarize(results, manifest):
    completed = [r for r in results if r["status"] == "completed"]
    rows = []
    for r in completed:
        reference = {row["action"]["id"]: row["mean"] for row in r["reference"]}
        for budget in manifest["config"]["budgets"]:
            runs = [
                run["report"] for run in r["runs"] if run["requested_budget"] == budget
            ]
            choices = Counter(run["candidates"][0]["id"] for run in runs)
            selected_reference = sum(
                reference[run["candidates"][0]["id"]] for run in runs
            ) / len(runs)
            own_estimate = sum(
                run["candidates"][0]["search_score"] for run in runs
            ) / len(runs)
            rows.append(
                {
                    "index": r["index"],
                    "seed": r["seed"],
                    "revision": r["revision"],
                    "budget": budget,
                    "choice_counts": dict(choices),
                    "modal_share": max(choices.values()) / len(runs),
                    "tactical_choice_share": choices[r["tactical_action"]] / len(runs),
                    "mean_selected_reference_score": selected_reference,
                    "tactical_reference_score": reference[r["tactical_action"]],
                    "selected_minus_tactical_reference_score": selected_reference
                    - reference[r["tactical_action"]],
                    "mean_reported_minus_reference_score": own_estimate
                    - selected_reference,
                    "all_reference_terminal": all(
                        x["samples"] == x["terminal"] for x in r["reference"]
                    ),
                }
            )
    aggregate = {}
    for budget in manifest["config"]["budgets"]:
        group = [row for row in rows if row["budget"] == budget]
        aggregate[budget] = (
            {
                key: sum(row[key] for row in group) / len(group)
                for key in (
                    "modal_share",
                    "tactical_choice_share",
                    "selected_minus_tactical_reference_score",
                    "mean_reported_minus_reference_score",
                )
            }
            if group
            else None
        )
    return {
        "manifest": manifest,
        "completed_positions": len(completed),
        "errors": [r for r in results if r["status"] == "error"],
        "rows": rows,
        "aggregate": aggregate,
        "interpretation": "Fixed tuning positions selected by revision/phase, not search outcome. Repeated recommendations measure stability, not quality alone. Independent uniform reference samples estimate the SAME rollout-opponent model with their own uncertainty; they are not ground truth, calibrated human win rates, or GTO. No completed-game strength claim.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-seed", type=int, default=6400)
    parser.add_argument("--positions", type=int, default=12)
    parser.add_argument("--replicates", type=int, default=6)
    parser.add_argument("--reference-per-action", type=int, default=64)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    args.engine_root = args.engine_root.resolve()
    init_worker(args.engine_root)
    from engine import ENGINE_VERSION
    from engine.arena import source_hashes

    config = {
        "first_seed": args.first_seed,
        "positions": args.positions,
        "replicates": args.replicates,
        "reference_per_action": args.reference_per_action,
        "budgets": [12, 48],
        "horizon": 1600,
        "max_initial_candidates": 4,
        "position_rule": "At/after revisions 0,100,220 cycling by seed; first nonterminal eligible decision with >=2 legal actions. Post-setup requires PLAY_TURN. Tactical play generates positions; all public trackers enabled.",
    }
    manifest = {
        "engine_version": ENGINE_VERSION,
        "source_sha256": source_hashes(),
        "script_sha256": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "config": config,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            raise ValueError("Existing audit uses a different source or protocol.")
        packets = [
            json.loads(p.read_text())
            for p in sorted((args.output / "packets").glob("*.json"))
        ]
    else:
        write_json(manifest_path, manifest)
        packets, missing = prepare(config, args.output)
        write_json(args.output / "missing.json", missing)
    results, pending = [], []
    for packet in packets:
        path = args.output / "positions" / f"{packet['index']}.json"
        existing = json.loads(path.read_text()) if path.exists() else None
        if existing and existing.get("status") == "completed":
            results.append(existing)
        else:
            pending.append((packet, config, str(args.output)))
    with ProcessPoolExecutor(
        max_workers=args.workers, initializer=init_worker, initargs=(args.engine_root,)
    ) as pool:
        for future in as_completed(
            [pool.submit(audit_position, task) for task in pending]
        ):
            result = future.result()
            results.append(result)
            print(
                f"{len(results)}/{len(packets)} positions; seed={result['seed']}; status={result['status']}; seconds={result['elapsed_seconds']}",
                flush=True,
            )
            write_json(args.output / "summary.json", summarize(results, manifest))
    summary = summarize(results, manifest)
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary["aggregate"], indent=2), flush=True)


if __name__ == "__main__":
    main()
