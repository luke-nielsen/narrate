# Architecture

Narrate is a strictly layered system. Each layer depends only on the layers below it, and the two extension surfaces (renderers and publishers) are plugins loaded through entry points, so the core never changes when capabilities are added.

```
interfaces      cli/  mcp/          thin adapters; no business logic
orchestration   orchestration/      lifecycle engine + task planner
plugins         rendering/  publishing/   registries + built-in plugins
storage         storage/            SQLAlchemy metadata + blob store
domain          models/             frozen Pydantic entities
```

## Domain (`narrate.models`)

Frozen (immutable) Pydantic models are the shared vocabulary of every layer:

- **Project** — a software product being documented (metadata, application URL).
- **Feature** — a discrete capability of a project; the unit of documentation.
- **DocumentationGoal** — "every feature should have a *`<kind>`*" plus audience/tone/guidance.
- **DocumentationTask** — one (feature × goal) unit of work for an AI agent, with a full instruction block and a lifecycle (`pending → in_progress → completed | failed | cancelled`).
- **Artifact** — stored content plus everything needed to version, regenerate, reuse, and publish it: kind, name, monotonic version, media type, SHA-256 content hash, provenance (`created_by`, `task_id`, `derived_from`, `renderer`), and free-form metadata.
- **Publication** — an audit record of one delivery attempt (success or failure).

Because models are frozen, all state changes flow through the storage layer, which returns fresh instances — no aliasing bugs, no partially mutated entities.

## Storage (`narrate.storage`)

Two complementary stores:

- **Relational metadata** (`Database`, `orm.py`, `repositories.py`). Any SQLAlchemy-supported database; SQLite by default. ORM rows are private to this layer — repositories accept and return domain models only. `Database.session()` provides commit/rollback transaction scoping; the orchestrator owns transaction boundaries.
- **BlobStore** — content-addressed artifact content at `blobs/<sha256[:2]>/<sha256>`. Identical content is deduplicated for free, writes are atomic (temp file + rename), and every read is integrity-checked against its address.

Splitting metadata from content means artifact rows stay tiny, re-saving identical content is free, and the blob directory can be relocated (or later re-backed by object storage) without touching the schema.

## Orchestration (`narrate.orchestration`)

- **TaskPlanner** is pure domain logic: it expands (feature × goal) pairs that lack a task into new pending tasks, composing per-task instructions from project, feature, and goal context plus a *format hint* describing the exact JSON/text shape the agent must save. Planning is idempotent.
- **Orchestrator** is the single facade every interface calls. It enforces lifecycle rules (claim before save, save before complete), computes artifact versions, stores render outputs as *derived artifacts* linked to their source via `derived_from`, and records every publish attempt. All dependencies (database, blob store, registries, planner) are injected through the constructor, so tests and embedders can swap any piece.

**Composition** happens in exactly one place: `narrate.container.Container` builds the standard object graph from `NarrateSettings` (environment-driven via `NARRATE_*` variables).

## Plugins (`narrate.rendering`, `narrate.publishing`)

Both surfaces follow the same pattern:

- An abstract base class (`Renderer`, `Publisher`) with a small, data-in/data-out contract. Renderers receive `RenderRequest` (source artifact + bytes + scratch workspace + options) and return `RenderResult` (bytes + kind + media type + metadata). Publishers receive `PublishRequest` and return `PublishReceipt`. Neither touches storage — persistence is the engine's job, which keeps plugins trivially testable.
- A `PluginRegistry` that lazily discovers instances from an entry-point group (`narrate.renderers`, `narrate.publishers`). A broken third-party plugin is isolated: it is skipped at discovery and its load error surfaces only if it is requested by name.
- The renderer registry additionally maps each artifact kind to a default renderer, so callers may omit the renderer name.

The built-in renderers and publishers register through the *same* entry-point mechanism as third-party ones — the core has no special knowledge of them.

## Interfaces (`narrate.cli`, `narrate.mcp`)

Both are deliberately thin:

- The **MCP server** (FastMCP) maps ~19 tools one-to-one onto orchestrator methods and serialises domain models with `model_dump(mode="json")`. Binary content crosses the wire base64-encoded.
- The **CLI** (Typer) covers the human side: describing projects, planning, inspecting progress, exporting/publishing artifacts, and launching the MCP server (`narrate serve`).

## Key flows

**Render** — `render_artifact(source_id)` reads the source artifact and its bytes, picks a renderer (named or default-for-kind), hands it a per-artifact workspace directory, and stores the returned bytes as a *new* artifact with `derived_from`/`renderer` provenance. Regeneration is therefore always possible: the source artifact is never mutated.

**Publish** — `publish_artifact(id, publisher, destination)` delivers bytes and records a `Publication` either way; failures are recorded and returned rather than raised, so delivery history is a complete audit trail.

**Concurrency** — task claiming is guarded by status transition checks inside a transaction; two agents cannot both move the same task from `pending` to `in_progress`.
