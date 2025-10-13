"""HTML report rendering utilities."""

from __future__ import annotations

import base64
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from jinja2 import Environment, PackageLoader, select_autoescape

from ..models import HierarchyResult
from ..traversal import DEFAULT_EXPECTED_COLLECTION_DIRS


_ENV = Environment(
    loader=PackageLoader("imca_report_table", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

CAMERA_PREVIEW_COLUMNS: list[dict[str, str]] = [
    {
        "key": "loop_inter_4_000",
        "search": "loop-inter_4_000",
        "header": "Loop Inter 4 (0°)",
        "missing": "loop-inter_4_000.jpeg",
    },
    {
        "key": "loop_inter_4_045",
        "search": "loop-inter_4_045",
        "header": "Loop Inter 4 (45°)",
        "missing": "loop-inter_4_045.jpeg",
    },
    {
        "key": "loop_inter_4_090",
        "search": "loop-inter_4_090",
        "header": "Loop Inter 4 (90°)",
        "missing": "loop-inter_4_090.jpeg",
    },
    {
        "key": "raster_090",
        "search": "raster_090",
        "header": "Raster 90°",
        "missing": "raster_090.jpeg",
    },
    {
        "key": "raster_180",
        "search": "raster_180",
        "header": "Raster 180°",
        "missing": "raster_180.jpeg",
    },
]

PROCESSING_PREVIEW_COLUMNS: list[dict[str, str]] = [
    {
        "key": "spots_per_image",
        "search": "SpotsPerImage",
        "header": "Spots Per Image",
        "missing": "SPOT.XDS.SpotsPerImage.png",
    },
    {
        "key": "integrate_fitness",
        "search": "INTEGRATE_select2.mrfana.fitness_batch_select2",
        "header": "Fitness Batch",
        "missing": "INTEGRATE_select2.mrfana.fitness_batch_select2.png",
    },
]


def _embed_images(image_paths: Sequence[str], *, name_filter: str | None = None) -> list[dict[str, str]]:
    previews: list[dict[str, str]] = []
    for path_str in image_paths:
        path = Path(path_str)
        if name_filter and name_filter not in path.name:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        mime, _ = mimetypes.guess_type(path.name)
        if mime is None:
            mime = "image/jpeg"
        encoded = base64.b64encode(data).decode("ascii")
        previews.append(
            {
                "path": path_str,
                "basename": path.name,
                "data_uri": f"data:{mime};base64,{encoded}",
            }
        )
    return previews


def flatten_collections(result: HierarchyResult) -> list[dict]:
    """Return flattened collection rows for tabular reporting."""
    rows: list[dict] = []
    for site, puck, pin, collection in result.trip.iter_collections():
        row = collection.to_flat_row(pin, puck, site, result.trip)
        expected_info = row.get("expected", {})
        camera_metadata = expected_info.get("camera", {}).get("metadata", {}) if expected_info else {}
        processing_metadata = expected_info.get("processing", {}).get("metadata", {}) if expected_info else {}
        row["missing_expected_list"] = row.get("missing_expected_names", [])
        row["issues"] = []
        if row["pin_missing_collections"]:
            row["issues"].append("Pin missing lettered collections")
        if row["missing_expected_list"]:
            row["issues"].append(
                "Missing: " + ", ".join(row["missing_expected_list"])
            )
        if row["extras"]:
            row["issues"].append("Extras: " + ", ".join(row["extras"]))
        image_files = camera_metadata.get("image_files", []) or []
        camera_cells: dict[str, dict[str, str] | None] = {}
        camera_previews: list[dict[str, str]] = []
        used_camera_paths: set[str] = set()
        for column in CAMERA_PREVIEW_COLUMNS:
            search_term = column["search"]
            candidates = [
                preview
                for preview in _embed_images(image_files, name_filter=search_term)
                if preview["path"] not in used_camera_paths
            ]
            preview = candidates[0] if candidates else None
            if preview:
                used_camera_paths.add(preview["path"])
                camera_previews.append(preview)
            camera_cells[column["key"]] = preview
        row["camera_previews"] = camera_previews
        row["camera_preview_cells"] = camera_cells
        row["camera_preview_missing"] = [
            column["missing"]
            for column in CAMERA_PREVIEW_COLUMNS
            if camera_cells[column["key"]] is None
        ]
        summary_images = processing_metadata.get("summary_images") or []
        if not summary_images:
            summary_image = processing_metadata.get("summary_image")
            summary_images = [summary_image] if summary_image else []
        processing_previews = _embed_images(summary_images) if summary_images else []
        row["processing_summary_preview"] = processing_previews
        processing_cells: dict[str, dict[str, str] | None] = {}
        for column in PROCESSING_PREVIEW_COLUMNS:
            marker = column["search"].lower()
            preview = next(
                (
                    candidate
                    for candidate in processing_previews
                    if marker in candidate["basename"].lower()
                ),
                None,
            )
            processing_cells[column["key"]] = preview
        row["processing_summary_cells"] = processing_cells
        row["processing_summary_missing"] = [
            column["missing"]
            for column in PROCESSING_PREVIEW_COLUMNS
            if processing_cells[column["key"]] is None
        ]
        rows.append(row)
    return rows


def render_html_report(
    result: HierarchyResult,
    *,
    expected_collection_dirs: Sequence[str] | None = None,
    generated_at: datetime | None = None,
    title: str | None = None,
) -> str:
    """Render the hierarchy into an HTML document."""
    template = _ENV.get_template("report.html.j2")
    expected_dirs = expected_collection_dirs or DEFAULT_EXPECTED_COLLECTION_DIRS
    generated_at = generated_at or datetime.now(timezone.utc)
    title = title or f"IMCA Trip Report - {result.trip_name}"

    stats = {
        "sites": len(result.trip.sites),
        "pucks": sum(len(site.pucks) for site in result.trip.sites),
        "pins": sum(len(puck.pins) for site in result.trip.sites for puck in site.pucks),
        "collections": sum(
            len(pin.collections)
            for site in result.trip.sites
            for puck in site.pucks
            for pin in puck.pins
        ),
    }
    stats["pins_with_issues"] = sum(1 for pin in result.trip.iter_pins() if pin.has_issues)

    return template.render(
        title=title,
        result=result,
        generated_at=generated_at,
        stats=stats,
        expected_collection_dirs=expected_dirs,
        flattened_rows=flatten_collections(result),
        camera_preview_columns=[
            {
                "key": column["key"],
                "header": column["header"],
                "missing": column["missing"],
            }
            for column in CAMERA_PREVIEW_COLUMNS
        ],
        processing_preview_columns=[
            {
                "key": column["key"],
                "header": column["header"],
                "missing": column["missing"],
            }
            for column in PROCESSING_PREVIEW_COLUMNS
        ],
    )


def write_html_report(output_path: Path | str, html_content: str) -> Path:
    """Write the HTML report to disk."""
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_content, encoding="utf-8")
    return output
