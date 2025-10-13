"""Utility helpers for serialising hierarchy data."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .models import (
    CollectionStatus,
    ExpectedDirectoryStatus,
    HierarchyResult,
    PinStatus,
    PuckStatus,
    SiteStatus,
    TripHierarchy,
)


def _serialise(value: Any) -> Any:
    if is_dataclass(value):
        return _serialise(asdict(value))
    if isinstance(value, dict):
        return {key: _serialise(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialise(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def hierarchy_to_dict(result: HierarchyResult) -> dict:
    """Convert HierarchyResult into a JSON-serialisable dictionary."""
    return _serialise(result)


def write_hierarchy_json(path: str | Path, result: HierarchyResult) -> Path:
    """Serialize hierarchy result to JSON at the given path."""
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data = hierarchy_to_dict(result)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output


def _expected_from_dict(data: dict) -> ExpectedDirectoryStatus:
    path_value = data.get("path")
    return ExpectedDirectoryStatus(
        name=data["name"],
        present=data.get("present", False),
        path=Path(path_value) if path_value else None,
        metadata=data.get("metadata", {}),
    )


def _collection_from_dict(data: dict) -> CollectionStatus:
    return CollectionStatus(
        name=data["name"],
        path=Path(data["path"]),
        expected=[_expected_from_dict(item) for item in data.get("expected", [])],
        extras=list(data.get("extras", [])),
    )


def hierarchy_from_dict(payload: dict) -> HierarchyResult:
    """Rehydrate HierarchyResult from a dictionary."""
    trip_data = payload["trip"]
    trip = TripHierarchy(name=trip_data["name"], path=Path(trip_data["path"]))

    for site_data in trip_data.get("sites", []):
        site = SiteStatus(name=site_data["name"], path=Path(site_data["path"]))
        trip.add_site(site)
        for puck_data in site_data.get("pucks", []):
            puck = PuckStatus(name=puck_data["name"], path=Path(puck_data["path"]))
            site.add_puck(puck)
            for pin_data in puck_data.get("pins", []):
                pin = PinStatus(name=pin_data["name"], path=Path(pin_data["path"]))
                pin.missing_collections = pin_data.get("missing_collections", False)
                for collection_data in pin_data.get("collections", []):
                    pin.add_collection(_collection_from_dict(collection_data))
                puck.add_pin(pin)
    return HierarchyResult(
        trip=trip,
        all_expected_present=payload.get("all_expected_present", False),
    )


def load_hierarchy_json(path: str | Path) -> HierarchyResult:
    """Load hierarchy result from a JSON file."""
    source = Path(path).expanduser().resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    return hierarchy_from_dict(data)
