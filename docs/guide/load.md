# Load

The load layer turns entities into tables and rows into inserts. It is the only place
(besides `extract`) allowed to touch databases; `entities`, `transform`, `docs` and
`static` never import it.

## ddl

```python
from fabric_etl.load import ddl

print(ddl(BronzeSalesLine))
# CREATE TABLE dbo.sales_line (
#     tenant varchar(4) NOT NULL,
#     ...
#     PRIMARY KEY NONCLUSTERED (tenant, document_no, line_no) NOT ENFORCED
# )
```

A thin wrapper over the pure driver renderers (which live in `entities.drivers`, so
the docs emitters can embed DDL without importing `load`). Accepts an `@entity` class
or an `EntityInfo`; `driver=` overrides the entity's driver to preview another
platform. Source entities have no DDL — `ddl()` raises `ValueError` for them.

## plan

`plan(registry, conn, **params)` diffs every non-source entity against the live
`INFORMATION_SCHEMA` and returns `PlanAction`s. There are exactly three kinds —
Fabric Warehouse has effectively no `ALTER COLUMN`, so type or nullability changes and
column drops are never automated:

| kind | when | detail |
|---|---|---|
| `create` | table missing | the full `CREATE TABLE` statement |
| `add_column` | model has a column the table lacks | the `ALTER TABLE ... ADD` statement |
| `recreate` | type/nullability mismatch or extra database column | human-readable reasons; the rebuild is yours to script |

Type comparison is deliberately loose: base name always, length for char/binary,
precision/scale for decimal. Entities whose `{placeholder}`s are not satisfied by
`params` are skipped — they are not bound to a physical table.

## Writers

```python
from fabric_etl.load import warehouse, lakehouse

n = warehouse(BronzeSalesLine, mapping.apply(rows), conn)  # append
n = warehouse(BronzeSalesLine, mapping.apply(rows), conn, merge=True)  # upsert on pk
```

`warehouse()` writes entity instances or dicts (keyed by attribute) over any DB-API 2
connection in batches of 1000 (`BATCH_SIZE`) — constant memory, `executemany` per
batch, one commit at the end, returns the row count. `merge=True` renders a `MERGE`
on the primary key (`ValueError` if the entity has none): matched rows update the
non-key columns, unmatched rows insert.

`lakehouse(entity_cls, df, mode="append")` writes a Spark DataFrame as the Delta table
named by the entity.

## to_spark_schema

```python
from fabric_etl.load import to_spark_schema

df = spark.createDataFrame(data, schema=to_spark_schema(BronzeSalesLine))
```

Builds a pyspark `StructType` with *physical* column names, nullability from
`T | None`, `DecimalType(p, s)` from `Col`. pyspark imports lazily — without the
`[spark]` extra you get an `ImportError` naming it.

## Control entities

fabric-etl's own operational tables ship as entities, declared with `@entity` exactly
like user tables:

| entity | table | purpose |
|---|---|---|
| `RunLog` | `control.run_log` | one row per load run: job, timing, row count, outcome |
| `Watermark` | `control.watermark` | last processed position per job (LSN hex, timestamp, id — as a string) |

Both target Warehouse. `fabric-etl ddl --registry fabric_etl.load.control --out sql/`
creates them; the [CDC window](extract.md#cdc) reads and advances `control.watermark`.
