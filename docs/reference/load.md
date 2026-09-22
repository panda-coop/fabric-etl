# load

`fabric_etl.load` re-exports lazily; the real homes are the modules below.

## ddl

::: fabric_etl.load.ddl
    options:
      members:
        - ddl

## plan

::: fabric_etl.load.plan
    options:
      members:
        - plan
        - PlanAction

## writers

::: fabric_etl.load.writers
    options:
      members:
        - warehouse
        - lakehouse
        - BATCH_SIZE

## spark

::: fabric_etl.load.spark
    options:
      members:
        - to_spark_schema

## control

::: fabric_etl.load.control
    options:
      members:
        - RunLog
        - Watermark
