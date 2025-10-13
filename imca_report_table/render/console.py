"""Console rendering utilities using Rich."""

from __future__ import annotations

from typing import Sequence

from rich.console import Console
from rich.text import Text
from rich.tree import Tree

from ..models import CollectionStatus, HierarchyResult, PinStatus, TripHierarchy
from ..traversal import DEFAULT_EXPECTED_COLLECTION_DIRS


def _collection_to_tree(
    collection: CollectionStatus, expected_collection_dirs: Sequence[str]
) -> Tree:
    label = Text.assemble(
        ("Collection ", "green"),
        (collection.name, "bold green"),
    )
    node = Tree(label)
    expected_lookup = {entry.name: entry for entry in collection.expected}
    for expected_name in expected_collection_dirs:
        entry = expected_lookup.get(expected_name)
        status = entry.status_label if entry else "missing"
        present = entry.present if entry else False
        style = "green" if present else "bold red"
        node.add(f"[{style}]- {expected_name} ({status})[/]")
    for extra in collection.extras:
        node.add(f"[yellow]- {extra} (extra)[/yellow]")
    return node


def _pin_to_tree(
    pin: PinStatus, expected_collection_dirs: Sequence[str]
) -> Tree:
    label = Text.assemble(("Pin: ", "bold magenta"), (pin.name, "white"))
    if pin.missing_collections:
        label.append(" (missing collections)", style="bold red")
    node = Tree(label)
    if pin.missing_collections:
        node.add("[bold red]- No lettered collection directories found.[/bold red]")
    for collection in pin.collections:
        node.add(_collection_to_tree(collection, expected_collection_dirs))
    return node


def _trip_to_tree(
    trip: TripHierarchy, expected_collection_dirs: Sequence[str]
) -> Tree:
    label = Text.assemble(("Trip: ", "bold"), (trip.name, "bold cyan"))
    tree = Tree(label, guide_style="bold bright_black")
    for site in trip.sites:
        site_label = Text.assemble(("Site: ", "cyan"), (site.name, "white"))
        site_node = tree.add(site_label)
        for puck in site.pucks:
            puck_label = Text.assemble(("Puck: ", "magenta"), (puck.name, "white"))
            puck_node = site_node.add(puck_label)
            for pin in puck.pins:
                puck_node.add(_pin_to_tree(pin, expected_collection_dirs))
    return tree


def render_hierarchy_console(
    result: HierarchyResult,
    console: Console | None = None,
    expected_collection_dirs: Sequence[str] | None = None,
) -> Console:
    """Render the hierarchy tree using Rich."""
    console = console or Console()
    expected_dirs = expected_collection_dirs or DEFAULT_EXPECTED_COLLECTION_DIRS

    if not result.trip.sites:
        console.print("[yellow]No sites found under the provided trip directory.[/yellow]")
        return console

    console.print(_trip_to_tree(result.trip, expected_dirs))
    if result.all_expected_present:
        console.print("[green]All expected collection directories found.[/green]")
    else:
        console.print("[bold red]Missing collection directories detected.[/bold red]")
    return console
