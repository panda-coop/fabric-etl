"""Lint rules over registered entities: physical names and driver constraints.

E002 (non-literal declarations) lives in the static extractor, not here.
"""

from __future__ import annotations

import inspect
import re
import sys
from dataclasses import dataclass

from fabric_etl.entities.drivers import Lakehouse, Warehouse
from fabric_etl.entities.entity import REGISTRY, EntityInfo, Registry

_BAD_CHARS = " $[]\"'`"  # rejected by Delta without column mapping
_SNAKE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    level: str  # "error" | "warning"
    message: str
    suggestion: str | None = None

    def __str__(self) -> str:
        text = f"{self.path}:{self.line}  {self.code}  {self.message}"
        return f"{text} -> {self.suggestion}" if self.suggestion else text


def _location(cls: type) -> tuple[str, int]:
    try:
        path = inspect.getsourcefile(cls)
    except TypeError:
        path = None
    if path is None:
        module = sys.modules.get(cls.__module__)
        path = getattr(module, "__file__", None) or cls.__module__
    try:
        _, line = inspect.getsourcelines(cls)
    except (OSError, TypeError):
        line = 1
    return path, line


def _bad_chars(name: str) -> list[str]:
    return [ch for ch in _BAD_CHARS if ch in name]


def _nav_style(attr: str) -> bool:
    return attr.endswith("_") or any(ch.isupper() for ch in attr)


def _suggest_snake(attr: str) -> str:
    snake = _SNAKE.sub("_", attr).lower()
    return re.sub(r"__+", "_", snake).strip("_")


def _entity_findings(info: EntityInfo) -> list[Finding]:
    path, line = _location(info.cls)
    out: list[Finding] = []

    def add(code: str, level: str, message: str, suggestion: str | None = None) -> None:
        out.append(Finding(path, line, code, level, message, suggestion))

    names = [("schema", info.schema), ("table", info.table)]
    names += [("column", c.physical) for c in info.columns]
    for what, name in names:
        if name and (bad := _bad_chars(name)):
            chars = ", ".join(repr(ch) for ch in bad)
            add("E001", "error", f"{what} name {name!r} contains {chars}")

    is_warehouse = info.driver is not None and issubclass(info.driver, Warehouse)
    is_lakehouse = info.driver is not None and issubclass(info.driver, Lakehouse)

    if is_warehouse:
        for c in info.columns:
            covered_by_native = c.col.native and "warehouse" in c.col.native
            if c.py_type is str and c.col.length is None and not covered_by_native:
                add(
                    "E003",
                    "error",
                    f"str column '{c.attr}' has no Col(length=) but the entity targets"
                    " Warehouse (varchar(n) requires a length)",
                )

    for c in info.columns:
        if _nav_style(c.attr):
            add(
                "W001",
                "warning",
                f"attribute '{c.attr}' looks NAV/BC-style (trailing '_', No_/Nr_, CamelCase)",
                _suggest_snake(c.attr),
            )

    if is_lakehouse and info.schema is not None:
        add(
            "W002",
            "warning",
            f"schema {info.schema!r} set for a Lakehouse entity — schema-less lakehouses reject it",
        )

    return out


def lint(registry: Registry = REGISTRY, *, strict: bool = False) -> list[Finding]:
    """All findings, sorted by entity key. source=True entities never error:
    their E-level findings are demoted to warnings and strict does not re-promote."""
    findings: list[Finding] = []
    for info in registry.entities():
        for f in _entity_findings(info):
            if info.source:
                level = "warning"
            elif strict:
                level = "error"
            else:
                level = f.level
            findings.append(
                Finding(f.path, f.line, f.code, level, f.message, f.suggestion)
                if level != f.level
                else f
            )
    return findings
