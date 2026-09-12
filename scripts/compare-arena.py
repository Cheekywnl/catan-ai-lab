"""Paired whole-board bootstrap for two completed, matched arena batches."""

import argparse
import json
import random
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--reference", type=Path, required=True)
parser.add_argument("--challenger", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
reference = json.loads(args.reference.read_text())
challenger = json.loads(args.challenger.read_text())
if reference["ruleset"] != challenger["ruleset"]:
    raise ValueError("Rulesets must match.")
for key in ("boards", "first_seed", "opponents", "track_beliefs", "max_actions"):
    if reference["config"][key] != challenger["config"][key]:
        raise ValueError(f"Unmatched protocol: {key}")
for path in ("strategy.py", "policy.py", "opening.py"):
    if (
        reference["config"]["source_sha256"][path]
        != challenger["config"]["source_sha256"][path]
    ):
        raise ValueError(f"Frozen opponent source differs: {path}")


def indexed(report):
    if (
        report["completed"] != report["planned_games"]
        or report["errors"]
        or report["truncated"]
    ):
        raise ValueError(
            "Wait for every planned game to complete; do not discard failures."
        )
    rows = {(r["seed"], r["seat"]): r for r in report["results"]}
    expected = {
        (seed, seat)
        for seed in range(
            report["config"]["first_seed"],
            report["config"]["first_seed"] + report["config"]["boards"],
        )
        for seat in range(4)
    }
    if rows.keys() != expected or len(rows) != len(report["results"]):
        raise ValueError("Missing or duplicated board/seat pairs.")
    return rows


a, b = indexed(reference), indexed(challenger)
if a.keys() != b.keys():
    raise ValueError("Board/seat pairs do not match.")
paired = []
for seed in sorted({seed for seed, _ in a}):
    av = sum(a[seed, seat]["win"] for seat in range(4)) / 4
    bv = sum(b[seed, seat]["win"] for seat in range(4)) / 4
    paired.append(
        {
            "seed": seed,
            "reference_rate": av,
            "challenger_rate": bv,
            "difference": bv - av,
        }
    )
rng = random.Random(20321)
values = [row["difference"] for row in paired]
draws = sorted(
    sum(rng.choices(values, k=len(values))) / len(values) for _ in range(10000)
)
result = {
    "reference": reference,
    "challenger": challenger,
    "paired_boards": paired,
    "win_rate_difference": sum(values) / len(values),
    "paired_board_bootstrap_95_interval": [draws[250], draws[9749]],
    "mean_game_seconds": {
        label: sum(row["elapsed_seconds"] for row in report["results"])
        / len(report["results"])
        for label, report in [("reference", reference), ("challenger", challenger)]
    },
    "interpretation": "Challenger minus reference winning rate against the named fixed opponents. Bootstrap resamples complete four-seat boards and retains pairing. This small comparison does not establish human strength, equilibrium play, or the benefit of subsequent engine changes. Runtime includes concurrent machine workload.",
}
args.output.write_text(json.dumps(result, indent=2) + "\n")
print(
    json.dumps(
        {
            k: v
            for k, v in result.items()
            if k not in ("reference", "challenger", "paired_boards")
        },
        indent=2,
    )
)
