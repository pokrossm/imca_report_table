"""Traversal utilities for IMCA trip directory structures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re
from typing import Iterable, Sequence

from .models import (
    CollectionStatus,
    ExpectedDirectoryStatus,
    HierarchyResult,
    PinStatus,
    PuckStatus,
    SiteStatus,
    TripHierarchy,
)

DEFAULT_EXPECTED_COLLECTION_DIRS: Sequence[str] = (
    "camera",
    "diff-center",
    "images",
    "processing",
)


def _iter_dirs(path: Path) -> Iterable[Path]:
    """Yield child directories sorted alphabetically."""
    return sorted((child for child in path.iterdir() if child.is_dir()), key=lambda p: p.name)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
CSV_EXTENSIONS = {".csv"}


def _collect_camera_metadata(camera_dir: Path) -> dict[str, list[str]]:
    """Collect absolute image and CSV file paths from a camera directory."""
    image_files: list[str] = []
    csv_files: list[str] = []
    for file_path in camera_dir.rglob("*"):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        resolved = str(file_path.resolve())
        if suffix in IMAGE_EXTENSIONS:
            image_files.append(resolved)
        elif suffix in CSV_EXTENSIONS:
            csv_files.append(resolved)
    image_files.sort()
    csv_files.sort()
    return {"image_files": image_files, "csv_files": csv_files}


_SUMMARY_IMG_PATTERN = re.compile(
    r'src=["\']([^"\']*(?:SPOT\.XDS[^"\']*SpotsPerImage|INTEGRATE_select2\.mrfana\.fitness_batch_select2)[^"\']*)["\']',
    re.IGNORECASE,
)


def _normalize_summary_path(raw_ref: str, processing_dir: Path, summary_file: Path) -> Path | None:
    ref = raw_ref.split("?")[0].split("#")[0]
    if ref.startswith("file://"):
        ref = ref[7:]
    ref = ref.replace("\\", "/")
    path_candidate = Path(ref)

    candidates: list[Path] = []
    if path_candidate.is_absolute():
        candidates.append(path_candidate)
    else:
        candidates.append((summary_file.parent / path_candidate))
        candidates.append((processing_dir / path_candidate.name))
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            resolved = candidate
        if resolved.exists():
            return resolved
    return None


def _collect_processing_metadata(processing_dir: Path) -> dict[str, str | list[str]]:
    """Extract summary image paths from processing directory."""
    candidate_summaries = [
        processing_dir / "00_summary.html",
        processing_dir / "00_summary" / "00_summary.html",
    ]
    if processing_dir.exists():
        candidate_summaries.extend(processing_dir.glob("**/00_summary.html"))

    summary_file: Path | None = None
    for candidate in candidate_summaries:
        if candidate.exists():
            summary_file = candidate
            break
    if summary_file is None:
        return {}

    try:
        content = summary_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}

    images: list[Path] = []
    seen: set[Path] = set()
    for match in _SUMMARY_IMG_PATTERN.finditer(content):
        img_path = match.group(1)
        image_file = _normalize_summary_path(img_path, processing_dir, summary_file)
        if image_file and image_file.exists():
            resolved = image_file.resolve()
            if resolved not in seen:
                seen.add(resolved)
                images.append(resolved)

    if not images:
        search_patterns = (
            "SPOT.XDS*SpotsPerImage*.png",
            "INTEGRATE_select2.mrfana.fitness_batch_select2.png",
        )
        for pattern in search_patterns:
            fallback = next(
                (
                    candidate.resolve()
                    for candidate in sorted(processing_dir.rglob(pattern))
                    if candidate.is_file()
                ),
                None,
            )
            if fallback and fallback not in seen:
                seen.add(fallback)
                images.append(fallback)
            if images:
                break

    if not images:
        return {}

    result: dict[str, str | list[str]] = {
        "summary_source": str(summary_file.resolve()),
        "summary_images": [str(path) for path in images],
    }
    if images:
        result["summary_image"] = str(images[0])
    return result


def build_hierarchy(
    root: Path | str,
    expected_collection_dirs: Sequence[str] | None = None,
    logger: Callable[[str], None] | None = None,
    *,
    no_site_level: bool = False,
) -> HierarchyResult:
    """
    Build a TripHierarchy representation rooted at `root`.

    Returns HierarchyResult capturing whether every expected directory exists.
    """
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(root_path)
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)

    expected_dirs = tuple(expected_collection_dirs or DEFAULT_EXPECTED_COLLECTION_DIRS)

    def log(message: str) -> None:
        if logger:
            logger(message)

    log(f"Scanning trip directory: {root_path}")

    trip = TripHierarchy(name=root_path.name, path=root_path)
    all_ok = True

    def process_puck(parent_site: SiteStatus, puck_dir: Path) -> None:
        nonlocal all_ok
        log(f"  Processing puck: {puck_dir.name}")
        puck_status = PuckStatus(name=puck_dir.name, path=puck_dir)
        parent_site.add_puck(puck_status)

        for pin_dir in _iter_dirs(puck_dir):
            log(f"   Inspecting pin: {pin_dir.name}")
            pin_status = PinStatus(name=pin_dir.name, path=pin_dir)
            puck_status.add_pin(pin_status)

            collection_dirs = [
                child
                for child in _iter_dirs(pin_dir)
                if len(child.name) == 1 and child.name.isalpha() and child.name.isupper()
            ]
            if not collection_dirs:
                log(f"    ⚠️  No collection directory found under pin {pin_dir.name}")
                pin_status.missing_collections = True
                all_ok = False
                continue

            for collection_dir in collection_dirs:
                log(f"    Collection {collection_dir.name}: analysing expected folders")
                present_dirs = {
                    child.name for child in _iter_dirs(collection_dir)
                }
                expected_status: list[ExpectedDirectoryStatus] = []
                for expected in expected_dirs:
                    expected_path = collection_dir / expected
                    present = expected_path.is_dir()
                    metadata: dict[str, list[str]] = {}
                    if present and expected == "camera":
                        metadata = _collect_camera_metadata(expected_path)
                    elif present and expected == "processing":
                        metadata = _collect_processing_metadata(expected_path)
                    status = ExpectedDirectoryStatus(
                        name=expected,
                        present=present,
                        path=expected_path.resolve() if present else None,
                        metadata=metadata,
                    )
                    expected_status.append(status)
                if any(not status.present for status in expected_status):
                    log(
                        f"     ⚠️  Missing expected directories: "
                        f"{', '.join(s.name for s in expected_status if not s.present)}"
                    )
                    all_ok = False
                extras = sorted(present_dirs - set(expected_dirs))
                collection_status = CollectionStatus(
                    name=collection_dir.name,
                    path=collection_dir,
                    expected=expected_status,
                    extras=extras,
                )
                pin_status.add_collection(collection_status)
                if extras:
                    log(
                        f"     ℹ️  Extra directories detected: {', '.join(extras)}"
                    )

    if no_site_level:
        log("No site level detected; grouping pucks directly under trip.")
        site_status = SiteStatus(name="root", path=root_path)
        trip.add_site(site_status)
        for puck_dir in _iter_dirs(root_path):
            process_puck(site_status, puck_dir)
    else:
        for site_dir in _iter_dirs(root_path):
            log(f" Found site: {site_dir.name}")
            site_status = SiteStatus(name=site_dir.name, path=site_dir)
            trip.add_site(site_status)
            for puck_dir in _iter_dirs(site_dir):
                process_puck(site_status, puck_dir)
    return HierarchyResult(trip=trip, all_expected_present=all_ok)
