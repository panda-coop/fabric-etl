"""Mapping between a source and a target entity: From, Param, column plan."""

from __future__ import annotations

import types
import typing
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar

from fabric_etl.entities import EntityInfo

S = TypeVar("S")
T = TypeVar("T")

MAPPINGS: list[type[Mapping]] = []


class Param:
    """A parameter of one concrete transfer. `default` is a plain value or a
    callable receiving a namespace of the already-resolved params."""

    def __init__(self, default: Any = None) -> None:
        self.default = default


class From:
    """Map a target attribute from a differently named source attribute,
    optionally through `fn` (value -> value)."""

    def __init__(self, source: str, fn: Callable | None = None) -> None:
        self.source = source
        self.fn = fn


@dataclass(frozen=True)
class MappedColumn:
    target: str
    origin: str  # source attr name, or param name
    kind: str  # "field" | "renamed" | "param"
    fn: Callable | None


def _entity_info(cls: type, arg: Any, side: str) -> EntityInfo:
    info = getattr(arg, "__entity__", None)
    if not isinstance(info, EntityInfo):
        raise TypeError(f"{cls.__name__}: {side} {arg!r} is not an @entity class")
    return info


class Mapping(Generic[S, T]):
    """Usage: `class X(Mapping[Src, Tgt])`. Same-name fields map automatically;
    `From` renames/transforms; a target column matching a `Param` is filled from
    it. Coverage is validated at class-definition time."""

    job: str | None = None  # Fabric notebook/pipeline join key

    source: ClassVar[EntityInfo]
    target: ClassVar[EntityInfo]
    _params: ClassVar[dict[str, Param]]
    _plan: ClassVar[list[MappedColumn]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        args = next(
            (
                typing.get_args(base)
                for base in cls.__dict__.get("__orig_bases__", ())
                if typing.get_origin(base) is Mapping
            ),
            None,
        )
        if args is None or not all(isinstance(a, type) for a in args):
            return  # generic alias (TypeVars) or plain subclass — nothing to resolve
        cls.source = _entity_info(cls, args[0], "source")
        cls.target = _entity_info(cls, args[1], "target")

        params: dict[str, Param] = {}
        froms: dict[str, From] = {}
        for klass in reversed(cls.__mro__):
            for name, value in vars(klass).items():
                if isinstance(value, Param):
                    params[name] = value
                elif isinstance(value, From):
                    froms[name] = value
        cls._params = params

        source_attrs = {c.attr for c in cls.source.columns}
        plan: list[MappedColumn] = []
        for name, frm in froms.items():
            if frm.source not in source_attrs:
                raise TypeError(
                    f"{cls.__name__}.{name}: From({frm.source!r}) — no such attribute on"
                    f" source entity {cls.source.key}"
                )
            plan.append(MappedColumn(target=name, origin=frm.source, kind="renamed", fn=frm.fn))
        uncovered: list[str] = []
        for c in cls.target.columns:
            if c.attr in froms:
                continue
            if c.attr in source_attrs:
                plan.append(MappedColumn(target=c.attr, origin=c.attr, kind="field", fn=None))
            elif c.attr in params:
                plan.append(MappedColumn(target=c.attr, origin=c.attr, kind="param", fn=None))
            elif not c.optional and cls.target.cls.model_fields[c.attr].is_required():
                uncovered.append(c.attr)
        if uncovered:
            raise TypeError(
                f"{cls.__name__}: required target field(s) {uncovered} covered by neither a"
                " same-name source field, From, nor Param"
            )
        cls._plan = sorted(plan, key=lambda mc: mc.target)
        MAPPINGS.append(cls)

    def __init__(self, **params: Any) -> None:
        declared = type(self)._params
        unknown = sorted(set(params) - set(declared))
        if unknown:
            raise TypeError(f"{type(self).__name__}: unknown param(s) {unknown}")
        missing = [n for n, p in declared.items() if n not in params and p.default is None]
        if missing:
            raise TypeError(f"{type(self).__name__}: missing required param(s) {missing}")
        resolved = dict(params)
        ns = types.SimpleNamespace(**resolved)
        for name, p in declared.items():
            if name not in resolved and not callable(p.default):
                resolved[name] = p.default
                setattr(ns, name, p.default)
        for name, p in declared.items():  # callables see plain params, declaration order
            if name not in resolved:
                resolved[name] = p.default(ns)
                setattr(ns, name, resolved[name])
        self.params = resolved

    @property
    def source_table(self) -> str:
        return self.source.full_name(**self.params)

    @property
    def target_table(self) -> str:
        return self.target.full_name(**self.params)

    def _quote_source(self, name: str) -> str:
        driver = self.source.driver
        return driver._quote(name) if driver is not None else name

    def plan(self) -> list[MappedColumn]:
        return list(self._plan)

    def select_sql(self) -> str:
        physical = {c.attr: c.physical for c in self.source.columns}
        cols = ", ".join(
            f"{self._quote_source(physical[mc.origin])} AS {mc.target}"
            for mc in self._plan
            if mc.kind != "param"
        )
        return f"SELECT {cols} FROM {self.source_table}"

    def apply(self, rows: Iterable[S]) -> Iterator[T]:
        for row in rows:
            data: dict[str, Any] = {}
            for mc in self._plan:
                if mc.kind == "param":
                    data[mc.target] = self.params[mc.origin]
                else:
                    value = getattr(row, mc.origin)
                    data[mc.target] = mc.fn(value) if mc.fn is not None else value
            yield self.target.cls.model_validate(data)
