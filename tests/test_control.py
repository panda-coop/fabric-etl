"""Tests for load.control — the package's own operational entities."""

from fabric_etl.entities import REGISTRY
from fabric_etl.entities.drivers import Warehouse
from fabric_etl.load.control import RunLog, Watermark


def test_registered():
    keys = {info.key for info in REGISTRY.entities()}
    assert RunLog.__entity__.key in keys
    assert Watermark.__entity__.key in keys


def test_run_log_ddl():
    ddl = Warehouse.ddl(RunLog.__entity__)
    assert ddl.startswith("CREATE TABLE control.run_log (")
    assert "id uniqueidentifier NOT NULL" in ddl
    assert "job varchar(100) NOT NULL" in ddl
    assert "error varchar(4000) NULL" in ddl
    assert "PRIMARY KEY NONCLUSTERED (id) NOT ENFORCED" in ddl


def test_watermark_ddl():
    ddl = Warehouse.ddl(Watermark.__entity__)
    assert ddl.startswith("CREATE TABLE control.watermark (")
    assert "value varchar(200) NOT NULL" in ddl
    assert "PRIMARY KEY NONCLUSTERED (job) NOT ENFORCED" in ddl


def test_pk_shapes():
    assert [c.attr for c in RunLog.__entity__.pk] == ["id"]
    assert [c.attr for c in Watermark.__entity__.pk] == ["job"]
