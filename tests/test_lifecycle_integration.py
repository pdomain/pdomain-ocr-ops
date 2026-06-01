"""End-to-end lifecycle integration test - §9 "Loading a page" flow.

Exercises the full compose-and-reload loop:
  BlobStore.write -> PageAggregate -> PagesApplication(SQLite) -> reload -> BlobStore.read
  -> Page.from_dict -> PagePayload round-trip.

This is the contract test for Plan 2: if this breaks, downstream consumers (Plans 3-5)
break too. Any ergonomic awkwardness found here should be addressed before consumers land.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from uuid import UUID  # noqa: TC003

from pdomain_book_tools.ocr.page import Page

from pdomain_ops.blob_store import BlobStore
from pdomain_ops.page_aggregate import PageAggregate, PagesApplication
from pdomain_ops.pages import PagePayload, PageRecord, ProvenanceNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sqlite_env(db_path: Path) -> dict[str, str]:
    return {
        "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        "SQLITE_DBNAME": str(db_path),
    }


def _minimal_page() -> Page:
    """Return a minimal valid Page with known dims and no blocks.

    ``blocks`` must be passed explicitly (even as ``[]``): ``Page.__post_init__``
    rejects ``None`` — the field is an ``InitVar`` with no default, so omitting
    it or passing ``None`` raises TypeError.  Passing an empty list produces a
    valid page with no OCR content, which is the minimal valid construction.
    """
    return Page(width=800, height=1200, page_index=0, blocks=[])


# ---------------------------------------------------------------------------
# Main integration test
# ---------------------------------------------------------------------------


def test_lifecycle_load_a_page(tmp_path: Path) -> None:
    """Full §9 "Loading a page" flow.

    Steps:
      1. Construct a real book-tools Page.
      2. Blob-store its JSON content + a fake image blob.
      3. Create the aggregate, fire ocr_completed, persist via SQLite.
      4. Reload from the application repository.
      5. Retrieve the content hash from CURRENT STATE (provenance head blob_refs).
      6. Read from BlobStore → Page.from_dict → assert round-trip.
      7. Build PagePayload; round-trip through JSON; assert page_id survives.
      8. Assert image hash is retrievable (lazy-load ref).
    """

    # ------------------------------------------------------------------
    # Step 1: real book-tools Page
    # ------------------------------------------------------------------
    page = _minimal_page()
    page_id: UUID = page.page_id
    assert page.width == 800
    assert page.height == 1200

    # ------------------------------------------------------------------
    # Step 2: BlobStore — content + image
    # ------------------------------------------------------------------
    store = BlobStore(tmp_path)
    page_json_bytes = json.dumps(page.to_dict()).encode()
    content_hash = store.write(page_json_bytes)
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16  # fake PNG header
    image_hash = store.write(fake_image_bytes)

    assert store.exists(content_hash)
    assert store.exists(image_hash)

    # ------------------------------------------------------------------
    # Step 3: create aggregate + persist (SQLite)
    # ------------------------------------------------------------------
    db_path = tmp_path / "events.db"
    app = PagesApplication(env=_sqlite_env(db_path))

    record = PageRecord(page_id=page_id, page_index=0, source="ocr")
    agg = PageAggregate(record=record)
    agg.ocr_completed(
        provenance_node=ProvenanceNode(
            id="ocr",
            source="ocr",
            tool="doctr",
            blob_refs=[content_hash, image_hash],
        ),
        blob_refs=[content_hash, image_hash],
    )
    app.save(agg)

    # ------------------------------------------------------------------
    # Step 4: reload from application repository
    # ------------------------------------------------------------------
    reloaded = app.repository.get(page_id)

    # ------------------------------------------------------------------
    # Step 5: retrieve content hash from CURRENT STATE
    #
    # Key ergonomics question: does `reloaded.record.provenance.head.blob_refs`
    # carry the hashes we put on the ProvenanceNode?  If not, consumers have no
    # way to reach the content hash from current state without replaying events.
    # ------------------------------------------------------------------
    prov = reloaded.record.provenance
    assert prov is not None, "provenance graph must exist after ocr_completed"
    head = prov.head
    assert head is not None, "provenance head must be set after ocr_completed"
    assert head.id == "ocr"

    # THE CRITICAL CHECK: blob_refs on the head node (current state, not raw event)
    assert head.blob_refs == [content_hash, image_hash], (
        f"Expected blob_refs on provenance head node but got: {head.blob_refs!r}. "
        "The §9 reload→reconstruct flow requires blob_refs on the stored ProvenanceNode "
        "so consumers can reach content from current state without replaying raw events."
    )

    retrieved_content_hash = head.blob_refs[0]

    # ------------------------------------------------------------------
    # Step 6: read from BlobStore → Page.from_dict
    # ------------------------------------------------------------------
    raw_bytes = store.read(retrieved_content_hash)
    page_dict = json.loads(raw_bytes.decode())
    reconstructed = Page.from_dict(page_dict)

    assert reconstructed.page_id == page_id, (
        f"Reconstructed page_id {reconstructed.page_id} != original {page_id}"
    )
    assert reconstructed.width == page.width
    assert reconstructed.height == page.height
    assert reconstructed.page_index == page.page_index
    assert list(reconstructed.items) == list(page.items)

    # ------------------------------------------------------------------
    # Step 7: PagePayload round-trip through JSON
    # ------------------------------------------------------------------
    payload = PagePayload(
        page_id=page_id,
        page_index=reloaded.record.page_index,
        record=reloaded.record,
        content=reconstructed.to_dict(),
        dims=(page.width, page.height),
    )
    payload_json = payload.model_dump_json()
    payload_reloaded = PagePayload.model_validate_json(payload_json)

    assert payload_reloaded.page_id == page_id
    assert payload_reloaded.dims == (page.width, page.height)
    assert payload_reloaded.record.page_index == 0
    assert payload_reloaded.record.source == "ocr"
    # Provenance head survives the payload round-trip
    assert payload_reloaded.record.provenance is not None
    assert payload_reloaded.record.provenance.head_id == "ocr"

    # ------------------------------------------------------------------
    # Step 8: image hash retrievable (lazy-load ref)
    # ------------------------------------------------------------------
    assert store.exists(image_hash), "Image blob hash must be retrievable for lazy-load"

    # Also confirm image hash is on the provenance node (so consumers can find it)
    assert image_hash in head.blob_refs, (
        "Image hash must be in provenance head blob_refs so consumers can build lazy-load URLs"
    )


# ---------------------------------------------------------------------------
# Supplementary: verify blob_refs after in-memory round-trip too (no SQLite)
# ---------------------------------------------------------------------------


def test_provenance_head_blob_refs_survive_in_memory(tmp_path: Path) -> None:
    """Confirm blob_refs on the ProvenanceNode are preserved in the in-memory graph
    (no eventsourcing involved — pure pydantic/ProvenanceNode state test).
    """
    store = BlobStore(tmp_path)
    content_hash = store.write(b"test content")
    image_hash = store.write(b"fake image bytes")

    page = _minimal_page()
    record = PageRecord(page_id=page.page_id, page_index=0)
    agg = PageAggregate(record=record)
    agg.ocr_completed(
        provenance_node=ProvenanceNode(
            id="ocr",
            source="ocr",
            blob_refs=[content_hash, image_hash],
        ),
        blob_refs=[content_hash, image_hash],
    )

    head = agg.record.provenance.head  # type: ignore[union-attr]
    assert head is not None
    assert head.blob_refs == [content_hash, image_hash]


# ---------------------------------------------------------------------------
# Supplementary: PagesApplication restarts cleanly from the same DB file
# ---------------------------------------------------------------------------


def test_pages_application_restart_from_db(tmp_path: Path) -> None:
    """A new PagesApplication instance pointing at the same SQLite DB file
    should be able to replay and return the same aggregate state.

    This mimics a process restart — critical for durable storage contract.
    """
    db_path = tmp_path / "events.db"
    store = BlobStore(tmp_path)
    content_hash = store.write(b"page content bytes")

    page = _minimal_page()
    page_id = page.page_id

    # First instance — save
    app1 = PagesApplication(env=_sqlite_env(db_path))
    record = PageRecord(page_id=page_id, page_index=0, source="ocr")
    agg = PageAggregate(record=record)
    agg.ocr_completed(
        provenance_node=ProvenanceNode(id="ocr", source="ocr", blob_refs=[content_hash]),
        blob_refs=[content_hash],
    )
    app1.save(agg)

    # Second instance — independent Python object, same DB
    app2 = PagesApplication(env=_sqlite_env(db_path))
    reloaded = app2.repository.get(page_id)

    assert reloaded.id == page_id
    assert reloaded.record.source == "ocr"
    prov = reloaded.record.provenance
    assert prov is not None
    assert prov.head is not None
    assert prov.head.blob_refs == [content_hash]
