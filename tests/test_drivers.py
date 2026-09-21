"""Tests for entities.drivers: type table, name rules, escape hatches."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import pytest
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.columns import columns
from fabric_etl.entities.drivers import Http, Lakehouse, SqlServer, UnsupportedType, Warehouse

SIZED = Col(length=20, precision=18, scale=2)

TYPE_TABLE = [
    (int, "int", "bigint", "long"),
    (float, "float", "float", "double"),
    (Decimal, "decimal(18,2)", "decimal(18,2)", "decimal(18,2)"),
    (bool, "bit", "bit", "boolean"),
    (str, "nvarchar(20)", "varchar(20)", "string"),
    (datetime, "datetime2", "datetime2(6)", "timestamp"),
    (date, "date", "date", "date"),
    (bytes, "varbinary(20)", "varbinary(20)", "binary"),
    (UUID, "uniqueidentifier", "uniqueidentifier", "string"),
]


@pytest.mark.parametrize(("py_type", "expected"), [(t, s) for t, s, _, _ in TYPE_TABLE])
def test_sqlserver_types(py_type, expected):
    assert SqlServer.render(py_type, SIZED) == expected


@pytest.mark.parametrize(("py_type", "expected"), [(t, w) for t, _, w, _ in TYPE_TABLE])
def test_warehouse_types(py_type, expected):
    assert Warehouse.render(py_type, SIZED) == expected


@pytest.mark.parametrize(("py_type", "expected"), [(t, lh) for t, _, _, lh in TYPE_TABLE])
def test_lakehouse_types(py_type, expected):
    assert Lakehouse.render(py_type, SIZED) == expected


def test_sqlserver_str_without_length_is_max():
    assert SqlServer.render(str, Col()) == "nvarchar(max)"
    assert SqlServer.render(bytes, Col()) == "varbinary(max)"


def test_decimal_default_precision_scale():
    assert Warehouse.render(Decimal, Col()) == "decimal(18,0)"


def test_warehouse_rejects_str_without_length():
    with pytest.raises(UnsupportedType, match=r"str requires Col\(length=") as exc:
        Warehouse.render(str, Col())
    assert isinstance(exc.value, ValueError)


def test_warehouse_rejects_bytes_without_length():
    with pytest.raises(UnsupportedType, match=r"bytes requires Col\(length="):
        Warehouse.render(bytes, Col())


def test_unsupported_type_message_lists_supported():
    with pytest.raises(UnsupportedType, match="unsupported column type complex"):
        Warehouse.render(complex, Col())


def test_lakehouse_ignores_length():
    assert Lakehouse.render(str, Col()) == "string"
    assert Lakehouse.render(str, Col(length=4000)) == "string"


def test_native_escape_hatch():
    col = Col(native={"warehouse": "varbinary(16)"})
    assert Warehouse.render(UUID, col) == "varbinary(16)"
    assert SqlServer.render(UUID, col) == "uniqueidentifier"


def test_nullable_rules():
    class M(BaseModel):
        a: int
        b: int | None = None
        c: Annotated[int, Col(nullable=True)]
        d: Annotated[int | None, Col(nullable=False)] = None

    by_attr = {c.attr: c for c in columns(M)}
    assert not Warehouse.nullable(by_attr["a"])
    assert Warehouse.nullable(by_attr["b"])
    assert Warehouse.nullable(by_attr["c"])
    assert not Warehouse.nullable(by_attr["d"])


def test_types_dict_is_public_contract():
    for driver in (SqlServer, Warehouse, Lakehouse):
        assert set(driver.types) == {int, float, Decimal, bool, str, datetime, date, bytes, UUID}
    assert Http.types == {}


@entity(schema="dbo", table="sales_line", database="erp", driver=SqlServer)
class QualifiedTable(BaseModel):
    x: int


@entity(
    schema="dbo",
    table="Cooperative Panda-{company}$Sales Line",
    driver=SqlServer,
    source=True,
)
class ErpSalesLine(BaseModel):
    no: Annotated[str, Col(length=20, name="No_")]


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class WhSalesLine(BaseModel):
    x: int


@entity(schema="bronze", table="sales_line", driver=Lakehouse)
class LhSalesLine(BaseModel):
    x: int


@entity(table="sales_line", driver=Lakehouse)
class LhBare(BaseModel):
    x: int


@entity(driver=Http, endpoint="https://api.example.com/{company}/orders", items="value")
class ApiOrders(BaseModel):
    id: int


def test_sqlserver_full_name():
    assert QualifiedTable.__entity__.full_name() == "[erp].[dbo].[sales_line]"


def test_sqlserver_full_name_nav_placeholder():
    info = ErpSalesLine.__entity__
    assert info.full_name(company="HO") == "[dbo].[Cooperative Panda-HO$Sales Line]"


def test_warehouse_full_name():
    assert WhSalesLine.__entity__.full_name() == "dbo.sales_line"


def test_lakehouse_full_name():
    assert LhSalesLine.__entity__.full_name() == "bronze.sales_line"
    assert LhBare.__entity__.full_name() == "sales_line"


def test_http_full_name_is_resolved_endpoint():
    info = ApiOrders.__entity__
    assert info.full_name(company="ho00") == "https://api.example.com/ho00/orders"


def test_http_render_and_ddl_raise():
    with pytest.raises(UnsupportedType):
        Http.render(int, Col())
    with pytest.raises(UnsupportedType):
        Http.ddl(ApiOrders.__entity__)
