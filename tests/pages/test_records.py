from pathlib import Path
from uuid import uuid4

from pdomain_ops.pages.provenance import ProvenanceGraph, ProvenanceNode
from pdomain_ops.pages.records import (
    PageChangeEntry,
    PageRecord,
    ProjectRecord,
    RotationSource,
)


def test_rotation_source_is_str_enum() -> None:
    assert RotationSource.NONE == "none"
    assert RotationSource.AUTO == "auto"
    assert RotationSource.MANUAL == "manual"
    assert f"{RotationSource.AUTO}" == "auto"


def test_page_record_minimal_defaults() -> None:
    pid = uuid4()
    rec = PageRecord(page_id=pid, page_index=0)
    assert rec.page_id == pid
    assert rec.source == "ocr"
    assert rec.ocr_failed is False
    assert rec.rotation_degrees == 0
    assert rec.rotation_source is RotationSource.NONE
    assert rec.provenance is None
    assert rec.changelog == []


def test_page_record_changelog_defaults_independent() -> None:
    a = PageRecord(page_id=uuid4(), page_index=0)
    b = PageRecord(page_id=uuid4(), page_index=1)
    a.changelog.append(PageChangeEntry(provenance_node_id="n", changes=[]))
    assert b.changelog == []


def test_page_record_round_trips_with_provenance() -> None:
    graph = ProvenanceGraph()
    graph.add_node(ProvenanceNode(id="ocr", source="ocr", tool="doctr"))
    rec = PageRecord(
        page_id=uuid4(),
        page_index=3,
        image_path=Path("/scans/page_0003.png"),
        rotation_degrees=90,
        rotation_source=RotationSource.AUTO,
        provenance=graph,
        changelog=[
            PageChangeEntry(
                provenance_node_id="ocr",
                changes=[{"type": "word_text", "word_id": "b0l2w3", "from": "thr", "to": "the"}],
            )
        ],
    )
    restored = PageRecord.model_validate_json(rec.model_dump_json())
    assert restored.page_id == rec.page_id
    assert restored.rotation_source is RotationSource.AUTO
    assert restored.provenance is not None
    assert restored.provenance.head_id == "ocr"
    assert restored.changelog[0].changes[0]["to"] == "the"


def test_project_record_orders_pages() -> None:
    p0, p1 = uuid4(), uuid4()
    proj = ProjectRecord(project_id=uuid4(), name="Book", page_ids=[p0, p1])
    assert proj.page_ids == [p0, p1]
    assert proj.source_dir is None
