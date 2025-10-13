# Repository Guidelines

## Project Structure & Module Organization
Core code now lives under the `imca_report_table/` package. Key modules: `traversal.py` builds the hierarchy, `models.py` stores dataclasses, `render/console.py` prints Rich trees, `render/html.py` builds HTML via Jinja templates, and `cli.py` wires everything together. Templates reside in `imca_report_table/templates/`. Keep new functionality in the appropriate module (e.g., rendering additions under `render/`) and export public helpers through `__init__.py`. Place tests in `tests/` mirroring the module under test. Persist generated reports outside version control; `.venv/` remains a local workspace artifact.

## Build, Test, and Development Commands
Stay on Python 3.12. Typical workflow:
- `python -m venv .venv && source .venv/bin/activate` – create/enter a local environment.
- `pip install --upgrade pip && pip install -e .` – install the package in editable mode with dependencies (`rich`, `jinja2`, `pytest` if desired).
- `imca-report-table /path/to/trip --output-html report.html --output-json hierarchy.json` – run the CLI entry point; omit `--no-console` to see the Rich tree, add `--quiet` to suppress progress logs, `--no-site-level` when pucks live directly under the trip directory, use `--input-json hierarchy.json` to reuse cached data, and `--strict` for non-zero exits on missing directories.
- `pytest` – execute the test suite under `tests/`. Add flags like `-k` or `-vv` for targeted runs.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation, descriptive snake_case for functions and variables, and PascalCase for classes. Annotate function signatures with type hints and add short docstrings describing intent and inputs. Keep imports grouped by standard library, third party, then local. Extract helpers instead of nesting conditionals deeply; aim for cohesive functions under ~40 lines to keep logic reviewable.

## Testing Guidelines
Use `pytest` with temporary directory fixtures for filesystem-heavy cases. Each new module should have focused tests (see `tests/test_traversal.py` for patterns). When adding renderers, assert on targeted substrings (HTML) or leverage Rich’s console recording helpers. Run `pytest` before submitting changes and capture example output when adjusting report formatting.

## Commit & Pull Request Guidelines
Write commits in the imperative mood (`Add CSV export helper`) and scope each to a single concern. Reference an issue ID or customer request when relevant. Pull requests should explain the problem, outline the solution, and list verification steps (CLI runs, screenshots, or sample output). Call out follow-up tasks or optimisation ideas so the next agent can pick them up with full context.
