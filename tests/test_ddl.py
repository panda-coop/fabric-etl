"""Tests for driver DDL rendering: golden strings per driver."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Lakehouse, SqlServer, Warehouse


@entity(
    schema="dbo",
    table="sales_line",
    driver=Warehouse,
    fks={("tenant", "document_no"): "dbo.sales_header.(tenant,no)"},
)
class WhSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    item_no: Annotated[str, Col(length=20, fk="dbo.item.no")]
    amount: Annotated[Decimal, Col(precision=18, scale=2)]
    posted_at: datetime | None = None


@entity(schema="dbo", table="item", database="erp", driver=SqlServer)
class SqlItem(BaseModel):
    no: Annotated[str, Col(length=20, pk=True, name="No_")]
    vendor_no: Annotated[str, Col(length=20, fk="dbo.vendor.No_")]
    unit_cost: Annotated[Decimal, Col(precision=18, scale=2)]
    blocked: bool | None = None


@entity(schema="bronze", table="events", driver=Lakehouse)
class LhEvents(BaseModel):
    id: Annotated[int, Col(pk=True)]
    payload: str | None = None
    seen_at: datetime


@entity(schema="dbo", table="src_{company}", driver=Warehouse, source=True)
class SourceThing(BaseModel):
    x: Annotated[str, Col(length=10, pk=True)]


def test_warehouse_ddl_golden():
    assert WhSalesLine.__entity__.driver.ddl(WhSalesLine.__entity__) == (
        "CREATE TABLE dbo.sales_line (\n"
        "    tenant varchar(4) NOT NULL,\n"
        "    document_no varchar(20) NOT NULL,\n"
        "    line_no bigint NOT NULL,\n"
        "    item_no varchar(20) NOT NULL,\n"
        "    amount decimal(18,2) NOT NULL,\n"
        "    posted_at datetime2(6) NULL,\n"
        "    PRIMARY KEY NONCLUSTERED (tenant, document_no, line_no) NOT ENFORCED,\n"
        "    FOREIGN KEY (item_no) REFERENCES dbo.item (no) NOT ENFORCED,\n"
        "    FOREIGN KEY (tenant, document_no) REFERENCES dbo.sales_header (tenant, no)"
        " NOT ENFORCED\n"
        ")"
    )


def test_sqlserver_ddl_golden():
    assert SqlServer.ddl(SqlItem.__entity__) == (
        "CREATE TABLE [erp].[dbo].[item] (\n"
        "    [No_] nvarchar(20) NOT NULL,\n"
        "    [vendor_no] nvarchar(20) NOT NULL,\n"
        "    [unit_cost] decimal(18,2) NOT NULL,\n"
        "    [blocked] bit NULL,\n"
        "    PRIMARY KEY ([No_]),\n"
        "    FOREIGN KEY ([vendor_no]) REFERENCES [dbo].[vendor] ([No_])\n"
        ")"
    )


def test_lakehouse_ddl_golden():
    assert Lakehouse.ddl(LhEvents.__entity__) == (
        "CREATE TABLE bronze.events (\n"
        "    id long NOT NULL,\n"
        "    payload string NULL,\n"
        "    seen_at timestamp NOT NULL\n"
        ") USING DELTA"
    )


def test_composite_pk_declaration_order():
    ddl = Warehouse.ddl(WhSalesLine.__entity__)
    assert "PRIMARY KEY NONCLUSTERED (tenant, document_no, line_no)" in ddl


def test_source_entity_still_renders():
    # ddl() is pure; "no DDL emitted for source=True" is the caller's rule.
    ddl = Warehouse.ddl(SourceThing.__entity__, company="ho00")
    assert ddl.startswith("CREATE TABLE dbo.src_ho00 (")


def test_ddl_resolves_placeholders_in_full_name():
    assert "dbo.src_ho00" in Warehouse.ddl(SourceThing.__entity__, company="ho00")
