# Changelog

## 0.1.0 — 2026-09-21

First functional release.

- `entities`: `@entity` decorator, `Col` annotations, `REGISTRY`, SqlServer /
  Warehouse / Lakehouse / Http drivers with per-platform type rendering and
  full-name rules, DDL rendering, lint rules E001/E003/W001/W002 with `--strict`.
- `transform`: `Mapping[Source, Target]` with `From` and `Param`,
  definition-time coverage validation, `select_sql()`, `apply()`,
  `spark_select()`; mappings registry for lineage.
- `extract`: DB-API `sql()` extractor, streaming `xml()` (lxml iterparse) and
  `csv()` readers, httpx client with retry/backoff and `pages()` iterator, auth
  strategies (Basic, Bearer, ClientCredentials, QueryAuth), entity-driven HTTP
  adapter, MSSQL CDC envelope/reader with control-table watermark integration.
- `load`: DDL wrapper, `plan()` drift detection against INFORMATION_SCHEMA
  (create / add column / recreate), warehouse writer (batched insert, MERGE
  upsert), lakehouse writer, `to_spark_schema()`, control entities
  (`control.run_log`, `control.watermark`).
- `docs`: deterministic emitters — markdown entity pages with stable anchors,
  DBML, JSON Schema, lineage pages with mermaid graph, driver type reference.
- `static`: griffe-based no-import registry extraction (E002 for non-literals,
  notebook `# datadict: schema` cell filter) for CI.
- `settings`: pydantic-settings base with optional Azure Key Vault source
  (`[azure]` extra).
- CLI: `fabric-etl docs|dbml|ddl|lint` with `--check` drift gate and
  `--mode runtime|static`.

## 0.0.1 — 2026-09-21

PyPI placeholder: name reservation, license metadata, publish workflow.
