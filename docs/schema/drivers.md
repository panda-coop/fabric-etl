# Driver type reference

## sqlserver

| python | sqlserver |
|---|---|
| int | int |
| float | float |
| Decimal | decimal(p,s) |
| bool | bit |
| str | nvarchar(n) |
| datetime | datetime2 |
| date | date |
| bytes | varbinary(n) |
| UUID | uniqueidentifier |

## warehouse

| python | warehouse |
|---|---|
| int | bigint |
| float | float |
| Decimal | decimal(p,s) |
| bool | bit |
| str | varchar(n) |
| datetime | datetime2(6) |
| date | date |
| bytes | varbinary(n) |
| UUID | uniqueidentifier |

- `str` requires `Col(length=)` — only `varchar(n)`; `nvarchar` and `varchar(max)` are not supported
- `datetime` maps to `datetime2(6)`; precision above 6 is not supported
- PK and FK constraints are metadata only: `NOT ENFORCED`

## lakehouse

| python | lakehouse |
|---|---|
| int | long |
| float | double |
| Decimal | decimal(p,s) |
| bool | boolean |
| str | string |
| datetime | timestamp |
| date | date |
| bytes | binary |
| UUID | string |

- `str` maps to `string`: length is unbounded, `Col(length=)` is ignored (the SQL endpoint shows `varchar(8000)`)
