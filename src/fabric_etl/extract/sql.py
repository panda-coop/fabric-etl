"""SQL extractor: typed rows from any DB-API 2 connection (pyodbc, mssql-python)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def select_sql(entity_cls: type, **params: Any) -> str:
    """SELECT of all physical columns, aliased to attribute names where they differ.

    Names are quoted per the entity's driver (brackets for SqlServer, plain otherwise);
    {placeholder}s in the full name resolve from params.

    Args:
        entity_cls: an @entity class.
        **params: values for ``{placeholder}``s in the table name.

    Returns:
        The SELECT statement.
    """
    info = entity_cls.__entity__
    from_ = info.full_name(**params)  # raises the clear no-driver error first
    quote = info.driver._quote
    parts = [
        quote(c.physical) if c.physical == c.attr else f"{quote(c.physical)} AS {c.attr}"
        for c in info.columns
    ]
    return f"SELECT {', '.join(parts)} FROM {from_}"


def sql(entity_cls: type, conn: Any, **params: Any) -> Iterator[Any]:
    """Execute select_sql on conn and yield validated models, one fetchmany batch
    at a time — constant memory, never fetchall.

    Args:
        entity_cls: an @entity class.
        conn: any DB-API 2 connection (pyodbc, mssql-python, ...).
        **params: values for ``{placeholder}``s in the table name.

    Yields:
        One validated model instance per row.
    """
    info = entity_cls.__entity__
    cursor = conn.cursor()
    cursor.execute(select_sql(entity_cls, **params))
    attrs = [d[0] for d in cursor.description]
    while rows := cursor.fetchmany(cursor.arraysize):
        for row in rows:
            yield info.cls.model_validate(dict(zip(attrs, row, strict=True)))
