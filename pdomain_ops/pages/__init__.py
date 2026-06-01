"""Universal page value models — imported by every pd-* consumer of pages.

Pure pydantic. No eventsourcing, no blob/file I/O. The event store
(``pdomain_ops.page_aggregate``) and blob store (``pdomain_ops.blob_store``)
are separate, lifecycle-consumer-only modules.
"""

from pdomain_ops.pages.payload import PagePayload
from pdomain_ops.pages.provenance import DeadBranch, ProvenanceGraph, ProvenanceNode
from pdomain_ops.pages.records import (
    PageChangeEntry,
    PageRecord,
    ProjectRecord,
    RotationSource,
)
from pdomain_ops.pages.summary import build_provenance_summary

__all__ = [
    "DeadBranch",
    "PageChangeEntry",
    "PagePayload",
    "PageRecord",
    "ProjectRecord",
    "ProvenanceGraph",
    "ProvenanceNode",
    "RotationSource",
    "build_provenance_summary",
]
