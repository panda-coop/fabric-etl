"""Tests for docs.markdown."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from fabric_etl.docs import markdown
from fabric_etl.entities import Col, Registry, entity
from fabric_etl.entities.drivers import Http, Lakehouse, SqlServer, Warehouse
from fabric_etl.transform import Mapping, Param


@entity(
    schema="dbo",
    table="Panda-{company}$Sales Line",
    database="nav",
    driver=SqlServer,
    source=True,
    description="NAV sales lines, one table per company.",
)
class ErpSalesLine(BaseModel):
    document_no: Annotated[str, Col(length=20, name="Document No_")]
    line_no: Annotated[int, Col(name="Line No_")]
    amount: Decimal


@entity(
    schema="dbo",
    table="sales_line",
    driver=Warehouse,
    description="Bronze copy of NAV Sales Line, all companies.",
)
class BronzeSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)] = Field(description="Line amount")


class ErpToBronze(Mapping[ErpSalesLine, BronzeSalesLine]):
    job = "nb_nav_sales_lines"
    tenant = Param()


def _registry() -> Registry:
    r = Registry()
    r.register(ErpSalesLine.__entity__)
    r.register(BronzeSalesLine.__entity__)
    return r


def test_page_paths_and_index():
    pages = markdown.emit(_registry(), mappings=[ErpToBronze])
    assert set(pages) == {
        "dbo/Panda-{company}$Sales Line.md",
        "dbo/sales_line.md",
        "index.md",
    }


def test_target_page():
    page = markdown.emit(_registry(), mappings=[ErpToBronze])["dbo/sales_line.md"]
    assert page.startswith(
        "# sales_line  `dbo.sales_line` · warehouse { #fabric-etl:dbo.sales_line }"
    )
    assert "Bronze copy of NAV Sales Line, all companies." in page
    assert "| field | python | warehouse | null | description |" in page
    assert (
        '| <a id="fabric-etl:dbo.sales_line.tenant"></a>tenant | str | varchar(4) | no | PK |'
        in page
    )
    assert (
        '| <a id="fabric-etl:dbo.sales_line.amount"></a>amount | Decimal | decimal(18,2)'
        " | no | Line amount |" in page
    )
    assert "```sql\nCREATE TABLE dbo.sales_line (" in page
    assert "PRIMARY KEY NONCLUSTERED (tenant, document_no, line_no) NOT ENFORCED" in page


def test_source_page_note_instead_of_ddl():
    page = markdown.emit(_registry())["dbo/Panda-{company}$Sales Line.md"]
    assert "```sql" not in page
    assert (
        "source; physical name with placeholders:"
        " `[nav].[dbo].[Panda-{company}$Sales Line]`" in page
    )


def test_fed_by_and_feeds_links():
    pages = markdown.emit(_registry(), mappings=[ErpToBronze])
    target = pages["dbo/sales_line.md"]
    assert "## Fed by" in target
    assert (
        "- ErpToBronze (job: `nb_nav_sales_lines`) ← [dbo.Panda-{company}$Sales Line]"
        "(Panda-{company}$Sales Line.md"
        "#fabric-etl:dbo.Panda-{company}$Sales Line)" in target
    )
    source = pages["dbo/Panda-{company}$Sales Line.md"]
    assert "## Feeds" in source
    assert "→ [dbo.sales_line](sales_line.md#fabric-etl:dbo.sales_line)" in source


def test_index_rows_sorted_and_linked():
    index = markdown.emit(_registry())["index.md"]
    rows = [line for line in index.splitlines() if line.startswith("| [")]
    assert rows == [
        "| [Panda-{company}$Sales Line]"
        "(dbo/Panda-{company}$Sales Line.md#fabric-etl:dbo.Panda-{company}$Sales Line)"
        " | `[nav].[dbo].[Panda-{company}$Sales Line]` | sqlserver | yes |",
        "| [sales_line](dbo/sales_line.md#fabric-etl:dbo.sales_line)"
        " | `dbo.sales_line` | warehouse | no |",
    ]


def test_lakehouse_length_ignored_and_no_schema():
    @entity(driver=Lakehouse)
    class Dim(BaseModel):
        code: Annotated[str, Col(length=10, pk=True)]
        note: str | None = None

    r = Registry()
    r.register(Dim.__entity__)
    pages = markdown.emit(r)
    page = pages["_noschema/dim.md"]
    assert "# dim  `dim` · lakehouse { #fabric-etl:_noschema.dim }" in page
    assert "| string (length ignored) | no | PK |" in page
    assert '| <a id="fabric-etl:_noschema.dim.note"></a>note | str | string | yes |  |' in page
    assert "USING DELTA" in page


def test_http_source_renders_dashes():
    @entity(driver=Http, source=True, endpoint="https://api/orders/{tenant}", items="value")
    class ApiOrder(BaseModel):
        id: Annotated[str, Col(path="id")]

    r = Registry()
    r.register(ApiOrder.__entity__)
    page = markdown.emit(r)["_noschema/api_order.md"]
    assert "`https://api/orders/{tenant}` · http" in page
    assert '| <a id="fabric-etl:_noschema.api_order.id"></a>id | str | - | no |  |' in page
    assert "source; physical name with placeholders: `https://api/orders/{tenant}`" in page


def test_deterministic():
    r = _registry()
    assert markdown.emit(r, mappings=[ErpToBronze]) == markdown.emit(r, mappings=[ErpToBronze])
