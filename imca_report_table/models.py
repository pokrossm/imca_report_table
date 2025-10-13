"""Data models for IMCA report table hierarchy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class ExpectedDirectoryStatus:
    """Status for an expected collection subdirectory."""

    name: str
    present: bool
    path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def status_label(self) -> str:
        return "OK" if self.present else "missing"


@dataclass(slots=True)
class CollectionStatus:
    """Details about a lettered collection directory beneath a pin."""

    name: str
    path: Path
    expected: list[ExpectedDirectoryStatus] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)

    @property
    def missing_expected(self) -> bool:
        return any(not entry.present for entry in self.expected)

    def to_flat_row(self, parent_pin: PinStatus, parent_puck: PuckStatus, parent_site: SiteStatus, trip: TripHierarchy) -> dict[str, Any]:
        """Return a flattened dictionary representation suitable for tabular output."""
        expected_status = {
            entry.name: {
                "present": entry.present,
                "status": entry.status_label,
                "path": str(entry.path) if entry.path else None,
                "metadata": entry.metadata,
            }
            for entry in self.expected
        }
        missing_expected_names = [
            name for name, status in expected_status.items() if not status["present"]
        ]
        return {
            "trip": trip.name,
            "trip_path": str(trip.path),
            "site": parent_site.name,
            "site_path": str(parent_site.path),
            "puck": parent_puck.name,
            "puck_path": str(parent_puck.path),
            "pin": parent_pin.name,
            "pin_path": str(parent_pin.path),
            "collection": self.name,
            "collection_path": str(self.path),
            "expected": expected_status,
            "extras": self.extras,
            "missing_expected": bool(missing_expected_names),
            "missing_expected_names": missing_expected_names,
            "pin_missing_collections": parent_pin.missing_collections,
        }


@dataclass(slots=True)
class PinStatus:
    """Information about a pin and its collection directories."""

    name: str
    path: Path
    collections: list[CollectionStatus] = field(default_factory=list)
    missing_collections: bool = False

    def add_collection(self, collection: CollectionStatus) -> None:
        self.collections.append(collection)

    @property
    def has_issues(self) -> bool:
        return self.missing_collections or any(
            collection.missing_expected for collection in self.collections
        )


@dataclass(slots=True)
class PuckStatus:
    """Grouping of pins inside a puck directory."""

    name: str
    path: Path
    pins: list[PinStatus] = field(default_factory=list)

    def add_pin(self, pin: PinStatus) -> None:
        self.pins.append(pin)


@dataclass(slots=True)
class SiteStatus:
    """Grouping of pucks within a site."""

    name: str
    path: Path
    pucks: list[PuckStatus] = field(default_factory=list)

    def add_puck(self, puck: PuckStatus) -> None:
        self.pucks.append(puck)


@dataclass(slots=True)
class TripHierarchy:
    """Top-level trip directory layout."""

    name: str
    path: Path
    sites: list[SiteStatus] = field(default_factory=list)

    def add_site(self, site: SiteStatus) -> None:
        self.sites.append(site)

    def iter_pins(self) -> Iterable[PinStatus]:
        for site in self.sites:
            for puck in site.pucks:
                for pin in puck.pins:
                    yield pin

    def iter_collections(self) -> Iterable[tuple[SiteStatus, PuckStatus, PinStatus, CollectionStatus]]:
        for site in self.sites:
            for puck in site.pucks:
                for pin in puck.pins:
                    for collection in pin.collections:
                        yield site, puck, pin, collection


@dataclass(slots=True)
class HierarchyResult:
    """Aggregate traversal result containing hierarchy and validation flag."""

    trip: TripHierarchy
    all_expected_present: bool

    @property
    def trip_name(self) -> str:
        return self.trip.name
