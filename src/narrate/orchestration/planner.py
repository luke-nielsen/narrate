"""Task planning: expand documentation goals into concrete tasks.

The planner is pure domain logic -- no I/O -- which keeps it trivially
testable and reusable by alternative engines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrate.models import ArtifactKind, DocumentationGoal, DocumentationTask, Feature, Project

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

__all__ = ["FORMAT_HINTS", "TaskPlanner"]

FORMAT_HINTS: dict[ArtifactKind, str] = {
    ArtifactKind.MARKDOWN: (
        "Save markdown text. Start with a # title heading and cover what the "
        "feature does, how to use it step by step, and common pitfalls."
    ),
    ArtifactKind.SCRIPT: (
        "Save plain text narration, one paragraph per scene, written to be "
        "read aloud in a friendly tone."
    ),
    ArtifactKind.TRANSCRIPT: (
        'Save JSON: {"cues": [{"start": <seconds>, "end": <seconds>, '
        '"text": "...", "speaker": "..."}]} with cues in chronological order.'
    ),
    ArtifactKind.SUBTITLES: (
        'Save JSON cues ({"cues": [{"start", "end", "text"}]}); they render to SRT or WebVTT.'
    ),
    ArtifactKind.SLIDE_DECK: (
        'Save JSON: {"title": "...", "subtitle": "...", "slides": '
        '[{"title": "...", "bullets": ["..."], "notes": "..."}]}.'
    ),
    ArtifactKind.PRESENTATION: (
        "Save slide-deck JSON (same shape as slide_deck); it renders to a .pptx presentation."
    ),
    ArtifactKind.VIDEO: (
        'Save a JSON composition spec: {"title": "...", "fps": 30, "width": '
        '1920, "height": 1080, "scenes": [{"heading": "...", "body": "...", '
        '"duration_seconds": 4}]}. It renders with Remotion.'
    ),
    ArtifactKind.GIF: (
        'Save JSON: {"width": 640, "height": 360, "frames": [{"text": "...", '
        '"duration_ms": 1500}]} showing one step per frame.'
    ),
    ArtifactKind.THUMBNAIL: (
        'Save JSON: {"title": "...", "subtitle": "...", "width": 1280, '
        '"height": 720} for the cover image.'
    ),
}


class TaskPlanner:
    """Expands (feature x goal) pairs into pending documentation tasks."""

    def plan(
        self,
        project: Project,
        features: Sequence[Feature],
        goals: Sequence[DocumentationGoal],
        existing: Iterable[tuple[str, str]],
    ) -> list[DocumentationTask]:
        """Compute the tasks that do not exist yet.

        Args:
            project: The project being planned.
            features: All registered features.
            goals: All configured documentation goals.
            existing: ``(feature_id, goal_id)`` pairs that already have a
                task (any status) and must not be duplicated.

        Returns:
            New pending tasks, ordered by feature priority then kind.
        """
        existing_pairs = set(existing)
        tasks: list[DocumentationTask] = []
        for feature in sorted(features, key=lambda f: (f.priority, f.slug)):
            for goal in sorted(goals, key=lambda g: g.kind.value):
                if (feature.id, goal.id) in existing_pairs:
                    continue
                tasks.append(
                    DocumentationTask(
                        project_id=project.id,
                        feature_id=feature.id,
                        goal_id=goal.id,
                        kind=goal.kind,
                        title=f"{goal.kind.value.replace('_', ' ').title()}: {feature.name}",
                        instructions=self.build_instructions(project, feature, goal),
                    )
                )
        return tasks

    @staticmethod
    def build_instructions(
        project: Project,
        feature: Feature,
        goal: DocumentationGoal,
    ) -> str:
        """Compose the full context an AI agent needs to do the task."""
        lines = [
            f"Produce a {goal.kind.value.replace('_', ' ')} documenting the feature "
            f"{feature.name!r} of {project.name!r}.",
            "",
            f"Project: {project.name} -- {project.description}".rstrip(" -"),
        ]
        if project.application_url:
            lines.append(f"Application URL: {project.application_url}")
        if project.repository_url:
            lines.append(f"Repository: {project.repository_url}")
        lines.append(f"Feature: {feature.name} -- {feature.description}".rstrip(" -"))
        if feature.url_path:
            lines.append(f"Feature location: {feature.url_path}")
        lines.extend(
            [
                f"Audience: {goal.audience}",
                f"Tone: {goal.tone}",
            ]
        )
        if goal.instructions:
            lines.append(f"Additional guidance: {goal.instructions}")
        hint = FORMAT_HINTS.get(goal.kind)
        if hint:
            lines.extend(["", f"Artifact format: {hint}"])
        return "\n".join(lines)
