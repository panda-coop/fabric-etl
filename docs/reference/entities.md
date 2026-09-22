# entities

::: fabric_etl.entities.entity
    options:
      members:
        - entity
        - EntityInfo
        - Registry

::: fabric_etl.entities.columns
    options:
      members:
        - Col
        - ColumnInfo

## Drivers

::: fabric_etl.entities.drivers
    options:
      members:
        - Driver
        - SqlServer
        - Warehouse
        - Lakehouse
        - Http
        - UnsupportedType

## Lint

::: fabric_etl.entities.lint
    options:
      members:
        - lint
        - Finding
