from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from pdomain_ops.blob_store import BlobStore

if TYPE_CHECKING:
    from pdomain_book_tools.ocr import BlobStoreProtocol


def test_write_returns_sha256_and_dedupes(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    data = b"the quick brown fox"
    h = store.write(data)
    assert h == sha256(data).hexdigest()
    assert store.write(data) == h  # idempotent re-write
    blobs = list((tmp_path / "blobs").iterdir())
    assert len(blobs) == 1


def test_read_round_trips(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    h = store.write(b"payload bytes")
    assert store.read(h) == b"payload bytes"


def test_exists(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    h = store.write(b"x")
    assert store.exists(h) is True
    assert store.exists("0" * 64) is False


def test_prune_orphans_deletes_unreferenced(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    keep = store.write(b"keep me")
    drop = store.write(b"drop me")
    deleted = store.prune_orphans(live_refs={keep})
    assert deleted == [drop]
    assert store.exists(keep) is True
    assert store.exists(drop) is False


def test_blobstore_satisfies_protocol(tmp_path: Path) -> None:
    # Structural conformance to the Plan-1 BlobStoreProtocol: this annotated
    # assignment makes basedpyright fail `make typecheck` if BlobStore ever
    # drifts from `read(self, hash: str) -> bytes`. Runtime asserts are secondary.
    store: BlobStoreProtocol = BlobStore(tmp_path)
    concrete = BlobStore(tmp_path)
    h = concrete.write(b"hi")
    assert store.read(h) == b"hi"
