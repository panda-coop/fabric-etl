# CLI

`fabric-etl` operates on a *registry* — the set of entities your schema module
declares. Four subcommands, all taking `--registry` and `--mode`:

| command | emits |
|---|---|
| `docs` | markdown entity pages, JSON Schema, lineage pages, driver type reference |
| `dbml` | one DBML schema file (paste into dbdiagram.io) |
| `ddl` | one `CREATE TABLE` file per non-source entity, `<schema>/<table>.sql` |
| `lint` | findings as `path:line  CODE  message -> suggestion`; exit 1 on errors |

```bash
fabric-etl docs --registry myproj.schema --out docs/schema
fabric-etl dbml --registry myproj.schema --out docs/schema.dbml
fabric-etl ddl  --registry myproj.schema --out sql/ --driver warehouse
fabric-etl lint --registry myproj.schema --strict
```

`ddl --driver` (sqlserver / warehouse / lakehouse) overrides every entity's driver —
useful to preview how models would land on another platform. `lint --strict` promotes
warnings to errors (except on `source=True` entities, which never error — see
[lint](entities.md#lint)).

## --mode runtime vs static

`--registry` accepts two spellings, and the mode decides how the registry is built:

- **runtime** (default for dotted paths): the module is imported; its `@entity`
  decorators fill the registry and `Mapping` subclasses register for lineage. The
  module must be importable — for a project that is not installed, put its root on
  `PYTHONPATH`.
- **static** (`--mode static`, and the default whenever `--registry` is a filesystem
  path — contains `/` or ends with `.py`): the griffe-based extractor parses the
  source without importing it. No pyodbc, lxml, httpx or Spark needed in the CI image;
  non-literal declarations are reported as E002. File-path registries need no import
  and therefore no `PYTHONPATH`. Static extraction yields no mappings, so lineage
  pages are skipped.

Verified local recipes:

```bash
# runtime, dotted registry: the project root must be importable
PYTHONPATH=. uv run --project <repo> fabric-etl ddl --registry myproj.schema --out sql/

# static, file-path registry: no PYTHONPATH, no heavy deps
uv run --with-editable '<repo>[docs]' --no-project fabric-etl lint \
    --registry myproj/schema.py --strict
```

## --check: the CI drift gate

`docs --check` and `dbml --check` regenerate into a temp directory and diff against
`--out` — nothing is written, differing relative paths go to stderr, exit 1 on drift.
Committed docs can then never lie about the code:

```yaml
# .github/workflows/test.yml (excerpt)
- run: uv run fabric-etl docs --registry myproj.schema --out docs/schema --check
- run: uv run fabric-etl lint --registry myproj.schema --strict
```

The regenerate-and-commit loop stays local: run `docs` without `--check`, review the
diff, commit generated pages together with the schema change that caused them.
