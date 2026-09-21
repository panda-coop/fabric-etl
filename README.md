# fabric-etl

Schema-as-code for Microsoft Fabric. Tables are described as Pydantic models with an
`@entity` decorator; from that description the package generates DDL, documentation
(markdown, DBML, JSON Schema, lineage), mappings between sources and target tables,
and typed I/O for loaders.

Not an ORM: no sessions, no query builder, no lazy relations — a data description
layer, per-platform type translation, a mapping layer, and artifact generation.

## Install

```bash
pip install fabric-etl            # core: entities, transform, docs emitters
pip install "fabric-etl[sql]"     # pyodbc extractors / plan drift
pip install "fabric-etl[http]"    # httpx client + auth strategies
pip install "fabric-etl[xml]"     # streaming XML extractor
pip install "fabric-etl[azure]"   # pydantic-settings with Azure Key Vault source
```

## Quick look

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

```bash
fabric-etl docs --registry myproj.schema --out docs/schema
fabric-etl dbml --registry myproj.schema --out docs/schema.dbml
fabric-etl ddl  --registry myproj.schema --out sql/
fabric-etl lint --registry myproj.schema --strict
```

`docs --check` regenerates into a temp dir and fails on drift — wire it into CI.
The static extractor (`--mode static`, griffe-based) builds the same registry
without importing user code, so docs and lint run in CI without pyodbc, lxml,
httpx or Spark.

## Layout

| package | role |
|---|---|
| `entities` | `@entity`, `Col`, `REGISTRY`, drivers (SqlServer / Warehouse / Lakehouse), lint |
| `transform` | `Mapping`, `From`, `Param` — typed source→target mappings |
| `extract` | sql / xml / csv / http / cdc readers driven by source entities |
| `load` | DDL, drift plan, warehouse/lakehouse writers, control tables |
| `docs` | markdown, DBML, JSON Schema, lineage, driver-reference emitters |
| `static` | griffe-based no-import registry extraction for CI |

Dependency rule: `entities`, `transform`, `docs`, `static` never import `extract`
or `load`; everything heavy is an extra.

## License

[GPL-3.0-or-later](LICENSE). Copyright (C) 2026 PANDA Coop.
