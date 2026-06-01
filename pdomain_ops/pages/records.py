"""Durable page/project records — the operational metadata stripped from Page.

``PageRecord`` owns everything ``Page`` shed in Plan 1: image path, source,
failure flag, rotation history, provenance, changelog. ``ProjectRecord`` owns
page ordering. Both are plain pydantic — zero eventsourcing imports
(design spec §7, §11).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import StrEnum
from pathlib import Path  # noqa: TC003
from typing import Any
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, Field

from pdomain_ops.pages.provenance import ProvenanceGraph  # noqa: TC001


class RotationSource(StrEnum):
    """How a page's rotation was determined (design spec §6)."""

    NONE = "none"
    AUTO = "auto"
    MANUAL = "manual"


class PageChangeEntry(BaseModel):
    """One entry in the per-page changelog — "git for pages" (design spec §7).

    ``changes`` is a flexible list of typed dict events for now; it becomes a
    discriminated union when proofreading ships (design spec §15).
    """

    provenance_node_id: str
    timestamp: datetime | None = None
    changes: list[dict[str, Any]] = Field(default_factory=list)


class PageRecord(BaseModel):
    """Durable, versioned record of a page's lifecycle metadata.

    ``page_id`` equals ``Page.page_id`` and ``PageAggregate.id`` — the stable
    identity of the physical page entity, not a content version.

    ``extensions`` is a namespaced dict for app-specific JSON-able state.
    Each app claims a unique key (e.g. ``"labeler"``, ``"prep"``) and stores
    a plain JSON-serialisable dict. Use ``get_extension``/``set_extension``
    from ``pdomain_ops.pages.extensions`` for typed access. The field
    serialises through ``_PageRecordTranscoding`` for free — no new
    transcoding is required (design: page-server v2 §1).
    """

    page_id: UUID
    page_index: int
    image_path: Path | None = None
    source: str = "ocr"
    ocr_failed: bool = False
    rotation_degrees: int = 0
    rotation_source: RotationSource = RotationSource.NONE
    provenance: ProvenanceGraph | None = None
    provenance_summary: str | None = None
    changelog: list[PageChangeEntry] = Field(default_factory=list)
    extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ProjectRecord(BaseModel):
    """Top-level organizing unit: a book/batch/job of pages processed together.

    ``page_ids`` is authoritative for ordering; ``PageRecord.page_index`` is a
    convenience cache (design spec §11).
    """

    project_id: UUID
    name: str
    page_ids: list[UUID] = Field(default_factory=list)
    source_dir: Path | None = None
    created_at: datetime | None = None
