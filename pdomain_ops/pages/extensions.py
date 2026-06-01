"""Typed access to PageRecord.extensions namespaces (design: page-server v2 §1)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from pdomain_ops.pages.records import PageRecord  # noqa: TC001

M = TypeVar("M", bound=BaseModel)


def get_extension(record: PageRecord, namespace: str, model: type[M]) -> M | None:
    """Return the namespace's data validated into ``model``, or None if absent."""
    data = record.extensions.get(namespace)
    return None if data is None else model.model_validate(data)


def set_extension(record: PageRecord, namespace: str, value: BaseModel) -> None:
    """Store ``value`` (JSON-dumped) under ``namespace`` on the record."""
    record.extensions[namespace] = value.model_dump(mode="json")
