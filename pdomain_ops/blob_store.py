"""Content-addressed blob store for all large page content (design spec §9).

Raw bytes keyed by SHA256 — content-type agnostic. Callers decide what to write
and how to pre-process it (images: ``oxipng.optimize_from_memory`` first; Page
JSON: ``page.to_dict()`` → UTF-8). Satisfies ``pdomain_book_tools.ocr.
BlobStoreProtocol`` (book-tools 0.17). Lifecycle consumers only.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


class BlobStore:
    """Per-project ``<project>/.pd-pages/blobs/<sha256>`` store."""

    def __init__(self, project_dir: Path) -> None:
        self._blobs_dir = Path(project_dir) / "blobs"
        self._blobs_dir.mkdir(parents=True, exist_ok=True)

    def write(self, data: bytes) -> str:
        """SHA256 the bytes, store if new (atomically), return the hash."""
        digest = sha256(data).hexdigest()
        path = self._blobs_dir / digest
        if not path.exists():
            tmp = path.with_name(f"{digest}.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # atomic on POSIX
        return digest

    def read(self, hash: str) -> bytes:
        """Return raw bytes for a blob identified by its SHA256 hash."""
        return (self._blobs_dir / hash).read_bytes()

    def exists(self, hash: str) -> bool:
        """Return True if a blob with the given SHA256 hash exists in the store."""
        return (self._blobs_dir / hash).is_file()

    def prune_orphans(self, live_refs: set[str]) -> list[str]:
        """Delete blobs whose hash is not in ``live_refs``. Returns deleted hashes."""
        deleted: list[str] = []
        for path in sorted(self._blobs_dir.iterdir()):
            if path.is_file() and not path.name.endswith(".tmp") and path.name not in live_refs:
                path.unlink()
                deleted.append(path.name)
        return deleted
