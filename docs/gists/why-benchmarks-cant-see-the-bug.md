# Why a graph benchmark can't see the bug that matters

There's a careful, well-built benchmark making the rounds for embedded graph
engines — [`prrao87/graph-benchmark`](https://github.com/prrao87/graph-benchmark).
It generates a 100K-person social network with Faker, loads it into Neo4j, Kuzu,
[Ladybug](https://github.com/LadybugDB/ladybug), and lance-graph, and times a
suite of nine queries in milliseconds. It's a good piece of work, and the
question it answers is a real one.

But it answers a *different* question than the one I spend my time on, and the
difference turns out to be the whole point.

## Two questions, one substrate

A performance benchmark asks: **given a correct graph, how fast does the engine
answer?**

The diagnostics I build ask: **given an engine, is the graph correct, complete,
and coherent in the first place?**

Those are orthogonal axes. And the performance genre doesn't just ignore the
second one — it *defines it away*. The dataset is correct by construction: Faker
doesn't fabricate edges, drop entities, duplicate them, or let an ontology drift.
Clean data goes in, speed comes out, correctness is assumed. That assumption is
exactly the thing worth measuring on a real system.

## The blind spot is structural, not incidental

This isn't a knock on any particular benchmark or engine. It's a property of the
*genre*. A real knowledge graph is almost never populated by a clean generator —
it's built by an extraction pipeline chewing on messy input. That pipeline is
where the failures that actually hurt you live:

- **Fabricated edges** — an LLM extractor inventing a relationship that isn't in
  the source.
- **Fragmented or duplicated entities** — one real-world thing landing as several
  nodes, or several things collapsed into one.
- **Ontology drift** — entity and edge types quietly diverging from the schema
  over successive ingests.

None of these are properties of the *database*. They're properties of the
*pipeline that fills it*. A benchmark that bulk-loads ground-truth-clean data and
runs read-only queries cannot see any of them — there's nothing dirty to catch.
So the genre is complementary to correctness testing, not a substitute for it.

## How you actually test for it

If clean-data-in / speed-out can't surface these, what does? You measure the
graph itself, structurally:

- **Ingestion integrity** — do edges trace back to real source spans, or were
  they invented? Do entities that should be one node collide, or stay
  fragmented?
- **Ontology coherence** — do the types and relationships in the graph still
  match the schema they were supposed to follow, ingest after ingest?
- **Topology** — degree distribution, connected components, communities, holes.
  Is the graph one connected fabric or a pile of disconnected islands?

That last one is also where the two worlds quietly meet. A performance
benchmark's results are *driven* by topology: the queries that discriminate one
engine from another are the multi-hop path queries, and those explode precisely
when the generator plants super-nodes and dense cliques. Hub density is what
makes a path query expensive. So the structural signature of a graph doesn't just
tell you whether it's *correct* — it predicts where it'll be *slow*. Speed and
correctness turn out to sit on the same substrate: the shape of the graph.

## Credit where it's due

The benchmark that prompted this is genuinely good, and the Ladybug maintainer's
response to it — engaging with a third-party result that beat them, crediting
upstream work openly, and shipping concrete fixes within weeks — is exactly the
kind of engaged, research-honest maintenance you want under a database you depend
on. None of the above is a criticism of that work. It's a note about what the
*category* of test can and can't see, and why the correctness question needs its
own instruments.

Speed benchmarks tell you whether a correct graph is fast. They can't tell you
whether your graph is correct. Both questions matter; they just need different
tools.
