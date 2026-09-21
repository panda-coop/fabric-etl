"""Tests for entities.columns."""

import typing
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from fabric_etl.entities.columns import Col, columns


class SalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True, name="Document No_")]
    line_no: Annotated[int, Col(pk=True)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)] = Field(description="Line amount")
    note: str | None = None
    legacy: typing.Optional[int] = None  # noqa: UP045  # exercise the typing.Union branch


def test_extraction():
    cols = {c.attr: c for c in columns(SalesLine)}
    assert cols["tenant"].col == Col(length=4, pk=True)
    assert cols["tenant"].py_type is str
    assert not cols["tenant"].optional
    assert cols["amount"].col.precision == 18
    assert cols["amount"].col.scale == 2


def test_default_col_when_absent():
    cols = {c.attr: c for c in columns(SalesLine)}
    assert cols["note"].col == Col()


def test_optional_unwrapping():
    cols = {c.attr: c for c in columns(SalesLine)}
    assert cols["note"].py_type is str
    assert cols["note"].optional
    assert cols["legacy"].py_type is int
    assert cols["legacy"].optional
    assert not cols["line_no"].optional


def test_physical_name_override():
    cols = {c.attr: c for c in columns(SalesLine)}
    assert cols["document_no"].physical == "Document No_"
    assert cols["tenant"].physical == "tenant"


def test_description_from_field():
    cols = {c.attr: c for c in columns(SalesLine)}
    assert cols["amount"].description == "Line amount"
    assert cols["tenant"].description is None


def test_declaration_order():
    attrs = [c.attr for c in columns(SalesLine)]
    assert attrs == ["tenant", "document_no", "line_no", "amount", "note", "legacy"]
