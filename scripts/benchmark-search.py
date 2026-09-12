"""Compare reference/optimized continuation runtime without profiler overhead."""
import json
from pathlib import Path
import statistics
import sys
import time

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from engine.session import Session
from engine import planning, fast_policy, strategy
from engine.arena import source_hashes

rows = []
optimized_choose = planning.choose_action
for seed, step in [(42, 60), (42, 150), (17, 180), (71, 100), (86, 150), (91, 200)]:
    session = Session(seed, False)
    session.auto(step, policy="tactical")
    if session.game.winning_color():
        continue
    view = session.observation(session.game.state.current_color().value, simulation=True)
    reports, seconds = {}, {}
    order = ["reference", "optimized"] if len(rows) % 2 == 0 else ["optimized", "reference"]
    for name in order:
        planning.choose_action = optimized_choose if name == "optimized" else lambda o: strategy.rank_actions(o)[0]
        fast_policy._eta.cache_clear()
        started = time.perf_counter()
        report = planning.search(view, budget=12, horizon=1600, max_candidates=4)
        seconds[name] = time.perf_counter() - started
        report.pop("elapsed_ms")
        reports[name] = report
    assert reports["reference"] == reports["optimized"]
    rows.append({"seed": seed, "revision": len(session.intents), **seconds,
                 "speedup": seconds["reference"] / seconds["optimized"],
                 "transitions": reports["optimized"]["transitions"],
                 "continuations": reports["optimized"]["budget"],
                 "identical_results": True})
    print(json.dumps(rows[-1]), flush=True)
planning.choose_action = optimized_choose
result = {"protocol": "Six fixed nonterminal positions. Alternate reference/optimized order, clear ETA cache before each run, identical root budget/horizon/seed. Compare complete results excluding wall-clock time. No profiler. Timing is local and machine-specific; it does not measure playing strength.",
          "budget": 12, "horizon": 1600, "source_sha256": source_hashes(),
          "median_speedup": statistics.median(r["speedup"] for r in rows),
          "aggregate_speedup": sum(r["reference"] for r in rows) / sum(r["optimized"] for r in rows),
          "positions": rows}
destination = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "research/speed-v3.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
print(json.dumps({k: v for k, v in result.items() if k not in ("source_sha256", "positions")}, indent=2))
