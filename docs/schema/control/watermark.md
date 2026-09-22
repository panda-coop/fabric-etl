# watermark  `control.watermark` · warehouse { #fabric-etl:control.watermark }

Last processed position per job (LSN hex, timestamp, id — as a string).

| field | python | warehouse | null | description |
|---|---|---|---|---|
| <a id="fabric-etl:control.watermark.job"></a>job | str | varchar(100) | no | PK |
| <a id="fabric-etl:control.watermark.value"></a>value | str | varchar(200) | no |  |
| <a id="fabric-etl:control.watermark.updated"></a>updated | datetime | datetime2(6) | no |  |

## DDL

```sql
CREATE TABLE control.watermark (
    job varchar(100) NOT NULL,
    value varchar(200) NOT NULL,
    updated datetime2(6) NOT NULL,
    PRIMARY KEY NONCLUSTERED (job) NOT ENFORCED
)
```
