# Extract

Extractors read *source* entities and yield validated model instances. All of them
stream — constant memory regardless of feed size — and all of them are functions over
the entity, driven by `Col.name` / `Col.path` and the entity's `items` record path.

Importing `fabric_etl.extract` never pulls a heavy dependency: re-exports are lazy, and
each module that needs lxml/httpx raises a clear `ImportError` naming the extra.

## sql

```python
from fabric_etl.extract import sql, select_sql

select_sql(ErpSalesLine, company="HO")
# SELECT [Document No_] AS document_no, [Line No_] AS line_no, [Quantity] AS quantity
# FROM [dbo].[Cooperative Panda-HO$Sales Line]

for line in sql(ErpSalesLine, conn, company="HO"):  # conn: any DB-API 2 connection
    ...
```

`select_sql` selects every physical column, aliased to the attribute name where they
differ, quoted per the entity's driver. `sql()` executes it and yields models one
`fetchmany` batch at a time — never `fetchall`. Works with pyodbc, mssql-python, or any
DB-API 2 connection; no driver package is imported.

## xml

```python
from fabric_etl.extract import xml  # requires fabric-etl[xml]


@entity(source=True, items="//Product")
class Product(BaseModel):
    id: Annotated[int, Col(path="@id")]
    name: Annotated[str, Col(path="Name/text()")]
    quantity: Annotated[Decimal, Col(path="Stock/Quantity/text()")]
    price: Annotated[Decimal | None, Col(name="Price")] = None  # no path: child element


for product in xml(Product, "feed.xml"):
    ...
```

lxml `iterparse` streaming: the record tag comes from the last segment of `items`
(`"//Tag"`, `"Tag"` and `"/Order/Line"` all work; namespace-agnostic). Field values
resolve via `Col.path` as a relative XPath, falling back to a child element named by
the physical name. Consumed elements are freed as the parse advances, so a multi-GB
feed runs in constant memory.

## csv

```python
from fabric_etl.extract import csv

with open("export.csv", "rb") as fh:
    rows = list(csv(VendorPrice, fh, sep=";", encoding="cp1251"))
```

`DictReader` keyed by physical names; accepts binary or text file objects (binary is
wrapped with the given encoding). Empty cells become `None` for optional non-`str`
fields, so `int`/`Decimal` parsing survives blanks.

## http

The HTTP stack lives in `fabric_etl.extract.http` (the `[http]` extra) and has three
layers: auth strategies, a retrying client, and an entity-driven adapter.

### Client

```python
from fabric_etl.extract.http import Client, Bearer

with Client(
    "https://api.vendor.example", auth=Bearer(token), retries=3, backoff=1.0, log_hook=print
) as client:
    resp = client.get("/v1/orders")
```

- Sync only — Fabric notebooks are sync callers.
- Retries transport errors and the throttling/transient statuses 429, 502, 503, 504
  with exponential backoff (`backoff * 2**attempt`); anything else non-2xx raises via
  `raise_for_status()`.
- `log_hook(event)` fires once per received response with method, url, status, elapsed
  and a per-Client `correlation_id` — wire it to your run log.
- `pages(url, params=..., next_url=...)` follows pagination as an iterator: it yields
  the first page, then keeps calling `next_url(response)` until it returns `None`.
  Never "return everything".

### Auth strategies

All are `httpx.Auth` implementations; callers resolve secrets first and pass plain
values in.

| class | behaviour |
|---|---|
| `Basic(username, password)` | HTTP basic auth |
| `Bearer(token_or_provider)` | bearer token; a zero-arg callable is re-evaluated per request |
| `ClientCredentials(token_url, client_id, client_secret, scope=None)` | OAuth2 client-credentials: cached token, one refresh-and-replay on 401 |
| `QueryAuth(params)` | credentials appended to every query string (legacy B2B vendors) |

`QueryAuth` enforces **https** — a plain-http request raises `ValueError` before any
credential leaves the process — and exposes `.masked`, the frozenset of its param
names; the client's log hook replaces those values with `***` in logged URLs.

### Entity adapter

```python
from fabric_etl.extract.http import http


@entity(
    driver=Http,
    source=True,
    endpoint="/v1/companies/{company}/orders",
    items="data.orders",
)
class ApiOrder(BaseModel):
    order_no: Annotated[str, Col(path="id")]
    total: Annotated[Decimal, Col(path="amounts.gross")]


for order in http(ApiOrder, client, company="HO"):
    ...
```

`http()` GETs the resolved `endpoint`, walks the dotted `items` path to the record
list (`None` means the payload root; a single dict is treated as one record), and maps
each column via its dotted `Col.path`, falling back to the physical name.

## cdc

SQL Server change data capture, over any DB-API 2 connection (the `[cdc]` extra for
pyodbc). Every change row arrives as a typed envelope:

```python
class Cdc(BaseModel, Generic[T]):
    operation: CdcOperation  # DELETE=1 INSERT=2 UPDATE_BEFORE=3 UPDATE_AFTER=4
    start_lsn: bytes
    seqval: bytes
    row: T  # the entity model
```

```python
from fabric_etl.extract import changes, window, max_lsn

# explicit window
for change in changes(ErpSalesLine, conn, from_lsn, max_lsn(conn), company="HO"):
    if change.operation is CdcOperation.DELETE:
        ...

# incremental pass driven by control.watermark
for change in window(ErpSalesLine, conn, job="sales_line_ho", company="HO"):
    ...
```

`changes()` streams from `cdc.fn_cdc_get_all_changes_<instance>` with
`N'all update old'` (update-before rows included), ordered by LSN/seqval, one
`fetchmany` batch at a time. The capture instance defaults to SQL Server's own naming
(`schema_table`, non-alphanumerics — `$` included — replaced by `_`); pass
`instance=` to override.

`window()` is one incremental pass: from the job's watermark in `control.watermark`
(capture minimum on first run) up to the current `max_lsn`. **The watermark advances
only after the iterator is fully consumed** — a partially consumed iterator leaves it
untouched, so a crashed run replays the same window instead of losing changes.
`get_watermark`/`set_watermark` store the LSN hex-encoded in the
[control tables](load.md#control-entities).
