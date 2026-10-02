# Contributing

Thanks for considering a contribution. This page covers the development
workflow.

## Setup

```bash
git clone https://github.com/BrunoMoreno/findmyjob.git
cd findmyjob

python -m venv env
source env/bin/activate      # Linux/macOS
# env\Scripts\activate       # Windows

pip install -e ".[dev,docs]"
```

## Tests and lint

```bash
pytest -v
ruff check .
```

The suite lives in `tests/`:

- `tests/test_main.py` - core functions (search, filtering, output, database).
- `tests/test_ats.py` - ATS providers, discovery and data-quality fixes.

Please keep `ruff` clean and add tests for new behavior.

## Documentation

The docs are built with MkDocs Material:

```bash
mkdocs serve      # live preview at http://127.0.0.1:8000
mkdocs build --strict
```

Deployment to GitHub Pages is automatic from `main` via
`.github/workflows/docs.yml`.

## Project layout

See [Architecture](architecture.md) for the module map. In short:

- `src/findmyjob/cli.py` is the orchestrator; keep it thin.
- Put new logic in a focused module and re-export it from `findmyjob.cli` if
  it is part of the public surface.
- Keep the public API in `src/findmyjob/__init__.py` in sync.

## Adding an ATS provider

1. Add the provider to `PROVIDERS` and `PROVIDER_DOMAINS` in `ats.py`.
2. Implement `fetch_<provider>(slug, **kwargs)` returning the standard job
   dictionaries (see [Data model](data-model.md#job-object)).
3. Register it in `FETCHERS`.
4. Add URL patterns to `ATS_URL_PATTERNS` and a dork domain in
   `discover.py`.
5. Add tests and update the [ATS docs](ats.md).

## Pull requests

1. Fork the project or create a branch.
2. Make your change with tests.
3. Run `pytest` and `ruff check .`.
4. Open a pull request describing the change.

## Release process (maintainers)

1. Bump `__version__` in `src/findmyjob/__init__.py`.
2. Open and merge the pull request into `main`.
3. Create a GitHub release for the new tag (`vX.Y.Z`). The
   `.github/workflows/publish-pypi.yml` workflow publishes to PyPI.
