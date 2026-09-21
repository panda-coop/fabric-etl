"""Tests for docs.lineage (and the lazy fabric_etl.docs namespace)."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.docs import lineage
from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer, Warehouse
from fabric_etl.transform import From, Mapping, Param


def quantize2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"))


@entity(schema="dbo", table="Panda-{company}$Sales Line", driver=SqlServer, source=True)
class ErpSalesLine(BaseModel):
    document_no: Annotated[str, Col(length=20, name="Document No_")]
    line_no: int
    amount: Decimal


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class BronzeSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    order_id: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    company: Annotated[str, Col(length=2)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)]


class ErpToBronze(Mapping[ErpSalesLine, BronzeSalesLine]):
    job = "nb_nav_sales_lines"
    tenant = Param()
    order_id = From("document_no")
    company = From("document_no", lambda v: v[:2])
    amount = From("amount", quantize2)


def test_mapping_page():
    page = lineage.emit(mappings=[ErpToBronze])["lineage/ErpToBronze.md"]
    assert page.startswith("# ErpToBronze\n")
    assert (
        "[dbo.Panda-{company}$Sales Line]"
        "(../dbo/Panda-{company}$Sales Line.md#fabric-etl:dbo.Panda-{company}$Sales Line)"
        " → [dbo.sales_line](../dbo/sales_line.md#fabric-etl:dbo.sales_line)" in page
    )
    assert "job: `nb_nav_sales_lines`" in page
    rows = [line for line in page.splitlines() if line.startswith("| ") and " | " in line[2:]]
    assert rows == [
        "| target field | from | transform |",
        "| amount | amount | quantize2 |",
        "| company | document_no | fn |",
        "| line_no | line_no | - |",
        "| order_id | document_no | - |",
        "| tenant | param: tenant | - |",
    ]


def test_index_and_mermaid():
    index = lineage.emit(mappings=[ErpToBronze])["lineage/index.md"]
    assert "| [ErpToBronze](ErpToBronze.md) |" in index
    assert "`nb_nav_sales_lines` |" in index
    assert "```mermaid\ngraph LR" in index
    assert (
        '    t_dbo_Panda_company_Sales_Line["dbo.Panda-{company}$Sales Line"]'
        ' --> m_ErpToBronze["ErpToBronze"]' in index
    )
    assert '    m_ErpToBronze --> t_dbo_sales_line["dbo.sales_line"]' in index


def test_index_sorted_and_deterministic():
    class AaaMap(Mapping[ErpSalesLine, BronzeSalesLine]):
        tenant = Param()
        order_id = From("document_no")
        company = From("document_no", lambda v: v[:2])

    mappings = [ErpToBronze, AaaMap]
    out = lineage.emit(mappings=mappings)
    assert out == lineage.emit(mappings=mappings)
    index = out["lineage/index.md"]
    assert index.index("[AaaMap](AaaMap.md)") < index.index("[ErpToBronze](ErpToBronze.md)")
    assert set(out) == {"lineage/AaaMap.md", "lineage/ErpToBronze.md", "lineage/index.md"}


def test_docs_namespace_lazy_submodules():
    import fabric_etl.docs as docs

    assert docs.lineage.emit is lineage.emit
    for name in ("markdown", "dbml", "jsonschema", "drivers"):
        assert hasattr(getattr(docs, name), "emit")
