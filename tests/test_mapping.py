"""Tests for transform.mapping."""

from typing import Annotated

import pytest
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.transform.mapping import MAPPINGS, From, Mapping, Param


@entity(source=True)
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


def test_non_entity_side_raises():
    class Plain(BaseModel):
        x: int

    with pytest.raises(TypeError, match="not an @entity class"):

        class Bad(Mapping[Src, Plain]):
            pass
