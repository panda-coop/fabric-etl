# Entities

An entity is a plain Pydantic model decorated with `@entity`. The decorator introspects
the model, builds an `EntityInfo`, stores it at `cls.__entity__` and registers it in the
global `REGISTRY` — the class itself is returned unchanged. Nothing is injected: every
operation (DDL, docs, extraction, writing) is a function *over* the entity.

```python
from typing import Annotated
from pydantic import BaseModel, Field
from fabric_etl.entities import entity, Col
from fabric_etl.entities.drivers import Warehouse


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class BronzeSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)] = Field(description="Line amount")
```

`@entity` arguments:

| argument | meaning |
|---|---|
| `schema` | physical schema; falls back to `REGISTRY.default_schema` |
| `table` | physical table; defaults to snake_case of the class name; may contain `{placeholder}`s |
| `database` | database prefix (SqlServer three-part names) |
| `driver` | a `Driver` subclass; falls back to `REGISTRY.default_driver` |
| `source` | `True` marks a read-only source: no DDL, lint errors demoted to warnings |
| `description` | overrides the class docstring in generated docs |
| `fks` | composite foreign keys: `{("a", "b"): "schema.table.(x,y)"}` |
| `indexes` | index declarations (documentation only) |
| `endpoint` | HTTP sources: the URL template |
| `items` | record path: XPath for XML, dotted path for JSON/HTTP payloads |

## Col

`Col` carries the column metadata a Python type cannot express. SQL type strings are
forbidden — `native` is the only per-driver escape hatch.

| field | meaning |
|---|---|
| `length` | `varchar(n)` / `varbinary(n)` length |
| `precision`, `scale` | `decimal(p,s)` |
| `nullable` | explicit override; otherwise nullability comes from `T \| None` |
| `default` | column default (documentation) |
| `pk` | primary key member; composite PK order = field declaration order |
| `fk` | single-column foreign key, `"schema.table.column"` |
| `name` | physical column name when it differs from the attribute |
| `native` | per-driver rendered type, e.g. `{"warehouse": "varbinary(16)"}` |
| `path` | XML XPath / dotted JSON path for source entities |

`Field(description=...)` is the single source of field descriptions; `Field(alias=...)`
stays JSON-only and never becomes a physical name.

## Drivers

A driver is an all-classmethod class, never instantiated: `render(py_type, col) -> str`
translates a Python type, `full_name(info, **params)` builds the platform's qualified
name, `ddl(info, **params)` renders `CREATE TABLE`. Each driver's `types` dict is a
public supported-type contract — the docs emitter turns it into a reference page. An
unsupported type raises `UnsupportedType` (a `ValueError`) with a clear message.

| Python | SqlServer | Warehouse | Lakehouse (Delta) |
|---|---|---|---|
| `int` | `int` | `bigint` | `long` |
| `float` | `float` | `float` | `double` |
| `Decimal` | `decimal(p,s)` | `decimal(p,s)` | `decimal(p,s)` |
| `bool` | `bit` | `bit` | `boolean` |
| `str` | `nvarchar(n)` | `varchar(n)` — **`length` required** | `string` (length ignored) |
| `datetime` | `datetime2` | `datetime2(6)` | `timestamp` |
| `date` | `date` | `date` | `date` |
| `bytes` | `varbinary(n)` | `varbinary(n)` — **`length` required** | `binary` |
| `UUID` | `uniqueidentifier` | `uniqueidentifier` | `string` |
| `T \| None` | nullable | nullable | nullable |

Platform notes:

- **Warehouse** refuses `str`/`bytes` without `Col(length=)` — Fabric Warehouse has no
  `nvarchar` and no `varchar(max)`. Constraints are metadata only:
  `PRIMARY KEY NONCLUSTERED ... NOT ENFORCED`, `FOREIGN KEY ... NOT ENFORCED`.
- **Lakehouse** renders Delta DDL (`... USING DELTA`); `str` length is ignored, PK/FK
  are documentation only.
- **SqlServer** brackets every name part: `[database].[schema].[table]`; the other SQL
  drivers use plain `schema.table`.
- **Http** is source-only: `render` and `ddl` raise, `full_name` returns the resolved
  `endpoint`.

Driver selection, more specific wins: `REGISTRY.default_driver` → `@entity(driver=)` →
CLI `--driver` (to preview how a model would land on another platform).

## full_name and placeholders

`table`, `schema` and `database` may contain `{placeholder}`s; `EntityInfo.full_name`
delegates to the driver and resolves them from keyword arguments:

```python
@entity(
    schema="dbo",
    table="Cooperative Panda-{company}$Sales Line",
    driver=SqlServer,
    source=True,
)
class ErpSalesLine(BaseModel): ...


ErpSalesLine.__entity__.full_name(company="HO")
# '[dbo].[Cooperative Panda-HO$Sales Line]'
```

A missing placeholder raises `KeyError` naming exactly which parameters are missing.
Placeholders bind late — one declared entity serves every NAV company / tenant.

## Lint

`fabric_etl.entities.lint.lint(registry, strict=False)` returns `Finding`s formatted as
`path:line  CODE  message -> suggestion`:

| code | level | rule |
|---|---|---|
| E001 | error | space, `$`, brackets or quotes in a schema/table/column name (rejected by Delta without column mapping) |
| E003 | error | `str` column without `Col(length=)` on a Warehouse entity |
| W001 | warning | NAV/BC-style attribute (trailing `_`, CamelCase) — suggests snake_case |
| W002 | warning | `schema` set on a Lakehouse entity (schema-less lakehouses reject it) |

E002 (non-literal values in declarations) belongs to the [static extractor](cli.md),
which lints without importing user code.

`strict=True` promotes warnings to errors — with one deliberate exception:
`source=True` entities never error. Their E-level findings are demoted to warnings and
strict does not re-promote them, so a NAV table full of `Document No_` columns can be
described honestly without breaking CI.
