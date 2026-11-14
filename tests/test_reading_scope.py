"""Cat 8 entity-type judgement scoped to the tables the ontology describes.

vault-rag's schema.md declares the types of its `Entity` table. Judged over
every table, each note type (`session-end`, `daily`), chunk and log row came
back "undeclared": 48 of them on the live graph, none a real schema gap.
"""

from __future__ import annotations

from sme.adapters.base import Edge, Entity
from sme.reading import entity_table, score_reading

SCHEMA = """---
entity_types: [person, project]
edge_types: [WORKS_ON]
---
# schema
"""


def _graph():
    ents = [
        Entity(id="Entity:1", name="Ada", entity_type="person", properties={"_table": "Entity"}),
        Entity(id="Entity:2", name="SME", entity_type="project", properties={"_table": "Entity"}),
        Entity(id="Entity:3", name="idea", entity_type="concept", properties={"_table": "Entity"}),
        # Document layer: typed by note frontmatter, not described by the schema.
        Entity(id="Note:a", name="a.md", entity_type="session-end"),
        Entity(id="Chunk:x", name="x", entity_type="Chunk"),
    ]
    return ents, [Edge(source_id="Entity:1", target_id="Entity:2", edge_type="WORKS_ON")]


def test_entity_table_from_property_or_id_prefix():
    ents, _ = _graph()
    assert [entity_table(e) for e in ents] == ["Entity", "Entity", "Entity", "Note", "Chunk"]
    assert entity_table(Entity(id="no-prefix", name="n", entity_type="t")) is None


def test_unscoped_judges_every_table(tmp_path):
    (tmp_path / "schema.md").write_text(SCHEMA)
    ents, eds = _graph()
    reading, *_ = score_reading(ents, eds, ontology=str(tmp_path / "schema.md"))
    assert sorted(reading["cat8"]["types_undeclared"]) == ["Chunk", "concept", "session-end"]
    assert reading["cat8"]["tables"] is None


def test_scoped_judges_only_the_described_table(tmp_path):
    (tmp_path / "schema.md").write_text(SCHEMA)
    ents, eds = _graph()
    reading, *_ = score_reading(
        ents, eds, ontology=str(tmp_path / "schema.md"), ontology_tables=["Entity"]
    )
    c8 = reading["cat8"]
    # The one real stray survives; the document layer is out of scope.
    assert c8["types_undeclared"] == ["concept"]
    assert (c8["tables"], c8["entities_judged"]) == (["Entity"], 3)
    # Cat 4 and Cat 5 still see every node.
    assert reading["cat4"]["entities"] == 5
