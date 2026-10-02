# Installation

## Requirements

- Python **3.10+**
- Dependencies (installed automatically): `ddgs`, `requests`, `openpyxl`

## From PyPI (recommended)

```bash
pip install findmyjob
```

This installs the `findmyjob` command and the `findmyjob` Python package.

## From source

```bash
git clone https://github.com/BrunoMoreno/findmyjob.git
cd findmyjob

# Regular install
pip install .

# Development install (changes take effect immediately)
pip install -e .
```

## Development setup

For a full development environment, including the test and documentation
dependencies:

```bash
python -m venv env
source env/bin/activate      # Linux/macOS
# env\Scripts\activate       # Windows

pip install -e ".[dev,docs]"
```

## Optional: Google Custom Search

The default backend (DuckDuckGo) needs no credentials. To use the Google
backend, set two environment variables:

```bash
export GOOGLE_API_KEY="your_key"
export GOOGLE_CX="your_cx"
```

See [CLI reference](cli.md#search-backends) for details.

## Verify the installation

```bash
findmyjob --version
findmyjob --help
```
