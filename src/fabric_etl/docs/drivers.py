"""Driver reference emitter: supported types and platform caveats per driver."""

from __future__ import annotations

from fabric_etl.entities.drivers import Driver, Lakehouse, SqlServer, Warehouse

_DRIVERS: tuple[type[Driver], ...] = (SqlServer, Warehouse, Lakehouse)

# Spec §3.3 caveats — a public contract, hardcoded on purpose.
_NOTES: dict[str, list[str]] = {
    SqlServer.name: [],
    Warehouse.name: [
        "`str` requires `Col(length=)` — only `varchar(n)`;"
        " `nvarchar` and `varchar(max)` are not supported",
        "`datetime` maps to `datetime2(6)`; precision above 6 is not supported",
        "PK and FK constraints are metadata only: `NOT ENFORCED`",
    ],
    Lakehouse.name: [
        "`str` maps to `string`: length is unbounded, `Col(length=)` is ignored"
        " (the SQL endpoint shows `varchar(8000)`)",
    ],
}


def emit() -> str:
    """One markdown page: per driver a python-type -> rendered-type table plus notes."""
    lines = ["# Driver type reference", ""]
    for driver in _DRIVERS:
        lines += [f"## {driver.name}", ""]
        lines += [f"| python | {driver.name} |", "|---|---|"]
        lines += [f"| {t.__name__} | {rendered} |" for t, rendered in driver.types.items()]
        lines.append("")
        if _NOTES[driver.name]:
            lines += [f"- {note}" for note in _NOTES[driver.name]]
            lines.append("")
    return "\n".join(lines)
