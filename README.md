# pdomain-ocr-ops

Library + tiny CLI providing suite plumbing, shared prefs, and GPU dispatch adapters
for the pd-* OCR suite.

`pdomain-ocr-ops` is a library (not a daemon) that runs in-process inside each pd-* app's
FastAPI server. It provides:

- **Suite registry** (`installed.toml`): apps self-register so the AppShell launcher
  can discover and spawn siblings.
- **Shared UI prefs** (`ui-prefs.json`): cross-app theme, density, accent color,
  layer colors, and per-app extension blobs.
- **Sibling launcher**: spawn sibling apps by binary, poll `/healthz`, surface
  the URL.
- **Auth and storage adapters**: local-mode stubs; Phase 4 adds cloud backends.
- **GPU dispatch adapters**: `StageDispatcher` for short page-level calls,
  `LongJobRunner` (SQLite-backed) for training runs and batch jobs.

## Quick start

```python
from fastapi import FastAPI
from pdomain_ocr_ops import mount_routes

app = FastAPI()
mount_routes(app)  # adds /api/suite/*
```

## JSON Schema for downstream codegen

```sh
uv run python -m pdomain_ocr_ops.schemas > schemas.json
```

See `pdomain_ocr_ops/schemas/emit.py::PUBLIC_MODELS` for the registration surface.

## Design

Full spec: `docs/specs/2026-05-16-cross-cut-design.md` in the workspace.

Phase 1.7 (shipped in v0.2.0): `pdomain-prep-for-pgdp`'s GPU dispatch primitives
(`ModalStageDispatcher`, `SharedContainerStageDispatcher`, `register_default_stages()`)
migrated into `pdomain-ocr-ops`. The registry now ships DocTR and Tesseract OCR stages
by default via `register_default_stages()`.
