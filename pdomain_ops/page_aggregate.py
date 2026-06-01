"""Event-sourced wrappers around PageRecord/ProjectRecord (design spec §8, §11).

``PageAggregate`` / ``ProjectAggregate`` use ``eventsourcing``'s ``@event``
declarative style: each decorated command method's body is the apply logic,
re-run deterministically on replay. ``PagesApplication`` registers pydantic
transcodings so events carrying ``PageRecord`` / ``ProvenanceNode`` /
``ProjectRecord`` serialize, and enables snapshotting. Lifecycle consumers only.

Command-argument ownership contract
-----------------------------------
``@event`` captures a command method's arguments *by reference* into the stored
event at call time. Callers MUST treat any argument passed to a command method
(``provenance_node``, ``changes``, ``blob_refs``, ``page_ids``, ``record``) as
owned by the event afterward and must not mutate it between the call and
``app.save()`` -- doing so would rewrite recorded history and can make a reloaded
aggregate diverge from the in-memory one. This is standard event-sourcing
discipline: events own their data. The aggregate's *own* state is already
isolated (``__init__`` deep-copies ``record``; ``PageChangeEntry`` copies
``changes`` on construction), so normal "build args -> fire -> save" usage is safe.

Extension mutation discipline
------------------------------
``PageRecord.extensions`` must **not** be mutated directly on an already-persisted
aggregate (i.e. after the first ``app.save()``). Direct mutation is not captured
as an event and is silently lost on the next reload / replay. Use
``PageAggregate.set_extension(namespace, value)`` instead -- it records an
``ExtensionSet`` event so the mutation survives replay and snapshotting.

The free ``set_extension(record, namespace, value)`` helper in
``pdomain_ops.pages.extensions`` remains the correct tool for pre-save record
construction (before the aggregate is first persisted).

``ocr_completed`` and ``preprocess`` backfill behaviour
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Both commands accept a ``blob_refs`` kwarg alongside ``provenance_node``.
Per design spec §8, ``blob_refs`` is the canonical location for
``[page_content_hash, source_image_hash, ...]``. When the caller supplies
``blob_refs`` but omits them from the node itself, both commands backfill the
node's ``blob_refs`` from the kwarg via ``_with_blob_refs`` (non-mutating
``model_copy``) before storing the node in the provenance graph. This means
either location works: a node that already carries ``blob_refs`` wins (existing
callers are unaffected), while a node with empty ``blob_refs`` inherits them
from the kwarg. Because the event stores both ``provenance_node`` *and*
``blob_refs`` as separate fields, the merge recomputes identically on replay --
replay determinism is preserved.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event
from eventsourcing.persistence import Transcoding

if TYPE_CHECKING:
    from pydantic import BaseModel

from pdomain_ops.pages import PageChangeEntry, PageRecord, ProjectRecord, ProvenanceNode
from pdomain_ops.pages.provenance import ProvenanceGraph


def _with_blob_refs(node: ProvenanceNode, blob_refs: list[str]) -> ProvenanceNode:
    """Return a node carrying blob_refs: the node's own if present, else the event's.

    Non-mutating (``model_copy``) so the stored event's node is never aliased.
    Replay-deterministic: the event stores both ``provenance_node`` and ``blob_refs``
    as separate fields, so this merge recomputes the same result on every replay.
    """
    if node.blob_refs:
        return node
    return node.model_copy(update={"blob_refs": list(blob_refs)})


class PageAggregate(Aggregate):
    """Lifecycle of a single page. ``id`` == ``record.page_id``."""

    @event("ImageIngested")
    def __init__(self, record: PageRecord) -> None:
        # Deep-copy so the aggregate's state is independent of the caller's object.
        # Without this, mutations before app.save() contaminate the stored event.
        self._record = record.model_copy(deep=True)

    @staticmethod
    def create_id(record: PageRecord) -> UUID:  # ties aggregate id to page_id
        """Return the stable aggregate ID from the page record."""
        return record.page_id

    @property
    def record(self) -> PageRecord:
        """The current state of the page."""
        return self._record

    def _apply_node(self, node: ProvenanceNode) -> None:
        graph = self._record.provenance or ProvenanceGraph()
        graph.add_node(node)
        self._record.provenance = graph

    @event("ImagePreprocessed")
    def preprocess(self, provenance_node: ProvenanceNode, blob_refs: list[str]) -> None:
        """Record image preprocessing and its provenance."""
        self._apply_node(_with_blob_refs(provenance_node, blob_refs))

    @event("OcrCompleted")
    def ocr_completed(self, provenance_node: ProvenanceNode, blob_refs: list[str]) -> None:
        """Record completed OCR: clear the failure flag and add the OCR provenance node."""
        self._record.ocr_failed = False
        self._apply_node(_with_blob_refs(provenance_node, blob_refs))

    @event("GtMapped")
    def gt_mapped(self, provenance_node: ProvenanceNode) -> None:
        """Record that ground-truth was mapped for this page."""
        self._apply_node(provenance_node)

    @event("LabelerEdited")
    def labeler_edited(
        self, provenance_node: ProvenanceNode, changes: list[dict[str, Any]]
    ) -> None:
        """Record a labeler edit session and append changes to the changelog."""
        self._apply_node(provenance_node)
        self._record.changelog.append(
            PageChangeEntry(provenance_node_id=provenance_node.id, changes=changes)
        )

    @event("Exported")
    def exported(self, provenance_node: ProvenanceNode) -> None:
        """Record that this page was exported."""
        self._apply_node(provenance_node)

    def set_extension(self, namespace: str, value: BaseModel) -> None:
        """Set or replace an extension namespace on this page, recording an event.

        Dumps ``value`` to a JSON-able dict (via ``model_dump(mode="json")``) and
        fires an ``ExtensionSet`` event so the mutation is captured in the event
        store and survives replay and snapshotting.

        Use this method for **post-persist** extension updates (i.e. after the
        aggregate has already been saved). For pre-save record construction use
        the free ``set_extension(record, namespace, value)`` helper in
        ``pdomain_ops.pages.extensions``.
        """
        self._record_extension(namespace=namespace, data=value.model_dump(mode="json"))

    @event("ExtensionSet")
    def _record_extension(self, namespace: str, data: dict[str, Any]) -> None:
        """Apply an ExtensionSet event: store data under namespace (deep-copied).

        Deep-copy guards the by-reference footgun: ``@event`` stores args by
        reference, so without the copy a subsequent mutation of ``data`` by the
        caller would corrupt the stored event. On replay the event carries the
        already-serialized dict copy, so replay is deterministic.
        """
        self._record.extensions[namespace] = deepcopy(data)


class ProjectAggregate(Aggregate):
    """Lifecycle of a project (book/batch/job). ``id`` == ``record.project_id``."""

    @event("ProjectCreated")
    def __init__(self, record: ProjectRecord) -> None:
        # Deep-copy so the aggregate's state is independent of the caller's object.
        # Without this, mutations before app.save() contaminate the stored event.
        self._record = record.model_copy(deep=True)

    @staticmethod
    def create_id(record: ProjectRecord) -> UUID:
        """Return the stable aggregate ID from the project record."""
        return record.project_id

    @property
    def record(self) -> ProjectRecord:
        """The current state of the project."""
        return self._record

    @event("PageAdded")
    def add_page(self, page_id: UUID, page_index: int) -> None:
        """Append a page to the project's ordered page list."""
        del page_index
        self._record.page_ids.append(page_id)

    @event("PageReordered")
    def reorder_pages(self, page_ids: list[UUID]) -> None:
        """Replace the project's page ordering with the given sequence."""
        self._record.page_ids = list(page_ids)

    @event("PageRemoved")
    def remove_page(self, page_id: UUID) -> None:
        """Remove a page from the project's ordered list (no-op if absent)."""
        if page_id in self._record.page_ids:
            self._record.page_ids.remove(page_id)

    @event("ProjectExported")
    def exported(self, provenance_node: ProvenanceNode) -> None:
        """Record that the project was exported."""
        del provenance_node


class _PageRecordTranscoding(Transcoding):
    type = PageRecord
    name = "pdomain_ops.PageRecord"

    def encode(self, obj: PageRecord) -> dict[str, Any]:
        return obj.model_dump(mode="json")

    def decode(self, data: dict[str, Any]) -> PageRecord:
        return PageRecord.model_validate(data)


class _ProjectRecordTranscoding(Transcoding):
    type = ProjectRecord
    name = "pdomain_ops.ProjectRecord"

    def encode(self, obj: ProjectRecord) -> dict[str, Any]:
        return obj.model_dump(mode="json")

    def decode(self, data: dict[str, Any]) -> ProjectRecord:
        return ProjectRecord.model_validate(data)


class _ProvenanceNodeTranscoding(Transcoding):
    type = ProvenanceNode
    name = "pdomain_ops.ProvenanceNode"

    def encode(self, obj: ProvenanceNode) -> dict[str, Any]:
        return obj.model_dump(mode="json")

    def decode(self, data: dict[str, Any]) -> ProvenanceNode:
        return ProvenanceNode.model_validate(data)


class PagesApplication(Application[UUID]):
    """Event-store application for page + project aggregates.

    Default persistence is in-memory POPO; pass ``env={"PERSISTENCE_MODULE":
    "eventsourcing.sqlite", "SQLITE_DBNAME": "<project>/.pd-pages/events.db"}``
    for durable storage. Migrate to Postgres by swapping the env (design spec §8).
    """

    snapshotting_intervals = {  # noqa: RUF012
        PageAggregate: 20,
        ProjectAggregate: 20,
    }

    def register_transcodings(self, transcoder: Any) -> None:
        """Register pydantic model transcodings for page and project types."""
        super().register_transcodings(transcoder)
        transcoder.register(_PageRecordTranscoding())
        transcoder.register(_ProjectRecordTranscoding())
        transcoder.register(_ProvenanceNodeTranscoding())
