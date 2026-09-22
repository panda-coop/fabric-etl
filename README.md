# fabric-etl

[![PyPI](https://img.shields.io/pypi/v/fabric-etl)](https://pypi.org/project/fabric-etl/)
[![tests](https://img.shields.io/github/actions/workflow/status/panda-coop/fabric-etl/test.yml?label=tests)](https://github.com/panda-coop/fabric-etl/actions/workflows/test.yml)
[![docs](https://img.shields.io/github/actions/workflow/status/panda-coop/fabric-etl/github-pages.yml?label=docs)](https://panda-coop.github.io/fabric-etl/)
[![license](https://img.shields.io/github/license/panda-coop/fabric-etl)](LICENSE)

Schema-as-code for Microsoft Fabric. Tables are described as Pydantic models
with an `@entity` decorator; from that description the package generates DDL,
documentation (markdown, DBML, JSON Schema, lineage), typed source-to-target
mappings, and typed I/O for loaders. Not an ORM — no sessions, no query
builder, no lazy relations.

**Documentation: <https://panda-coop.github.io/fabric-etl/>**

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

```sh
fabric-etl docs --registry myproj.schema --out docs/schema   # markdown + lineage
fabric-etl dbml --registry myproj.schema --out schema.dbml   # ER diagram source
fabric-etl ddl  --registry myproj.schema --out sql/          # CREATE TABLE per entity
fabric-etl lint --registry myproj.schema --strict            # naming/type rules
```

Install extras per surface: `[sql]` `[cdc]` `[xml]` `[http]` `[spark]`
`[docs]` `[settings]` `[azure]` — the core depends on pydantic alone, and
docs/lint run in CI without any platform driver installed.

## Development

Prerequisites: Python >= 3.11 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --group dev
uv run pytest                          # 238 tests
uv run ruff check . && uv run ruff format --check .
uv run --group site zensical serve    # docs preview
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full gate and commit
conventions.

## License

[GPL-3.0-or-later](LICENSE). Copyright (C) 2026 PANDA Coop.
