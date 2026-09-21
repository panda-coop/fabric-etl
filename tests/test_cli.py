"""Tests for the CLI: entrypoint, version, registry loading."""

import pytest

from fabric_etl import __version__
from fabric_etl.cli import load_registry, main

MODULE = '''
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Warehouse


@entity(schema="dbo", table="cli_sample", driver=Warehouse)
class CliSample(BaseModel):
    """CLI test entity."""

    tenant: Annotated[str, Col(length=4, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
'''


MAPPING_MODULE = """
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer, Warehouse
from fabric_etl.transform import Mapping


@entity(schema="dbo", table="cli_sample", driver=Warehouse)
class CliSample(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    line_no: Annotated[int, Col(pk=True)]


@entity(schema="dbo", table="erp_sample", driver=SqlServer, source=True)
class ErpSample(BaseModel):
    tenant: Annotated[str, Col(length=4)]
    line_no: int


class ErpToCli(Mapping[ErpSample, CliSample]):
    job = "nb_cli_sample"
"""

DDL_MODULE = """
from typing import Annotated

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import SqlServer, Warehouse


@entity(schema="dbo", table="cli_sample", driver=Warehouse)
class CliSample(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    line_no: Annotated[int, Col(pk=True)]


@entity(schema="dbo", table="erp_sample", driver=SqlServer, source=True)
class ErpSample(BaseModel):
    tenant: Annotated[str, Col(length=4)]


@entity(schema="dbo", table="pl_{company}", driver=Warehouse)
class Placeholder(BaseModel):
    line_no: Annotated[int, Col(pk=True)]
"""

DOCS_TREE = {
    "index.md",
    "drivers.md",
    "dbo/cli_sample.md",
    "dbo/erp_sample.md",
    "dbo/cli_sample.schema.json",
    "dbo/erp_sample.schema.json",
    "lineage/ErpToCli.md",
    "lineage/index.md",
}


def write_module(tmp_path, monkeypatch, name, source=MODULE):
    (tmp_path / f"{name}.py").write_text(source)
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


def relfiles(root):
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def fresh_mappings(monkeypatch):
    fresh: list = []
    monkeypatch.setattr("fabric_etl.transform.mapping.MAPPINGS", fresh)
    monkeypatch.setattr("fabric_etl.transform.MAPPINGS", fresh)
    return fresh


def test_version(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out == f"{__version__}\n"


def test_no_command_prints_usage(capsys):
    assert main([]) == 2
    assert "usage: fabric-etl" in capsys.readouterr().err


def test_unknown_command_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["frobnicate"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_load_registry_runtime(tmp_path, monkeypatch):
    name = write_module(tmp_path, monkeypatch, "cli_runtime_sample")
    registry, mappings = load_registry(name)
    from fabric_etl.entities import REGISTRY

    assert registry is REGISTRY
    assert isinstance(mappings, list)
    assert any(i.table == "cli_sample" for i in registry.entities())


def test_load_registry_static_path(tmp_path):
    path = tmp_path / "cli_static_sample.py"
    path.write_text(MODULE)
    registry, mappings = load_registry(str(path))
    assert mappings == []
    (info,) = registry.entities()
    assert info.table == "cli_sample"
    assert [c.attr for c in info.columns] == ["tenant", "line_no"]


def test_load_registry_static_mode_over_dir(tmp_path):
    (tmp_path / "cli_static_dir.py").write_text(MODULE)
    registry, _ = load_registry(str(tmp_path), mode="static")
    assert [i.table for i in registry.entities()] == ["cli_sample"]


def test_missing_module_exits_1(tmp_path, capsys):
    assert main(["docs", "--registry", "cli_no_such_module", "--out", str(tmp_path)]) == 1
    assert "fabric-etl:" in capsys.readouterr().err


def test_docs_writes_tree(tmp_path, monkeypatch, capsys, fresh_mappings):
    from fabric_etl.entities import REGISTRY

    REGISTRY.clear()
    name = write_module(tmp_path, monkeypatch, "cli_docs_write", MAPPING_MODULE)
    out = tmp_path / "docs"
    assert main(["docs", "--registry", name, "--out", str(out)]) == 0
    assert relfiles(out) == DOCS_TREE
    assert f"wrote {len(DOCS_TREE)} files" in capsys.readouterr().out
    page = (out / "dbo" / "cli_sample.md").read_text()
    assert "fabric-etl:dbo.cli_sample" in page


def test_docs_check(tmp_path, monkeypatch, capsys, fresh_mappings):
    from fabric_etl.entities import REGISTRY

    REGISTRY.clear()
    name = write_module(tmp_path, monkeypatch, "cli_docs_check", MAPPING_MODULE)
    out = tmp_path / "docs"
    assert main(["docs", "--registry", name, "--out", str(out)]) == 0
    capsys.readouterr()

    assert main(["docs", "--registry", name, "--out", str(out), "--check"]) == 0
    assert capsys.readouterr().err == ""

    tampered = (out / "index.md").read_text() + "tampered\n"
    (out / "index.md").write_text(tampered)
    (out / "extra.md").write_text("stray\n")
    assert main(["docs", "--registry", name, "--out", str(out), "--check"]) == 1
    err = capsys.readouterr().err
    assert "index.md" in err
    assert "extra.md" in err
    # --check never writes into --out
    assert (out / "index.md").read_text() == tampered


def test_dbml_write_and_check(tmp_path, capsys):
    src = tmp_path / "cli_dbml_sample.py"
    src.write_text(MODULE)
    out = tmp_path / "out" / "schema.dbml"
    assert main(["dbml", "--registry", str(src), "--out", str(out)]) == 0
    content = out.read_text()
    assert 'Table "dbo"."cli_sample" {' in content

    assert main(["dbml", "--registry", str(src), "--out", str(out), "--check"]) == 0
    out.write_text(content + "tampered\n")
    capsys.readouterr()
    assert main(["dbml", "--registry", str(src), "--out", str(out), "--check"]) == 1
    assert str(out) in capsys.readouterr().err


def test_ddl_writes_sql_per_target(tmp_path, capsys):
    src = tmp_path / "cli_ddl_sample.py"
    src.write_text(DDL_MODULE)
    out = tmp_path / "sql"
    assert main(["ddl", "--registry", str(src), "--out", str(out)]) == 0
    assert relfiles(out) == {"dbo/cli_sample.sql"}
    sql = (out / "dbo" / "cli_sample.sql").read_text()
    assert sql.startswith("CREATE TABLE dbo.cli_sample (")
    assert "varchar(4)" in sql
    captured = capsys.readouterr()
    assert "wrote 1 files" in captured.out
    assert "skipped" in captured.err
    assert "Placeholder" in captured.err


def test_ddl_driver_override(tmp_path):
    src = tmp_path / "cli_ddl_override.py"
    src.write_text(MODULE)
    out = tmp_path / "sql"
    assert main(["ddl", "--registry", str(src), "--out", str(out), "--driver", "lakehouse"]) == 0
    sql = (out / "dbo" / "cli_sample.sql").read_text()
    assert "USING DELTA" in sql
    assert "tenant string" in sql
