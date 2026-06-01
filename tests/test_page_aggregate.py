from pathlib import Path
from uuid import uuid4

from pdomain_ops.page_aggregate import PageAggregate, PagesApplication, ProjectAggregate
from pdomain_ops.pages import (
    PageRecord,
    ProjectRecord,
    ProvenanceNode,
    RotationSource,
)


def _sqlite_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        "SQLITE_DBNAME": str(tmp_path / "events.db"),
    }


def test_aggregate_id_equals_page_id() -> None:
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    assert agg.id == pid


def test_ocr_completed_updates_record_and_provenance() -> None:
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0, ocr_failed=True))
    agg.ocr_completed(
        provenance_node=ProvenanceNode(id="ocr", source="ocr", tool="doctr"),
        blob_refs=["content_hash", "image_hash"],
    )
    assert agg.record.ocr_failed is False
    assert agg.record.provenance is not None
    assert agg.record.provenance.head_id == "ocr"


def test_labeler_edited_appends_changelog() -> None:
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    agg.ocr_completed(provenance_node=ProvenanceNode(id="ocr", source="ocr"), blob_refs=["c"])
    agg.labeler_edited(
        provenance_node=ProvenanceNode(id="lbl", source="labeler", parent_ids=["ocr"]),
        changes=[{"type": "word_text", "word_id": "w1", "from": "thr", "to": "the"}],
    )
    assert agg.record.provenance is not None
    assert agg.record.provenance.head_id == "lbl"
    assert agg.record.changelog[-1].provenance_node_id == "lbl"
    assert agg.record.changelog[-1].changes[0]["to"] == "the"


def test_save_and_reload_replays_state(tmp_path: Path) -> None:
    app = PagesApplication(env=_sqlite_env(tmp_path))
    pid = uuid4()
    agg = PageAggregate(
        record=PageRecord(page_id=pid, page_index=4, rotation_source=RotationSource.AUTO)
    )
    agg.ocr_completed(
        provenance_node=ProvenanceNode(id="ocr", source="ocr", tool="doctr"),
        blob_refs=["content_hash"],
    )
    app.save(agg)

    reloaded: PageAggregate = app.repository.get(pid)
    assert reloaded.id == pid
    assert reloaded.record.rotation_source is RotationSource.AUTO
    assert reloaded.record.provenance is not None
    assert reloaded.record.provenance.head_id == "ocr"


def test_snapshotting_truncates_replay(tmp_path: Path) -> None:
    class SnappyApp(PagesApplication):
        snapshotting_intervals = {PageAggregate: 2}  # noqa: RUF012

    app = SnappyApp(env=_sqlite_env(tmp_path))
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    agg.ocr_completed(provenance_node=ProvenanceNode(id="ocr", source="ocr"), blob_refs=["c"])
    app.save(agg)  # version 2 → snapshot taken
    assert app.snapshots is not None
    snaps = list(app.snapshots.get(pid))
    assert len(snaps) >= 1
    assert app.repository.get(pid).record.provenance is not None


def test_project_aggregate_round_trips(tmp_path: Path) -> None:
    app = PagesApplication(env=_sqlite_env(tmp_path))
    proj_id = uuid4()
    p0, p1 = uuid4(), uuid4()
    proj = ProjectAggregate(record=ProjectRecord(project_id=proj_id, name="Book"))
    proj.add_page(page_id=p0, page_index=0)
    proj.add_page(page_id=p1, page_index=1)
    app.save(proj)

    reloaded: ProjectAggregate = app.repository.get(proj_id)
    assert reloaded.record.page_ids == [p0, p1]
