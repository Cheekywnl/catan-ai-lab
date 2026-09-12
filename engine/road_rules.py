"""Exact base-game road trails and award ownership, using public board data.

An opponent's building terminates a trail, but the road ending there still
counts. Edges may not repeat. The incumbent keeps a tied award; otherwise a
tie leaves it unclaimed. See https://www.catan.com/faq/basegame .
"""

from collections import defaultdict
from functools import lru_cache


@lru_cache(maxsize=32768)
def longest_trail(edges, blocked):
    adjacency = defaultdict(list)
    for i, (a, b) in enumerate(edges):
        adjacency[a].append((b, i))
        adjacency[b].append((a, i))
    blocked = frozenset(blocked)

    def walk(node, used):
        if used and node in blocked:
            return ()
        best = ()
        for other, i in adjacency[node]:
            if not used & (1 << i):
                path = (edges[i],) + walk(other, used | (1 << i))
                if len(path) > len(best):
                    best = path
        return best

    return max((walk(node, 0) for node in sorted(adjacency)), key=len, default=())


def award_owner(lengths, incumbent):
    best = max(lengths.values(), default=0)
    if best < 5:
        return None
    tied = [color for color, length in lengths.items() if length == best]
    if incumbent in tied:
        return incumbent
    return tied[0] if len(tied) == 1 else None


def refresh_networks(board):
    """Rebuild the small road/expansion caches after a road or settlement."""
    colors = set(board.connected_components) | set(board.roads.values())
    colors.update(color for color, _ in board.buildings.values())
    components = defaultdict(list)
    lengths = defaultdict(int)
    for color in sorted(colors, key=lambda c: c.value):
        edges = tuple(
            sorted({tuple(sorted(e)) for e, c in board.roads.items() if c == color})
        )
        blocked = tuple(
            sorted(n for n, (c, _) in board.buildings.items() if c != color)
        )
        lengths[color] = len(longest_trail(edges, blocked))
        # Expansion cannot pass through an opponent's building. Include isolated
        # own settlements so their first road remains legal during the draft.
        adjacency = defaultdict(set)
        available = {n for e in edges for n in e if n not in blocked}
        available.update(n for n, (c, _) in board.buildings.items() if c == color)
        for a, b in edges:
            if a not in blocked and b not in blocked:
                adjacency[a].add(b)
                adjacency[b].add(a)
        while available:
            start = min(available)
            reached, agenda = set(), [start]
            while agenda:
                node = agenda.pop()
                if node in reached:
                    continue
                reached.add(node)
                agenda.extend(adjacency[node] - reached)
            available.difference_update(reached)
            components[color].append(reached)
    board.connected_components = components
    board.road_lengths = lengths
    board.road_color = award_owner(lengths, board.road_color)
    board.road_length = lengths[board.road_color] if board.road_color is not None else 0
    board.buildable_edges_cache = {}
    board.player_port_resources_cache = {}
