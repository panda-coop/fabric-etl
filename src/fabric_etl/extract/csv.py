"""Streaming CSV extractor: DictReader keyed by physical names, typed rows out."""

from __future__ import annotations

import csv as _csv
import io
from collections.abc import Iterator
from typing import IO, Any


def csv(entity_cls: type, fh: IO, *, sep: str = ",", encoding: str = "utf-8") -> Iterator[Any]:
    """Yield validated models from a binary or text file object. Empty cells become
    None for optional non-str fields so int/Decimal parsing survives blanks.

    Args:
        entity_cls: an @entity class; the header row must carry the physical names.
        fh: binary or text file object (binary is wrapped with ``encoding``).
        sep: field delimiter.
        encoding: used only when ``fh`` is binary.

    Yields:
        One validated model per data row.
    """
    info = entity_cls.__entity__
    if isinstance(fh.read(0), bytes):
        fh = io.TextIOWrapper(fh, encoding=encoding, newline="")
    for row in _csv.DictReader(fh, delimiter=sep):
        record = {}
        for c in info.columns:
            value = row.get(c.physical)
            if value == "" and c.optional and c.py_type is not str:
                value = None
            record[c.attr] = value
        yield info.cls.model_validate(record)
