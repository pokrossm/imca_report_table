from __future__ import annotations

from pathlib import Path

import base64
import json

from imca_report_table.render import html as html_render
from imca_report_table.traversal import build_hierarchy
from imca_report_table.utils import hierarchy_from_dict, hierarchy_to_dict


def create_collection(tmp_path: Path, site: str, puck: str, pin: str, collection: str) -> None:
    base = tmp_path / site / puck / pin / collection
    for sub in ("camera", "diff-center", "images", "processing"):
        (base / sub).mkdir(parents=True, exist_ok=True)


def test_build_hierarchy_detects_missing_collection(tmp_path: Path) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "A")
    (tmp_path / "site1" / "puck01" / "pin2").mkdir(parents=True)

    result = build_hierarchy(tmp_path)

    assert result.trip.name == tmp_path.name
    assert len(result.trip.sites) == 1
    pin1, pin2 = result.trip.sites[0].pucks[0].pins
    assert not pin1.has_issues
    assert pin2.missing_collections
    assert not result.all_expected_present


def test_build_hierarchy_handles_extras(tmp_path: Path) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "B")
    extra_dir = tmp_path / "site1" / "puck01" / "pin1" / "B" / "extra-folder"
    extra_dir.mkdir()

    result = build_hierarchy(tmp_path)

    pin = result.trip.sites[0].pucks[0].pins[0]
    collection = pin.collections[0]
    assert "extra-folder" in collection.extras


def test_camera_metadata_collected(tmp_path: Path, monkeypatch) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "C")
    camera_dir = tmp_path / "site1" / "puck01" / "pin1" / "C" / "camera"
    (camera_dir / "image1.JPG").write_text("", encoding="utf-8")
    (camera_dir / "subdir").mkdir()
    (camera_dir / "subdir" / "image2.png").write_text("", encoding="utf-8")
    (camera_dir / "metadata.csv").write_text("a,b,c\n", encoding="utf-8")

    result = build_hierarchy(tmp_path)

    collection = result.trip.sites[0].pucks[0].pins[0].collections[0]
    camera_status = next(
        status for status in collection.expected if status.name == "camera"
    )
    assert camera_status.present
    assert camera_status.path == camera_dir.resolve()
    assert sorted(camera_status.metadata["image_files"]) == sorted(
        [
            str((camera_dir / "image1.JPG").resolve()),
            str((camera_dir / "subdir" / "image2.png").resolve()),
        ]
    )
    assert camera_status.metadata["csv_files"] == [
        str((camera_dir / "metadata.csv").resolve())
    ]


def test_hierarchy_json_serialisation(tmp_path: Path) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "D")
    result = build_hierarchy(tmp_path)

    data = hierarchy_to_dict(result)
    assert data["trip"]["name"] == tmp_path.name
    assert isinstance(data["trip"]["path"], str)
    restored = hierarchy_from_dict(data)
    assert restored.trip.name == result.trip.name
    assert restored.trip.sites[0].pucks[0].pins[0].missing_collections == result.trip.sites[0].pucks[0].pins[0].missing_collections
    json_path = tmp_path / "hierarchy.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    from imca_report_table.utils import load_hierarchy_json

    loaded = load_hierarchy_json(json_path)
    assert loaded.trip.name == result.trip.name


def test_flatten_collections_embeds_loop_images(tmp_path: Path) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "E")
    camera_dir = tmp_path / "site1" / "puck01" / "pin1" / "E" / "camera"
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    (camera_dir / "loop-inter_4_000.jpeg").write_bytes(png_bytes)

    result = build_hierarchy(tmp_path)
    rows = html_render.flatten_collections(result)
    assert rows
    row = rows[0]
    loop_preview = row["camera_preview_cells"]["loop_inter_4_000"]
    assert loop_preview is not None
    preview = loop_preview
    assert preview["basename"] == "loop-inter_4_000.jpeg"
    assert preview["data_uri"].startswith("data:image/")
    assert row["camera_preview_missing"] == [
        "loop-inter_4_045.jpeg",
        "loop-inter_4_090.jpeg",
        "raster_090.jpeg",
        "raster_180.jpeg",
    ]


def test_processing_summary_embedding(tmp_path: Path) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "F")
    processing_dir = tmp_path / "site1" / "puck01" / "pin1" / "F" / "processing"
    img_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    (processing_dir / "images").mkdir(parents=True, exist_ok=True)
    summary_img = processing_dir / "images" / "SPOT.XDS.SpotsPerImage.png"
    summary_img.write_bytes(img_bytes)
    second_img = processing_dir / "INTEGRATE_select2.mrfana.fitness_batch_select2.png"
    second_img.write_bytes(img_bytes)
    summary_html = processing_dir / "00_summary.html"
    summary_html.write_text(
        (
            '<html><body>'
            '<img src="images/SPOT.XDS.SpotsPerImage.png?width=600"/>'
            '<img src="INTEGRATE_select2.mrfana.fitness_batch_select2.png"/>'
            "</body></html>"
        ),
        encoding="utf-8",
    )

    result = build_hierarchy(tmp_path)
    rows = html_render.flatten_collections(result)
    row = rows[0]
    spots_preview = row["processing_summary_cells"]["spots_per_image"]
    integrate_preview = row["processing_summary_cells"]["integrate_fitness"]
    assert spots_preview is not None
    assert integrate_preview is not None
    assert spots_preview["basename"] == "SPOT.XDS.SpotsPerImage.png"
    assert integrate_preview["basename"] == "INTEGRATE_select2.mrfana.fitness_batch_select2.png"
    assert spots_preview["data_uri"].startswith("data:image/")
    assert integrate_preview["data_uri"].startswith("data:image/")
    assert row["processing_summary_missing"] == []


def test_flatten_collections_includes_raster_previews(tmp_path: Path) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "G")
    camera_dir = tmp_path / "site1" / "puck01" / "pin1" / "G" / "camera"
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    (camera_dir / "raster_090.jpeg").write_bytes(png_bytes)
    (camera_dir / "subdir").mkdir()
    (camera_dir / "subdir" / "raster_180.jpeg").write_bytes(png_bytes)

    result = build_hierarchy(tmp_path)
    rows = html_render.flatten_collections(result)
    row = rows[0]
    assert row["camera_preview_cells"]["raster_090"] is not None
    assert row["camera_preview_cells"]["raster_090"]["basename"] == "raster_090.jpeg"
    assert row["camera_preview_cells"]["raster_180"] is not None
    assert row["camera_preview_cells"]["raster_180"]["basename"] == "raster_180.jpeg"
    assert row["camera_preview_missing"] == [
        "loop-inter_4_000.jpeg",
        "loop-inter_4_045.jpeg",
        "loop-inter_4_090.jpeg",
    ]


def test_processing_summary_embedding_no_site(tmp_path: Path) -> None:
    base = tmp_path / "puckA" / "pin1" / "A"
    for sub in ("camera", "diff-center", "images", "processing"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    processing_dir = base / "processing"
    summary_img = processing_dir / "SPOT.XDS_pre-cleanup.SpotsPerImage.png"
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    summary_img.write_bytes(png_bytes)
    summary_html = processing_dir / "00_summary.html"
    summary_html.write_text(
        f'<html><body><img src="file://{summary_img.resolve()}"/></body></html>',
        encoding="utf-8",
    )

    result = build_hierarchy(tmp_path, no_site_level=True)
    rows = html_render.flatten_collections(result)
    row = rows[0]
    assert row["processing_summary_cells"]["spots_per_image"] is not None
    assert row["processing_summary_cells"]["integrate_fitness"] is None
    assert row["processing_summary_missing"] == ["INTEGRATE_select2.mrfana.fitness_batch_select2.png"]


def test_processing_summary_embedding_only_integrate(tmp_path: Path) -> None:
    create_collection(tmp_path, "site1", "puck01", "pin1", "H")
    processing_dir = tmp_path / "site1" / "puck01" / "pin1" / "H" / "processing"
    img_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    summary_img = processing_dir / "INTEGRATE_select2.mrfana.fitness_batch_select2.png"
    summary_img.write_bytes(img_bytes)
    summary_html = processing_dir / "00_summary.html"
    summary_html.write_text(
        '<html><body><img src="INTEGRATE_select2.mrfana.fitness_batch_select2.png"/></body></html>',
        encoding="utf-8",
    )

    result = build_hierarchy(tmp_path)
    rows = html_render.flatten_collections(result)
    row = rows[0]
    spots_cell = row["processing_summary_cells"]["spots_per_image"]
    integrate_cell = row["processing_summary_cells"]["integrate_fitness"]
    assert spots_cell is None
    assert integrate_cell is not None
    assert integrate_cell["basename"] == "INTEGRATE_select2.mrfana.fitness_batch_select2.png"
    assert integrate_cell["data_uri"].startswith("data:image/")
    assert row["processing_summary_missing"] == ["SPOT.XDS.SpotsPerImage.png"]


def test_traversal_without_site_level(tmp_path: Path) -> None:
    base = tmp_path / "puck01" / "pin1" / "A"
    for sub in ("camera", "diff-center", "images", "processing"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    result = build_hierarchy(tmp_path, no_site_level=True)

    assert len(result.trip.sites) == 1
    site = result.trip.sites[0]
    assert site.name == "root"
    assert len(site.pucks) == 1
    assert site.pucks[0].name == "puck01"
