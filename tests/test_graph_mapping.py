"""Tests for sme.adapters._graph_mapping.project_graph.

Pins the input/output contract for the shared palace-daemon /graph
projection. Both MemPalaceDaemonAdapter and FamiliarAdapter consume
this function, so any change to the output shape is a coordinated
break across two adapters and any downstream Cat 8 scoring.

Covers:

- Output type contract: ``(list[Entity], list[Edge])``
- Wing entities: id prefix, type, drawer_count carried in properties
- Room entities: cross-wing aggregation, ``general`` filtered out
- room→wing ``member_of`` edges
- Tunnel edges: wing<->wing pairs (skip self-pair, all combinations)
- KG entities + KG triples: id prefixing, temporal/source props copied
- Edge cases: empty payload, missing keys, malformed entries, the
  exact field shape MemPalace daemon emits.
"""
from __future__ import annotations

from sme.adapters._graph_mapping import project_graph
from sme.adapters.base import Edge, Entity


# ── Output contract ────────────────────────────────────────────────


def test_project_graph_returns_two_lists():
    entities, edges = project_graph({})
    assert isinstance(entities, list)
    assert isinstance(edges, list)


def test_project_graph_empty_payload():
    entities, edges = project_graph({})
    assert entities == []
    assert edges == []


def test_project_graph_missing_keys_are_safe():
    """All top-level keys are optional; missing ones don't raise."""
    entities, edges = project_graph({"wings": {"alpha": 3}})
    # Just the wing entity, no edges
    assert len(entities) == 1
    assert entities[0].entity_type == "wing"
    assert edges == []


def test_project_graph_null_values_treated_as_empty():
    """None for any top-level field is normalized to empty."""
    payload = {
        "wings": None,
        "rooms": None,
        "tunnels": None,
        "kg_entities": None,
        "kg_triples": None,
    }
    entities, edges = project_graph(payload)
    assert entities == []
    assert edges == []


# ── Wing entities ──────────────────────────────────────────────────


def test_wings_become_entities_with_drawer_count():
    payload = {"wings": {"alpha": 10, "beta": 5}}
    entities, _ = project_graph(payload)
    wings = [e for e in entities if e.entity_type == "wing"]
    assert len(wings) == 2
    by_id = {e.id: e for e in wings}
    assert "wing:alpha" in by_id
    assert by_id["wing:alpha"].name == "alpha"
    assert by_id["wing:alpha"].properties["drawer_count"] == 10
    assert by_id["wing:alpha"].properties["_table"] == "wing"
    assert by_id["wing:beta"].properties["drawer_count"] == 5


def test_wings_emitted_in_sorted_order():
    """Determinism matters for diffing graph snapshots."""
    payload = {"wings": {"zebra": 1, "alpha": 2, "mango": 3}}
    entities, _ = project_graph(payload)
    wing_ids = [e.id for e in entities if e.entity_type == "wing"]
    assert wing_ids == ["wing:alpha", "wing:mango", "wing:zebra"]


# ── Room entities + edges ─────────────────────────────────────────


def test_rooms_aggregate_across_wings():
    """A room appearing in two wings has wings_list of both and the
    drawer count is summed."""
    payload = {
        "wings": {"alpha": 10, "beta": 5},
        "rooms": [
            {"wing": "alpha", "rooms": {"shared": 3, "alpha_only": 7}},
            {"wing": "beta", "rooms": {"shared": 2, "beta_only": 3}},
        ],
    }
    entities, edges = project_graph(payload)
    rooms = {e.id: e for e in entities if e.entity_type == "room:untyped"}
    assert set(rooms.keys()) == {"room:shared", "room:alpha_only", "room:beta_only"}
    assert rooms["room:shared"].properties["wings"] == ["alpha", "beta"]
    assert rooms["room:shared"].properties["drawer_count"] == 5
    assert rooms["room:alpha_only"].properties["wings"] == ["alpha"]
    assert rooms["room:alpha_only"].properties["drawer_count"] == 7


def test_room_general_is_filtered_out():
    """The 'general' room is a default catch-all; the projection skips it."""
    payload = {
        "wings": {"alpha": 10},
        "rooms": [{"wing": "alpha", "rooms": {"general": 5, "real": 3}}],
    }
    entities, _ = project_graph(payload)
    room_ids = [e.id for e in entities if e.entity_type == "room:untyped"]
    assert "room:general" not in room_ids
    assert "room:real" in room_ids


def test_room_empty_string_filtered_out():
    payload = {
        "wings": {"alpha": 10},
        "rooms": [{"wing": "alpha", "rooms": {"": 5, "real": 3}}],
    }
    entities, _ = project_graph(payload)
    room_ids = [e.id for e in entities if e.entity_type == "room:untyped"]
    assert "room:" not in room_ids


def test_room_to_wing_member_of_edges():
    payload = {
        "wings": {"alpha": 10, "beta": 5},
        "rooms": [
            {"wing": "alpha", "rooms": {"shared": 3}},
            {"wing": "beta", "rooms": {"shared": 2}},
        ],
    }
    _, edges = project_graph(payload)
    member_edges = [e for e in edges if e.edge_type == "member_of"]
    # One edge per (room, wing) — two wings sharing one room → 2 edges
    assert len(member_edges) == 2
    edge_pairs = {(e.source_id, e.target_id) for e in member_edges}
    assert ("room:shared", "wing:alpha") in edge_pairs
    assert ("room:shared", "wing:beta") in edge_pairs
    # The drawer_count is preserved on the edge
    for e in member_edges:
        assert e.properties["drawer_count"] == 5  # aggregate
        assert e.properties["_table"] == "structural"


def test_rooms_emitted_in_sorted_order():
    payload = {
        "wings": {"a": 1},
        "rooms": [{"wing": "a", "rooms": {"z": 1, "m": 1, "b": 1}}],
    }
    entities, _ = project_graph(payload)
    room_ids = [
        e.id for e in entities if e.entity_type == "room:untyped"
    ]
    assert room_ids == ["room:b", "room:m", "room:z"]


def test_rooms_handle_null_rooms_field():
    """A wing whose rooms map is None doesn't crash."""
    payload = {"wings": {"a": 1}, "rooms": [{"wing": "a", "rooms": None}]}
    entities, _ = project_graph(payload)
    rooms = [e for e in entities if e.entity_type.startswith("room")]
    assert rooms == []


def test_rooms_drawer_count_handles_null():
    """Null counts default to zero, not crash."""
    payload = {
        "wings": {"a": 1},
        "rooms": [{"wing": "a", "rooms": {"foo": None}}],
    }
    entities, _ = project_graph(payload)
    foo = next(e for e in entities if e.id == "room:foo")
    assert foo.properties["drawer_count"] == 0


# ── Tunnel edges ───────────────────────────────────────────────────


def test_tunnels_emit_wing_pair_edges():
    payload = {
        "wings": {"a": 1, "b": 1},
        "tunnels": [{"room": "shared", "wings": ["a", "b"]}],
    }
    _, edges = project_graph(payload)
    tunnel_edges = [e for e in edges if e.edge_type == "tunnel"]
    assert len(tunnel_edges) == 1
    assert tunnel_edges[0].source_id == "wing:a"
    assert tunnel_edges[0].target_id == "wing:b"
    assert tunnel_edges[0].properties["via_room"] == "shared"


def test_tunnels_three_wings_yield_three_pairs():
    """Three wings sharing one room → C(3,2) = 3 tunnel edges."""
    payload = {
        "wings": {"a": 1, "b": 1, "c": 1},
        "tunnels": [{"room": "shared", "wings": ["a", "b", "c"]}],
    }
    _, edges = project_graph(payload)
    tunnel_edges = [e for e in edges if e.edge_type == "tunnel"]
    assert len(tunnel_edges) == 3
    pairs = {(e.source_id, e.target_id) for e in tunnel_edges}
    # Sorted within tunnel → no duplicate reversed pairs
    assert pairs == {
        ("wing:a", "wing:b"),
        ("wing:a", "wing:c"),
        ("wing:b", "wing:c"),
    }


def test_single_wing_tunnel_yields_no_edges():
    """A tunnel with only one wing in the list has no pairs to form."""
    payload = {"tunnels": [{"room": "lonely", "wings": ["a"]}]}
    _, edges = project_graph(payload)
    assert [e for e in edges if e.edge_type == "tunnel"] == []


def test_tunnel_null_wings_field_safe():
    payload = {"tunnels": [{"room": "r", "wings": None}]}
    _, edges = project_graph(payload)
    assert [e for e in edges if e.edge_type == "tunnel"] == []


# ── KG entities and triples ───────────────────────────────────────


def test_kg_entities_get_kg_prefix():
    payload = {
        "kg_entities": [
            {"id": "max", "name": "Max", "type": "person",
             "properties": {"age": 11}}
        ]
    }
    entities, _ = project_graph(payload)
    kg = [e for e in entities if e.id.startswith("kg:")]
    assert len(kg) == 1
    assert kg[0].id == "kg:max"
    assert kg[0].name == "Max"
    assert kg[0].entity_type == "kg:person"
    assert kg[0].properties["age"] == 11
    assert kg[0].properties["_table"] == "kg_entity"


def test_kg_entity_without_id_skipped():
    payload = {
        "kg_entities": [
            {"name": "missing-id"},
            {"id": "valid", "type": "x"},
        ]
    }
    entities, _ = project_graph(payload)
    kg = [e for e in entities if e.id.startswith("kg:")]
    assert len(kg) == 1
    assert kg[0].id == "kg:valid"


def test_kg_entity_defaults_when_fields_missing():
    payload = {"kg_entities": [{"id": "bare"}]}
    entities, _ = project_graph(payload)
    bare = next(e for e in entities if e.id == "kg:bare")
    # Name falls back to id; type falls back to 'unknown'
    assert bare.name == "bare"
    assert bare.entity_type == "kg:unknown"


def test_kg_triples_become_edges_with_temporal_props():
    payload = {
        "kg_triples": [
            {
                "subject": "max",
                "predicate": "loves",
                "object": "chess",
                "valid_from": "2026-01-01",
                "valid_to": None,
                "confidence": 0.9,
                "source_file": "diary.md",
            }
        ]
    }
    _, edges = project_graph(payload)
    kg_edges = [e for e in edges if e.source_id.startswith("kg:")]
    assert len(kg_edges) == 1
    e = kg_edges[0]
    assert e.source_id == "kg:max"
    assert e.target_id == "kg:chess"
    assert e.edge_type == "loves"
    assert e.properties["_created_at"] == "2026-01-01"
    assert e.properties["confidence"] == 0.9
    assert e.properties["source_file"] == "diary.md"
    assert e.properties["_table"] == "kg_triple"


def test_kg_triple_missing_subject_or_object_skipped():
    payload = {
        "kg_triples": [
            {"subject": "max", "predicate": "loves"},  # no object
            {"object": "chess", "predicate": "loves"},  # no subject
            {"subject": "max", "predicate": "loves", "object": "chess"},
        ]
    }
    _, edges = project_graph(payload)
    kg_edges = [e for e in edges if e.source_id.startswith("kg:")]
    assert len(kg_edges) == 1


def test_kg_triple_default_predicate_when_missing():
    payload = {
        "kg_triples": [{"subject": "a", "object": "b"}]  # no predicate
    }
    _, edges = project_graph(payload)
    kg_edges = [e for e in edges if e.source_id.startswith("kg:")]
    assert kg_edges[0].edge_type == "kg_related"


# ── Extra/unknown fields don't break projection ────────────────────


def test_extra_fields_ignored():
    """Extra top-level keys like ``kg_stats`` and unknown sub-fields
    don't affect the projection — forward compatibility."""
    payload = {
        "wings": {"a": 1},
        "kg_stats": {"some_future_field": 123},
        "rooms": [],
        "tunnels": [],
        "kg_entities": [],
        "kg_triples": [],
        "rfc_status": "experimental",  # unknown future field
    }
    entities, edges = project_graph(payload)
    assert len(entities) == 1  # just the wing
    assert edges == []


# ── End-to-end realistic payload ───────────────────────────────────


def test_realistic_palace_daemon_payload():
    """A payload shaped like an actual daemon /graph response covering
    all five projection paths."""
    payload = {
        "wings": {"code": 50, "decisions": 30, "personal": 20},
        "rooms": [
            {"wing": "code", "rooms": {"chromadb": 5, "general": 10}},
            {"wing": "decisions", "rooms": {"chromadb": 2}},
            {"wing": "personal", "rooms": {"family": 8}},
        ],
        "tunnels": [
            {"room": "chromadb", "wings": ["code", "decisions"]},
        ],
        "kg_entities": [
            {"id": "chroma", "name": "ChromaDB", "type": "tool"},
            {"id": "max", "name": "Max", "type": "person"},
        ],
        "kg_triples": [
            {
                "subject": "max",
                "predicate": "uses",
                "object": "chroma",
                "valid_from": "2026-04-01",
            }
        ],
    }
    entities, edges = project_graph(payload)

    # All five entity classes are produced
    types = {e.entity_type for e in entities}
    assert "wing" in types
    assert "room:untyped" in types
    assert any(t.startswith("kg:") for t in types)

    # Wings: 3
    assert sum(1 for e in entities if e.entity_type == "wing") == 3
    # Rooms: 2 (chromadb + family; general filtered)
    rooms = [e for e in entities if e.entity_type == "room:untyped"]
    assert {e.id for e in rooms} == {"room:chromadb", "room:family"}
    # KG entities: 2
    assert sum(1 for e in entities if e.id.startswith("kg:")) == 2

    # Edges: member_of (3 room→wing edges), tunnel (1 pair), kg (1 triple)
    member_edges = [e for e in edges if e.edge_type == "member_of"]
    assert len(member_edges) == 3
    tunnel_edges = [e for e in edges if e.edge_type == "tunnel"]
    assert len(tunnel_edges) == 1
    kg_edges = [e for e in edges if e.source_id.startswith("kg:")]
    assert len(kg_edges) == 1
    assert kg_edges[0].edge_type == "uses"


def test_returned_entities_and_edges_are_correct_types():
    """Every returned item must be an Entity / Edge dataclass instance —
    downstream code uses field access on these."""
    payload = {
        "wings": {"a": 1},
        "rooms": [{"wing": "a", "rooms": {"r": 1}}],
        "tunnels": [{"room": "r", "wings": ["a", "b"]}],
        "kg_entities": [{"id": "x", "type": "t"}],
        "kg_triples": [{"subject": "x", "object": "y", "predicate": "p"}],
    }
    entities, edges = project_graph(payload)
    for e in entities:
        assert isinstance(e, Entity)
    for ed in edges:
        assert isinstance(ed, Edge)
