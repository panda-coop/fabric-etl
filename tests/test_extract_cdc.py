"""Tests for extract.cdc against fake DB-API 2 connections."""

from decimal import Decimal
from typing import Annotated

import pytest
from pydantic import BaseModel, ValidationError

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer
from fabric_etl.extract.cdc import Cdc, CdcOperation


@entity(
    schema="dbo",
    database="NAV",
    table="Cooperative Panda-{company}$Sales Line",
    driver=SqlServer,
    source=True,
)
class ErpSalesLine(BaseModel):
    document_no: Annotated[str, Col(length=20, pk=True, name="Document No_")]
    line_no: Annotated[int, Col(pk=True, name="Line No_")]
    amount: Annotated[Decimal, Col(precision=18, scale=2, name="Amount")]


def test_envelope_validates_and_types():
    env = Cdc[ErpSalesLine](
        operation=CdcOperation.INSERT,
        start_lsn=b"\x00" * 10,
        seqval=b"\x01" * 10,
        row={"document_no": "SO-001", "line_no": 10000, "amount": "12.50"},
    )
    assert env.operation is CdcOperation.INSERT
    assert env.start_lsn == b"\x00" * 10
    assert env.seqval == b"\x01" * 10
    assert type(env.row) is ErpSalesLine
    assert env.row.amount == Decimal("12.50")


def test_operation_coerces_from_int():
    env = Cdc[ErpSalesLine](
        operation=3,
        start_lsn=b"\x00",
        seqval=b"\x00",
        row=ErpSalesLine(document_no="SO-001", line_no=10000, amount=0),
    )
    assert env.operation is CdcOperation.UPDATE_BEFORE
    with pytest.raises(ValidationError):
        Cdc[ErpSalesLine](
            operation=5,
            start_lsn=b"\x00",
            seqval=b"\x00",
            row=env.row,
        )


def test_operation_values():
    assert [op.value for op in CdcOperation] == [1, 2, 3, 4]
    assert CdcOperation.DELETE == 1
    assert CdcOperation.UPDATE_AFTER == 4


def test_lazy_export():
    from fabric_etl import extract

    assert extract.Cdc is Cdc
    assert extract.CdcOperation is CdcOperation
