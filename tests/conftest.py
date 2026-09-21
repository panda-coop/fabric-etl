"""Shared fixtures: registry isolation per test."""

import pytest

from fabric_etl.entities import REGISTRY


@pytest.fixture(autouse=True)
def _isolate_registry():
    saved = REGISTRY.entities()
    driver, schema = REGISTRY.default_driver, REGISTRY.default_schema
    yield
    REGISTRY.clear()
    for info in saved:
        REGISTRY.register(info)
    REGISTRY.default_driver, REGISTRY.default_schema = driver, schema
