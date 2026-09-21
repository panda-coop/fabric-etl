"""Tests for extract.sql against a fake DB-API 2 connection."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer
from fabric_etl.extract.sql import select_sql, sql


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
    posting_date: Annotated[datetime, Col(name="Posting Date")]
    dimension_1: Annotated[str | None, Col(length=20, name="Shortcut Dimension 1 Code")] = None
    sync_state: int = 0  # physical == attr: no alias


ROWS = [
    ("SO-001", 10000, Decimal("12.50"), datetime(2026, 1, 5, 8, 30), "ADM", 0),
    ("SO-001", 20000, Decimal("0.00"), datetime(2026, 1, 5, 8, 31), None, 1),
    ("SO-002", 10000, Decimal("99.99"), datetime(2026, 2, 1, 12, 0), "OPS", 0),
]


class FakeCursor:
    arraysize = 2

    def __init__(self, rows):
        self._rows = list(rows)
        self.executed: list[str] = []
        self.fetch_sizes: list[int] = []

    def execute(self, statement):
        self.executed.append(statement)

    @property
    def description(self):
        names = ["document_no", "line_no", "amount", "posting_date", "dimension_1", "sync_state"]
        return [(n, None, None, None, None, None, None) for n in names]

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        batch, self._rows = self._rows[:size], self._rows[size:]
        return batch


class FakeConnection:
    def __init__(self, rows):
        self.last_cursor = FakeCursor(rows)

    def cursor(self):
        return self.last_cursor


def test_select_sql_golden():
    assert select_sql(ErpSalesLine, company="HO") == (
        "SELECT [Document No_] AS document_no, [Line No_] AS line_no, [Amount] AS amount,"
        " [Posting Date] AS posting_date, [Shortcut Dimension 1 Code] AS dimension_1,"
        " [sync_state]"
        " FROM [NAV].[dbo].[Cooperative Panda-HO$Sales Line]"
    )


def test_sql_yields_typed_rows():
    conn = FakeConnection(ROWS)
    out = list(sql(ErpSalesLine, conn, company="HO"))

    assert conn.last_cursor.executed == [select_sql(ErpSalesLine, company="HO")]
    assert [type(r) for r in out] == [ErpSalesLine] * 3
    assert out[0].amount == Decimal("12.50")
    assert out[0].posting_date == datetime(2026, 1, 5, 8, 30)
    assert out[1].dimension_1 is None
    assert out[2].document_no == "SO-002"


def test_sql_fetches_in_arraysize_batches():
    conn = FakeConnection(ROWS)
    it = sql(ErpSalesLine, conn, company="HO")

    assert conn.last_cursor.fetch_sizes == []  # lazy: nothing until iterated
    next(it)
    assert conn.last_cursor.fetch_sizes == [2]
    assert len(list(it)) == 2
    assert conn.last_cursor.fetch_sizes == [2, 2, 2]  # last call returns empty, stops
