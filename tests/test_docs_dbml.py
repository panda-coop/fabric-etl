"""Tests for docs.dbml."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from fabric_etl.docs import dbml
from fabric_etl.entities import Col, Registry, entity
from fabric_etl.entities.drivers import SqlServer, Warehouse


@entity(
    schema="dbo",
    table="Panda-{company}$Sales Line",
    driver=SqlServer,
    source=True,
    description="NAV sales lines.",
)
class ErpSalesLine(BaseModel):
    document_no: Annotated[str, Col(length=20, name="Document No_")]
    amount: Decimal


@entity(
    schema="dbo",
    table="sales_line",
    driver=Warehouse,
    description="Bronze copy of NAV Sales Line.",
    fks={("tenant", "document_no"): "dbo.sales_header.(tenant, document_no)"},
)
class BronzeSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True, fk="dbo.tenant.code")]
    document_no: Annotated[str, Col(length=20, pk=True)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)] = Field(description="Line amount")
    note: Annotated[str | None, Col(length=100)] = None


def _registry() -> Registry:
    r = Registry()
    r.register(ErpSalesLine.__entity__)
    r.register(BronzeSalesLine.__entity__)
    return r


def test_target_table_block():
    out = dbml.emit(_registry())
    assert (
        'Table "dbo"."sales_line" {\n'
        '  "tenant" varchar(4) [pk, not null]\n'
        '  "document_no" varchar(20) [pk, not null]\n'
        "  \"amount\" decimal(18,2) [not null, note: 'Line amount']\n"
        '  "note" varchar(100)\n'
        "\n"
        "  Note: 'Bronze copy of NAV Sales Line.'\n"
        "}" in out
    )


def test_source_table_block_notes_source():
    out = dbml.emit(_registry())
    assert 'Table "dbo"."Panda-{company}$Sales Line" {' in out
    assert '  "Document No_" nvarchar(20) [not null]' in out
    assert "  Note: 'source'" in out


def test_ref_lines():
    out = dbml.emit(_registry())
    assert 'Ref: "dbo"."sales_line"."tenant" > "dbo"."tenant"."code"' in out
    assert (
        'Ref: "dbo"."sales_line".("tenant", "document_no")'
        ' > "dbo"."sales_header".("tenant", "document_no")' in out
    )


def test_table_group_from_module():
    out = dbml.emit(_registry())
    assert (
        "TableGroup test_docs_dbml {\n"
        '  "dbo"."Panda-{company}$Sales Line"\n'
        '  "dbo"."sales_line"\n'
        "}" in out
    )


def test_deterministic_ordering():
    r = _registry()
    out = dbml.emit(r)
    assert out == dbml.emit(r)
    # source entity sorts before the target: "Panda-..." < "sales_line"
    assert out.index('Table "dbo"."Panda-{company}$Sales Line"') < out.index(
        'Table "dbo"."sales_line"'
    )
    # Refs after all Table blocks, TableGroup last
    assert out.index("Ref: ") > out.rindex("Table ")
    assert out.rstrip().endswith("}")
    assert out.index("TableGroup ") > out.index("Ref: ")
