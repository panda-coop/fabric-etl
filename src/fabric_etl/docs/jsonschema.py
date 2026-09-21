"""JSON Schema emitter: one schema file per entity, straight from pydantic."""

from __future__ import annotations

import json

from fabric_etl.docs.markdown import sorted_entities
from fabric_etl.entities import REGISTRY, Registry


def emit(registry: Registry = REGISTRY) -> dict[str, str]:
    """Relative path "<schema>/<table>.schema.json" -> pretty-printed JSON Schema."""
    return {
        f"{info.schema or '_noschema'}/{info.table}.schema.json": json.dumps(
            info.cls.model_json_schema(), indent=2, sort_keys=True
        )
        + "\n"
        for info in sorted_entities(registry)
    }
