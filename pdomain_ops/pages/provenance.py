"""Provenance DAG: how a page was produced and what was done to it.

Each processing step (ingest, threshold, ocr, layout, reorganize, labeler,
proofread, export, …) is a node. Edges are ``parent_ids``: 0 parents = root,
1 = linear, 2+ = merge (e.g. reorganize consumes both layout and ocr).
Design spec §5.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, Field


class ProvenanceNode(BaseModel):
    """One processing step in the provenance DAG."""

    id: str
    source: str
    tool: str | None = None
    tool_version: str | None = None
    config: dict[str, Any] | None = None
    timestamp: datetime | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    blob_refs: list[str] = Field(default_factory=list)
    extra: dict[str, Any] | None = None
    parent_ids: list[str] = Field(default_factory=list)


class DeadBranch(BaseModel):
    """A superseded path awaiting pruning (design spec §5 dead branches)."""

    tip_id: str
    forked_from_id: str
    superseded_at: datetime
    retain_until: datetime


class ProvenanceGraph(BaseModel):
    """DAG of provenance nodes with an active head and head-history."""

    nodes: dict[str, ProvenanceNode] = Field(default_factory=dict)
    head_id: str = ""
    history: list[str] = Field(default_factory=list)
    dead_branches: list[DeadBranch] = Field(default_factory=list)

    @property
    def head(self) -> ProvenanceNode | None:
        """Return the current head node, or ``None`` if the graph is empty."""
        return self.nodes.get(self.head_id)

    def add_node(self, node: ProvenanceNode, *, advance_head: bool = True) -> None:
        """Insert a node. When ``advance_head`` is set, make it the new head
        and append it to the active-lineage history.
        """
        self.nodes[node.id] = node
        if advance_head:
            self.head_id = node.id
            self.history.append(node.id)
