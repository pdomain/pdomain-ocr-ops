from pdomain_ops.pages.provenance import ProvenanceGraph, ProvenanceNode
from pdomain_ops.pages.summary import build_provenance_summary


def test_summary_of_none_graph() -> None:
    assert build_provenance_summary(None) == "no provenance"


def test_summary_of_empty_graph() -> None:
    assert build_provenance_summary(ProvenanceGraph()) == "no provenance"


def test_summary_walks_active_lineage_with_tools() -> None:
    graph = ProvenanceGraph()
    graph.add_node(ProvenanceNode(id="i", source="ingest", tool="prep-for-pgdp"))
    graph.add_node(ProvenanceNode(id="t", source="threshold", tool="prep-for-pgdp"))
    graph.add_node(ProvenanceNode(id="o", source="ocr", tool="doctr"))
    graph.add_node(ProvenanceNode(id="r", source="reorganize"))
    graph.add_node(ProvenanceNode(id="l", source="labeler", tool="labeler-spa"))
    assert build_provenance_summary(graph) == (
        "ingest(prep-for-pgdp) → threshold(prep-for-pgdp) → ocr(doctr) "
        "→ reorganize → labeler(labeler-spa)"
    )


def test_summary_skips_unknown_head_history_ids() -> None:
    graph = ProvenanceGraph()
    graph.add_node(ProvenanceNode(id="o", source="ocr", tool="doctr"))
    graph.history.append("ghost")
    assert build_provenance_summary(graph) == "ocr(doctr)"


def test_summary_falls_back_to_head_when_history_empty() -> None:
    """Graph with a node and head_id set but history == [] falls back to the head."""
    node = ProvenanceNode(id="n", source="ocr", tool="doctr")
    graph = ProvenanceGraph(nodes={"n": node}, head_id="n")
    # bypass add_node so history stays empty
    assert graph.history == []
    assert build_provenance_summary(graph) == "ocr(doctr)"
