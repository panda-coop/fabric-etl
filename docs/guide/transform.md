# Transform

`Mapping[Source, Target]` describes how one source entity becomes one target entity.
Both sides are `@entity` classes; the mapping is validated when the class is defined,
not when the first row flows.

The canonical example — a NAV table into a Bronze Warehouse table:

```python
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel
from fabric_etl.entities import entity, Col
from fabric_etl.entities.drivers import SqlServer, Warehouse
from fabric_etl.transform import Mapping, From, Param


@entity(
    schema="dbo",
    table="Cooperative Panda-{company}$Sales Line",
    driver=SqlServer,
    source=True,
)
class ErpSalesLine(BaseModel):
    document_no: Annotated[str, Col(length=20, name="Document No_")]
    line_no: Annotated[int, Col(name="Line No_")]
    quantity: Annotated[Decimal, Col(precision=18, scale=5, name="Quantity")]


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class BronzeSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    document_no: Annotated[str, Col(length=20, pk=True)]
    line_no: Annotated[int, Col(pk=True)]
    amount: Annotated[Decimal, Col(precision=18, scale=2)]


class ErpToBronze(Mapping[ErpSalesLine, BronzeSalesLine]):
    tenant = Param()  # required parameter
    company = Param(default=lambda p: p.tenant[:2].upper())

    amount = From("quantity", lambda d: d.quantize(Decimal("0.01")))
    # document_no, line_no — same names, mapped automatically
```

## The rules

- **Same-name fields map automatically** — `document_no` and `line_no` need no code.
- **`From(source, fn=None)`** renames and/or transforms a single value.
- **`Param(default=None)`** is a parameter of one concrete transfer. A plain value or a
  callable receiving a namespace of the already-resolved params (`company` above derives
  from `tenant`). A target column matching a `Param` name is filled from it — that is how
  `tenant` gets its value.
- **Coverage is validated at class-definition time**: a required target field covered by
  neither a same-name source field, `From`, nor `Param` raises `TypeError` when the
  module imports — not at 3 a.m. in the pipeline.
- `{placeholder}`s in source/target names resolve from the params.

Every `Mapping` subclass appends itself to `fabric_etl.transform.MAPPINGS`; the lineage
docs emitter iterates that list. The optional `job` class attribute is the join key to a
Fabric notebook or pipeline.

## Instance API

```python
m = ErpToBronze(tenant="ho00")  # missing required Param -> TypeError

m.source_table  # [dbo].[Cooperative Panda-HO$Sales Line]
m.target_table  # dbo.sales_line
m.select_sql()
# SELECT [Quantity] AS amount, [Document No_] AS document_no, [Line No_] AS line_no
# FROM [dbo].[Cooperative Panda-HO$Sales Line]
m.plan()  # [MappedColumn(target=..., origin=..., kind="field|renamed|param", fn=...)]
```

Names in `select_sql()` are quoted by the *source* driver (brackets for SqlServer),
and every physical column is aliased to the target attribute — the SELECT output is
directly `model_validate`-able into the target model.

## apply

`m.apply(rows)` is a generator: `Iterable[Source] -> Iterator[Target]`. Each output row
is built from the plan (params filled from `m.params`, `From.fn` applied per value) and
validated through the target model — a type error surfaces as a pydantic
`ValidationError` naming the row and field.

## spark_select

`m.spark_select(df)` produces the same projection as `select_sql()` on a Spark
DataFrame: `col(physical).alias(target)` per mapped column, `lit(param)` per param
column. Two constraints:

- pyspark is imported lazily; without the `[spark]` extra it raises `ImportError`
  telling you to install `fabric-etl[spark]`.
- **`From.fn` is not supported** — a Python callable cannot be pushed into a Spark
  column expression, so a plan containing `fn` raises `NotImplementedError` listing the
  offending columns. Write those transforms as SQL/Spark expressions by hand.
