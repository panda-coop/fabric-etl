"""Tests for the static extractor. Sample sources are written to tmp_path and
never imported — that is the point."""

from decimal import Decimal
from uuid import UUID

from fabric_etl.entities import REGISTRY, Col
from fabric_etl.entities.drivers import SqlServer, Warehouse
from fabric_etl.static import extract_registry, lint_static

NORMAL = '''
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer, Warehouse


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class BronzeSalesLine(BaseModel):
    """Bronze copy of NAV Sales Line."""

    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)] = Field(description="Line amount")
    batch: Annotated[UUID | None, Col()] = None
    note: str | None = None


@entity(
    schema="dbo",
    table="Cooperative Panda-{company}$Sales Line",
    database="NAV2018",
    driver=SqlServer,
    source=True,
)
class ErpSalesLine(BaseModel):
    document_no: Annotated[str, Col(length=20, pk=True, name="Document No_")]
    line_no: Annotated[int, Col(pk=True, name="Line No_")]
    customer_no: Annotated[str, Col(length=20, fk="dbo.customer.no", name="Sell-to Customer No_")]
'''


def entity_by_table(registry, table):
    return next(i for i in registry.entities() if i.table == table)


def test_extracts_two_entities(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text(NORMAL)
    registry = extract_registry([path])
    assert registry.findings == []
    assert len(registry.entities()) == 2

    bronze = entity_by_table(registry, "sales_line")
    assert bronze.schema == "dbo"
    assert bronze.driver is Warehouse
    assert bronze.source is False
    assert bronze.description == "Bronze copy of NAV Sales Line."
    assert [c.attr for c in bronze.columns] == [
        "tenant",
        "document_no",
        "line_no",
        "amount",
        "batch",
        "note",
    ]
    assert [c.attr for c in bronze.pk] == ["tenant", "document_no", "line_no"]
    by_attr = {c.attr: c for c in bronze.columns}
    assert by_attr["tenant"].col == Col(length=4, pk=True)
    assert by_attr["amount"].py_type is Decimal
    assert by_attr["amount"].col == Col(precision=18, scale=2)
    assert by_attr["amount"].description == "Line amount"
    assert by_attr["batch"].py_type is UUID
    assert by_attr["batch"].optional is True
    assert by_attr["note"].py_type is str
    assert by_attr["note"].optional is True
    assert by_attr["note"].col == Col()

    erp = entity_by_table(registry, "Cooperative Panda-{company}$Sales Line")
    assert erp.driver is SqlServer
    assert erp.source is True
    assert erp.database == "NAV2018"
    assert [c.physical for c in erp.columns] == [
        "Document No_",
        "Line No_",
        "Sell-to Customer No_",
    ]
    assert erp.columns[2].col.fk == "dbo.customer.no"
    assert erp.full_name(company="HO") == "[NAV2018].[dbo].[Cooperative Panda-HO$Sales Line]"


def test_no_import_and_not_global_registry(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text("import nonexistent_dependency\n" + NORMAL)
    before = len(REGISTRY.entities())
    registry = extract_registry([path])
    assert len(registry.entities()) == 2
    assert len(REGISTRY.entities()) == before


FSTRING = """
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Warehouse

PREFIX = "x"


@entity(schema="dbo", table=f"{PREFIX}_line", driver=Warehouse)
class FLine(BaseModel):
    id: Annotated[int, Col(pk=True)]
"""


def test_fstring_table_is_e002_entity_still_registered(tmp_path):
    path = tmp_path / "bad.py"
    path.write_text(FSTRING)
    registry = extract_registry([path])
    assert len(registry.findings) == 1
    f = registry.findings[0]
    assert f.code == "E002"
    assert f.level == "error"
    assert f.path == str(path)
    assert f.line == 12  # the decorator line
    assert "non-literal value in declaration" in f.message

    info = entity_by_table(registry, "f_line")  # snake_case fallback
    assert info.schema == "dbo"
    assert info.driver is Warehouse
    assert [c.attr for c in info.pk] == ["id"]


def test_unresolvable_annotation_is_e002(tmp_path):
    path = tmp_path / "odd.py"
    path.write_text(
        "from pydantic import BaseModel\n"
        "from fabric_etl.entities import entity\n"
        "@entity(table='odd')\n"
        "class Odd(BaseModel):\n"
        "    ok: int\n"
        "    weird: list[int]\n"
    )
    registry = extract_registry([path])
    assert [f.code for f in registry.findings] == ["E002"]
    assert registry.findings[0].line == 6
    info = entity_by_table(registry, "odd")
    assert [c.attr for c in info.columns] == ["ok"]


NOTEBOOK = """# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" }
# META }

# CELL ********************

# datadict: schema
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Warehouse


@entity(schema="dbo", table="marked", driver=Warehouse)
class Marked(BaseModel):
    id: Annotated[int, Col(pk=True)]

# METADATA ********************

# META { "language": "python" }

# CELL ********************

# MAGIC %%sql
# MAGIC SELECT 1

# CELL ********************

from pydantic import BaseModel

from fabric_etl.entities import entity


@entity(table="unmarked")
class Unmarked(BaseModel):
    id: int


df = spark.read.table("dbo.marked")
display(df)
"""


def test_notebook_takes_only_marked_cells(tmp_path):
    path = tmp_path / "notebook-content.py"
    path.write_text(NOTEBOOK)
    registry = extract_registry([path])
    assert registry.findings == []
    tables = [i.table for i in registry.entities()]
    assert tables == ["marked"]
    info = entity_by_table(registry, "marked")
    assert info.driver is Warehouse
    assert [c.attr for c in info.pk] == ["id"]


def test_lint_static_combines_and_sorts(tmp_path):
    bad = tmp_path / "a_bad.py"
    bad.write_text(FSTRING)
    nav = tmp_path / "b_nav.py"
    nav.write_text(
        "from typing import Annotated\n"
        "from pydantic import BaseModel\n"
        "from fabric_etl.entities import Col, entity\n"
        "from fabric_etl.entities.drivers import Warehouse\n"
        "@entity(schema='dbo', table='t', driver=Warehouse)\n"
        "class Nav(BaseModel):\n"
        "    No_: Annotated[str, Col(length=20)]\n"
        "    unsized: str\n"
    )
    findings = lint_static([tmp_path])
    codes = [f.code for f in findings]
    assert "E002" in codes  # from a_bad.py extraction
    assert "E003" in codes and "W001" in codes  # entities.lint on the registry
    assert findings == sorted(findings, key=lambda f: (f.path, f.line))
    assert findings[0].path == str(bad)

    strict = lint_static([tmp_path], strict=True)
    assert all(f.level == "error" for f in strict)


def test_static_matches_runtime(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text(NORMAL)
    static = extract_registry([path])

    namespace = {}
    exec(compile(NORMAL, str(path), "exec"), namespace)  # runtime: real decorator
    for name in ("BronzeSalesLine", "ErpSalesLine"):
        runtime = namespace[name].__entity__
        extracted = entity_by_table(static, runtime.table)
        assert extracted.schema == runtime.schema
        assert extracted.table == runtime.table
        assert extracted.database == runtime.database
        assert extracted.driver is runtime.driver
        assert extracted.source == runtime.source
        assert extracted.description == runtime.description
        assert extracted.endpoint == runtime.endpoint
        assert extracted.items == runtime.items

        def flat(info):
            return [
                (c.attr, c.physical, c.py_type, c.optional, c.col, c.description)
                for c in info.columns
            ]

        assert flat(extracted) == flat(runtime)
        assert [c.attr for c in extracted.pk] == [c.attr for c in runtime.pk]
