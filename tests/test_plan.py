"""Tests for load.plan — drift against a fake INFORMATION_SCHEMA."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, Registry, entity
from fabric_etl.entities.drivers import Warehouse
from fabric_etl.load.plan import PlanAction, plan


@entity(schema="dbo", table="thing", driver=Warehouse)
class Thing(BaseModel):
    id: Annotated[int, Col(pk=True)]
    name: Annotated[str, Col(length=50)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)]
    note: Annotated[str | None, Col(length=100)] = None


# (column_name, is_nullable, data_type, character_maximum_length, numeric_precision, scale)
IN_SYNC = [
    ("id", "NO", "bigint", None, 19, 0),
    ("name", "NO", "varchar", 50, None, None),
    ("amount", "NO", "decimal", None, 18, 2),
    ("note", "YES", "varchar", 100, None, None),
]


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows = []

    def execute(self, sql, params=()):
        self._conn.queries.append((sql, tuple(params)))
        key = tuple(params)
        if "INFORMATION_SCHEMA.TABLES" in sql:
            self._rows = [(key[1],)] if key in self._conn.tables else []
        else:
            self._rows = self._conn.tables.get(key, [])

    def fetchall(self):
        return self._rows


class FakeConn:
    """Serves INFORMATION_SCHEMA result sets keyed by (schema, table)."""

    def __init__(self, tables):
        self.tables = tables
        self.queries = []

    def cursor(self):
        return FakeCursor(self)


def _registry(*classes):
    r = Registry()
    for cls in classes:
        r.register(cls.__entity__)
    return r


def test_missing_table_is_create():
    actions = plan(_registry(Thing), FakeConn({}))
    assert [a.kind for a in actions] == ["create"]
    assert actions[0].entity is Thing.__entity__
    assert actions[0].detail.startswith("CREATE TABLE dbo.thing (")


def test_missing_column_is_add_column():
    rows = [r for r in IN_SYNC if r[0] != "note"]
    actions = plan(_registry(Thing), FakeConn({("dbo", "thing"): rows}))
    assert actions == [
        PlanAction("add_column", Thing.__entity__, "ALTER TABLE dbo.thing ADD note varchar(100)")
    ]


def test_type_mismatch_is_recreate():
    rows = [("name", "NO", "varchar", 20, None, None) if r[0] == "name" else r for r in IN_SYNC]
    actions = plan(_registry(Thing), FakeConn({("dbo", "thing"): rows}))
    assert [a.kind for a in actions] == ["recreate"]
    assert "column name: varchar in database vs varchar(50)" in actions[0].detail


def test_nullability_mismatch_is_recreate():
    rows = [("name", "YES", "varchar", 50, None, None) if r[0] == "name" else r for r in IN_SYNC]
    actions = plan(_registry(Thing), FakeConn({("dbo", "thing"): rows}))
    assert [a.kind for a in actions] == ["recreate"]
    assert "column name: nullability differs" in actions[0].detail


def test_extra_db_column_is_recreate():
    rows = [*IN_SYNC, ("legacy", "YES", "varchar", 10, None, None)]
    actions = plan(_registry(Thing), FakeConn({("dbo", "thing"): rows}))
    assert [a.kind for a in actions] == ["recreate"]
    assert "extra column legacy in database" in actions[0].detail


def test_in_sync_no_actions():
    conn = FakeConn({("dbo", "thing"): IN_SYNC})
    assert plan(_registry(Thing), conn) == []
    # both probes are parameterized on schema + name, never interpolated
    assert all("?" in sql and params == ("dbo", "thing") for sql, params in conn.queries)


def test_source_entity_skipped():
    @entity(schema="dbo", table="src", driver=Warehouse, source=True)
    class Src(BaseModel):
        x: Annotated[str, Col(length=10)]

    conn = FakeConn({})
    assert plan(_registry(Src), conn) == []
    assert conn.queries == []


def test_unresolved_placeholder_skipped():
    @entity(schema="dbo", table="t_{company}", driver=Warehouse)
    class Placeholdered(BaseModel):
        id: Annotated[int, Col(pk=True)]

    conn = FakeConn({})
    assert plan(_registry(Placeholdered), conn) == []
    assert conn.queries == []


def test_resolved_placeholder_planned():
    @entity(schema="dbo", table="t_{company}", driver=Warehouse)
    class Placeholdered(BaseModel):
        id: Annotated[int, Col(pk=True)]

    actions = plan(_registry(Placeholdered), FakeConn({}), company="ho00")
    assert [a.kind for a in actions] == ["create"]
    assert "dbo.t_ho00" in actions[0].detail
