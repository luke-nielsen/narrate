# Extending Narrate

Narrate's extension points are ordinary Python packages that declare entry points. Nothing in the core needs to change — publish your package, install it next to `narrate`, and the plugin appears in `narrate plugins list`, the CLI, and the MCP tools.

## Writing a renderer

A renderer consumes one *source* artifact and returns rendered bytes. It must be stateless and must not touch storage; the engine persists the result as a new artifact with provenance.

```python
# my_narrate_pdf/renderer.py
from typing import ClassVar

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult


class PdfRenderer(Renderer):
    """Render markdown sources to PDF."""

    name: ClassVar[str] = "pdf"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset({ArtifactKind.MARKDOWN})
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.MARKDOWN
    description: ClassVar[str] = "Render markdown as PDF"

    def render(self, request: RenderRequest) -> RenderResult:
        self.check_input(request)          # validates the source kind
        markdown = request.text()          # or request.json() for JSON sources
        pdf_bytes = my_pdf_library.convert(markdown)
        return RenderResult(
            content=pdf_bytes,
            kind=self.output_kind,
            media_type="application/pdf",
            suffix=".pdf",
            metadata={"pages": 3},
        )
```

Declare it in your package's `pyproject.toml`:

```toml
[project.entry-points."narrate.renderers"]
pdf = "my_narrate_pdf.renderer:PdfRenderer"
```

Useful helpers on `RenderRequest`:

- `request.text()` / `request.json()` — decode the source with clear `RenderError`s on bad input.
- `request.workspace` — a per-artifact scratch directory for intermediate files.
- `request.options` — caller-supplied options; validate and raise `RenderError` for bad values.

## Writing a publisher

A publisher delivers bytes to a destination and returns a receipt. Raise `PublishError` on failure — the engine records it as a failed `Publication` (the delivery history is an audit trail, so failures are data, not crashes).

```python
# my_narrate_s3/publisher.py
from typing import ClassVar

from narrate.exceptions import PublishError
from narrate.publishing.base import Publisher, PublishReceipt, PublishRequest


class S3Publisher(Publisher):
    """Upload artifacts to an S3 bucket."""

    name: ClassVar[str] = "s3"
    description: ClassVar[str] = "Upload artifacts to S3 (destination: bucket/prefix)"

    def publish(self, request: PublishRequest) -> PublishReceipt:
        bucket, _, prefix = request.destination.partition("/")
        key = f"{prefix}/{request.filename}" if prefix else request.filename
        try:
            boto3.client("s3").put_object(
                Bucket=bucket, Key=key, Body=request.content,
                ContentType=request.artifact.media_type,
            )
        except Exception as exc:
            raise PublishError(f"s3 upload failed: {exc}") from exc
        return PublishReceipt(location=f"s3://{bucket}/{key}")
```

```toml
[project.entry-points."narrate.publishers"]
s3 = "my_narrate_s3.publisher:S3Publisher"
```

`request.filename` gives you a collision-safe versioned name (`guide.v2.md`).

## Testing plugins

Registries can be built empty and populated by hand, so plugin tests never depend on what's installed:

```python
from narrate.rendering.registry import RendererRegistry

registry = RendererRegistry(discover=False)
registry.register(PdfRenderer())
```

For end-to-end tests, construct an `Orchestrator` with your registry (see `tests/conftest.py` in the Narrate repo for the pattern) — or register into a live container's registries: `container.renderers.register(PdfRenderer())`.

## Optional dependencies

If your plugin needs a heavy library, import it *inside* `render()`/`publish()` and raise a helpful error when missing, as the built-in `pptx`/`gif`/`thumbnail` renderers do. A plugin whose entry point fails to import is skipped at discovery without breaking other plugins, but a lazy import with a clear message is a much better experience.

## Other extension seams

- **AI providers** don't need a plugin API at all: any MCP client is a "provider". Alternative integrations can also embed the engine directly — construct a `Container` and call `Orchestrator` methods from your own agent loop.
- **Storage** — the engine takes `Database` and `BlobStore` by injection; a different database is just a `NARRATE_DATABASE_URL`, and a different blob backend can implement the same `put`/`get`/`exists` surface.
- **Planning** — pass a custom `planner` to `Orchestrator` to change how goals expand into tasks (e.g. one task per user journey instead of per feature).
