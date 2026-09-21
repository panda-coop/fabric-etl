"""Command line interface over the registry: entrypoint and registry loading."""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import TYPE_CHECKING

from fabric_etl import __version__

if TYPE_CHECKING:
    from fabric_etl.entities import Registry


def _is_path(value: str) -> bool:
    return "/" in value or value.endswith(".py")


def load_registry(registry: str, mode: str = "runtime") -> tuple[Registry, list]:
    """(registry, mappings) for --registry/--mode.

    A dotted module is imported — its @entity decorators fill the global
    REGISTRY and Mapping subclasses fill transform.MAPPINGS. A filesystem path
    (contains "/" or ends with .py) or --mode static goes through the static
    extractor, which never imports user code and yields no mappings."""
    if mode == "static" or _is_path(registry):
        from fabric_etl.static import extract_registry

        return extract_registry([registry]), []
    importlib.import_module(registry)
    from fabric_etl.entities import REGISTRY
    from fabric_etl.transform import MAPPINGS

    return REGISTRY, list(MAPPINGS)


def _add_registry_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--registry",
        required=True,
        help="dotted module to import, or a .py file / directory for static extraction",
    )
    sub.add_argument("--mode", choices=("runtime", "static"), default="runtime")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-etl", description="Schema-as-code toolkit")
    parser.add_argument("--version", action="store_true", help="print the package version")
    parser.add_subparsers(dest="command")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    func = getattr(args, "func", None)
    if func is None:
        parser.print_usage(sys.stderr)
        return 2
    try:
        return func(args)
    except ImportError as exc:
        print(f"fabric-etl: {exc}", file=sys.stderr)
        return 1
