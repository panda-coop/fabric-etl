"""Static entity extraction via griffe: parse, never import user code.

Only literal values are visible; anything else (f-strings, name references,
calls, arithmetic) is reported as E002 and skipped, the rest is extracted.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

try:
    import griffe
except ImportError as exc:  # pragma: no cover
    raise ImportError("fabric_etl.static requires griffe; install fabric-etl[docs]") from exc

from fabric_etl.entities import drivers as _drivers
from fabric_etl.entities.columns import Col, ColumnInfo
from fabric_etl.entities.entity import EntityInfo, Registry, _snake_case
from fabric_etl.entities.lint import Finding, lint

_TYPES: dict[str, type] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "bytes": bytes,
    "Decimal": Decimal,
    "datetime": datetime,
    "date": date,
    "UUID": UUID,
}
_DRIVER_NAMES = ("SqlServer", "Warehouse", "Lakehouse", "Http")
_DRIVERS = {name: getattr(_drivers, name) for name in _DRIVER_NAMES}
_COL_FIELDS = {f.name for f in dataclasses.fields(Col)}

_FUTURE = "from __future__ import annotations\n"
_BOUNDARY = re.compile(r"^# [A-Z]+ \*{4,}\s*$")
_CELL = re.compile(r"^# CELL \*{4,}\s*$")
_MARKER = "# datadict: schema"


class _NonLiteral(Exception):
    pass


def _e002(path: str | Path, line: int, detail: str) -> Finding:
    return Finding(str(path), line, "E002", "error", f"non-literal value in declaration: {detail}")


def _literal(expr: str | griffe.Expr | None) -> Any:
    """ast.literal_eval over a griffe expression: griffe keeps literal leaves as
    source text and str(Expr) reassembles the source, so one call covers both."""
    if expr is None:
        raise _NonLiteral
    try:
        return ast.literal_eval(expr if isinstance(expr, str) else str(expr))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        raise _NonLiteral from None


def _name_of(expr: Any) -> str | None:
    if isinstance(expr, griffe.ExprName | griffe.ExprAttribute):
        return expr.canonical_name
    return None


def _is_none(expr: Any) -> bool:
    return expr == "None" or (isinstance(expr, griffe.ExprName) and expr.name == "None")


def _is_call(expr: Any, name: str) -> bool:
    return isinstance(expr, griffe.ExprCall) and _name_of(expr.function) == name


def _call_kwargs(
    call: griffe.ExprCall, path: str, line: int, what: str, findings: list[Finding]
) -> dict[str, Any]:
    """Keyword literals of a call; each non-literal value becomes one E002."""
    kwargs: dict[str, Any] = {}
    for arg in call.arguments:
        if not isinstance(arg, griffe.ExprKeyword):
            findings.append(_e002(path, line, f"positional argument to {what}(...)"))
            continue
        try:
            kwargs[arg.name] = _literal(arg.value)
        except _NonLiteral:
            findings.append(_e002(path, line, f"{what}({arg.name}=...)"))
    return kwargs


def _resolve_annotation(expr: Any) -> tuple[type | None, bool, griffe.ExprCall | None]:
    """(py_type, optional, Col call) from an annotation expression; py_type None
    when the annotation does not resolve to a supported scalar type."""
    if isinstance(expr, griffe.ExprSubscript):
        base = _name_of(expr.left)
        if base == "Annotated":
            elements = (
                expr.slice.elements if isinstance(expr.slice, griffe.ExprTuple) else [expr.slice]
            )
            py_type, optional, _ = _resolve_annotation(elements[0])
            col = next((e for e in elements[1:] if _is_call(e, "Col")), None)
            return py_type, optional, col
        if base == "Optional":
            py_type, _, col = _resolve_annotation(expr.slice)
            return py_type, True, col
        return None, False, None
    if isinstance(expr, griffe.ExprBinOp) and expr.operator == "|":
        sides = [expr.left, expr.right]
        others = [s for s in sides if not _is_none(s)]
        if len(others) == 1:
            py_type, _, col = _resolve_annotation(others[0])
            return py_type, True, col
        return None, False, None
    name = _name_of(expr)
    if name in _TYPES:
        return _TYPES[name], False, None
    return None, False, None


def _column(
    member: griffe.Attribute, path: str, offset: int, findings: list[Finding]
) -> ColumnInfo | None:
    line = (member.lineno or 1) - offset
    py_type, optional, col_expr = _resolve_annotation(member.annotation)
    if py_type is None:
        findings.append(_e002(path, line, f"unresolvable annotation for field {member.name!r}"))
        return None
    col = Col()
    if col_expr is not None:
        kwargs = _call_kwargs(col_expr, path, line, "Col", findings)
        col = Col(**{k: v for k, v in kwargs.items() if k in _COL_FIELDS})
    description = None
    if _is_call(member.value, "Field"):
        field_kwargs = _call_kwargs(member.value, path, line, "Field", findings)
        raw = field_kwargs.get("description")
        description = raw if isinstance(raw, str) else None
    return ColumnInfo(
        attr=member.name,
        physical=col.name or member.name,
        py_type=py_type,
        optional=optional,
        col=col,
        description=description,
    )


def _entity_decorator(cls: griffe.Class) -> griffe.Decorator | None:
    for dec in cls.decorators:
        if _is_call(dec.value, "entity"):
            return dec
    return None


def _skip_column(member: griffe.Object | griffe.Alias) -> bool:
    if not isinstance(member, griffe.Attribute) or member.annotation is None:
        return True
    if member.name.startswith("_"):
        return True
    ann = member.annotation
    return isinstance(ann, griffe.ExprSubscript) and _name_of(ann.left) == "ClassVar"


def _extract_class(
    cls: griffe.Class,
    path: Path,
    offset: int,
    registry: Registry,
    findings: list[Finding],
) -> EntityInfo | None:
    dec = _entity_decorator(cls)
    if dec is None:
        return None
    call = dec.value
    dec_line = (dec.lineno or cls.lineno or 1) - offset
    kwargs: dict[str, Any] = {}
    for arg in call.arguments:
        if not isinstance(arg, griffe.ExprKeyword):
            findings.append(_e002(path, dec_line, "positional argument to entity(...)"))
            continue
        if arg.name == "driver":
            driver_name = _name_of(arg.value)
            if driver_name in _DRIVERS:
                kwargs["driver"] = _DRIVERS[driver_name]
            else:
                findings.append(_e002(path, dec_line, f"entity(driver={arg.value})"))
            continue
        try:
            kwargs[arg.name] = _literal(arg.value)
        except _NonLiteral:
            findings.append(_e002(path, dec_line, f"entity({arg.name}=...)"))

    columns = [
        info
        for member in cls.members.values()
        if not _skip_column(member)
        and (info := _column(member, str(path), offset, findings)) is not None
    ]
    docstring = cls.docstring.value.strip() if cls.docstring else None
    # Placeholder class: no user code is imported. __module__ carries the file
    # path so entities.lint locates findings at the real file (line stays 1).
    placeholder = type(
        cls.name, (), {"__module__": str(path), "__qualname__": cls.name, "__doc__": docstring}
    )
    info = EntityInfo(
        cls=placeholder,
        key=f"{placeholder.__module__}.{cls.name}",
        schema=kwargs.get("schema", registry.default_schema),
        table=kwargs.get("table") or _snake_case(cls.name),
        database=kwargs.get("database"),
        driver=kwargs.get("driver") or registry.default_driver,
        source=bool(kwargs.get("source", False)),
        description=kwargs.get("description") or docstring,
        fks=dict(kwargs.get("fks") or {}),
        indexes=list(kwargs.get("indexes") or []),
        endpoint=kwargs.get("endpoint"),
        items=kwargs.get("items"),
        columns=columns,
    )
    registry.register(info)
    return info


def _schema_cells(source: str) -> str:
    """Keep only `# datadict: schema` cells of a Fabric notebook-content.py.

    Dropped lines become blank lines so reported line numbers stay exact."""
    out: list[str] = []
    keep = False
    pending = False  # inside a CELL, before its first non-blank line
    for line in source.splitlines():
        if _BOUNDARY.match(line):
            keep = False
            pending = bool(_CELL.match(line))
            out.append("")
            continue
        if pending and line.strip():
            pending = False
            keep = line.rstrip() == _MARKER
        out.append(line if keep else "")
    return "\n".join(out) + "\n"


def _visit(path: Path) -> tuple[griffe.Module, int]:
    source = path.read_text(encoding="utf-8")
    if path.name == "notebook-content.py":
        source = _schema_cells(source)
    # Without `from __future__ import annotations` griffe re-parses string
    # literals inside annotations as forward references, turning e.g.
    # Col(fk="dbo.customer.no") into a name expression. Injecting the import
    # (and offsetting line numbers by 1) keeps annotation strings literal.
    offset = 0
    if "__future__" not in source:
        source = _FUTURE + source
        offset = 1
    module_name = re.sub(r"\W", "_", path.stem)
    return griffe.visit(module_name, filepath=path, code=source), offset


def _files(paths: Any) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        p = Path(p)
        out.extend(sorted(p.rglob("*.py")) if p.is_dir() else [p])
    return out


def extract_registry(paths: Any) -> Registry:
    """Fresh Registry built from .py files without importing them. Collected
    E002 findings are attached as `registry.findings`."""
    registry = Registry()
    findings: list[Finding] = []
    for path in _files(paths):
        module, offset = _visit(path)
        for member in module.members.values():
            if isinstance(member, griffe.Class):
                _extract_class(member, path, offset, registry, findings)
    registry.findings = findings
    return registry


def lint_static(paths: Any, strict: bool = False) -> list[Finding]:
    """E002 findings from extraction plus entities.lint over the built registry."""
    registry = extract_registry(paths)
    findings = registry.findings + lint(registry, strict=strict)
    return sorted(findings, key=lambda f: (f.path, f.line))
