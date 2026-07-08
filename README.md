# Narrate

**AI-native documentation orchestration for software products.**

Narrate does not write documentation — it orchestrates the AI agents that do. You describe *what* should be documented (projects, features, and documentation goals); Narrate plans the work and exposes it over the [Model Context Protocol](https://modelcontextprotocol.io) so any MCP-capable AI assistant can pick up tasks and produce documentation one deterministic tool call at a time.

[![CI](https://github.com/luke-nielsen/narrate/actions/workflows/ci.yml/badge.svg)](https://github.com/luke-nielsen/narrate/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## How it works

```
you                        AI assistant (over MCP)                 Narrate
───────────────────────   ─────────────────────────────────────   ──────────────────────────────
narrate project create
narrate feature add
narrate goal add
narrate plan            →  list_pending_tasks                      plans (feature × goal) tasks
                           claim_task                              locks the task to the agent
                           save_artifact                           versions + stores content
                           render_artifact                         markdown / video / slides / …
                           publish_artifact                        filesystem / site / webhook
                           complete_task                           records progress
narrate status
```

Every artifact is stored with full metadata (kind, version, provenance, content hash) in a content-addressed store, so documentation can be **versioned, regenerated, reused, and published to multiple destinations**.

## Supported outputs

| Kind | Source format (saved by the agent) | Rendered output |
| --- | --- | --- |
| `markdown` | Markdown text | `.md` with provenance front matter |
| `script` | Plain-text narration | Numbered teleprompter `.txt` |
| `transcript` | JSON timed cues | Readable timestamped transcript |
| `subtitles` | JSON timed cues | SRT or WebVTT |
| `slide_deck` | Slide JSON | Self-contained HTML presentation |
| `presentation` | Slide JSON | PowerPoint `.pptx` *(extra: `pptx`)* |
| `video` | Composition spec JSON | Remotion render bundle or MP4 |
| `gif` | Frame spec JSON | Animated GIF *(extra: `media`)* |
| `thumbnail` | Title-card JSON | PNG cover image *(extra: `media`)* |

## Installation

```bash
uv tool install narrate            # or: pip install narrate
uv tool install 'narrate[all]'     # with PowerPoint + image extras
```

Requires Python 3.13+. Rendering real MP4s additionally requires Node.js (Remotion); without it, the video renderer produces a portable, ready-to-render project bundle.

## Quick start

```bash
# 1. Describe what to document
narrate project create "Acme Notes" --slug acme-notes \
  --description "A collaborative note-taking app" \
  --app-url https://notes.acme.test
narrate feature add acme-notes "Shared notebooks" \
  --description "Create notebooks and invite teammates" --url-path /notebooks
narrate goal add acme-notes markdown --audience "end users"
narrate goal add acme-notes video

# 2. Plan the work
narrate plan acme-notes

# 3. Let an AI assistant do it (stdio MCP server)
narrate serve
```

Register the server with your assistant, e.g. for Claude Code:

```bash
claude mcp add narrate -- narrate serve
```

Then ask it to *"check Narrate for pending documentation tasks and complete them"*. The assistant discovers tasks (each carries complete instructions and the exact artifact format), saves its work, renders outputs, and publishes them:

```bash
narrate status acme-notes
narrate artifact list acme-notes
narrate publish <artifact-id> static_site ./public/docs
```

## MCP tools

| Tool | Purpose |
| --- | --- |
| `list_projects` / `get_project` | Discover what to document |
| `get_documentation_status` | Progress summary per project |
| `plan_documentation` | Create tasks for uncovered (feature, goal) pairs |
| `list_pending_tasks` / `get_task` | Find work |
| `claim_task` / `complete_task` / `fail_task` | Task lifecycle |
| `save_artifact` | Store generated content (text or base64) |
| `render_artifact` | Produce videos, slides, subtitles, GIFs, … |
| `publish_artifact` / `list_publications` | Deliver and audit |
| `list_artifacts` / `read_artifact` | Reuse earlier work |
| `list_renderers` / `list_publishers` / `list_artifact_kinds` | Capabilities |

See [docs/mcp.md](docs/mcp.md) for the full reference.

## Architecture

```
┌─────────────┐   ┌─────────────┐
│  Typer CLI  │   │  MCP server │        interfaces (thin adapters)
└──────┬──────┘   └──────┬──────┘
       └────────┬────────┘
        ┌───────▼────────┐
        │  Orchestrator  │               lifecycle engine + task planner
        └───┬───────┬────┘
   ┌────────▼──┐ ┌──▼──────────┐
   │ Renderers │ │ Publishers  │         plugins via entry points
   └───────────┘ └─────────────┘
        ┌───────▼────────┐
        │    Storage     │               SQLAlchemy metadata +
        │  DB + blobs    │               content-addressed blob store
        └────────────────┘
```

Renderers and publishers are discovered from the `narrate.renderers` / `narrate.publishers` entry-point groups — third-party packages extend Narrate without touching its core. See [docs/architecture.md](docs/architecture.md) and [docs/extending.md](docs/extending.md).

## Development

```bash
git clone https://github.com/luke-nielsen/narrate && cd narrate
uv sync --all-extras
uv run pytest                 # tests
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
uv run pyright                # types (strict)
```

An end-to-end example lives in [examples/](examples/).

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Narrate is [MIT licensed](LICENSE).
