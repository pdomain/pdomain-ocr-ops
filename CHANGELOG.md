# Changelog

## [0.7.1] - 2026-06-01

### Added

- `PageAggregate.set_extension(namespace, value)` -- event-backed extension
  mutation. Dumps `value` (a `pydantic.BaseModel`) to a JSON-able dict and
  records an `ExtensionSet` event, so the mutation is captured in the event
  store and survives replay and snapshotting.
- `PageAggregate._record_extension(namespace, data)` -- the `@event("ExtensionSet")`
  command method that applies the deep-copied dict to `record.extensions[namespace]`.

### Fixed

- Extension updates on an already-persisted `PageAggregate` were silently lost
  on reload: mutating `record.extensions` directly does not produce an event,
  so replay rebuilds the aggregate without the mutation. Post-persist extension
  changes must now go through `PageAggregate.set_extension`, which records the
  `ExtensionSet` event. Pre-persist construction via the free
  `set_extension(record, ns, value)` helper in `pdomain_ops.pages.extensions`
  is unaffected.

### Notes

- `ProjectRecord` has no `extensions` field; `ProjectAggregate` does not gain
  a `set_extension` command.
- The free `get_extension` / `set_extension` helpers in
  `pdomain_ops.pages.extensions` are unchanged; they remain the correct tools
  for pre-persist record construction.

## [0.7.0] - 2026-06-01

### Added

- `PageRecord.extensions` — namespaced `dict[str, dict[str, Any]]` field for
  app-specific JSON-able state (e.g. `extensions["labeler"]`, `extensions["prep"]`).
  Serializes through the existing `_PageRecordTranscoding` with no new transcoding
  required (design: page-server v2 §1).
- `pdomain_ops.pages.extensions` — `get_extension` / `set_extension` typed helpers
  for validated access to `PageRecord.extensions` namespaces; re-exported from
  `pdomain_ops.pages` and top-level `pdomain_ops`.
- `pdomain_ops.page_server` — shard/distribute-ready server model:
  `BlobBackend`, `PageStore`, `ShardRouter` `runtime_checkable` Protocols;
  `LocalPageStore` (single-process, `PagesApplication`-backed);
  `SingleShard` (trivial all-local `ShardRouter`);
  `ShardedPageStore` (project-routed composition over a shard map);
  `RemotePageStore` (stub — raises `NotImplementedError` until transport ships).
  Not re-exported at top level — lifecycle consumers only.
- `ProjectAggregate.remove_page(page_id)` — `@event("PageRemoved")` that removes a
  page from the project's ordered list; no-op if absent.

## [0.6.0] - 2026-06-01

### Added

- `pdomain_ops.pages` — universal page value models imported by every pd-*
  page consumer: `PageRecord`, `ProjectRecord`,
  `ProvenanceGraph`/`ProvenanceNode`/`DeadBranch`, `RotationSource`,
  `PageChangeEntry`, `PagePayload`, and `build_provenance_summary`. These are
  re-exported from the top-level `pdomain_ops` package.
- `pdomain_ops.blob_store.BlobStore` — content-addressed SHA256 blob store
  implementing `pdomain_book_tools.ocr.BlobStoreProtocol` (lifecycle consumers).
- `pdomain_ops.page_aggregate` — `PageAggregate`, `ProjectAggregate`, and
  `PagesApplication` (event sourcing; sqlite persistence + snapshotting). Not
  re-exported at top level, so `import pdomain_ops` stays free of the
  `eventsourcing` dependency.

### Changed

- Bumped the `pdomain-book-tools` floor to `>=0.17.0` (the Page
  operational-field split). Adopted its new
  `Document.from_image_ocr_via_doctr -> tuple[Document, int]` return shape.
- Added the `eventsourcing>=9.4,<10` dependency.

## [0.3.1] - 2026-05-30

### Added

- VRAM-aware batched OCR dispatch for the local `StageDispatcher`, including
  DocTR batch-size selection, a shared `run_doctr_batch` worker, sized predictor
  caching, and OOM backoff with CPU fallback.
- Batch request/response DTOs and a `StageDispatcher.run_ocr_batch` Protocol
  seam so future remote dispatchers can implement the same interface.

### Fixed

- Release metadata now points at `pdomain/pdomain-ops` after the repo rename.
- The release workflow now dispatches the `pdomain-ops` package name to
  `pdomain-index-pip`.
- The `pdomain-book-tools` dependency floor now requires `0.15.1`, the first
  release with batched DocTR APIs used by this package.

## [0.3.0] - 2026-05-27

### Breaking

- Distribution renamed from `pdomain-ocr-ops` to `pdomain-ops`. The library
  has outgrown its OCR-specific name — it houses suite plumbing, GPU dispatch,
  prefs, sibling-spawn, port helpers, and SPA bootstrap that are not OCR-specific.
- Python import path changed: `pdomain_ocr_ops` → `pdomain_ops`. All
  downstream consumers must update their dependency pin and imports.
- Console-script entry point renamed: `pdomain-ocr-ops-schemas` →
  `pdomain-ops-schemas`.

## [0.2.3] - 2026-05-24

### Added

- `find_available_port` helper and `register_self(actual_port=)` override for
  SPA bootstrap without EADDRINUSE crashes.

## [0.2.2] - 2026-05-22

### Fixed

- Add `# pyright: ignore[reportMissingTypeStubs]` inline on `pdomain_book_tools` import
  lines in `default_stages.py`. The basedpyright baseline stored column-position-based
  suppressions that matched Python 3.13 but not Python 3.12, leaving 2 unmatched
  warnings in CI. Inline ignores are stable across Python versions. Removed 2 now-
  redundant baseline entries (275 → 273). pdomain-book-tools is a wheel without `py.typed`
  (genuinely stubless), so this suppression is correct per workspace conventions.

## [0.2.1] - 2026-05-19

### Fixed

- Replace workspace-local `path = "../pdomain-book-tools"` source override with a git-rev
  reference. uv applies `[tool.uv.sources]` transitively when resolving dependencies
  of a git-pinned package; the relative path anchor constructed an invalid URL
  (`git+https://…pdomain-ops.git@v0.2.0#subdirectory=../pdomain-book-tools`) and failed.

## [0.2.0] - 2026-05-19

### Added

- GPU dispatch wire-shape types migrated from pdomain-prep-for-pgdp:
  `ProcessPageRequest`, `ProcessPageResponse`, `OcrPageRequest`, `OcrPageResponse`,
  `BatchJobItem`, `BatchJobResult`, `BatchProgressCb`, `GPUBackend` Protocol
  (`pdomain_ops.gpu.types`)
- `ModalStageDispatcher` (renamed from `ModalBackend`; legacy alias kept)
- `SharedContainerStageDispatcher` stub (renamed from `SharedContainerBackend`; legacy alias kept)
- `modal_app.py` — Modal deploy scaffold for `pdomain-ops` app name
- Optional dep group `modal = ["modal>=0.66"]`

## [0.1.0] - 2026-05-10

### Added (v0.1.0)

- Initial release: `StageDispatcher` / `LongJobRunner` Protocols
- `LocalStageDispatcher` + `LocalLongJobRunner` implementations
- `register_default_stages()` for DocTR and Tesseract OCR
- Suite plumbing: `mount_routes()`, `register_self()`, `prefs`, `sibling_spawn`, `desktop`
- `schemas.emit` for JSON Schema generation
