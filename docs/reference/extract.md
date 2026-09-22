# extract

`fabric_etl.extract` re-exports lazily; the real homes are the modules below.

## sql

::: fabric_etl.extract.sql
    options:
      members:
        - select_sql
        - sql

## xml

::: fabric_etl.extract.xml
    options:
      members:
        - xml

## csv

::: fabric_etl.extract.csv
    options:
      members:
        - csv

## http

::: fabric_etl.extract.http
    options:
      members:
        - http

::: fabric_etl.extract.http.client
    options:
      members:
        - Client
        - RETRY_STATUSES

::: fabric_etl.extract.http.auth
    options:
      members:
        - Basic
        - Bearer
        - ClientCredentials
        - QueryAuth

## cdc

::: fabric_etl.extract.cdc
    options:
      members:
        - CdcOperation
        - Cdc
        - capture_instance
        - max_lsn
        - changes
        - window
        - get_watermark
        - set_watermark
