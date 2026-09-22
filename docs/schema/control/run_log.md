# run_log  `control.run_log` · warehouse { #fabric-etl:control.run_log }

One row per load run: job, timing, row count, outcome.

| field | python | warehouse | null | description |
|---|---|---|---|---|
| <a id="fabric-etl:control.run_log.id"></a>id | UUID | uniqueidentifier | no | PK |
| <a id="fabric-etl:control.run_log.job"></a>job | str | varchar(100) | no |  |
| <a id="fabric-etl:control.run_log.started"></a>started | datetime | datetime2(6) | no |  |
| <a id="fabric-etl:control.run_log.finished"></a>finished | datetime | datetime2(6) | no |  |
| <a id="fabric-etl:control.run_log.rows"></a>rows | int | bigint | no |  |
| <a id="fabric-etl:control.run_log.status"></a>status | str | varchar(20) | no |  |
| <a id="fabric-etl:control.run_log.error"></a>error | str | varchar(4000) | yes |  |

## DDL

```sql
CREATE TABLE control.run_log (
    id uniqueidentifier NOT NULL,
    job varchar(100) NOT NULL,
    started datetime2(6) NOT NULL,
    finished datetime2(6) NOT NULL,
    rows bigint NOT NULL,
    status varchar(20) NOT NULL,
    error varchar(4000) NULL,
    PRIMARY KEY NONCLUSTERED (id) NOT ENFORCED
)
```
