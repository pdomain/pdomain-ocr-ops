"""Tests for PageRecord.extensions + get/set typed helpers."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field

from pdomain_ops.pages import PageRecord, get_extension, set_extension


class _PrepExt(BaseModel):
    """Dummy extension model for test purposes."""

    idx0: int
    splits: list[str] = Field(default_factory=list)


def _page() -> PageRecord:
    return PageRecord(page_id=uuid4(), page_index=0)


def test_default_extensions_empty() -> None:
    """PageRecord.extensions defaults to an empty dict."""
    assert _page().extensions == {}


def test_extensions_independent_across_instances() -> None:
    """Each PageRecord instance has its own extensions dict (not shared)."""
    a = _page()
    b = _page()
    set_extension(a, "prep", _PrepExt(idx0=1))
    assert b.extensions == {}


def test_set_and_get_round_trip() -> None:
    """set_extension then get_extension validates back into the model."""
    record = _page()
    ext = _PrepExt(idx0=5, splits=["a", "b"])
    set_extension(record, "prep", ext)
    recovered = get_extension(record, "prep", _PrepExt)
    assert recovered is not None
    assert recovered.idx0 == 5
    assert recovered.splits == ["a", "b"]


def test_get_extension_missing_namespace_returns_none() -> None:
    """get_extension returns None when the namespace is absent."""
    record = _page()
    assert get_extension(record, "labeler", _PrepExt) is None


def test_extensions_survives_json_round_trip() -> None:
    """PageRecord with extensions serializes and validates via model_dump_json."""
    record = _page()
    set_extension(record, "labeler", _PrepExt(idx0=99, splits=["x"]))
    json_str = record.model_dump_json()
    restored = PageRecord.model_validate_json(json_str)
    assert restored.extensions["labeler"] == {"idx0": 99, "splits": ["x"]}
    recovered = get_extension(restored, "labeler", _PrepExt)
    assert recovered is not None
    assert recovered.idx0 == 99


def test_multiple_namespaces_coexist() -> None:
    """Multiple extension namespaces on the same record don't interfere."""
    record = _page()
    set_extension(record, "prep", _PrepExt(idx0=1))
    set_extension(record, "labeler", _PrepExt(idx0=2, splits=["q"]))
    prep = get_extension(record, "prep", _PrepExt)
    labeler = get_extension(record, "labeler", _PrepExt)
    assert prep is not None
    assert prep.idx0 == 1
    assert labeler is not None
    assert labeler.idx0 == 2
