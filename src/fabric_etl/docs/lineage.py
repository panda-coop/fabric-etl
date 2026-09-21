"""Lineage emitter: one page per mapping plus a mermaid overview index.

Deterministic — mappings sorted by class name. Pages link back into the
entity pages emitted by docs.markdown, carrying their anchor ids.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fabric_etl.docs.markdown import label, page_link
from fabric_etl.entities import REGISTRY, Registry
from fabric_etl.transform import MAPPINGS, MappedColumn, Mapping

if TYPE_CHECKING:
    from fabric_etl.entities import EntityInfo


def _entity_link(from_page: str, info: EntityInfo) -> str:
    return f"[{label(info)}]({page_link(from_page, info)})"


def _from_cell(mc: MappedColumn) -> str:
    return f"param: {mc.origin}" if mc.kind == "param" else mc.origin


def _transform_cell(mc: MappedColumn) -> str:
    if mc.fn is None:
        return "-"
    name = getattr(mc.fn, "__name__", "")
    return "fn" if not name or name == "<lambda>" else name


def _mapping_page(mapping: type[Mapping]) -> str:
    path = f"lineage/{mapping.__name__}.md"
    lines = [
        f"# {mapping.__name__}",
        "",
        f"{_entity_link(path, mapping.source)} → {_entity_link(path, mapping.target)}",
        "",
    ]
    if mapping.job:
        lines += [f"job: `{mapping.job}`", ""]
    lines += ["| target field | from | transform |", "|---|---|---|"]
    lines += [f"| {mc.target} | {_from_cell(mc)} | {_transform_cell(mc)} |" for mc in mapping._plan]
    lines.append("")
    return "\n".join(lines)


def _node_id(prefix: str, text: str) -> str:
    return prefix + re.sub(r"\W+", "_", text)


def _index(mappings: list[type[Mapping]]) -> str:
    path = "lineage/index.md"
    lines = ["# Lineage", "", "| mapping | source | target | job |", "|---|---|---|---|"]
    for m in mappings:
        job = f"`{m.job}`" if m.job else ""
        lines.append(
            f"| [{m.__name__}]({m.__name__}.md) | {_entity_link(path, m.source)}"
            f" | {_entity_link(path, m.target)} | {job} |"
        )
    lines += ["", "```mermaid", "graph LR"]
    for m in mappings:
        src, tgt = label(m.source), label(m.target)
        node = _node_id("m_", m.__name__)
        lines.append(f'    {_node_id("t_", src)}["{src}"] --> {node}["{m.__name__}"]')
        lines.append(f'    {node} --> {_node_id("t_", tgt)}["{tgt}"]')
    lines += ["```", ""]
    return "\n".join(lines)


def emit(mappings=None, registry: Registry = REGISTRY) -> dict[str, str]:
    """Relative path -> markdown content: lineage/<Mapping>.md pages + lineage/index.md."""
    ordered = sorted(MAPPINGS if mappings is None else mappings, key=lambda m: m.__name__)
    pages = {f"lineage/{m.__name__}.md": _mapping_page(m) for m in ordered}
    pages["lineage/index.md"] = _index(ordered)
    return pages
