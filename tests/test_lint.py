"""Tests for entities.lint."""

from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import REGISTRY, Col, Registry, entity
from fabric_etl.entities.drivers import Lakehouse, SqlServer, Warehouse
from fabric_etl.entities.lint import Finding, lint


def make_registry(*classes) -> Registry:
    reg = Registry()
    for cls in classes:
        reg.register(cls.__entity__)
    return reg


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class Clean(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    line_no: Annotated[int, Col(pk=True)]


@entity(schema="dbo", table="Sales Line$2024", driver=Warehouse)
class BadNames(BaseModel):
    ok: Annotated[str, Col(length=4)]
    weird: Annotated[str, Col(length=4, name="Unit Cost")]


@entity(schema="dbo", table="t", driver=Warehouse)
class NoLength(BaseModel):
    unsized: str
    sized: Annotated[str, Col(length=10)]
    escaped: Annotated[str, Col(native={"warehouse": "varchar(8000)"})]


@entity(schema="dbo", table="t2", driver=Warehouse)
class NavAttrs(BaseModel):
    No_: Annotated[str, Col(length=20)]
    DocumentNo: Annotated[str, Col(length=20)]
    document_no: Annotated[str, Col(length=20)]


@entity(schema="bronze", table="events", driver=Lakehouse)
class SchemaOnLakehouse(BaseModel):
    id: int


@entity(table="events2", driver=Lakehouse)
class BareLakehouse(BaseModel):
    id: int


@entity(
    schema="dbo",
    table="Cooperative Panda-{company}$Sales Line",
    driver=SqlServer,
    source=True,
)
class ErpSource(BaseModel):
    no: Annotated[str, Col(length=20, name="No_")]


def codes(findings, level=None):
    return [f.code for f in findings if level is None or f.level == level]


def test_clean_entity_has_no_findings():
    assert lint(make_registry(Clean)) == []


def test_e001_fires_on_table_and_column():
    findings = lint(make_registry(BadNames))
    e001 = [f for f in findings if f.code == "E001"]
    assert len(e001) == 2
    assert all(f.level == "error" for f in e001)
    assert any("Sales Line$2024" in f.message for f in e001)
    assert any("Unit Cost" in f.message for f in e001)


def test_e003_fires_only_without_length_or_native():
    findings = lint(make_registry(NoLength))
    e003 = [f for f in findings if f.code == "E003"]
    assert len(e003) == 1
    assert "unsized" in e003[0].message
    assert e003[0].level == "error"


def test_e003_not_for_lakehouse():
    @entity(table="lh", driver=Lakehouse)
    class LhStr(BaseModel):
        s: str

    assert codes(lint(make_registry(LhStr))) == []


def test_w001_fires_with_snake_suggestion():
    findings = lint(make_registry(NavAttrs))
    w001 = {f.message.split("'")[1]: f for f in findings if f.code == "W001"}
    assert set(w001) == {"No_", "DocumentNo"}
    assert w001["No_"].suggestion == "no"
    assert w001["DocumentNo"].suggestion == "document_no"
    assert all(f.level == "warning" for f in w001.values())


def test_w002_fires_only_with_schema():
    findings = lint(make_registry(SchemaOnLakehouse))
    assert codes(findings) == ["W002"]
    assert findings[0].level == "warning"
    assert lint(make_registry(BareLakehouse)) == []


def test_source_demotes_errors_to_warnings():
    findings = lint(make_registry(ErpSource))
    assert "E001" in codes(findings)
    assert all(f.level == "warning" for f in findings)


def test_strict_promotes_warnings():
    findings = lint(make_registry(NavAttrs, SchemaOnLakehouse), strict=True)
    assert codes(findings)
    assert all(f.level == "error" for f in findings)


def test_strict_does_not_repromote_source():
    findings = lint(make_registry(ErpSource), strict=True)
    assert all(f.level == "warning" for f in findings)


def test_str_finding_format():
    f = Finding("src/x.py", 12, "E001", "error", "bad name", None)
    assert str(f) == "src/x.py:12  E001  bad name"
    f = Finding("src/x.py", 12, "W001", "warning", "NAV style", "document_no")
    assert str(f) == "src/x.py:12  W001  NAV style -> document_no"


def test_path_and_line_point_at_class():
    findings = lint(make_registry(BadNames))
    assert findings[0].path.endswith("test_lint.py")
    assert findings[0].line > 1


def test_lint_defaults_to_module_registry():
    REGISTRY.clear()
    REGISTRY.register(SchemaOnLakehouse.__entity__)
    assert codes(lint()) == ["W002"]
