"""Tests for extract.csv: physical-name headers, blank handling, binary and text."""

import io
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.extract import csv

DATA = """\
Item No_;Quantity;Price;Note
A-100;5;9.99;Größe M8
B-200;;0.10;
"""


@entity(source=True)
class StockRow(BaseModel):
    item_no: Annotated[str, Col(length=20, name="Item No_")]
    quantity: Annotated[int | None, Col(name="Quantity")] = None
    price: Annotated[Decimal, Col(name="Price")]
    note: Annotated[str | None, Col(length=50, name="Note")] = None


def test_csv_binary_file_object():
    out = list(csv(StockRow, io.BytesIO(DATA.encode("utf-8")), sep=";"))

    assert [type(r) for r in out] == [StockRow, StockRow]
    assert out[0].item_no == "A-100"
    assert out[0].quantity == 5
    assert out[0].price == Decimal("9.99")
    assert out[0].note == "Größe M8"


def test_csv_text_file_object():
    out = list(csv(StockRow, io.StringIO(DATA), sep=";"))
    assert [r.item_no for r in out] == ["A-100", "B-200"]


def test_csv_blank_optional_int_becomes_none():
    out = list(csv(StockRow, io.StringIO(DATA), sep=";"))
    assert out[1].quantity is None
    assert out[1].price == Decimal("0.10")
    assert out[1].note == ""  # optional str keeps the empty string


def test_csv_encoding():
    raw = DATA.encode("cp1252")
    out = list(csv(StockRow, io.BytesIO(raw), sep=";", encoding="cp1252"))
    assert out[0].note == "Größe M8"


def test_csv_default_comma_sep():
    data = "Item No_,Quantity,Price,Note\nC-300,1,2.50,x\n"
    out = list(csv(StockRow, io.StringIO(data)))
    assert out[0].item_no == "C-300"
    assert out[0].price == Decimal("2.50")
