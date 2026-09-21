"""Tests for transform.mapping."""

from decimal import Decimal
from typing import Annotated

import pytest
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer, Warehouse
from fabric_etl.transform.mapping import MAPPINGS, From, MappedColumn, Mapping, Param


@entity(schema="stg", driver=Warehouse, source=True)
class Src(BaseModel):
    document_no: Annotated[str, Col(length=20)]
    line_no: int
    quantity: int


@entity()
class Tgt(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    amount: int


class SrcToTgt(Mapping[Src, Tgt]):
    tenant = Param()
    company = Param(default=lambda p: p.tenant[:2].upper())

    amount = From("quantity")


def test_auto_map_same_names():
    by_target = {mc.target: mc for mc in SrcToTgt._plan}
    assert by_target["document_no"].kind == "field"
    assert by_target["document_no"].origin == "document_no"
    assert by_target["line_no"].kind == "field"


def test_from_rename():
    by_target = {mc.target: mc for mc in SrcToTgt._plan}
    assert by_target["amount"].kind == "renamed"
    assert by_target["amount"].origin == "quantity"
    assert by_target["amount"].fn is None


def test_param_covers_target_column():
    by_target = {mc.target: mc for mc in SrcToTgt._plan}
    assert by_target["tenant"].kind == "param"
    assert by_target["tenant"].origin == "tenant"


def test_from_unknown_source_attr_raises():
    with pytest.raises(TypeError, match=r"From\('nope'\).*no such attribute"):

        class Bad(Mapping[Src, Tgt]):
            tenant = Param()
            amount = From("nope")


def test_uncovered_required_target_field_raises():
    with pytest.raises(TypeError, match=r"\['tenant', 'amount'\]"):

        class Bad(Mapping[Src, Tgt]):
            pass


def test_optional_and_defaulted_target_fields_dont_raise():
    @entity()
    class Loose(BaseModel):
        document_no: Annotated[str, Col(length=20)]
        note: str | None = None
        status: Annotated[str, Col(length=10)] = "new"

    class Ok(Mapping[Src, Loose]):
        pass

    assert [mc.target for mc in Ok._plan] == ["document_no"]


def test_param_callable_default():
    m = SrcToTgt(tenant="ho00")
    assert m.params == {"tenant": "ho00", "company": "HO"}


def test_param_explicit_beats_default():
    m = SrcToTgt(tenant="ho00", company="XX")
    assert m.params["company"] == "XX"


def test_missing_required_param_raises():
    with pytest.raises(TypeError, match=r"missing required param\(s\) \['tenant'\]"):
        SrcToTgt()


def test_unknown_param_raises():
    with pytest.raises(TypeError, match=r"unknown param\(s\) \['bogus'\]"):
        SrcToTgt(tenant="ho00", bogus=1)


def test_mappings_registration():
    assert SrcToTgt in MAPPINGS
    assert SrcToTgt.job is None


# Spec §4 example: NAV source, Bronze Warehouse target, tenant as a mapping param.


@entity(
    schema="dbo",
    table="Cooperative Panda-{company}$Sales Line",
    driver=SqlServer,
    source=True,
)
class ErpSalesLine(BaseModel):
    document_no: Annotated[str, Col(length=20, name="Document No_")]
    line_no: Annotated[int, Col(name="Line No_")]
    quantity: Annotated[Decimal, Col(precision=18, scale=5, name="Quantity")]


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class BronzeSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)]


class ErpToBronze(Mapping[ErpSalesLine, BronzeSalesLine]):
    tenant = Param()
    company = Param(default=lambda p: p.tenant[:2].upper())

    amount = From("quantity", lambda d: d.quantize(Decimal("0.01")))


def test_source_table_resolves_placeholders():
    m = ErpToBronze(tenant="ho00")
    assert m.source_table == "[dbo].[Cooperative Panda-HO$Sales Line]"


def test_target_table():
    m = ErpToBronze(tenant="ho00")
    assert m.target_table == "dbo.sales_line"


def test_select_sql_golden():
    m = ErpToBronze(tenant="ho00")
    assert m.select_sql() == (
        "SELECT [Quantity] AS amount, [Document No_] AS document_no,"
        " [Line No_] AS line_no"
        " FROM [dbo].[Cooperative Panda-HO$Sales Line]"
    )


def test_select_sql_unquoted_without_sql_driver():
    m = SrcToTgt(tenant="ho00")
    assert "document_no AS document_no" in m.select_sql()


def test_apply_end_to_end():
    m = ErpToBronze(tenant="ho00")
    rows = [
        ErpSalesLine(document_no="SO-1001", line_no=10000, quantity=Decimal("2.50000")),
        ErpSalesLine(document_no="SO-1001", line_no=20000, quantity=Decimal("1.00000")),
    ]
    out = list(m.apply(rows))
    assert all(isinstance(r, BronzeSalesLine) for r in out)
    first = out[0]
    assert first.tenant == "ho00"
    assert first.document_no == "SO-1001"
    assert first.line_no == 10000
    assert first.amount == Decimal("2.50")
    assert first.amount.as_tuple().exponent == -2
    assert out[1].amount == Decimal("1.00")


def test_plan_sorted_by_target():
    m = ErpToBronze(tenant="ho00")
    plan = m.plan()
    fn = plan[0].fn
    assert fn is not None and fn(Decimal("3.14159")) == Decimal("3.14")
    assert plan == [
        MappedColumn(target="amount", origin="quantity", kind="renamed", fn=fn),
        MappedColumn(target="document_no", origin="document_no", kind="field", fn=None),
        MappedColumn(target="line_no", origin="line_no", kind="field", fn=None),
        MappedColumn(target="tenant", origin="tenant", kind="param", fn=None),
    ]


def test_non_entity_side_raises():
    class Plain(BaseModel):
        x: int

    with pytest.raises(TypeError, match="not an @entity class"):

        class Bad(Mapping[Src, Plain]):
            pass
