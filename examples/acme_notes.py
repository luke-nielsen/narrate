"""End-to-end Narrate walkthrough.

Plays both roles in one script: the *human* describing a product and its
documentation goals, and the *AI agent* that discovers tasks, generates
content, renders outputs, and publishes them.  In production the human
side is the ``narrate`` CLI and the agent side is an MCP client.

Run with::

    uv run python examples/acme_notes.py
"""

from __future__ import annotations

import json
from pathlib import Path

from narrate.config import NarrateSettings
from narrate.container import Container
from narrate.models import ArtifactKind, DocumentationTask

OUTPUT = Path(__file__).parent.parent / "example-output"


def generate_content(task: DocumentationTask) -> bytes:
    """Stand-in for an AI agent generating content for a task.

    A real agent reads ``task.instructions`` (which include the exact
    format for each kind) and produces something far more interesting.
    """
    if task.kind is ArtifactKind.MARKDOWN:
        return (
            b"# Shared notebooks\n\n"
            b"Notebooks let your whole team write together.\n\n"
            b"## Create a notebook\n\n"
            b"1. Open **Notebooks** in the sidebar.\n"
            b"2. Click **New notebook** and give it a name.\n"
            b"3. Invite teammates with **Share**.\n"
        )
    if task.kind is ArtifactKind.SLIDE_DECK:
        deck = {
            "title": "Acme Notes in five minutes",
            "subtitle": "Collaborative notes for teams",
            "slides": [
                {"title": "Shared notebooks", "bullets": ["Create", "Invite", "Write together"]},
                {"title": "Instant search", "bullets": ["Every note, indexed", "Filters"]},
            ],
        }
        return json.dumps(deck).encode()
    if task.kind is ArtifactKind.VIDEO:
        spec = {
            "title": "Getting started with Acme Notes",
            "fps": 30,
            "scenes": [
                {"heading": "Welcome", "body": "Acme Notes in 60 seconds.", "duration_seconds": 3},
                {
                    "heading": "Notebooks",
                    "body": "Create and share instantly.",
                    "duration_seconds": 4,
                },
            ],
        }
        return json.dumps(spec).encode()
    if task.kind is ArtifactKind.TRANSCRIPT:
        cues = {
            "cues": [
                {"start": 0.0, "end": 3.0, "text": "Welcome to Acme Notes.", "speaker": "Host"},
                {"start": 3.0, "end": 7.0, "text": "Let's create your first notebook."},
            ]
        }
        return json.dumps(cues).encode()
    msg = f"this example does not generate {task.kind.value} content"
    raise ValueError(msg)


def main() -> None:
    """Run the walkthrough."""
    settings = NarrateSettings(home=OUTPUT / "narrate-home")
    site = OUTPUT / "site"

    with Container(settings) as container:
        engine = container.orchestrator

        # -- The human describes the product ---------------------------
        if not engine.list_projects():
            project = engine.create_project(
                "Acme Notes",
                description="A collaborative note-taking app",
                application_url="https://notes.acme.test",
                tags=("example",),
            )
            engine.add_feature(
                project.slug,
                "Shared notebooks",
                description="Create notebooks and invite teammates",
                url_path="/notebooks",
                priority=1,
            )
            engine.add_goal(project.slug, ArtifactKind.MARKDOWN)
            engine.add_goal(project.slug, ArtifactKind.SLIDE_DECK, audience="new customers")
            engine.add_goal(project.slug, ArtifactKind.VIDEO, tone="energetic")
            engine.add_goal(project.slug, ArtifactKind.TRANSCRIPT)

        planned = engine.plan("acme-notes")
        print(f"planned {len(planned)} task(s)")

        # -- The "AI agent" works every pending task -------------------
        for task in engine.list_pending_tasks("acme-notes"):
            claimed = engine.claim_task(task.id, agent="example-agent")
            print(f"\n▶ {claimed.title}")

            source = engine.save_task_artifact(claimed.id, generate_content(claimed))
            print(f"  saved   {source.name} v{source.version}")

            derived = engine.render_artifact(source.id)
            print(f"  rendered {derived.name} ({derived.media_type}, {derived.size_bytes} bytes)")

            # Transcripts additionally render to subtitles.
            if task.kind is ArtifactKind.TRANSCRIPT:
                subs = engine.render_artifact(source.id, renderer="subtitles")
                engine.publish_artifact(subs.id, "static_site", str(site))
                print(f"  rendered {subs.name} ({subs.media_type})")

            publication = engine.publish_artifact(
                derived.id, "static_site", str(site), options={"site_title": "Acme Notes Docs"}
            )
            print(f"  published -> {publication.location}")

            engine.complete_task(claimed.id)

        # -- The human checks progress ---------------------------------
        report = engine.status("acme-notes")
        print(f"\ntasks: {report.tasks_by_status}")
        print(f"artifacts stored: {report.artifacts}, publications: {report.publications}")
        print(f"open {site / 'index.html'} to browse the published docs")


if __name__ == "__main__":
    main()
