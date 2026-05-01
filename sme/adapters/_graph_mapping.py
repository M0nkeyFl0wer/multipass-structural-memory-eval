"""Shared /graph payload to (Entity, Edge) mapping.

palace-daemon's GET /graph returns a single payload shape (wings,
rooms, tunnels, kg_entities, kg_triples, kg_stats). Both the
MemPalaceDaemonAdapter and the FamiliarAdapter consume this shape.
Familiar's GET /api/familiar/graph proxies the daemon's response
unchanged (with a 5-minute cache), so both adapters share this
projection function rather than re-implementing it.

Extracted verbatim from MemPalaceDaemonAdapter._project_graph 2026-04-26.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sme.adapters.base import Edge, Entity


def project_graph(body: dict[str, Any]) -> tuple[list[Entity], list[Edge]]:
    """Turn the daemon's /graph response into (entities, edges).

    Mirrors the wing/room/tunnel projection in
    ``sme.adapters.mempalace.MemPalaceAdapter.get_graph_snapshot``,
    minus drawer-level surface (impractical at 151K-drawer scale
    through the HTTP API).
    """
    wings: dict[str, int] = body.get("wings") or {}
    rooms_by_wing: list[dict] = body.get("rooms") or []
    tunnels: list[dict] = body.get("tunnels") or []
    kg_ents: list[dict] = body.get("kg_entities") or []
    kg_trips: list[dict] = body.get("kg_triples") or []

    entities: list[Entity] = []
    edges: list[Edge] = []

    # Wings
    for wing in sorted(wings):
        entities.append(
            Entity(
                id=f"wing:{wing}",
                name=wing,
                entity_type="wing",
                properties={"_table": "wing", "drawer_count": wings[wing]},
            )
        )

    # Rooms — collect wings-per-room across the per-wing lists
    room_wings: dict[str, set[str]] = defaultdict(set)
    room_count: dict[str, int] = defaultdict(int)
    for entry in rooms_by_wing:
        wing = entry.get("wing", "")
        for room, n in (entry.get("rooms") or {}).items():
            if not room or room == "general":
                continue
            room_wings[room].add(wing)
            room_count[room] += int(n or 0)

    for room in sorted(room_wings):
        wings_list = sorted(room_wings[room])
        entities.append(
            Entity(
                id=f"room:{room}",
                name=room,
                entity_type="room:untyped",
                properties={
                    "_table": "room",
                    "wings": wings_list,
                    "drawer_count": room_count[room],
                },
            )
        )
        for wing in wings_list:
            edges.append(
                Edge(
                    source_id=f"room:{room}",
                    target_id=f"wing:{wing}",
                    edge_type="member_of",
                    properties={
                        "_table": "structural",
                        "drawer_count": room_count[room],
                    },
                )
            )

    # Tunnels — wing<->wing for each shared room
    for t in tunnels:
        room = t.get("room", "")
        t_wings = sorted(t.get("wings") or [])
        for i, wa in enumerate(t_wings):
            for wb in t_wings[i + 1:]:
                edges.append(
                    Edge(
                        source_id=f"wing:{wa}",
                        target_id=f"wing:{wb}",
                        edge_type="tunnel",
                        properties={
                            "_table": "structural",
                            "via_room": room,
                        },
                    )
                )

    # KG layer
    for ke in kg_ents:
        ent_id = ke.get("id")
        if not ent_id:
            continue
        props = dict(ke.get("properties") or {})
        props["_table"] = "kg_entity"
        entities.append(
            Entity(
                id=f"kg:{ent_id}",
                name=ke.get("name") or ent_id,
                entity_type=f"kg:{ke.get('type') or 'unknown'}",
                properties=props,
            )
        )
    for tr in kg_trips:
        subj, obj = tr.get("subject"), tr.get("object")
        if not subj or not obj:
            continue
        edges.append(
            Edge(
                source_id=f"kg:{subj}",
                target_id=f"kg:{obj}",
                edge_type=tr.get("predicate") or "kg_related",
                properties={
                    "_table": "kg_triple",
                    "_created_at": tr.get("valid_from"),
                    "valid_to": tr.get("valid_to"),
                    "confidence": tr.get("confidence"),
                    "source_file": tr.get("source_file"),
                },
            )
        )

    return entities, edges
