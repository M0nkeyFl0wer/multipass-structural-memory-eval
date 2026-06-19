# LadybugDB graph sins — operational findings from production graph-RAG

Field notes from running **embedded LadybugDB** as the graph store under several
production knowledge-graph / graph-RAG deployments. These are the ways we have
actually corrupted, crashed, or silently degraded a graph, and the patterns that
avoid them. Versions are called out where a finding is build-specific.

Shared in case they're useful to the LadybugDB community. The most important one
for maintainers is **§A.4** — a silent data-corruption bug we can reproduce on
0.17.1.

Applies to any embedded `*.ldb` on this LadybugDB build.

> Format: **the rule** — one-line why. Findings are grouped Mutation /
> Concurrency / Recovery / Don't-over-react, then the inverse "safe primitives".

---

## ⭐ Headline for maintainers — §A.4 (silent REL corruption on incremental writes)

**Any incremental edge write into a *populated* consolidated REL table corrupts
other rows — and a version bump does not fix it.**

Symptom: a column's values scramble/rotate across ~30–120 *other* rows on the
next checkpoint/reopen — `edge_type` flips type, or free-text columns
(`evidence`, `context`) swap between unrelated rows.

Two layered causes, one symptom:
- `≤ 0.15.3` has an `edge_type` checkpoint / page-reclaim race.
- **Reproduced on 0.17.1 (2026-06):** *any* incremental write — `MERGE` +
  `ON MATCH SET`, **or** plain `CREATE` — into a REL table that already holds
  checkpointed rows scrambles other rows on close + reopen.

A single write on an idle copy with no reopen is clean (which is why it "never
reproduced" before); it fires only with **multiple writes + checkpoint/reopen**.
It is **not** ALTER-specific (a freshly drop+recreated table corrupts again once
repopulated), **not** multi-`SET`-specific (`CREATE` corrupts too), **not**
`<0.17`-specific.

Minimal repro shape: into a REL table already holding rows, issue N incremental
writes, then close + reopen.
- 9 × `ON MATCH SET` → 32 collateral rows mutated
- 10 × `ON CREATE` → 117 collateral rows mutated

**The only safe write is reconstruct-and-swap:** drop the REL table → bulk-insert
*all* edges into the now-empty table in one pass → verify `collateral == 0` →
swap. Plus a write-guard that refuses incremental REL writes into a non-empty
table.

The tell in the wild: a re-extraction rebuild that *fights itself* — edge count
drops instead of climbing, a typed edge flips type mid-observation, or evidence
quotes describe a different relationship than the edge claims.

---

## A. Mutation sins (silently destroy VALID data)

1. **Never in-place bulk DELETE edges/nodes.** On this build, deleting many
   typed REL rows in sequence scrambles the edge store and destroys valid edges
   too (proven 6 ways: single-conn, reopen, per-process, checkpoint/100,
   per-note). Only a *single isolated* DELETE statement is safe. → use
   **reconstruct-filtered** (all-CREATE into a fresh graph, swap on verify).

2. **Never multi-property SET a REL with a string literal.** Multi-assignment
   `SET r.a=..., r.b='x'` picks wrong values from across the matched rows. Use
   single-field SET with **parameters** only.

3. **Never `ALTER ... ADD COLUMN` a consolidated REL table that takes writes.**
   An ALTER-grown REL table's physical/logical column order diverges, so any
   later write mis-maps `edge_type` across ~80 unrelated rows (e.g. one edge type
   silently rewritten to another). Define all columns inline in one
   `CREATE REL TABLE`, or migrate via drop+recreate.

4. **Any incremental edge write into a populated consolidated REL table
   corrupts.** See the headline section above. The only safe write is
   reconstruct-and-swap; guard `add_edge` to refuse incremental REL writes into a
   non-empty table.

5. **Over-merge is unrecoverable.** Merging entities that aren't the same thing
   cannot be cleanly undone. Treat merges as one-way; verify identity first.

## B. Concurrency / crash sins (corrupt the store or SIGSEGV)

6. **RAM-flush:** LadybugDB buffers ALL writes in RAM until the connection
   closes. Bulk ops (> ~2000 nodes) MUST close + reopen periodically or risk OOM
   and corruption.

7. **Singleton writer handle + any concurrent read-only open → hard SIGSEGV.**
   Use per-request open/close (noisier, never segfaults).

8. **The no-op `close()` trap:** making `close()` a no-op "to let GC handle it"
   silently keeps the exclusive writer lock, starving other writers for weeks.

9. **`close()` while another process holds the lock → SEGV.** Liveness/health
   probes must be **read-only**.

10. **Shutdown deadlock:** the Rust `Drop` at process exit hangs in kernel
    D-state if another process holds the `.ldb`. A single short-lived writer
    avoids it.

11. **Two writers, ever.** If a builder/enricher writes, every other process
    MUST open `read_only=True` on every hot path and route its writes through a
    queue the single writer drains.

12. **Never interrupt a `DETACH DELETE` on an HNSW-indexed table.** One node can
    take minutes (index rebuild); killing mid-delete poisons `.wal` + `.shadow` →
    SIGSEGV on next open. Drop the index first, or don't interrupt.

13. **An OOM-killer SIGKILL of a writer = poisoned WAL with no breadcrumb.** On
    systemd, disable the userspace OOM manager (`systemd-oomd`) on writer-class
    units and let the kernel OOM-killer (which logs to dmesg) be the sole
    authority, so there's a trail.

## C. Recovery (do this, NOT a rollback)

14. **`UNREACHABLE_CODE` / `Corrupted wal` on open is usually an orphan WAL, not
    real corruption.** Move the `.wal` (and `.shadow` if present) aside and
    reopen — do NOT restore from backup first. Check `dmesg -T` for an
    OOM/SIGKILL line in the prior hour to confirm the real cause.

## D. Don't over-react

15. **Constraint/grade-locality debt is harmless noise.** Accepting the stock is
    fine. Do NOT bulk-DELETE to "clean" it — that triggers sin #1 and destroys
    valid edges.

---

## The safe primitives (the inverse of the sins)

- **Reads:** per-request open/close, `read_only=True`. Many readers OK.
- **Writes:** ONE short-lived writer on a write-safe build (≥ 0.17.0 — necessary
  but **not** sufficient, see §A.4); other processes enqueue to a queue the
  writer drains.
- **Edge writes:** NEVER incremental into a populated REL table (§A.4). ALL edge
  adds/updates/deletes go through **reconstruct-and-swap** — drop the REL table,
  bulk-insert every edge into the empty table in one pass, verify
  `collateral == 0`, swap. A write-guard on `add_edge` should refuse incremental
  REL writes once the table is non-empty. Empty-table bulk load in one pass is
  the only safe incremental-looking write.
- **Pruning/retyping:** reconstruct-filtered (all-CREATE, swap), never in-place
  DELETE.
- **Schema:** all REL columns inline at `CREATE`; migrate by drop+recreate, never
  ALTER.
- **Bulk:** close + reopen every ~2000 nodes; `CHECKPOINT` is not a substitute.

---

*Provenance: surfaced while building and dogfooding embedded-LadybugDB
knowledge graphs (including the [good-dog graph pipeline](../tools/good-dog-graph-pipeline/),
whose `--force` build is the reconstruct-and-swap pattern above). Repro details
for §A.4 available on request.*
