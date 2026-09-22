# fabric-etl

Schema-as-code for Microsoft Fabric. Tables are described once, as Pydantic models
with an `@entity` decorator; from that single description the package generates DDL,
documentation (markdown, DBML, JSON Schema, lineage), typed source-to-target mappings,
and streaming extractors and writers.

It is not an ORM: there are no sessions, no query builder, no lazy relations. What you
get is a data description layer, per-platform type translation, a mapping layer, and
artifact generation — everything a Fabric warehouse/lakehouse pipeline needs to stay
consistent between code, database, and documentation.

## Install

```bash
pip install fabric-etl            # core: entities, transform, docs emitters
pip install "fabric-etl[sql]"     # pyodbc extractors / plan drift
pip install "fabric-etl[http]"    # httpx client + auth strategies
pip install "fabric-etl[xml]"     # streaming XML extractor
pip install "fabric-etl[azure]"   # pydantic-settings with Azure Key Vault source
```

The core depends on pydantic only. Every heavy dependency (pyodbc, lxml, httpx,
pyspark, azure) sits behind an extra and is imported lazily — a missing one raises an
`ImportError` naming the extra to install.

## A first entity

```python
from decimal import Decimal
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

That one class is enough to render `CREATE TABLE` DDL for a Fabric Warehouse, emit a
documented schema page, lint the naming, and validate rows on the way in:

```bash
fabric-etl docs --registry myproj.schema --out docs/schema
fabric-etl dbml --registry myproj.schema --out docs/schema.dbml
fabric-etl ddl  --registry myproj.schema --out sql/
fabric-etl lint --registry myproj.schema --strict
```

`docs --check` regenerates into a temp dir and fails on drift — wire it into CI. The
static extractor (`--mode static`, griffe-based) builds the same registry without
importing user code, so docs and lint run in CI without pyodbc, lxml, httpx or Spark.

## Layout

| package | role |
|---|---|
| `entities` | `@entity`, `Col`, `REGISTRY`, drivers (SqlServer / Warehouse / Lakehouse), lint |
| `transform` | `Mapping`, `From`, `Param` — typed source→target mappings |
| `extract` | sql / xml / csv / http / cdc readers driven by source entities |
| `load` | DDL, drift plan, warehouse/lakehouse writers, control tables |
| `docs` | markdown, DBML, JSON Schema, lineage, driver-reference emitters |
| `static` | griffe-based no-import registry extraction for CI |

Dependency rule: `entities`, `transform`, `docs`, `static` never import `extract` or
`load`; everything heavy is an extra.

## License

[GPL-3.0-or-later](https://github.com/panda-coop/fabric-etl/blob/main/LICENSE).
Copyright (C) 2026 PANDA Coop.
