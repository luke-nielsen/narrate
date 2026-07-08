# Contributing to Narrate

Thanks for your interest in improving Narrate! This document covers the practical side of contributing.

## Development setup

Requirements: [uv](https://docs.astral.sh/uv/) (which will install Python 3.13 for you).

```bash
git clone https://github.com/luke-nielsen/narrate
cd narrate
uv sync --all-extras
```

## Quality gates

Every pull request must pass all four; CI enforces them:

```bash
uv run pytest                 # unit + integration tests
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
uv run pyright                # strict type checking
```

Run `uv run ruff format .` and `uv run ruff check . --fix` to auto-fix most issues.

## Ground rules

- **Layering**: `models` ← `storage` ← `rendering`/`publishing` ← `orchestration` ← `cli`/`mcp`. Never import upward. Interfaces (CLI/MCP) contain no business logic — if you're tempted, the logic belongs in `Orchestrator`.
- **Domain models are frozen.** State changes go through repositories; ORM rows never leave `narrate/storage`.
- **Plugins stay pure.** Renderers and publishers are data-in/data-out and must not touch storage. New output formats should be new renderer plugins, not engine changes.
- **Types and docs**: complete type hints (pyright runs in strict mode) and Google-style docstrings on every public module, class, and function.
- **Tests**: new behaviour needs tests. Unit tests live in `tests/unit`, cross-layer tests in `tests/integration` (marked `@pytest.mark.integration`). Use the fixtures in `tests/conftest.py` — every test gets an isolated temporary Narrate home.
- **Errors**: raise subclasses of `NarrateError` with actionable messages; never let raw library exceptions escape a public API.

## Adding a built-in renderer or publisher

1. Implement it under `src/narrate/rendering/builtin/` or `src/narrate/publishing/builtin/`.
2. Register it in `pyproject.toml` under `[project.entry-points."narrate.renderers"]` / `."narrate.publishers"`.
3. If the source format is new, add a format hint in `orchestration/planner.py` and (if needed) a default in `rendering/registry.py`.
4. Add tests covering the happy path and at least one malformed-input path.
5. Document options in `docs/mcp.md` and the README table.

Heavy dependencies must be optional extras, imported lazily inside `render()`/`publish()` with a helpful install message.

## Commit and PR conventions

- Keep PRs focused; separate refactors from behaviour changes.
- Describe *why* in the PR body, including trade-offs you considered.
- Update `CHANGELOG.md` under an `Unreleased` heading.

## Reporting issues

Use the GitHub issue tracker. For bugs, include your Python version, Narrate version (`narrate version`), and a minimal reproduction — ideally as a failing test.

## Code of conduct

Be kind and assume good faith. Harassment or personal attacks are not tolerated.
