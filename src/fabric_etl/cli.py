"""Command line interface over the registry: docs, dbml, ddl and lint."""

from __future__ import annotations

import argparse
import importlib
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from fabric_etl import __version__

if TYPE_CHECKING:
    from fabric_etl.entities import Registry

_DDL_DRIVERS = ("sqlserver", "warehouse", "lakehouse")


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


def _write_tree(pages: dict[str, str], out: Path) -> None:
    for rel, content in pages.items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _check_tree(pages: dict[str, str], out: Path) -> int:
    """Render into a tempdir and diff file sets plus contents against out.

    Differing relative paths go to stderr; out is never written to."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        _write_tree(pages, fresh)
        expected = {p.relative_to(fresh).as_posix() for p in fresh.rglob("*") if p.is_file()}
        actual = (
            {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
            if out.is_dir()
            else set()
        )
        differing = sorted(
            (expected ^ actual)
            | {
                rel
                for rel in expected & actual
                if (fresh / rel).read_bytes() != (out / rel).read_bytes()
            }
        )
    for rel in differing:
        print(rel, file=sys.stderr)
    return 1 if differing else 0


def _cmd_docs(args: argparse.Namespace) -> int:
    registry, mappings = load_registry(args.registry, args.mode)
    from fabric_etl.docs import drivers, jsonschema, lineage, markdown

    pages: dict[str, str] = {}
    pages.update(markdown.emit(registry, mappings))
    pages.update(jsonschema.emit(registry))
    if mappings:
        pages.update(lineage.emit(mappings, registry))
    pages["drivers.md"] = drivers.emit()

    out = Path(args.out)
    if args.check:
        return _check_tree(pages, out)
    _write_tree(pages, out)
    print(f"wrote {len(pages)} files to {out}")
    return 0


def _cmd_dbml(args: argparse.Namespace) -> int:
    registry, _ = load_registry(args.registry, args.mode)
    from fabric_etl.docs import dbml

    content = dbml.emit(registry)
    out = Path(args.out)
    if args.check:
        if out.is_file() and out.read_text(encoding="utf-8") == content:
            return 0
        print(str(out), file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return 0


def _cmd_ddl(args: argparse.Namespace) -> int:
    registry, _ = load_registry(args.registry, args.mode)
    from fabric_etl.entities.drivers import Lakehouse, SqlServer, Warehouse
    from fabric_etl.load.ddl import ddl

    by_name = {d.name: d for d in (SqlServer, Warehouse, Lakehouse)}
    driver = by_name[args.driver] if args.driver else None
    out = Path(args.out)
    count = 0
    for info in registry.entities():
        if info.source:
            continue
        try:
            statement = ddl(info, driver=driver)
        except (KeyError, ValueError) as exc:
            print(f"skipped {info.key}: {exc}", file=sys.stderr)
            continue
        path = out / (info.schema or "_noschema") / f"{info.table}.sql"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(statement + "\n", encoding="utf-8")
        count += 1
    print(f"wrote {count} files to {out}")
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    if args.mode == "static" or _is_path(args.registry):
        from fabric_etl.static import lint_static

        findings = lint_static([args.registry], strict=args.strict)
    else:
        importlib.import_module(args.registry)
        from fabric_etl.entities import REGISTRY
        from fabric_etl.entities.lint import lint

        findings = lint(REGISTRY, strict=args.strict)
    for finding in findings:
        print(finding)
    return 1 if any(f.level == "error" for f in findings) else 0


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
    sub = parser.add_subparsers(dest="command")

    docs = sub.add_parser("docs", help="emit markdown, JSON Schema and lineage pages")
    _add_registry_args(docs)
    docs.add_argument("--out", required=True, help="output directory")
    docs.add_argument("--check", action="store_true", help="diff against --out, write nothing")
    docs.set_defaults(func=_cmd_docs)

    dbml = sub.add_parser("dbml", help="emit one DBML schema file")
    _add_registry_args(dbml)
    dbml.add_argument("--out", required=True, help="output file")
    dbml.add_argument("--check", action="store_true", help="diff against --out, write nothing")
    dbml.set_defaults(func=_cmd_dbml)

    ddl = sub.add_parser("ddl", help="emit CREATE TABLE per non-source entity")
    _add_registry_args(ddl)
    ddl.add_argument("--out", required=True, help="output directory")
    ddl.add_argument("--driver", choices=_DDL_DRIVERS, help="override the entity driver")
    ddl.set_defaults(func=_cmd_ddl)

    lint = sub.add_parser("lint", help="lint entity names and driver constraints")
    _add_registry_args(lint)
    lint.add_argument("--strict", action="store_true", help="promote warnings to errors")
    lint.set_defaults(func=_cmd_lint)

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
