"""Tests for _graph_mapping.project_graph (issue #18).

Pins the /graph payload → (Entity, Edge) mapping so daemon payload
format drift is caught by CI rather than silently changing topology
readings.
"""

from __future__ import annotations

from sme.adapters._graph_mapping import project_graph


def _minimal_payload(**overrides) -> dict:
    return {
        "wings": overrides.get("wings", {}),
        "rooms": overrides.get("rooms", []),
        "tunnels": overrides.get("tunnels", []),
        "kg_entities": overrides.get("kg_entities", []),
        "kg_triples": overrides.get("kg_triples", []),
    }


class TestWingProjection:
    def test_wings_become_entities(self):
        payload = _minimal_payload(wings={"code": 10, "diary": 5})
        ents, edges = project_graph(payload)
        wing_ents = [e for e in ents if e.entity_type == "wing"]
        assert len(wing_ents) == 2
        names = {e.name for e in wing_ents}
        assert names == {"code", "diary"}

    def test_wing_drawer_count_in_properties(self):
        payload = _minimal_payload(wings={"code": 42})
        ents, _ = project_graph(payload)
        wing = [e for e in ents if e.name == "code"][0]
        assert wing.properties["drawer_count"] == 42

    def test_wing_id_prefixed(self):
        payload = _minimal_payload(wings={"projects": 1})
        ents, _ = project_graph(payload)
        assert ents[0].id == "wing:projects"


class TestRoomProjection:
    def test_rooms_create_entities_and_member_of_edges(self):
        payload = _minimal_payload(
            wings={"w1": 10},
            rooms=[{"wing": "w1", "rooms": {"setup": 3, "config": 2}}],
        )
        ents, edges = project_graph(payload)
        room_ents = [e for e in ents if e.entity_type == "room:untyped"]
        assert len(room_ents) == 2
        member_edges = [e for e in edges if e.edge_type == "member_of"]
        assert len(member_edges) == 2

    def test_general_room_filtered_out(self):
        payload = _minimal_payload(
            wings={"w1": 1},
            rooms=[{"wing": "w1", "rooms": {"general": 5, "real": 1}}],
        )
        ents, _ = project_graph(payload)
        room_ents = [e for e in ents if e.entity_type == "room:untyped"]
        assert len(room_ents) == 1
        assert room_ents[0].name == "real"

    def test_room_shared_across_wings(self):
        payload = _minimal_payload(
            wings={"w1": 1, "w2": 1},
            rooms=[
                {"wing": "w1", "rooms": {"shared-room": 3}},
                {"wing": "w2", "rooms": {"shared-room": 2}},
            ],
        )
        ents, edges = project_graph(payload)
        room_ents = [e for e in ents if e.entity_type == "room:untyped"]
        assert len(room_ents) == 1
        assert sorted(room_ents[0].properties["wings"]) == ["w1", "w2"]
        assert room_ents[0].properties["drawer_count"] == 5
        member_edges = [e for e in edges if e.edge_type == "member_of"]
        assert len(member_edges) == 2


class TestTunnelProjection:
    def test_tunnel_creates_wing_to_wing_edge(self):
        payload = _minimal_payload(
            wings={"w1": 1, "w2": 1},
            tunnels=[{"room": "shared", "wings": ["w1", "w2"]}],
        )
        _, edges = project_graph(payload)
        tunnel_edges = [e for e in edges if e.edge_type == "tunnel"]
        assert len(tunnel_edges) == 1
        assert tunnel_edges[0].source_id == "wing:w1"
        assert tunnel_edges[0].target_id == "wing:w2"
        assert tunnel_edges[0].properties["via_room"] == "shared"

    def test_three_way_tunnel(self):
        payload = _minimal_payload(
            wings={"a": 1, "b": 1, "c": 1},
            tunnels=[{"room": "x", "wings": ["a", "b", "c"]}],
        )
        _, edges = project_graph(payload)
        tunnel_edges = [e for e in edges if e.edge_type == "tunnel"]
        assert len(tunnel_edges) == 3


class TestKGProjection:
    def test_kg_entities_prefixed(self):
        payload = _minimal_payload(
            kg_entities=[
                {"id": "e1", "name": "Alice", "type": "person", "properties": {}},
            ]
        )
        ents, _ = project_graph(payload)
        kg = [e for e in ents if e.id.startswith("kg:")]
        assert len(kg) == 1
        assert kg[0].entity_type == "kg:person"

    def test_kg_triples_become_edges(self):
        payload = _minimal_payload(
            kg_entities=[
                {"id": "e1", "name": "Alice"},
                {"id": "e2", "name": "Bob"},
            ],
            kg_triples=[
                {"subject": "e1", "object": "e2", "predicate": "knows"},
            ],
        )
        _, edges = project_graph(payload)
        kg_edges = [e for e in edges if e.edge_type == "knows"]
        assert len(kg_edges) == 1
        assert kg_edges[0].source_id == "kg:e1"
        assert kg_edges[0].target_id == "kg:e2"

    def test_kg_entity_without_id_skipped(self):
        payload = _minimal_payload(
            kg_entities=[{"name": "orphan"}]
        )
        ents, _ = project_graph(payload)
        assert not any(e.id.startswith("kg:") for e in ents)

    def test_kg_triple_without_subject_skipped(self):
        payload = _minimal_payload(
            kg_triples=[{"object": "e2", "predicate": "orphan"}]
        )
        _, edges = project_graph(payload)
        assert len(edges) == 0


class TestEmptyPayload:
    def test_empty_returns_empty(self):
        ents, edges = project_graph({})
        assert ents == []
        assert edges == []

    def test_all_none_fields(self):
        payload = {
            "wings": None,
            "rooms": None,
            "tunnels": None,
            "kg_entities": None,
            "kg_triples": None,
        }
        ents, edges = project_graph(payload)
        assert ents == []
        assert edges == []
