"""Tests for docs.drivers."""

from fabric_etl.docs import drivers


def test_page_has_a_table_per_driver():
    page = drivers.emit()
    for name in ("sqlserver", "warehouse", "lakehouse"):
        assert f"## {name}" in page
        assert f"| python | {name} |" in page
    assert "| int | int |" in page  # sqlserver
    assert "| int | bigint |" in page  # warehouse
    assert "| int | long |" in page  # lakehouse
    assert "| str | varchar(n) |" in page
    assert "| datetime | datetime2(6) |" in page
    assert "| str | string |" in page


def test_caveats_present():
    page = drivers.emit()
    assert "`str` requires `Col(length=)`" in page
    assert "`nvarchar` and `varchar(max)` are not supported" in page
    assert "`datetime2(6)`" in page
    assert "length is unbounded" in page


def test_deterministic():
    assert drivers.emit() == drivers.emit()
