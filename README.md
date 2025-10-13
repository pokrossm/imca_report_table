# IMCA Report Table

Utilities for inspecting IMCA trip directories, validating their structure, and emitting console and HTML summaries.

## Features
- Traverses trip → site → puck → pin → collection hierarchies and verifies required subdirectories.
- Collects camera assets (loop-inter images at 0°, 45°, 90° plus raster previews) and processing outputs (SpotsPerImage and fitness plots).
- Renders a Rich console tree and a sortable HTML report with one table cell per expected preview, highlighting missing files inline.
- Supports JSON export/import so expensive traversals can be cached.

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### Using `uv`
```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Usage
Basic run against a trip directory:
```bash
imca-report-table /path/to/trip
```

Common flags:
- `--output-html report.html` – write the HTML overview.
- `--output-json cache.json` – persist the hierarchy for reuse.
- `--input-json cache.json` – skip traversal and load cached data.
- `--no-console` – suppress Rich tree output.
- `--quiet` – silence progress logs.
- `--no-site-level` – treat pucks as direct children of the trip directory.
- `--strict` – return a non-zero exit code if any required directory is missing.

### Example: generate HTML and JSON outputs
```bash
imca-report-table /data/trips/2025_09_28_IMCA_LVL \
  --output-html reports/2025_09_28_IMCA_LVL.html 
```

## Development
- Code lives under `imca_report_table/`; tests mirror modules under `tests/`.
- Run the full suite with:
  ```bash
  pytest
  ```
- HTML templates are in `imca_report_table/templates/`; editing them typically requires adjusting `flatten_collections` in `render/html.py` and the associated tests.

## Output Notes
- The console renderer uses Rich to display the hierarchy and issue status.
- The HTML report’s collections table dedicates columns to loop-inter images at 0°, 45°, 90°, raster previews, and processing summaries; missing assets are called out directly in each cell.
- Embedded images are base64 encoded for portability; large datasets may produce sizable reports.
