from uuid import uuid4

from pdomain_ops.pages.payload import PagePayload
from pdomain_ops.pages.provenance import ProvenanceGraph, ProvenanceNode
from pdomain_ops.pages.records import PageRecord


def test_payload_round_trips_through_json() -> None:
    pid = uuid4()
    graph = ProvenanceGraph()
    graph.add_node(ProvenanceNode(id="ocr", source="ocr", tool="doctr"))
    record = PageRecord(page_id=pid, page_index=2, provenance=graph)
    payload = PagePayload(
        page_id=pid,
        page_index=2,
        record=record,
        content={"type": "Page", "width": 1000, "height": 1500, "items": []},
        dims=(1000, 1500),
    )
    restored = PagePayload.model_validate_json(payload.model_dump_json())
    assert restored.page_id == pid
    assert restored.page_index == 2
    assert restored.record.provenance is not None
    assert restored.content["width"] == 1000
    assert restored.dims == (1000, 1500)
    assert restored.image_url is None


def test_payload_page_id_matches_record() -> None:
    pid = uuid4()
    payload = PagePayload(
        page_id=pid,
        page_index=0,
        record=PageRecord(page_id=pid, page_index=0),
        content={},
    )
    assert payload.page_id == payload.record.page_id
