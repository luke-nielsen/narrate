# Examples

## `acme_notes.py` — the full lifecycle, end to end

A self-contained walkthrough that plays *both* roles: the human describing a product (normally the CLI) and the AI agent doing the work (normally an MCP client). It creates a project with two features and three documentation goals, plans tasks, "generates" content for each one, renders every output (markdown, HTML slides, SRT subtitles, a Remotion video bundle), and publishes everything to a static site.

```bash
uv run python examples/acme_notes.py
```

Everything is written to `./example-output/`:

- `narrate-home/` — the Narrate state (SQLite DB + content-addressed blobs)
- `site/` — the published documentation site; open `site/index.html` in a browser

## Doing the same with the CLI + an AI assistant

The human side, with the CLI:

```bash
export NARRATE_HOME=./example-output/narrate-home
narrate project create "Acme Notes" --description "A collaborative note-taking app" \
  --app-url https://notes.acme.test
narrate feature add acme-notes "Shared notebooks" --url-path /notebooks
narrate goal add acme-notes markdown
narrate goal add acme-notes video
narrate plan acme-notes
```

The agent side, over MCP — register the server with your assistant:

```bash
claude mcp add narrate --env NARRATE_HOME=$PWD/example-output/narrate-home -- narrate serve
```

then prompt it with something like:

> Check Narrate for pending documentation tasks and complete them all. Render each artifact and publish the results to ./public with the static_site publisher.

Watch progress from the human side with `narrate status acme-notes` and `narrate task list acme-notes`.
