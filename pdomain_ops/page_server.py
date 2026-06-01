"""Page server model — Protocols + Local impls, shard/distribute-ready.

Consumers depend only on these Protocols; the default is LocalPageStore +
SingleShard + BlobStore. Sharding = supply a ShardRouter + ShardedPageStore;
distribution = supply RemotePageStore / a networked BlobBackend. No consumer
change. Design: docs page-server v2 §2. Lifecycle consumers only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from pdomain_ops.page_aggregate import PageAggregate, PagesApplication, ProjectAggregate


@runtime_checkable
class BlobBackend(Protocol):
    """Protocol for a content-addressed blob store backend."""

    def write(self, data: bytes) -> str:
        """Write bytes; return the content-addressed hash."""
        ...

    def read(self, hash: str) -> bytes:
        """Return raw bytes for the given content hash."""
        ...

    def exists(self, hash: str) -> bool:
        """Return True if a blob with this hash exists."""
        ...

    def prune_orphans(self, live_refs: set[str]) -> list[str]:
        """Delete blobs not in live_refs; return the deleted hashes."""
        ...


@runtime_checkable
class PageStore(Protocol):
    """Protocol for a durable page + project aggregate store."""

    def save_page(self, aggregate: PageAggregate) -> None:
        """Persist a PageAggregate."""
        ...

    def get_page(self, page_id: UUID) -> PageAggregate:
        """Return the PageAggregate for page_id."""
        ...

    def save_project(self, aggregate: ProjectAggregate) -> None:
        """Persist a ProjectAggregate."""
        ...

    def get_project(self, project_id: UUID) -> ProjectAggregate:
        """Return the ProjectAggregate for project_id."""
        ...


@runtime_checkable
class ShardRouter(Protocol):
    """Protocol for mapping a project_id to a shard name."""

    def shard_for(self, project_id: UUID) -> str:
        """Return the shard identifier for the given project."""
        ...

    def shards(self) -> list[str]:
        """Return all known shard identifiers."""
        ...


class LocalPageStore:
    """Single-process PageStore backed by one PagesApplication (sqlite/POPO)."""

    def __init__(self, app: PagesApplication) -> None:
        """Wrap a PagesApplication as a PageStore."""
        self._app = app

    def save_page(self, aggregate: PageAggregate) -> None:
        """Persist a PageAggregate via the backing application."""
        self._app.save(aggregate)

    def get_page(self, page_id: UUID) -> PageAggregate:
        """Return the PageAggregate for page_id from the backing application."""
        return self._app.repository.get(page_id)  # type: ignore[return-value]

    def save_project(self, aggregate: ProjectAggregate) -> None:
        """Persist a ProjectAggregate via the backing application."""
        self._app.save(aggregate)

    def get_project(self, project_id: UUID) -> ProjectAggregate:
        """Return the ProjectAggregate for project_id from the backing application."""
        return self._app.repository.get(project_id)  # type: ignore[return-value]


class SingleShard:
    """Trivial router: everything maps to one shard. The no-op default."""

    def shard_for(self, project_id: UUID) -> str:
        """Return 'local' for any project_id."""
        del project_id
        return "local"

    def shards(self) -> list[str]:
        """Return ['local']."""
        return ["local"]


class ShardedPageStore:
    """Routes each project to a per-shard PageStore via a ShardRouter.

    Concrete composition over a ``{shard_id: PageStore}`` map. Page operations
    route by the page's project; callers pass ``project_id`` for page ops so
    routing stays project-local (split families co-locate). Cross-process
    transport is the only thing it lacks — that arrives via RemotePageStore.
    """

    def __init__(self, router: ShardRouter, stores: dict[str, PageStore]) -> None:
        """Compose a ShardRouter with a map of shard-id → PageStore."""
        self._router = router
        self._stores = stores

    def _store_for(self, project_id: UUID) -> PageStore:
        shard = self._router.shard_for(project_id)
        try:
            return self._stores[shard]
        except KeyError as exc:
            raise KeyError(f"no PageStore registered for shard {shard!r}") from exc

    def save_project(self, aggregate: ProjectAggregate) -> None:
        """Persist a ProjectAggregate to its assigned shard."""
        self._store_for(aggregate.id).save_project(aggregate)

    def get_project(self, project_id: UUID) -> ProjectAggregate:
        """Return the ProjectAggregate from its assigned shard."""
        return self._store_for(project_id).get_project(project_id)

    def save_page(self, project_id: UUID, aggregate: PageAggregate) -> None:
        """Persist a PageAggregate to the shard owning project_id."""
        self._store_for(project_id).save_page(aggregate)

    def get_page(self, project_id: UUID, page_id: UUID) -> PageAggregate:
        """Return the PageAggregate from the shard owning project_id."""
        return self._store_for(project_id).get_page(page_id)


class RemotePageStore:
    """PageStore stub for a networked shard (HTTP/gRPC to a page-server process).

    Present so consumers can depend on PageStore and swap this in later; every
    method raises NotImplementedError until the transport ships.
    """

    def __init__(self, endpoint: str) -> None:
        """Record the remote endpoint URL for future transport implementation."""
        self._endpoint = endpoint

    def save_page(self, aggregate: PageAggregate) -> None:
        """Not yet implemented — remote transport pending."""
        raise NotImplementedError("RemotePageStore transport not yet implemented")

    def get_page(self, page_id: UUID) -> PageAggregate:
        """Not yet implemented — remote transport pending."""
        raise NotImplementedError("RemotePageStore transport not yet implemented")

    def save_project(self, aggregate: ProjectAggregate) -> None:
        """Not yet implemented — remote transport pending."""
        raise NotImplementedError("RemotePageStore transport not yet implemented")

    def get_project(self, project_id: UUID) -> ProjectAggregate:
        """Not yet implemented — remote transport pending."""
        raise NotImplementedError("RemotePageStore transport not yet implemented")
