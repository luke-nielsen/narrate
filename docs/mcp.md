# MCP server reference

Start the server with `narrate serve` (stdio transport). Register it with any MCP-capable assistant, e.g.:

```bash
claude mcp add narrate -- narrate serve
```

Configuration comes from `NARRATE_*` environment variables (see `narrate.config.NarrateSettings`); by default all state lives under `~/.narrate/`.

## The agent workflow

```
list_projects ──► get_project ──► plan_documentation (optional)
      │
      ▼
list_pending_tasks ──► get_task ──► claim_task
      │
      ▼
save_artifact ──► render_artifact ──► publish_artifact ──► complete_task
                                                    (or fail_task)
```

Each task's `instructions` field contains everything the agent needs: project context, feature description, audience, tone, and the exact source format for the artifact kind (also available via `list_artifact_kinds`).

## Tools

### Discovery

| Tool | Arguments | Returns |
| --- | --- | --- |
| `list_projects` | — | All projects |
| `get_project` | `project` (slug or id) | Project with features and goals |
| `get_documentation_status` | `project` | Task counts, artifact/publication totals, pending task ids |
| `list_artifact_kinds` | — | Every kind with its expected source format |
| `list_renderers` | — | Renderer names with input/output kinds |
| `list_publishers` | — | Publisher names and descriptions |

### Task lifecycle

| Tool | Arguments | Notes |
| --- | --- | --- |
| `plan_documentation` | `project` | Idempotent; returns only newly created tasks |
| `list_pending_tasks` | `project?` | Omit `project` to see all pending work |
| `list_tasks` | `project`, `status?` | Full task list with optional status filter |
| `get_task` | `task_id` | Includes full instructions |
| `claim_task` | `task_id`, `agent_name?` | Only pending tasks can be claimed |
| `complete_task` | `task_id` | Requires a saved artifact |
| `fail_task` | `task_id`, `reason` | Records the reason for humans |

### Artifacts

| Tool | Arguments | Notes |
| --- | --- | --- |
| `save_artifact` | `task_id`, `content`, `name?`, `media_type?`, `encoding?`, `metadata?` | `encoding` is `text` (default) or `base64`; saving again creates a new version |
| `list_artifacts` | `project`, `feature?`, `kind?`, `latest_only?` | |
| `read_artifact` | `artifact_id` | Text inline (truncated at 100k chars) or base64 |

### Rendering & publishing

| Tool | Arguments | Notes |
| --- | --- | --- |
| `render_artifact` | `artifact_id`, `renderer?`, `options?` | Defaults to the standard renderer for the source kind; output is a new artifact with `derived_from` set |
| `publish_artifact` | `artifact_id`, `publisher`, `destination`, `options?` | Failures are *recorded and returned*, not raised |
| `list_publications` | `artifact_id` | Full delivery history |

## Renderer options

| Renderer | Option | Values |
| --- | --- | --- |
| `subtitles` | `format` | `srt` (default), `vtt` |
| `markdown` | `front_matter` | `true` (default) / `false`; `title` overrides the heading |
| `script` | `width` | Wrap column, default 72 |
| `remotion_video` | `mode` | `bundle` (default, portable ZIP) or `video` (MP4; requires Node.js) |

## Publisher destinations

| Publisher | Destination | Options |
| --- | --- | --- |
| `filesystem` | Directory path | `overwrite_latest` (default true) |
| `static_site` | Site root directory | `site_title` |
| `webhook` | `http(s)://` URL | `include_content` (default true), `timeout_seconds`, `headers` |

## Source formats

| Kind | Agent saves |
| --- | --- |
| `markdown` | Markdown text |
| `script` | Plain text, one paragraph per scene |
| `transcript` / `subtitles` | `{"cues": [{"start": 0.0, "end": 3.2, "text": "...", "speaker": "..."}]}` |
| `slide_deck` / `presentation` | `{"title": "...", "subtitle": "...", "slides": [{"title": "...", "bullets": ["..."], "notes": "..."}]}` |
| `video` | `{"title": "...", "fps": 30, "width": 1920, "height": 1080, "scenes": [{"heading": "...", "body": "...", "duration_seconds": 4}]}` |
| `gif` | `{"width": 640, "height": 360, "frames": [{"text": "...", "duration_ms": 1500}]}` |
| `thumbnail` | `{"title": "...", "subtitle": "...", "width": 1280, "height": 720}` |
