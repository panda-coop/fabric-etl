"""Tests for extract.cdc against fake DB-API 2 connections."""

from decimal import Decimal
from typing import Annotated

import pytest
from pydantic import BaseModel, ValidationError

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer
from fabric_etl.extract.cdc import Cdc, CdcOperation, capture_instance, changes, max_lsn


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


class FakeCursor:
    """Records executed (sql, params); serves one scripted result set per execute."""

    arraysize = 2

    def __init__(self, results):
        self._results = list(results)
        self._current: list = []
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, statement, params=()):
        self.executed.append((statement, tuple(params)))
        self._current = list(self._results.pop(0)) if self._results else []

    def fetchone(self):
        return self._current.pop(0) if self._current else None

    def fetchmany(self, size):
        batch, self._current = self._current[:size], self._current[size:]
        return batch


class FakeConnection:
    def __init__(self, *results):
        self.last_cursor = FakeCursor(results)
        self.commits = 0

    def cursor(self):
        return self.last_cursor

    def commit(self):
        self.commits += 1


INSTANCE = "dbo_Cooperative_Panda_HO_Sales_Line"
CHANGES_SQL = (
    "SELECT __$operation, __$start_lsn, __$seqval, [Document No_], [Line No_], [Amount]"
    f" FROM cdc.fn_cdc_get_all_changes_{INSTANCE}(?, ?, N'all update old')"
    " ORDER BY __$start_lsn, __$seqval"
)
LSN = [bytes([0] * 9 + [n]) for n in range(10)]
CHANGE_ROWS = [
    (2, LSN[1], LSN[0], "SO-001", 10000, Decimal("12.50")),
    (3, LSN[2], LSN[0], "SO-001", 10000, Decimal("12.50")),
    (4, LSN[2], LSN[1], "SO-001", 10000, Decimal("99.99")),
    (1, LSN[3], LSN[0], "SO-001", 10000, Decimal("99.99")),
]


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


def test_capture_instance_sanitizes_resolved_name():
    assert capture_instance(ErpSalesLine, company="HO") == INSTANCE


def test_max_lsn():
    conn = FakeConnection([(LSN[9],)])
    assert max_lsn(conn) == LSN[9]
    assert conn.last_cursor.executed == [("SELECT sys.fn_cdc_get_max_lsn()", ())]


def test_changes_golden_query_and_typed_envelopes():
    conn = FakeConnection(CHANGE_ROWS)
    out = list(changes(ErpSalesLine, conn, LSN[0], LSN[9], company="HO"))

    assert conn.last_cursor.executed == [(CHANGES_SQL, (LSN[0], LSN[9]))]
    assert [e.operation for e in out] == [
        CdcOperation.INSERT,
        CdcOperation.UPDATE_BEFORE,
        CdcOperation.UPDATE_AFTER,
        CdcOperation.DELETE,
    ]
    assert all(type(e) is Cdc[ErpSalesLine] for e in out)
    assert all(type(e.row) is ErpSalesLine for e in out)
    assert out[0].start_lsn == LSN[1]
    assert out[2].seqval == LSN[1]
    assert out[1].row.amount == Decimal("12.50")
    assert out[2].row.amount == Decimal("99.99")


def test_changes_instance_override():
    conn = FakeConnection([])
    list(changes(ErpSalesLine, conn, LSN[0], LSN[9], instance="custom_instance"))
    (statement, params) = conn.last_cursor.executed[0]
    assert "cdc.fn_cdc_get_all_changes_custom_instance(?, ?, N'all update old')" in statement
    assert params == (LSN[0], LSN[9])


def test_changes_from_lsn_none_uses_min_lsn():
    conn = FakeConnection([(LSN[1],)], CHANGE_ROWS[:1])
    out = list(changes(ErpSalesLine, conn, None, LSN[9], company="HO"))

    assert conn.last_cursor.executed == [
        ("SELECT sys.fn_cdc_get_min_lsn(?)", (INSTANCE,)),
        (CHANGES_SQL, (LSN[1], LSN[9])),
    ]
    assert len(out) == 1
    assert out[0].operation is CdcOperation.INSERT


def test_changes_streams_lazily():
    conn = FakeConnection(CHANGE_ROWS)
    it = changes(ErpSalesLine, conn, LSN[0], LSN[9], company="HO")
    assert conn.last_cursor.executed == []  # nothing until iterated
    next(it)
    assert len(conn.last_cursor.executed) == 1
