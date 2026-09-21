"""Static extractor: build a registry from source files without importing them."""

from fabric_etl.static.extractor import extract_registry, lint_static

__all__ = ["extract_registry", "lint_static"]
