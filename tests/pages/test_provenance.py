from datetime import UTC, datetime

from pdomain_ops.pages.provenance import DeadBranch, ProvenanceGraph, ProvenanceNode


def test_node_defaults_are_independent() -> None:
    a = ProvenanceNode(id="a", source="ingest")
    b = ProvenanceNode(id="b", source="ocr")
    a.blob_refs.append("hash1")
    a.parent_ids.append("a")
    assert b.blob_refs == []
    assert b.parent_ids == []


def test_node_carries_step_specific_config() -> None:
    node = ProvenanceNode(
        id="ocr_node",
        source="ocr",
        tool="doctr",
        tool_version="0.15.2",
        config={"model": "db_resnet50", "model_version": "v2", "threshold": 0.3},
        parent_ids=["thresh_node"],
    )
    assert node.config is not None
    assert node.config["model"] == "db_resnet50"
    assert node.parent_ids == ["thresh_node"]


def test_add_node_advances_head_and_history() -> None:
    graph = ProvenanceGraph()
    assert graph.head_id == ""
    graph.add_node(ProvenanceNode(id="n1", source="ingest"))
    graph.add_node(ProvenanceNode(id="n2", source="ocr", parent_ids=["n1"]))
    assert graph.head_id == "n2"
    assert graph.history == ["n1", "n2"]
    assert graph.head is not None
    assert graph.head.source == "ocr"
    assert set(graph.nodes) == {"n1", "n2"}


def test_add_node_without_advancing_head() -> None:
    graph = ProvenanceGraph()
    graph.add_node(ProvenanceNode(id="n1", source="ingest"))
    graph.add_node(ProvenanceNode(id="branch", source="ocr"), advance_head=False)
    assert graph.head_id == "n1"
    assert graph.history == ["n1"]
    assert "branch" in graph.nodes


def test_head_is_none_on_empty_graph() -> None:
    assert ProvenanceGraph().head is None


def test_dead_branch_round_trips_through_json() -> None:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    branch = DeadBranch(
        tip_id="old_tip", forked_from_id="fork", superseded_at=when, retain_until=when
    )
    graph = ProvenanceGraph(dead_branches=[branch])
    restored = ProvenanceGraph.model_validate_json(graph.model_dump_json())
    assert restored.dead_branches[0].tip_id == "old_tip"
