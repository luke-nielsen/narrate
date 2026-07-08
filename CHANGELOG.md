# Changelog

All notable changes to Narrate are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-07

Initial release.

### Added

- Domain model: projects, features, documentation goals, tasks, artifacts, publications.
- Storage: SQLAlchemy metadata store plus content-addressed, integrity-checked blob store.
- Orchestration engine with idempotent task planning and strict lifecycle rules.
- MCP server (`narrate serve`) exposing 19 tools for AI assistants to discover, claim, generate, render, publish, and complete documentation work.
- Typer CLI for humans: project/feature/goal management, planning, status, artifact export, render, publish.
- Renderer plugins (entry-point group `narrate.renderers`): markdown, script, transcript, subtitles (SRT/VTT), HTML slides, PowerPoint, Remotion video (portable bundle or MP4), animated GIF, thumbnail.
- Publisher plugins (entry-point group `narrate.publishers`): filesystem, static site with manifest + index, webhook.
- Optional extras: `pptx` (python-pptx), `media` (Pillow), `all`.
- Documentation: architecture, MCP reference, plugin-authoring guide, runnable example.
- CI: ruff lint/format, strict pyright, pytest on Linux/macOS/Windows, build artifacts; trusted-publishing release workflow.
