"""@entity decorator, EntityInfo and the registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fabric_etl.entities.columns import ColumnInfo, columns

if TYPE_CHECKING:
    from fabric_etl.entities.drivers.base import Driver

_SNAKE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _snake_case(name: str) -> str:
    return _SNAKE.sub("_", name).lower()


def resolve(template: str, **params: Any) -> str:
    """str.format that names the missing placeholders on failure."""
    try:
        return template.format(**params)
    except KeyError:
        missing = sorted(set(re.findall(r"{(\w+)}", template)) - params.keys())
        raise KeyError(
            f"missing placeholder params {missing} for {template!r}; pass them as keyword"
            " arguments (e.g. full_name(company=...))"
        ) from None


@dataclass
class EntityInfo:
    cls: type
    key: str  # f"{cls.__module__}.{cls.__qualname__}"
    schema: str | None
    table: str  # may contain {placeholder}
    database: str | None
    driver: type[Driver] | None
    source: bool
    description: str | None
    fks: dict[tuple[str, ...], str]
    indexes: list
    endpoint: str | None
    items: str | None
    columns: list[ColumnInfo]

    @property
    def pk(self) -> list[ColumnInfo]:
        return [c for c in self.columns if c.col.pk]

    def full_name(self, **params: Any) -> str:
        if self.driver is None:
            raise ValueError(
                f"entity {self.key} has no driver; pass @entity(driver=...) or set"
                " REGISTRY.default_driver"
            )
        return self.driver.full_name(self, **params)


class Registry:
    default_driver: type[Driver] | None = None
    default_schema: str | None = None

    def __init__(self) -> None:
        self._entities: dict[str, EntityInfo] = {}

    def register(self, info: EntityInfo) -> None:
        self._entities[info.key] = info

    def get(self, key: str) -> EntityInfo:
        return self._entities[key]

    def entities(self) -> list[EntityInfo]:
        return [self._entities[k] for k in sorted(self._entities)]

    def clear(self) -> None:
        self._entities.clear()


REGISTRY = Registry()


def entity(
    *,
    schema: str | None = None,
    table: str | None = None,
    database: str | None = None,
    driver: type[Driver] | None = None,
    source: bool = False,
    description: str | None = None,
    fks: dict[tuple[str, ...], str] | None = None,
    indexes: list | None = None,
    endpoint: str | None = None,
    items: str | None = None,
):
    """Store EntityInfo at cls.__entity__ and register it; the class is returned
    unchanged — every operation is a function over the entity, nothing is injected."""

    def wrap(cls: type) -> type:
        docstring = (cls.__doc__ or "").strip() or None
        info = EntityInfo(
            cls=cls,
            key=f"{cls.__module__}.{cls.__qualname__}",
            schema=schema if schema is not None else REGISTRY.default_schema,
            table=table or _snake_case(cls.__name__),
            database=database,
            driver=driver or REGISTRY.default_driver,
            source=source,
            description=description or docstring,
            fks=dict(fks or {}),
            indexes=list(indexes or []),
            endpoint=endpoint,
            items=items,
            columns=columns(cls),
        )
        cls.__entity__ = info
        REGISTRY.register(info)
        return cls

    return wrap
