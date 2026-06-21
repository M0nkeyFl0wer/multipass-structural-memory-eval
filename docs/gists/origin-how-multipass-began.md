# How a one-page spec turned into a diagnostic toolkit

This project started as a comment on someone else's issue, and a request I
overshot by about an order of magnitude. Here's the actual story, because the
way it began explains what it's for.

## The palace

I'd been reading through the [agentic-memory
survey](https://github.com/lhl/agentic-memory) and got stuck on one system:
[MemPalace](https://github.com/MemPalace/mempalace). Most memory systems are a
vector store with a query box bolted on. MemPalace used a spatial metaphor
instead — **wings** for domains, **halls** for edge types, **rooms** for topics,
**tunnels** for the cross-domain connections between wings. An ontology expressed
as *architecture* rather than declared in a schema file.

That framing stuck with me, because it implied something most memory systems
hide: a memory has a *shape*. You can't tell from `mempalace search` that your
security wing has dense tunnels to devops but none to legal. You can't see the
isolated wing with no tunnels to anything — a knowledge silo hiding in plain
sight. Those are structural facts. They're already true in the palace; they're
just invisible until you render the graph.

So I [opened an issue](https://github.com/MemPalace/mempalace/issues/101) with
three things: a 3D palace visualizer that made the structure walkable, a sketch
of an eval framework that would test what the architecture uniquely enables, and
a contradiction-detection pattern. The visualizer was the part I was excited
about — I'd already built it on `3d-force-graph`, isolated wings glowing red,
tunnels rendered as particle flow.

## The reply that reframed it

The maintainer — [@milla-jovovich](https://github.com/milla-jovovich), the Leeloo
to this whole thing — took it through the CLI and replied to each piece. The
visualizer she liked but parked: a visualization is only useful once the thing
being visualized has settled shape, and the retrieval stack was still moving.

Then she pointed at the part I'd treated as a footnote and called it the most
important thing in the issue. Her reasoning is the reason this repo exists, so
I'll quote the shape of it: a calibrated benchmark grid (@gizmax's work in their
#39) had shown that, **under standard LongMemEval-style QA benchmarks**, the
palace's room structure was a statistical no-op — one configuration even
*regressed* ~13.6 points. But those benchmarks only measure single-question
retrieve-and-answer. They can't score what the palace is actually *for*:
multi-hop reasoning, cross-session connection, contradiction detection, tracking
an entity as it changes over months. If the architecture has a real edge, it's on
those axes — and standard QA benchmarks are the wrong lens to find it.

Her ask was small and specific: **would I write the spec? Not the code — just the
spec. A one-page write-up of what to test, why, and how you'd know it worked.**

## Getting carried away

I did not write a one-page spec.

What happened instead is that I already had pieces lying around — the visualizer,
some structural-analysis scripts I'd been using to poke at my own knowledge
graph's health, a half-formed sense that "is this graph any good?" was a question
nobody's retrieval benchmark answered. The spec request gave all of it a center
of gravity. Each question on her one-pager turned into a test, each test wanted a
metric, each metric wanted a corpus to run against and a baseline to compare to.
I kept iterating the tools I'd built to make sense of graph health and
retrieval-effectiveness in a RAG system, and they kept compounding.

By the time I came back to the thread, what I had to report was: *"I realized I
delivered a lot more than the one-page spec you asked for."* It had become a
nine-category diagnostic framework — The Lookup (factual retrieval), The Stairway
(multi-hop by depth), The Missing Room (structural gaps via topology), The
Threshold (ingestion integrity), The Blueprint (ontology coherence), The Abacus
(token efficiency), and eventually The Handshake (whether the model actually
reaches the memory in production) — built and run across several corpora, against
MemPalace and other graphs alike.

The name *Multipass* is a double reference: multi-hop path traversal through the
graph, and a Fifth Element callback, because the palace metaphor deserved one.
(It's also literally what the framework does — multiple passes over every system
under test, across corpus shapes and retrieval conditions, so behaviour that
hides on any single pass shows up when the readings sit side by side.)

## What it became

The thing I didn't expect is that other people started running it on memory I'd
never seen. One contributor pointed it at a 165K-drawer production palace and got
back a structural snapshot nobody had had before — including a finding that one
edge type held 73% of the graph, the kind of legible reading the framework was
supposed to make possible. He also found a bug, which I fixed, which is how you
know the tool is real.

So that's the lineage: a metaphor that made me want to *see* a memory's shape, a
maintainer who redirected me from the pretty part to the useful part, and a
one-page spec I couldn't stop expanding. The founding observation hasn't changed,
and it's the same one I keep coming back to — **standard benchmarks ask whether
you can find a memory; they can't tell you whether the memory is structurally
sound.** That gap is the whole project. (The longer-form version of that argument
is in [the companion note](./why-benchmarks-cant-see-the-bug.md).)
