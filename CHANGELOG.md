# Changelog

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
  (`git+https://…pdomain-ocr-ops.git@v0.2.0#subdirectory=../pdomain-book-tools`) and failed.

## [0.2.0] - 2026-05-19

### Added

- GPU dispatch wire-shape types migrated from pdomain-prep-for-pgdp:
  `ProcessPageRequest`, `ProcessPageResponse`, `OcrPageRequest`, `OcrPageResponse`,
  `BatchJobItem`, `BatchJobResult`, `BatchProgressCb`, `GPUBackend` Protocol
  (`pdomain_ocr_ops.gpu.types`)
- `ModalStageDispatcher` (renamed from `ModalBackend`; legacy alias kept)
- `SharedContainerStageDispatcher` stub (renamed from `SharedContainerBackend`; legacy alias kept)
- `modal_app.py` — Modal deploy scaffold for `pdomain-ocr-ops` app name
- Optional dep group `modal = ["modal>=0.66"]`

## [0.1.0] - 2026-05-10

### Added (v0.1.0)

- Initial release: `StageDispatcher` / `LongJobRunner` Protocols
- `LocalStageDispatcher` + `LocalLongJobRunner` implementations
- `register_default_stages()` for DocTR and Tesseract OCR
- Suite plumbing: `mount_routes()`, `register_self()`, `prefs`, `sibling_spawn`, `desktop`
- `schemas.emit` for JSON Schema generation
