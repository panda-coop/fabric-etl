"""Streaming XML extractor: lxml iterparse, constant memory on feeds of any size."""

from __future__ import annotations

from collections.abc import Iterator
from typing import IO, Any

try:
    from lxml import etree
except ImportError as exc:
    raise ImportError("extract.xml requires lxml; install fabric-etl[xml]") from exc

from fabric_etl.entities.columns import ColumnInfo


def _record_tag(info: Any) -> str:
    """Record tag from info.items: accepts "//Tag", "Tag" or "/Order/Line" —
    iterparse matches the last segment's localname, namespace-agnostic."""
    if not info.items:
        raise ValueError(f"entity {info.key} has no items= record path")
    tag = info.items.rsplit("/", 1)[-1]
    if not tag or "[" in tag or "@" in tag:
        raise ValueError(f"items must end in a plain element tag: {info.items!r}")
    return tag


def _value(node: Any, column: ColumnInfo) -> Any:
    if column.col.path:
        found = node.xpath(column.col.path)
        if not found:
            return None
        first = found[0]
        return first if isinstance(first, str) else first.text
    child = node.find(column.physical)
    return None if child is None else child.text


def xml(entity_cls: type, source: IO[bytes] | str, **params: Any) -> Iterator[Any]:
    """Yield validated models per record element; fields resolve via Col.path as a
    relative XPath, falling back to a child element named by the physical name."""
    info = entity_cls.__entity__
    tag = _record_tag(info)
    for _, elem in etree.iterparse(source, events=("end",), tag=f"{{*}}{tag}"):
        yield info.cls.model_validate({c.attr: _value(elem, c) for c in info.columns})
        # Free what we've consumed: this element's content + already-yielded
        # preceding siblings kept alive by the parent.
        elem.clear()
        parent = elem.getparent()
        if parent is not None:
            while elem.getprevious() is not None:
                del parent[0]
