"""Markdown emitter: one page per entity plus index.md.

Deterministic — entities sorted by (schema, table), no timestamps. Pages carry
mkdocs attr_list anchors `fabric-etl:<schema>.<table>` (H1) and per-column
`<a id="...">` spans so lineage pages can deep-link into the column table.
"""

from __future__ import annotations

import posixpath
from string import Formatter
from typing import TYPE_CHECKING

from fabric_etl.entities import REGISTRY, Registry
from fabric_etl.entities.drivers import Driver, Lakehouse

if TYPE_CHECKING:
    from fabric_etl.entities import ColumnInfo, EntityInfo


def placeholder_params(*templates: str | None) -> dict[str, str]:
    """Map each {placeholder} in the templates to itself, so str.format keeps it."""
    names = {field for t in templates if t for _, field, _, _ in Formatter().parse(t) if field}
    return {name: "{" + name + "}" for name in names}


def entity_params(info: EntityInfo) -> dict[str, str]:
    return placeholder_params(info.database, info.schema, info.table, info.endpoint)


def full_name(info: EntityInfo) -> str:
    """Full physical name with {placeholder} segments kept literally."""
    if info.driver is None:
        return f"{info.schema}.{info.table}" if info.schema else info.table
    try:
        return info.driver.full_name(info, **entity_params(info))
    except ValueError:
        return f"{info.schema}.{info.table}" if info.schema else info.table


def anchor(info: EntityInfo) -> str:
    return f"fabric-etl:{info.schema or '_noschema'}.{info.table}"


def page_path(info: EntityInfo) -> str:
    return f"{info.schema or '_noschema'}/{info.table}.md"


def page_link(from_page: str, info: EntityInfo) -> str:
    rel = posixpath.relpath(page_path(info), posixpath.dirname(from_page) or ".")
    return f"{rel}#{anchor(info)}"


def label(info: EntityInfo) -> str:
    return f"{info.schema}.{info.table}" if info.schema else info.table


def sorted_entities(registry: Registry) -> list[EntityInfo]:
    return sorted(registry.entities(), key=lambda i: (i.schema or "", i.table))


def sorted_mappings(mappings) -> list:
    return sorted(mappings or [], key=lambda m: m.__name__)


def _type_cell(info: EntityInfo, c: ColumnInfo) -> str:
    if info.driver is None:
        return "-"
    try:
        rendered = info.driver.render(c.py_type, c.col)
    except ValueError:
        return "-"
    if issubclass(info.driver, Lakehouse) and c.py_type is str and c.col.length is not None:
        return f"{rendered} (length ignored)"
    return rendered


def _description_cell(c: ColumnInfo) -> str:
    parts = (["PK"] if c.col.pk else []) + ([c.description] if c.description else [])
    return " ".join(parts)


def _ddl(info: EntityInfo) -> str | None:
    if info.driver is None:
        return None
    try:
        return info.driver.ddl(info, **entity_params(info))
    except ValueError:
        return None


def _mapping_line(mapping, other: EntityInfo, arrow: str, from_page: str) -> str:
    job = f" (job: `{mapping.job}`)" if mapping.job else ""
    return f"- {mapping.__name__}{job} {arrow} [{label(other)}]({page_link(from_page, other)})"


def _entity_page(info: EntityInfo, mappings: list) -> str:
    driver_name = info.driver.name if info.driver is not None else "-"
    path = page_path(info)
    lines = [f"# {info.table}  `{full_name(info)}` · {driver_name} {{ #{anchor(info)} }}", ""]
    if info.description:
        lines += [info.description, ""]

    lines += [
        f"| field | python | {driver_name} | null | description |",
        "|---|---|---|---|---|",
    ]
    for c in info.columns:
        field = f'<a id="{anchor(info)}.{c.attr}"></a>{c.attr}'
        null = "yes" if Driver.nullable(c) else "no"
        lines.append(
            f"| {field} | {c.py_type.__name__} | {_type_cell(info, c)}"
            f" | {null} | {_description_cell(c)} |"
        )
    lines.append("")

    if info.source:
        lines += [f"source; physical name with placeholders: `{full_name(info)}`", ""]
    elif (ddl := _ddl(info)) is not None:
        lines += ["## DDL", "", "```sql", ddl, "```", ""]

    fed_by = [m for m in mappings if m.target.key == info.key]
    feeds = [m for m in mappings if m.source.key == info.key]
    if fed_by:
        lines += ["## Fed by", ""]
        lines += [_mapping_line(m, m.source, "←", path) for m in fed_by]
        lines.append("")
    if feeds:
        lines += ["## Feeds", ""]
        lines += [_mapping_line(m, m.target, "→", path) for m in feeds]
        lines.append("")

    return "\n".join(lines)


def _index(entities: list[EntityInfo]) -> str:
    lines = [
        "# Entities",
        "",
        "| entity | physical name | driver | source |",
        "|---|---|---|---|",
    ]
    for info in entities:
        driver_name = info.driver.name if info.driver is not None else "-"
        source = "yes" if info.source else "no"
        lines.append(
            f"| [{info.table}]({page_link('index.md', info)}) | `{full_name(info)}`"
            f" | {driver_name} | {source} |"
        )
    lines.append("")
    return "\n".join(lines)


def emit(registry: Registry = REGISTRY, mappings=None) -> dict[str, str]:
    """Relative path -> markdown content: one page per entity plus index.md."""
    ordered = sorted_entities(registry)
    by_name = sorted_mappings(mappings)
    pages = {page_path(info): _entity_page(info, by_name) for info in ordered}
    pages["index.md"] = _index(ordered)
    return pages
