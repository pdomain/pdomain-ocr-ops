"""Universal portable page format (design spec §12).

Used for CLI/simple-gui JSON output, API responses, and cross-service transfer
(import a CLI ``PagePayload`` into the labeler's event store). Assembled at
write/response time — never stored directly; the event store + blob store are
the durable form for lifecycle consumers.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel

from pdomain_ops.pages.records import PageRecord  # noqa: TC001


class PagePayload(BaseModel):
    """Portable, self-contained page snapshot for serialization and transfer."""

    page_id: UUID
    page_index: int
    record: PageRecord
    content: dict[str, Any]
    image_url: str | None = None
    dims: tuple[int, int] | None = None
