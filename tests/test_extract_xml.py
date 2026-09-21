"""Tests for extract.xml: streaming, XPath columns, lazy lxml dependency."""

import importlib
import io
import sys
from decimal import Decimal
from typing import Annotated

import pytest
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.extract import xml

DOC = b"""\
<Catalog>
  <Product id="1">
    <Name>Bolt M8</Name>
    <Stock><Quantity>4.5</Quantity></Stock>
    <Price>9.99</Price>
  </Product>
  <Product id="2">
    <Name>Nut M8</Name>
    <Stock><Quantity>0</Quantity></Stock>
  </Product>
</Catalog>
"""


@entity(source=True, items="//Product")
class Product(BaseModel):
    id: Annotated[int, Col(path="@id")]
    name: Annotated[str, Col(path="Name/text()")]
    quantity: Annotated[Decimal, Col(path="Stock/Quantity/text()")]
    price: Annotated[Decimal | None, Col(name="Price")] = None  # no path: child by physical name


def test_xml_typed_records():
    out = list(xml(Product, io.BytesIO(DOC)))

    assert [type(r) for r in out] == [Product, Product]
    assert out[0].id == 1
    assert out[0].name == "Bolt M8"
    assert out[0].quantity == Decimal("4.5")
    assert out[0].price == Decimal("9.99")
    assert out[1].price is None  # missing child element -> None


def test_items_accepts_absolute_path_and_bare_tag():
    @entity(source=True, items="/Catalog/Product")
    class ByPath(BaseModel):
        id: Annotated[int, Col(path="@id")]

    @entity(source=True, items="Product")
    class ByTag(BaseModel):
        id: Annotated[int, Col(path="@id")]

    assert [r.id for r in xml(ByPath, io.BytesIO(DOC))] == [1, 2]
    assert [r.id for r in xml(ByTag, io.BytesIO(DOC))] == [1, 2]


def test_items_missing_or_not_a_tag():
    @entity(source=True)
    class NoItems(BaseModel):
        id: int

    @entity(source=True, items="//Product/@id")
    class BadItems(BaseModel):
        id: int

    with pytest.raises(ValueError, match="no items="):
        next(xml(NoItems, io.BytesIO(DOC)))
    with pytest.raises(ValueError, match="plain element tag"):
        next(xml(BadItems, io.BytesIO(DOC)))


class CountingReader:
    """File-like recording how many bytes the parser has pulled."""

    def __init__(self, data: bytes):
        self._fh = io.BytesIO(data)
        self.read_bytes = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._fh.read(size)
        self.read_bytes += len(chunk)
        return chunk


def test_xml_streams_incrementally():
    record = (
        b'<Product id="%d"><Name>Item %d</Name><Stock><Quantity>1.0</Quantity></Stock></Product>'
    )
    body = b"".join(record % (i, i) for i in range(20000))
    doc = b"<Catalog>" + body + b"</Catalog>"
    reader = CountingReader(doc)

    it = xml(Product, reader)
    first = next(it)

    assert first.id == 0
    assert reader.read_bytes < len(doc) / 8  # first record before the doc is read
    assert sum(1 for _ in it) == 19999


def test_extract_package_imports_without_lxml(monkeypatch):
    for mod in ("fabric_etl.extract", "fabric_etl.extract.xml"):
        monkeypatch.delitem(sys.modules, mod, raising=False)
    monkeypatch.setitem(sys.modules, "lxml", None)  # blocks any lxml import
    monkeypatch.setitem(sys.modules, "lxml.etree", None)

    pkg = importlib.import_module("fabric_etl.extract")  # must not pull lxml
    with pytest.raises(ImportError, match=r"fabric-etl\[xml\]"):
        getattr(pkg, "xml")  # noqa: B009 — attribute access is the behavior under test
