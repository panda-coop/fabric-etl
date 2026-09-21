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


def write_module(tmp_path, monkeypatch, name, source=MODULE):
    (tmp_path / f"{name}.py").write_text(source)
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


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
