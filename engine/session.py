"""Authoritative game session, event views, replay, and observation-only bot boundary."""

import copy
import hashlib
import json
import math
from enum import Enum

from engine import ENGINE_VERSION, RULESET, REPLAY_VERSIONS, REPLAY_RULESETS
from engine.beliefs import ResourceBelief
from engine.policy import rank_actions, draft_search
from catanatron.game import Game
from catanatron.models.player import Color, SimplePlayer
from catanatron.models.enums import Action, ActionType, RESOURCES, DEVELOPMENT_CARDS
from catanatron.models.tiles import Port
from catanatron.state_functions import (
    player_key,
    get_player_freqdeck,
    player_num_resource_cards,
)


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [plain(x) for x in value]
    if isinstance(value, dict):
        return {plain(k): plain(v) for k, v in value.items()}
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def action_value(action):
    return {
        "type": action.action_type.value,
        "color": action.color.value,
        "value": plain(action.value),
    }


def decode_action(value):
    kind = ActionType(value["type"])
    payload = value.get("value")
    if kind == ActionType.MOVE_ROBBER:
        payload = (tuple(payload[0]), Color(payload[1]) if payload[1] else None)
    elif kind == ActionType.CONFIRM_TRADE:
        payload = (*payload[:10], Color(payload[10]))
    elif isinstance(payload, list):
        payload = tuple(payload)
    return Action(Color(value["color"]), kind, payload)


def action_label(action):
    kind, value = action["type"], action["value"]
    if kind in ("BUILD_SETTLEMENT", "BUILD_CITY"):
        return f"{'Settlement' if kind=='BUILD_SETTLEMENT' else 'City'} at intersection {value}"
    if kind == "BUILD_ROAD":
        return f"Road {value[0]}–{value[1]}"
    if kind == "MOVE_ROBBER":
        return f"Robber to {','.join(map(str,value[0]))}" + (
            f"; steal from {value[1].title()}" if value[1] else ""
        )
    if kind == "MARITIME_TRADE":
        return f"Trade {sum(v is not None for v in value[:-1])} {value[0].lower()} for 1 {value[-1].lower()}"
    if kind == "DISCARD_RESOURCE":
        return f"Discard 1 {value.lower()}"
    if kind == "PLAY_MONOPOLY":
        return f"Monopoly: {value.lower()}"
    if kind == "PLAY_YEAR_OF_PLENTY":
        return "Year of Plenty: " + ", ".join(v.lower() for v in value)
    if kind == "CONFIRM_TRADE":
        return f"Confirm trade with {value[10].title()}"
    return kind.replace("_", " ").capitalize()


class Session:
    def __init__(self, seed=2026, track_beliefs=True, ruleset=RULESET):
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("Seed must be a whole number from 0 to 4294967295.")
        self.seed = seed
        self.replay_version = ENGINE_VERSION
        if ruleset not in REPLAY_RULESETS:
            raise ValueError("Unsupported ruleset.")
        self.game = Game([SimplePlayer(color) for color in Color], seed=seed)
        self.game.state.board.rules_revision = 2 if ruleset == RULESET else 1
        self.intents = []
        self.events = []
        self.last_completed_turn_public_points = {}
        self.chain = "0" * 64
        self.track_beliefs = track_beliefs
        self.trackers = (
            {
                color.value: ResourceBelief([c.value for c in self.game.state.colors])
                for color in Color
            }
            if track_beliefs
            else {}
        )
        self._geometry = self.geometry()

    def geometry(self):
        board = self.game.state.board
        nodes = {}
        tiles = []
        offsets = {
            "NORTH": (0, -1),
            "NORTHEAST": (math.sqrt(3) / 2, -0.5),
            "SOUTHEAST": (math.sqrt(3) / 2, 0.5),
            "SOUTH": (0, 1),
            "SOUTHWEST": (-math.sqrt(3) / 2, 0.5),
            "NORTHWEST": (-math.sqrt(3) / 2, -0.5),
        }
        for coordinate, tile in board.map.land_tiles.items():
            # Catanatron cube axes: coordinate[0] points northeast, coordinate[2] northwest.
            q, r, s = coordinate
            x = math.sqrt(3) * (q + s / 2)
            y = 1.5 * s
            tiles.append(
                {
                    "id": tile.id,
                    "coordinate": list(coordinate),
                    "x": x,
                    "y": y,
                    "resource": tile.resource,
                    "number": tile.number,
                    "nodes": list(tile.nodes.values()),
                }
            )
            for ref, node in tile.nodes.items():
                dx, dy = offsets[ref.value]
                nodes[node] = {
                    "id": node,
                    "x": round(x + dx, 6),
                    "y": round(y + dy, 6),
                    "neighbors": [],
                }
        edges = set()
        for tile in board.map.land_tiles.values():
            for edge in tile.edges.values():
                edges.add(tuple(sorted(edge)))
        for a, b in edges:
            nodes[a]["neighbors"].append(b)
            nodes[b]["neighbors"].append(a)
        ports = []
        for tile in board.map.tiles.values():
            if isinstance(tile, Port):
                # Only the two coastal nodes of the oriented port grant access.
                port_nodes = (
                    sorted(
                        n
                        for n in board.map.port_nodes.get(tile.resource, [])
                        if n in tile.nodes.values()
                    )
                    if hasattr(board.map, "port_nodes")
                    else []
                )
                ports.append({"resource": tile.resource, "nodes": port_nodes})
        return {
            "tiles": tiles,
            "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
            "edges": [list(e) for e in sorted(edges)],
            "ports": ports,
        }

    def legal(self):
        return (
            sorted(self.game.playable_actions, key=lambda a: canonical(action_value(a)))
            if self.game.winning_color() is None
            else []
        )

    def observation(
        self,
        viewer="RED",
        include_history=True,
        include_belief=True,
        compact=False,
        simulation=False,
    ):
        viewer = Color(viewer)
        state = self.game.state
        board = state.board
        players = []
        bought = {color: 0 for color in state.colors}
        for record in reversed(state.action_records):
            if record.action.action_type == ActionType.END_TURN:
                break
            if record.action.action_type == ActionType.BUY_DEVELOPMENT_CARD:
                bought[record.action.color] += 1
        for color in state.colors:
            key = player_key(state, color)
            p = state.player_state
            row = {
                "color": color.value,
                "public_points": p[f"{key}_VICTORY_POINTS"],
                "resource_count": player_num_resource_cards(state, color),
                "development_count": sum(
                    p[f"{key}_{card}_IN_HAND"] for card in DEVELOPMENT_CARDS
                ),
                "roads_available": p[f"{key}_ROADS_AVAILABLE"],
                "settlements_available": p[f"{key}_SETTLEMENTS_AVAILABLE"],
                "cities_available": p[f"{key}_CITIES_AVAILABLE"],
                "played_knights": p[f"{key}_PLAYED_KNIGHT"],
                "longest_road": p[f"{key}_LONGEST_ROAD_LENGTH"],
                "has_road": p[f"{key}_HAS_ROAD"],
                "has_army": p[f"{key}_HAS_ARMY"],
                "played_development": {
                    card: p[f"{key}_PLAYED_{card}"] for card in DEVELOPMENT_CARDS
                },
                "has_rolled": bool(p[f"{key}_HAS_ROLLED"]),
                "has_played_development": bool(
                    p[f"{key}_HAS_PLAYED_DEVELOPMENT_CARD_IN_TURN"]
                ),
                "development_bought_this_turn": bought[color],
                "last_completed_turn_public_points": getattr(
                    self, "last_completed_turn_public_points", {}
                ).get(color.value),
            }
            if color == viewer:
                row["own_points"] = p[f"{key}_ACTUAL_VICTORY_POINTS"]
            players.append(row)
        key = player_key(state, viewer)
        legal = []
        if state.current_color() == viewer:
            for i, action in enumerate(self.legal()):
                value = action_value(action)
                legal.append({**value, "id": i, "label": action_label(value)})
        public_board = {
            **(self._geometry if compact else copy.deepcopy(self._geometry)),
            "buildings": [
                {"node": node, "color": color.value, "type": kind}
                for node, (color, kind) in sorted(board.buildings.items())
            ],
            "roads": [
                {"edge": list(edge), "color": color.value}
                for edge, color in sorted(board.roads.items())
                if edge[0] < edge[1]
            ],
            "robber": list(board.robber_coordinate),
        }
        out = {
            "engine_version": ENGINE_VERSION,
            "ruleset": REPLAY_RULESETS[self.game.state.board.rules_revision - 1],
            "revision": len(self.intents),
            "viewer": viewer.value,
            "actor": state.current_color().value,
            "turn_owner": state.colors[state.current_turn_index].value,
            "phase": state.current_prompt.value,
            "initial": state.is_initial_build_phase,
            "turn": max(1, state.num_turns - 5),
            "winner": plain(self.game.winning_color()),
            "board": public_board,
            "players": players,
            "own_hand": get_player_freqdeck(state, viewer),
            "own_development": {
                card: state.player_state[f"{key}_{card}_IN_HAND"]
                for card in DEVELOPMENT_CARDS
            },
            "own_dev_playable_age": {
                card: bool(state.player_state[f"{key}_{card}_OWNED_AT_START"])
                for card in DEVELOPMENT_CARDS
                if card != "VICTORY_POINT"
            },
            "has_rolled": bool(state.player_state[f"{key}_HAS_ROLLED"]),
            "has_played_development": bool(
                state.player_state[f"{key}_HAS_PLAYED_DEVELOPMENT_CARD_IN_TURN"]
            ),
            "free_roads_available": (
                state.free_roads_available if state.is_road_building else 0
            ),
            "legal_actions": legal,
            "development_bank_count": len(state.development_listdeck),
            "trade": (
                plain(state.current_trade[:10]) if state.is_resolving_trade else None
            ),
            "discard_remaining": state.discard_counts[state.color_to_index[viewer]],
            "can_offer": state.current_color() == viewer
            and state.current_prompt.value == "PLAY_TURN"
            and bool(state.player_state[f"{key}_HAS_ROLLED"])
            and not state.is_road_building
            and self.game.winning_color() is None,
        }
        if include_history:
            out["events"] = [
                self.event_view(e, viewer.value) for e in self.events[-80:]
            ]
        if include_belief and viewer.value in self.trackers:
            out["belief"] = self.trackers[viewer.value].summary()
        if simulation:
            # Only public board/cache/phase fields. No full-state serialization or RNG.
            from catanatron.serialization import map_to_json, board_to_json

            out["simulation"] = {
                "map": map_to_json(board.map),
                "board": board_to_json(board),
                "num_turns": state.num_turns,
                "buildings_by_color": plain(state.buildings_by_color),
                "discard_counts": list(state.discard_counts),
                "is_discarding": state.is_discarding,
                "is_moving_knight": state.is_moving_knight,
                "is_road_building": state.is_road_building,
                "is_resolving_trade": state.is_resolving_trade,
                "current_trade": plain(state.current_trade),
                "acceptees": list(state.acceptees),
            }
            tracker = self.trackers.get(viewer.value)
            out["joint_belief"] = (
                [
                    {"hands": list(world), "weight": weight}
                    for world, weight in tracker.worlds.items()
                ]
                if tracker
                else []
            )
        return out

    def event_view(self, event, viewer):
        view = copy.deepcopy(event["public"])
        view.update(event["private"].get(viewer, {}))
        return view

    def execute(self, action, expected_revision=None):
        if expected_revision is not None and expected_revision != len(self.intents):
            raise ValueError(
                "That action belongs to an earlier position. Refresh the position and choose again."
            )
        state = self.game.state
        before = {
            color.value: get_player_freqdeck(state, color) for color in state.colors
        }
        intent = action_value(action)
        ending_points = (
            state.player_state[player_key(state, action.color) + "_VICTORY_POINTS"]
            if action.action_type == ActionType.END_TURN
            else None
        )
        record = self.game.execute(action)
        if ending_points is not None:
            self.last_completed_turn_public_points[action.color.value] = ending_points
        self.intents.append(intent)
        event = {
            "sequence": len(self.intents),
            "type": intent["type"],
            "color": intent["color"],
            "value": intent["value"],
        }
        private = {}
        if intent["type"] == "ROLL":
            event["dice"] = plain(record.result)
        if intent["type"] == "MOVE_ROBBER":
            victim = intent["value"][1]
            event["victim"] = victim
            for color in (victim, intent["color"]):
                if color:
                    private[color] = {"resource": record.result}
        elif intent["type"] == "DISCARD_RESOURCE":
            event["value"] = None
            private[intent["color"]] = {"resource": record.result}
        elif intent["type"] == "BUY_DEVELOPMENT_CARD":
            event["value"] = None
            private[intent["color"]] = {"development_card": record.result}
        if intent["type"] not in ("MOVE_ROBBER", "DISCARD_RESOURCE"):
            event["deltas"] = {
                color.value: [
                    a - b
                    for a, b in zip(
                        get_player_freqdeck(state, color), before[color.value]
                    )
                ]
                for color in state.colors
            }
            event["deltas"] = {
                color: delta for color, delta in event["deltas"].items() if any(delta)
            }
        self.events.append({"public": event, "private": private})
        self.chain = hashlib.sha256(
            (
                self.chain
                + canonical({"intent": intent, "result": plain(record.result)})
            ).encode()
        ).hexdigest()
        totals = {
            color.value: player_num_resource_cards(state, color)
            for color in state.colors
        }
        for viewer, tracker in self.trackers.items():
            tracker.update(
                self.event_view(self.events[-1], viewer),
                viewer,
                get_player_freqdeck(state, Color(viewer)),
                totals,
            )
        self.check_invariants()
        return record

    def apply(self, index, revision):
        if type(index) is not int or index < 0 or index >= len(self.legal()):
            raise ValueError("Choose a legal action.")
        return self.execute(self.legal()[index], revision)

    def offer(self, give, receive, revision):
        if (
            not isinstance(give, list)
            or not isinstance(receive, list)
            or len(give) != 5
            or len(receive) != 5
        ):
            raise ValueError("A trade needs five offered and five requested counts.")
        return self.execute(
            Action(
                self.game.state.current_color(),
                ActionType.OFFER_TRADE,
                tuple(give + receive),
            ),
            revision,
        )

    def auto(self, count=1, stop_at_viewer=None, policy="baseline"):
        count = max(1, min(200, int(count)))
        if policy == "search":
            count = 1  # Keep browser batches interruptible between decisions.
        for _ in range(count):
            if self.game.winning_color() is not None:
                break
            actor = self.game.state.current_color().value
            if stop_at_viewer == actor:
                break
            observation = self.observation(
                actor, include_history=False, include_belief=False, compact=True
            )
            if policy == "search":
                if len(observation["legal_actions"]) == 1:
                    ranked = observation["legal_actions"]
                else:
                    from engine.planning import search

                    ranked = search(
                        self.observation(actor, simulation=True),
                        budget=12,
                        horizon=1600,
                        max_candidates=4,
                    )["candidates"]
            elif policy == "strategic":
                from engine.strategy import rank_actions as strategic_rank

                ranked = strategic_rank(observation)
            elif policy == "tactical":
                from engine.tactics import rank_actions as tactical_rank

                ranked = tactical_rank(observation)
            elif policy == "baseline":
                ranked = rank_actions(observation)
            else:
                raise ValueError("Unknown policy.")
            if not ranked:
                raise RuntimeError("No legal move in a nonterminal game.")
            self.apply(ranked[0]["id"], len(self.intents))

    def check_invariants(self):
        state = self.game.state
        for i, resource in enumerate(RESOURCES):
            holdings = [get_player_freqdeck(state, color)[i] for color in state.colors]
            if (
                min(holdings + [state.resource_freqdeck[i]]) < 0
                or sum(holdings) + state.resource_freqdeck[i] != 19
            ):
                raise RuntimeError(f"Resource conservation failed for {resource}")
        for color in state.colors:
            key = player_key(state, color)
            p = state.player_state
            buildings = [
                kind for owner, kind in state.board.buildings.values() if owner == color
            ]
            if p[f"{key}_SETTLEMENTS_AVAILABLE"] + buildings.count("SETTLEMENT") != 5:
                raise RuntimeError("Settlement inventory mismatch")
            if p[f"{key}_CITIES_AVAILABLE"] + buildings.count("CITY") != 4:
                raise RuntimeError("City inventory mismatch")
            roads = sum(
                owner == color
                for edge, owner in state.board.roads.items()
                if edge[0] < edge[1]
            )
            if p[f"{key}_ROADS_AVAILABLE"] + roads != 15:
                raise RuntimeError("Road inventory mismatch")
        dev = len(state.development_listdeck)
        for color in state.colors:
            key = player_key(state, color)
            dev += sum(
                state.player_state[f"{key}_{card}_IN_HAND"]
                + state.player_state[f"{key}_PLAYED_{card}"]
                for card in DEVELOPMENT_CARDS
            )
        if dev != 25:
            raise RuntimeError("Development deck conservation failed")

    def export(self):
        return {
            "format": "catan-lab-replay-v1",
            "engine_version": self.replay_version,
            "ruleset": REPLAY_RULESETS[self.game.state.board.rules_revision - 1],
            "scope": "research-replay-includes-hidden-information",
            "seed": self.seed,
            "intents": copy.deepcopy(self.intents),
            "checksum": self.chain,
        }

    @classmethod
    def from_replay(cls, replay, track_beliefs=True):
        if (
            not isinstance(replay, dict)
            or replay.get("format") != "catan-lab-replay-v1"
            or replay.get("ruleset") not in REPLAY_RULESETS
            or replay.get("engine_version") not in REPLAY_VERSIONS
        ):
            raise ValueError("Unsupported replay format, engine version, or ruleset.")
        if (
            not isinstance(replay.get("intents"), list)
            or len(replay["intents"]) > 20000
        ):
            raise ValueError("Replay must contain at most 20,000 actions.")
        session = cls(
            replay["seed"], track_beliefs=track_beliefs, ruleset=replay["ruleset"]
        )
        session.replay_version = replay["engine_version"]
        for value in replay["intents"]:
            session.execute(decode_action(value))
        if session.chain != replay.get("checksum"):
            raise ValueError(
                "Replay checksum mismatch; the action history was changed or is incompatible."
            )
        return session

    def undo(self):
        if not self.intents:
            return self
        fresh = Session(
            self.seed,
            track_beliefs=self.track_beliefs,
            ruleset=REPLAY_RULESETS[self.game.state.board.rules_revision - 1],
        )
        fresh.replay_version = self.replay_version
        for intent in self.intents[:-1]:
            fresh.execute(decode_action(intent))
        return fresh


_session = None


def dispatch(message, progress=None):
    global _session
    request = json.loads(message)
    command = request.get("command")
    viewer = request.get("viewer", "RED")
    if command == "new":
        _session = Session(request.get("seed", 2026))
    elif command == "import":
        _session = Session.from_replay(request["replay"])
    elif _session is None:
        raise ValueError("Start a new game first.")
    elif command == "act":
        _session.apply(request["action"], request["revision"])
    elif command == "auto":
        _session.auto(
            request.get("count", 1),
            request.get("stop_at_viewer"),
            request.get("policy", "tactical"),
        )
    elif command == "offer":
        _session.offer(request["give"], request["receive"], request["revision"])
    elif command == "undo":
        _session = _session.undo()
    elif command == "export":
        return json.dumps(_session.export())
    elif command == "search":
        return json.dumps(
            draft_search(_session.observation(viewer), request.get("trials", 24))
        )
    elif command == "plan":
        from engine.planning import search

        return json.dumps(
            search(
                _session.observation(viewer, simulation=True),
                budget=request.get("budget", 24),
                horizon=request.get("horizon", 48),
                progress=progress,
            )
        )
    elif command == "forecast":
        from engine.forecast import forecast

        return json.dumps(
            forecast(
                _session.observation(viewer, simulation=True),
                samples=request.get("samples", 12),
                horizon=request.get("horizon", 1600),
                progress=progress,
            )
        )
    elif command != "observe":
        raise ValueError("Unknown engine command.")
    result = _session.observation(viewer)
    from engine.strategy import rank_actions as strategic_rank, analyze
    from engine.tactics import rank_actions as tactical_rank
    from engine.planning import development_beliefs

    result["analysis"] = analyze(result)
    result["development_belief"] = development_beliefs(result)
    from engine.opening import report as opening_report
    from engine.forecast import dice_exposure

    result["opening"] = opening_report(result)
    result["dice_exposure"] = dice_exposure(result)
    result["recommendations"] = (
        rank_actions
        if request.get("policy") == "baseline"
        else strategic_rank if request.get("policy") == "strategic" else tactical_rank
    )(result)[:8]
    return json.dumps(result)
