"""Tests for the lazy fabric_etl.load re-exports."""

import pytest

import fabric_etl.load as load
import fabric_etl.load.control as control_mod
import fabric_etl.load.ddl as ddl_mod
import fabric_etl.load.plan as plan_mod
import fabric_etl.load.spark as spark_mod
import fabric_etl.load.writers as writers_mod


def test_lazy_exports():
    # ddl/plan share a name with their submodule, which shadows the package
    # attribute once imported — exercise the lazy hook itself for those two.
    assert load.__getattr__("ddl") is ddl_mod.ddl
    assert load.__getattr__("plan") is plan_mod.plan
    assert load.PlanAction is plan_mod.PlanAction
    assert load.warehouse is writers_mod.warehouse
    assert load.lakehouse is writers_mod.lakehouse
    assert load.to_spark_schema is spark_mod.to_spark_schema
    assert load.RunLog is control_mod.RunLog
    assert load.Watermark is control_mod.Watermark


def test_all_is_complete():
    assert set(load.__all__) == {
        "ddl",
        "plan",
        "PlanAction",
        "warehouse",
        "lakehouse",
        "to_spark_schema",
        "RunLog",
        "Watermark",
    }


def test_unknown_attribute():
    with pytest.raises(AttributeError, match="no attribute 'nope'"):
        load.nope  # noqa: B018
