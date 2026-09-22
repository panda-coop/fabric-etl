"""load.ddl — thin wrapper over the pure driver DDL renderers."""

from __future__ import annotations

from typing import Any

from fabric_etl.entities.drivers.base import Driver
from fabric_etl.entities.entity import EntityInfo


def ddl(
    entity_or_info: type | EntityInfo, driver: type[Driver] | None = None, **params: Any
) -> str:
    """CREATE TABLE for an @entity class or its EntityInfo.

    `driver` overrides info.driver. Source entities have no DDL — the drivers
    render anything, so this wrapper is where the caller-side rule lives.

    Args:
        entity_or_info: an @entity class or its ``EntityInfo``.
        driver: platform override (preview a model on another platform).
        **params: values for ``{placeholder}``s in the table name.

    Returns:
        The CREATE TABLE statement.

    Raises:
        ValueError: source entity, or no driver anywhere.
    """
    if isinstance(entity_or_info, EntityInfo):
        info = entity_or_info
    else:
        info = entity_or_info.__entity__
    if info.source:
        raise ValueError(f"source entities have no DDL: {info.key}")
    drv = driver or info.driver
    if drv is None:
        raise ValueError(
            f"entity {info.key} has no driver; pass ddl(..., driver=...) or set"
            " REGISTRY.default_driver"
        )
    return drv.ddl(info, **params)
