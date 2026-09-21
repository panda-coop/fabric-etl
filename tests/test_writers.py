"""Tests for load.writers — fake DB-API connection and fake Spark DataFrame."""

from typing import Annotated

import pytest
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Warehouse
from fabric_etl.load.writers import lakehouse, warehouse


@entity(schema="dbo", table="thing", driver=Warehouse)
class Thing(BaseModel):
    id: Annotated[int, Col(pk=True)]
    name: Annotated[str, Col(length=50)]


@entity(schema="dbo", table="nav_thing", driver=Warehouse)
class NavThing(BaseModel):
    no: Annotated[str, Col(length=20, pk=True, name="No_")]


@entity(schema="dbo", table="keyless", driver=Warehouse)
class Keyless(BaseModel):
    x: Annotated[str, Col(length=10)]


class FakeCursor:
    def __init__(self):
        self.executemany_calls = []
        self.execute_calls = []

    def executemany(self, sql, seq_of_params):
        self.executemany_calls.append((sql, list(seq_of_params)))

    def execute(self, sql, params=()):
        self.execute_calls.append((sql, list(params)))


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1


def test_insert_batching_constant_memory():
    conn = FakeConn()
    rows = ({"id": i, "name": f"n{i}"} for i in range(2500))  # generator, never a list
    assert warehouse(Thing, rows, conn) == 2500
    sizes = [len(params) for _, params in conn.cur.executemany_calls]
    assert sizes == [1000, 1000, 500]
    sql = conn.cur.executemany_calls[0][0]
    assert sql == "INSERT INTO dbo.thing (id, name) VALUES (?, ?)"
    assert conn.commits == 1


def test_insert_model_instances():
    conn = FakeConn()
    assert warehouse(Thing, [Thing(id=1, name="a"), Thing(id=2, name="b")], conn) == 2
    assert conn.cur.executemany_calls[0][1] == [(1, "a"), (2, "b")]


def test_insert_uses_physical_names():
    conn = FakeConn()
    warehouse(NavThing, [{"no": "X1"}], conn)
    sql, params = conn.cur.executemany_calls[0]
    assert sql == "INSERT INTO dbo.nav_thing (No_) VALUES (?)"
    assert params == [("X1",)]


def test_insert_empty():
    conn = FakeConn()
    assert warehouse(Thing, [], conn) == 0
    assert conn.cur.executemany_calls == []


def test_merge_golden():
    conn = FakeConn()
    rows = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    assert warehouse(Thing, rows, conn, merge=True) == 2
    sql, params = conn.cur.execute_calls[0]
    assert sql == (
        "MERGE dbo.thing AS t USING (VALUES (?, ?), (?, ?)) AS s (id, name)"
        " ON t.id = s.id"
        " WHEN MATCHED THEN UPDATE SET t.name = s.name"
        " WHEN NOT MATCHED THEN INSERT (id, name) VALUES (s.id, s.name);"
    )
    assert params == [1, "a", 2, "b"]
    assert conn.commits == 1


def test_merge_pk_only_skips_update():
    conn = FakeConn()
    warehouse(NavThing, [{"no": "X1"}], conn, merge=True)
    sql, _ = conn.cur.execute_calls[0]
    assert "WHEN MATCHED" not in sql
    assert "WHEN NOT MATCHED THEN INSERT (No_) VALUES (s.No_);" in sql


def test_merge_requires_pk():
    with pytest.raises(ValueError, match="merge requires a primary key"):
        warehouse(Keyless, [{"x": "a"}], FakeConn(), merge=True)


class FakeWriter:
    def __init__(self):
        self.calls = []

    def format(self, fmt):
        self.calls.append(("format", fmt))
        return self

    def mode(self, mode):
        self.calls.append(("mode", mode))
        return self

    def saveAsTable(self, name):
        self.calls.append(("saveAsTable", name))


class FakeDF:
    def __init__(self):
        self.write = FakeWriter()


def test_lakehouse_append_default():
    df = FakeDF()
    lakehouse(Thing, df)
    assert df.write.calls == [("format", "delta"), ("mode", "append"), ("saveAsTable", "dbo.thing")]


def test_lakehouse_mode_override():
    df = FakeDF()
    lakehouse(Thing, df, mode="overwrite")
    assert ("mode", "overwrite") in df.write.calls
