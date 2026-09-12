"""Behavior-preserving acceleration of the frozen strategic-v2 policy.

The mean-flow affordability function is piecewise linear. Solve its zero, then
check the adjacent grid points used by the reference's nine bisections. The
policy's quantization, tolerance, caps, scoring and tie breaks remain unchanged.

Function bindings copy the reference functions' global dictionaries rather than
mutating the reference module or maintaining a second copy of its policy code.
"""

from functools import lru_cache
import math
from types import FunctionType

from engine import strategy as reference

STEP = 120.0 / 512
EPSILON = 1e-9


@lru_cache(maxsize=32768)
def _eta(hand, cost, production, rates):
    def feasible(t):
        # Preserve the reference's floating-point arithmetic and summation order.
        balance = [h + p * t - c for h, p, c in zip(hand, production, cost)]
        return (
            sum(max(0, b) / r for b, r in zip(balance, rates))
            >= sum(max(0, -b) for b in balance) - EPSILON
        )

    if feasible(0):
        return 0.0
    if not feasible(120):
        return 120.0

    balances = [h - c for h, c in zip(hand, cost)]
    value = sum(max(0, b) / r for b, r in zip(balances, rates)) - sum(
        max(0, -b) for b in balances
    )
    slope = sum(p if b < 0 else p / r for b, p, r in zip(balances, production, rates))
    knots = sorted(
        ((-b / p), p / r - p)
        for b, p, r in zip(balances, production, rates)
        if b < 0 and p > 0
    )
    left = 0.0
    root = 120.0
    for right, change in knots + [(120.0, 0.0)]:
        right = min(120.0, right)
        if slope > 0:
            candidate = left + (-EPSILON - value) / slope
            if candidate <= right:
                root = max(left, candidate)
                break
        value += slope * (right - left)
        left = right
        slope += change
        if right >= 120:
            break

    index = max(1, min(512, math.ceil(root / STEP)))
    # Analytic arithmetic can land either side of a grid boundary. The original
    # predicate determines the exact same smallest feasible grid point.
    while index < 512 and not feasible(index * STEP):
        index += 1
    while index > 1 and feasible((index - 1) * STEP):
        index -= 1
    return index * STEP


def eta(hand, cost, production, rates):
    return _eta(tuple(hand), tuple(cost), tuple(production), tuple(rates))


def _bind(function, replacements):
    return FunctionType(
        function.__code__,
        {**function.__globals__, **replacements},
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )


analyze = _bind(reference.analyze, {"eta": eta})
rank_actions = _bind(reference.rank_actions, {"eta": eta, "analyze": analyze})


def choose_action(observation):
    legal = observation["legal_actions"]
    return legal[0] if len(legal) == 1 else rank_actions(observation)[0]
