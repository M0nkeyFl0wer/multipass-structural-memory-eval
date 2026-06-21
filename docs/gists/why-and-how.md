# Why I built a structural diagnostic for my own "agentic" memory systems — and how I actually use it

*A longer note behind [multipass-structural-memory-eval](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval).*

## The itch

I have recently become obsessed with Knowledge Graphs. I will be the first one to admit that I have become like the wack job connecting different colours of string to pins representing nodes in a graph. But there are reasons behind my madness. The most immediate problem I was trying to solve was maintaining memory over long sessions or across different projects within my own work environment. This is the same problem many many people are trying to solve and truth be told its not a one size fits all solution Its also worth saying, like a relative said to me when i tried to explain why I was spending so much time building graphs "I would love to have more accurate memory too" They were talking about in their own brain, not their "second brain" on a computer but for many of us the division between the first and second is getting blurrier all the time.

So I built myself a personal knowledge-graph RAG stack (everything I've typed, decided or saved, ingested into an embedded graph), plus the usual pile of RAG and agent-memory experiments. The promise of all of it is the same: *the structure gives you something retrieval alone can't* multi-hop chains, contradiction surfacing, "what superseded this," provenance.

The problem is that every benchmark I could find measures the wrong thing. They ask **"can you find a memory?"** — recall ok, answer accuracy. That's necessary, but a filing cabinet can find a memory. None of them answer the question I actually care about: **is the structure of my graph any good, and is my build actually using it?**

I kept getting burned by failures that retrieval metrics literally cannot see:

- A graph that looked fine but had silently **fragmented** into hundreds of disconnected islands — multi-hop was dead, and R@5 never moved.
- The same entity split under two IDs because two slug functions disagreed on one character — recall capped below the ceiling, both rows looked fine in isolation.
- Whole enrichment timers dead for days; the eval stayed green the entire time because it measures "can retrieval return good results *when called*," not whether anything is still flowing.

These are *structural* and *operational* failures. A leaderboard score will sit there at 85% while five of them are active.

## What it actually does

So I built the thing I wanted: a **diagnostic**, not a benchmark. It runs multiple passes over a memory system across several corpus shapes and retrieval conditions, and reports on nine categories of structural health — factual lookup, multi-hop, contradiction, alias resolution, *gaps* (the room that should exist and doesn't), ontology coherence, token efficiency, and — the one every deployment actually trips on — whether the model **reaches the memory at all when it runs in production** (Cat 9, "The Handshake").

The honest unit isn't a single score. It's **before/after deltas under identical conditions** and **within-system A/B/C ablations** — change one thing, hold everything else, read the difference. That's what's defensible, and it's what tells me whether a change I made helped or quietly hurt.

## How I actually use it

Not as a leaderboard. As a **standing health check on my own graph.**

It runs on a schedule against my live personal knowledge graph and tells me when the structure regressed — when a rebuild fragmented something, when a category's coverage cratered, when the ontology drifted from what I declared. The loop is simply: *run it, see what got worse, fix the graph, watch the number recover.* It makes my graphs healthier over time instead of just scoring them once. That dogfooding loop is the actual product; the public benchmark stuff is downstream of it.

## A concrete example (the good-dog demo)

To have something shareable that isn't my private graph, I built a small public corpus — ~60 notes on dog breeds, nutrition, behavior, and policy — where every note carries **hand-authored ground-truth edges** in its frontmatter. The answer key ships with the corpus.

Then I rebuilt the graph from scratch with a Claude-subagent extraction pipeline (strong model for edges, local model only for embeddings — small models fabricate a huge fraction of typed edges), and measured the result against that answer key: **86% edge-recall, zero fabricated edges**, and a connected core that grew from 27 nodes to 289 once the extraction was done right.

The most telling result wasn't the score — it's that the diagnostic **caught errors in its own answer key.** A few of the hand-authored ground-truth edges were just wrong (e.g. "AKC is a member of the FCI" — it isn't), and the extractor *correctly declined to assert them*. The diagnostic flagged them as misses; they were the answer key's bugs, not the graph's. That's the kind of thing you only catch when you're watching structure, not scores.

That's the posture I want from a memory tool: not "you scored 0.85," but "here's the room that's missing, here's the edge that's lying, here's where your structure decayed since last week."

## Where it came from — and the name

It didn't start as a solo project: it grew out of a thread on **[MemPalace](https://github.com/MemPalace/mempalace)** ([issue #101](https://github.com/MemPalace/mempalace/issues/101)) about how you'd actually *test* a memory-palace / second-brain system — not just retrieve from it, but check whether its structure holds up.

The name is Leeloo's line from *The Fifth Element* — **"Multipass!"** (much respect to [milla-jovovich](https://github.com/milla-jovovich)) — and it turned out to describe the method: **multiple passes** over every system under test, across several corpus shapes and retrieval conditions (A / B / C), so brittle default behaviours that hide on any single pass become visible when the readings are compared side by side. The structure is the point; the score is just how you read it.

---

*Diagnostic posture, not a leaderboard. Repo + the nine-category menu: https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval*
