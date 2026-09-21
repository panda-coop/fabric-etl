"""DBML emitter: Table, Note, Ref and TableGroup blocks for the whole registry.

Deterministic — entities sorted by (schema, table), columns in declaration
order, groups sorted by name. Source entities keep their Table block but are
marked `Note: 'source'` instead of DDL-worthy metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabric_etl.docs.markdown import sorted_entities
from fabric_etl.entities import REGISTRY, Registry
from fabric_etl.entities.drivers import Driver

if TYPE_CHECKING:
    from fabric_etl.entities import ColumnInfo, EntityInfo


def _q(name: str) -> str:
    return f'"{name}"'


def _table_name(info: EntityInfo) -> str:
    parts = [info.schema, info.table]
    return ".".join(_q(p) for p in parts if p is not None)


def _note_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def _col_type(info: EntityInfo, c: ColumnInfo) -> str:
    if info.driver is not None:
        try:
            rendered = info.driver.render(c.py_type, c.col)
        except ValueError:
            rendered = c.py_type.__name__
    else:
        rendered = c.py_type.__name__
    return _q(rendered) if " " in rendered else rendered


def _column_line(info: EntityInfo, c: ColumnInfo) -> str:
    settings = []
    if c.col.pk:
        settings.append("pk")
    if not Driver.nullable(c):
        settings.append("not null")
    if c.description:
        settings.append(f"note: '{_note_text(c.description)}'")
    suffix = f" [{', '.join(settings)}]" if settings else ""
    return f"  {_q(c.physical)} {_col_type(info, c)}{suffix}"


def _table_block(info: EntityInfo) -> str:
    lines = [f"Table {_table_name(info)} {{"]
    lines += [_column_line(info, c) for c in info.columns]
    note = "source" if info.source else info.description
    if note:
        lines += ["", f"  Note: '{_note_text(note)}'"]
    lines.append("}")
    return "\n".join(lines)


def _qualify(dotted: str) -> str:
    return ".".join(_q(p) for p in dotted.split("."))


def _ref_lines(info: EntityInfo) -> list[str]:
    lines = []
    for c in info.columns:
        if c.col.fk:  # "schema.table.column"
            table, _, ref_col = c.col.fk.rpartition(".")
            lines.append(
                f"Ref: {_table_name(info)}.{_q(c.physical)} > {_qualify(table)}.{_q(ref_col)}"
            )
    by_attr = {c.attr: c for c in info.columns}
    for attrs, ref in info.fks.items():  # {("a", "b"): "s.t.(x,y)"}
        table, _, cols_part = ref.partition(".(")
        ref_cols = [r.strip() for r in cols_part.rstrip(")").split(",")]
        local = ", ".join(_q(by_attr[a].physical) for a in attrs)
        remote = ", ".join(_q(r) for r in ref_cols)
        lines.append(f"Ref: {_table_name(info)}.({local}) > {_qualify(table)}.({remote})")
    return lines


def _group_blocks(entities: list[EntityInfo]) -> list[str]:
    groups: dict[str, list[EntityInfo]] = {}
    for info in entities:
        groups.setdefault(info.cls.__module__.rsplit(".", 1)[-1], []).append(info)
    blocks = []
    for name in sorted(groups):
        members = "\n".join(f"  {_table_name(i)}" for i in groups[name])
        blocks.append(f"TableGroup {name} {{\n{members}\n}}")
    return blocks


def emit(registry: Registry = REGISTRY) -> str:
    """One DBML document: Table blocks, Ref lines, TableGroup per module."""
    entities = sorted_entities(registry)
    blocks = [_table_block(info) for info in entities]
    refs = [line for info in entities for line in _ref_lines(info)]
    if refs:
        blocks.append("\n".join(refs))
    blocks.extend(_group_blocks(entities))
    return "\n\n".join(blocks) + "\n"
