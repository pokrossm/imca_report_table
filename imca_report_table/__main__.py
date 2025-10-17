"""Command-line interface for IMCA report table utilities."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from rich.console import Console

from . import __version__
from .render.console import render_hierarchy_console
from .render.html import render_html_report, write_html_report
from .traversal import DEFAULT_EXPECTED_COLLECTION_DIRS, build_hierarchy
from .utils import load_hierarchy_json, write_hierarchy_json


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect IMCA trip directory structures and produce reports."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="Path to the trip directory to analyse (optional when --input-json is provided).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status if any expected directories are missing.",
    )
    parser.add_argument(
        "--output-html",
        type=str,
        help="Write an HTML report to the given path.",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="Write the collected hierarchy to a JSON file at the given path.",
    )
    parser.add_argument(
        "--input-json",
        type=str,
        help="Load hierarchy data from a JSON file and skip filesystem traversal.",
    )
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Suppress console tree output (other messages still appear).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logging (errors still printed).",
    )
    parser.add_argument(
        "--title",
        type=str,
        help="Optional HTML report title.",
    )
    parser.add_argument(
        "--no-site-level",
        action="store_true",
        help="Treat trip directories as containing pucks directly (no site level).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the installed version and exit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console()
    log_console = console if not args.quiet else None

    def log(message: str) -> None:
        if log_console:
            log_console.log(message)

    result_source = ""
    if args.input_json:
        try:
            result = load_hierarchy_json(args.input_json)
        except Exception as exc:
            console.print(f"[bold red]error:[/bold red] failed to load hierarchy JSON: {exc}")
            return 1
        result_source = args.input_json
        if log_console:
            log(f"Loaded hierarchy from JSON: {args.input_json}")
    else:
        if args.root is None:
            console.print(
                "[bold red]error:[/bold red] provide a trip directory or use --input-json to supply cached data."
            )
            return 2
        root_path = Path(args.root)
        try:
            if log_console:
                with console.status("Building trip hierarchy...", spinner="dots"):
                    result = build_hierarchy(
                        root_path,
                        DEFAULT_EXPECTED_COLLECTION_DIRS,
                        logger=log,
                        no_site_level=args.no_site_level,
                    )
            else:
                result = build_hierarchy(
                    root_path,
                    DEFAULT_EXPECTED_COLLECTION_DIRS,
                    no_site_level=args.no_site_level,
                )
        except (FileNotFoundError, NotADirectoryError) as exc:
            console.print(f"[bold red]error:[/bold red] {exc}")
            return 1
        result_source = str(root_path)

    if log_console:
        site_count = len(result.trip.sites)
        puck_count = sum(len(site.pucks) for site in result.trip.sites)
        pin_count = sum(len(puck.pins) for site in result.trip.sites for puck in site.pucks)
        log(
            f"Hierarchy ready from {result_source}: {site_count} sites, {puck_count} pucks, {pin_count} pins."
        )

    if not args.no_console:
        render_hierarchy_console(result, console, DEFAULT_EXPECTED_COLLECTION_DIRS)

    if args.output_html:
        if log_console:
            log(f"Rendering HTML report → {args.output_html}")
        html = render_html_report(
            result,
            expected_collection_dirs=DEFAULT_EXPECTED_COLLECTION_DIRS,
            title=args.title,
        )
        output_path = write_html_report(args.output_html, html)
        console.print(f"[green]HTML report written to[/green] {output_path}")

    if args.output_json:
        if log_console:
            log(f"Writing hierarchy JSON → {args.output_json}")
        output_json_path = write_hierarchy_json(args.output_json, result)
        console.print(f"[green]Hierarchy JSON written to[/green] {output_json_path}")

    if log_console and args.strict and not result.all_expected_present:
        log("Strict mode enabled and missing directories detected; exiting with status 1.")
    if args.strict and not result.all_expected_present:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
