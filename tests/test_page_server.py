"""Tests for pdomain_ops.page_server — Protocols + Local impls."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from pdomain_ops.blob_store import BlobStore
from pdomain_ops.page_aggregate import PageAggregate, PagesApplication, ProjectAggregate
from pdomain_ops.page_server import (
    BlobBackend,
    LocalPageStore,
    PageStore,
    RemotePageStore,
    ShardedPageStore,
    ShardRouter,
    SingleShard,
)
from pdomain_ops.pages import PageRecord, ProjectRecord

if TYPE_CHECKING:
    from pathlib import Path


def _sqlite_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        "SQLITE_DBNAME": str(tmp_path / "events.db"),
    }


# ---------------------------------------------------------------------------
# BlobBackend Protocol
# ---------------------------------------------------------------------------


def test_blob_store_satisfies_blob_backend(tmp_path: Path) -> None:
    """BlobStore is a structural BlobBackend (runtime_checkable isinstance)."""
    store = BlobStore(tmp_path)
    assert isinstance(store, BlobBackend)


def test_blob_backend_write_read_round_trip(tmp_path: Path) -> None:
    """BlobStore write+read round-trip via a BlobBackend-typed variable."""
    backend: BlobBackend = BlobStore(tmp_path)
    data = b"hello blob"
    digest = backend.write(data)
    assert backend.read(digest) == data
    assert backend.exists(digest)


# ---------------------------------------------------------------------------
# PageStore Protocol + LocalPageStore
# ---------------------------------------------------------------------------


def test_local_page_store_satisfies_page_store(tmp_path: Path) -> None:
    """LocalPageStore is a structural PageStore (runtime_checkable isinstance)."""
    app = PagesApplication(env=_sqlite_env(tmp_path))
    store = LocalPageStore(app)
    assert isinstance(store, PageStore)


def test_local_page_store_round_trips_page_aggregate(tmp_path: Path) -> None:
    """LocalPageStore save_page → get_page round-trips a PageAggregate."""
    app = PagesApplication(env=_sqlite_env(tmp_path))
    store = LocalPageStore(app)
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=3))
    store.save_page(agg)

    recovered: PageAggregate = store.get_page(pid)
    assert recovered.id == pid
    assert recovered.record.page_index == 3


def test_local_page_store_round_trips_project_aggregate(tmp_path: Path) -> None:
    """LocalPageStore save_project → get_project round-trips a ProjectAggregate."""
    app = PagesApplication(env=_sqlite_env(tmp_path))
    store = LocalPageStore(app)
    proj_id = uuid4()
    p0 = uuid4()
    proj = ProjectAggregate(record=ProjectRecord(project_id=proj_id, name="TestBook"))
    proj.add_page(page_id=p0, page_index=0)
    store.save_project(proj)

    recovered: ProjectAggregate = store.get_project(proj_id)
    assert recovered.id == proj_id
    assert p0 in recovered.record.page_ids


# ---------------------------------------------------------------------------
# ShardRouter Protocol + SingleShard
# ---------------------------------------------------------------------------


def test_single_shard_satisfies_shard_router(tmp_path: Path) -> None:
    """SingleShard is a structural ShardRouter."""
    router = SingleShard()
    assert isinstance(router, ShardRouter)


def test_single_shard_routes_all_to_local() -> None:
    """SingleShard routes any project_id to 'local'."""
    router = SingleShard()
    assert router.shard_for(uuid4()) == "local"
    assert router.shard_for(uuid4()) == "local"


def test_single_shard_shards_list() -> None:
    """SingleShard.shards() returns ['local']."""
    assert SingleShard().shards() == ["local"]


# ---------------------------------------------------------------------------
# ShardedPageStore
# ---------------------------------------------------------------------------


def test_sharded_page_store_round_trips_project(tmp_path: Path) -> None:
    """ShardedPageStore with SingleShard + LocalPageStore round-trips a project."""
    app = PagesApplication(env=_sqlite_env(tmp_path))
    local = LocalPageStore(app)
    sharded = ShardedPageStore(router=SingleShard(), stores={"local": local})

    proj_id = uuid4()
    proj = ProjectAggregate(record=ProjectRecord(project_id=proj_id, name="Sharded"))
    sharded.save_project(proj)

    recovered = sharded.get_project(proj_id)
    assert recovered.id == proj_id


def test_sharded_page_store_round_trips_page(tmp_path: Path) -> None:
    """ShardedPageStore page ops route via project_id."""
    app = PagesApplication(env=_sqlite_env(tmp_path))
    local = LocalPageStore(app)
    sharded = ShardedPageStore(router=SingleShard(), stores={"local": local})

    proj_id = uuid4()
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=7))
    sharded.save_page(project_id=proj_id, aggregate=agg)

    recovered = sharded.get_page(project_id=proj_id, page_id=pid)
    assert recovered.id == pid
    assert recovered.record.page_index == 7


def test_sharded_page_store_unknown_shard_raises(tmp_path: Path) -> None:
    """ShardedPageStore raises KeyError for unknown shard."""
    app = PagesApplication(env=_sqlite_env(tmp_path))
    local = LocalPageStore(app)
    sharded = ShardedPageStore(router=SingleShard(), stores={"other": local})  # "local" missing

    with pytest.raises(KeyError, match="local"):
        sharded.get_project(uuid4())


# ---------------------------------------------------------------------------
# RemotePageStore
# ---------------------------------------------------------------------------


def test_remote_page_store_satisfies_page_store() -> None:
    """RemotePageStore is a structural PageStore (runtime_checkable isinstance)."""
    remote = RemotePageStore("http://example.com")
    assert isinstance(remote, PageStore)


def test_remote_page_store_raises_not_implemented() -> None:
    """Every RemotePageStore method raises NotImplementedError."""
    remote = RemotePageStore("http://example.com")
    pid = uuid4()
    proj_id = uuid4()
    dummy_page = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    dummy_proj = ProjectAggregate(record=ProjectRecord(project_id=proj_id, name="x"))
    with pytest.raises(NotImplementedError):
        remote.save_page(dummy_page)
    with pytest.raises(NotImplementedError):
        remote.get_page(pid)
    with pytest.raises(NotImplementedError):
        remote.save_project(dummy_proj)
    with pytest.raises(NotImplementedError):
        remote.get_project(proj_id)
