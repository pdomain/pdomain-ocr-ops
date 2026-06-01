"""Human-readable provenance one-liner.

Replaces ``_build_provenance_summary`` in labeler-spa's ``api/pages.py``
(design spec §7). Assembled at payload-build time — not auto-updated on graph
mutation; callers set ``PageRecord.provenance_summary`` when they build a payload.
"""

from __future__ import annotations

from pdomain_ops.pages.provenance import ProvenanceGraph  # noqa: TC001


def build_provenance_summary(graph: ProvenanceGraph | None) -> str:
    """Render the active lineage as ``source(tool) → source(tool) → …``.

    Walks ``graph.history`` (the ordered head-over-time list); falls back to the
    current head when history is empty. Unknown ids are skipped. Returns
    ``"no provenance"`` for a missing or empty graph.
    """
    if graph is None or not graph.nodes:
        return "no provenance"
    chain = graph.history or ([graph.head_id] if graph.head_id else [])
    labels: list[str] = []
    for node_id in chain:
        node = graph.nodes.get(node_id)
        if node is None:
            continue
        labels.append(node.source if node.tool is None else f"{node.source}({node.tool})")
    return " → ".join(labels) if labels else "no provenance"
