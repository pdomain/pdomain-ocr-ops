---
repo: ConcaveTrillion/ocr-container-meta
plan_type: cross-cut
status: draft
synced: never
---

# Batched OCR Dispatch — VRAM-aware GPU batching with OOM backoff

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking. This plan spans three repos — implement bottom-up
> (pdomain-book-tools → pdomain-ops → consumers).

**Goal:** Replace the current per-page sequential/concurrent OCR loop with a single
**chunked, batched** dispatch path that (a) exploits DocTR's real GPU batching, (b)
auto-sizes the batch from available VRAM/RAM, (c) backs off and retries on OOM, and
(d) isolates failures so one bad chunk never loses the whole job. The dispatch
mechanics live in **pdomain-ops** because every OCR consumer (simple-gui, pdomain-ocr-cli,
labeler-spa, trainer-spa) routes through the same `StageDispatcher`, so this pattern is
shared infrastructure, not an app concern.

---

## Background — how DocTR batching actually works

Investigated against DocTR 1.0.2 source (installed under the book-tools venv):

- `OCRPredictor.forward(pages)` (`doctr/models/predictor/pytorch.py:81`) hands the whole
  page list to the detection predictor, and (line 133) flattens **all** word-crops from
  **all** pages into a single recognition call.
- `DetectionPredictor.forward` (`doctr/models/detection/predictor/pytorch.py:52-59`):
  `pre_processor(pages)` → `PreProcessor.batch_inputs` does
  `torch.stack(samples[i*bs:(i+1)*bs], dim=0)` — it **stacks images into one batched
  tensor**, then `self.model(batch)` runs them through the device in **one forward pass**
  (data-parallel across the batch dim). This is genuine GPU batching, **not** a Python
  loop over images.
- Default batch sizes (`doctr/models/zoo.py:24-25`): **`det_bs = 2`**, **`reco_bs = 128`**.

**Implications:**

1. **Peak VRAM is set by `det_bs`, not by how many pages you pass.** A list of N pages
   becomes `ceil(N/det_bs)` sequential forward passes, each of size ≤ `det_bs`.
   Therefore: *splitting our page list does not reduce peak VRAM — only lowering `det_bs`
   does.*
2. **Detection is the batching win.** Today book-tools calls `predictor([rgb])` with a
   **single** image, so detection runs a batch of 1 even though `det_bs=2` could hold 2.
   Passing multiple pages lets DocTR batch detection forward passes.
3. **Recognition is already saturated per page.** A book page usually has >128 word-crops,
   so `reco_bs=128` is near-full from a single page; raising `reco_bs` only helps when
   batching **many pages' crops together**, and crops are tiny so it is not VRAM-bound —
   `reco_bs` is bounded by *crop supply*, not memory.

---

## Design

### Two distinct knobs (keep them separate)

| Knob | Layer | Bounds | Purpose |
|---|---|---|---|
| `chunk_size` (a.k.a. `batch_pages`) | consumer / dispatcher | failure-isolation, progress, retry-blast-radius | how many pages per `predictor()` call |
| `det_bs` | book-tools predictor build | **VRAM** | DocTR internal detection forward-batch; the OOM lever |
| `reco_bs` | book-tools predictor build | crop supply (high VRAM ceiling) | DocTR internal recognition forward-batch |

A chunk of `C` pages at `det_bs=B` runs `ceil(C/B)` internal detection passes. Typically
`chunk_size ≥ det_bs`.

### Option B — unified batched path, no concurrency

Both CPU and GPU use the **same** chunked-batched code path; device-specific sizing and
backoff differ:

- **GPU:** `det_bs` from free VRAM; CUDA OOM → halve `det_bs`, rebuild predictor, retry
  the chunk; floor (det_bs=1 still OOM) → CPU fallback for that chunk.
- **CPU:** `det_bs` modest (torch intra-op threads parallelize the stacked tensor);
  `MemoryError` backoff (rare at 67 GB) with the same halve-and-retry shape. **No asyncio
  worker-pool concurrency** — concurrent batched calls would each spawn torch threads and
  oversubscribe cores (the thermal-spike risk on hybrid CPUs). One batched call lets torch
  use all cores cleanly.

This **replaces** the Phase-1 per-page asyncio concurrency in simple-gui's `run_project`
(commit `4e03f8b`). The user-facing `parallel_pages` field is renamed to **`batch_pages`**
(pages per call); it no longer means concurrency.

### Chunked processing — failure isolation

```python
for chunk in chunks(pages, chunk_size):
    try:
        results = run_batched_with_oom_backoff(chunk)   # halve det_bs → retry → CPU floor
        write_results(results)                          # per-page sidecar/txt/output mirror
        mark_chunk_succeeded(chunk)
    except Exception as e:                              # non-OOM, or even CPU-floor failure
        logger.exception(...)
        mark_pages_failed(chunk, error=str(e))          # only THIS chunk's pages
        # do NOT abort — continue to the next chunk
    persist_status(); await status_callback(...)        # progress per chunk
```

Three nested resilience levels:
1. **Inside a chunk:** CUDA OOM → halve `det_bs`, rebuild, retry; floor → CPU fallback.
2. **Per chunk:** any other exception fails only that chunk's pages; the loop continues.
3. **Progress:** a status callback per chunk; a late failure never erases earlier success.

Geometric backoff (8→4→2→1) reaches a safe size in log steps. Retries are idempotent (OCR
is pure), so re-running a chunk is safe; smaller `chunk_size` bounds retry recompute waste.

### OOM detection

```python
def _is_oom(e: BaseException) -> bool:
    if isinstance(e, torch.cuda.OutOfMemoryError):   # torch >= 1.13
        return True
    return isinstance(e, RuntimeError) and "out of memory" in str(e).lower()
```
On CPU, also treat `MemoryError` as the backoff trigger. **Re-raise anything that is not
OOM** so real bugs surface. Before rebuilding, `del` the old predictor reference and call
`torch.cuda.empty_cache()` so the failed allocation's reserved blocks are released —
otherwise the retry OOMs again.

---

## Per-layer changes

### 1. pdomain-book-tools — expose batch sizes (pure DocTR pass-through)

`_assemble_doctr_predictor` already builds via DocTR's **public** factories
(`ocr_predictor`, `detection_predictor`, `recognition_predictor`), all of which accept the
batch-size kwargs. **No DocTR fork.**

- [ ] Add `det_bs: int = 2, reco_bs: int = 128` params to
      `get_finetuned_torch_doctr_predictor`, `get_default_doctr_predictor`, and
      `_assemble_doctr_predictor`; forward to `ocr_predictor(det_bs=…, reco_bs=…)` and the
      standalone `detection_predictor(batch_size=det_bs)` / `recognition_predictor(batch_size=reco_bs)`.
- [ ] Add a batch OCR entry point `Document.from_images_ocr_via_doctr(images: list, …)` (or
      confirm callers can just pass a list to the existing per-image path) that calls
      `predictor([rgb1, rgb2, …])` once and returns one Document with N pages. Mirror
      `from_image_ocr_via_doctr`'s preprocessing per image.
- [ ] Tests: predictor built with custom `det_bs`/`reco_bs` carries them on its
      sub-predictors' preprocessors; batch entry point returns N pages for N inputs.

### 2. pdomain-ops — sizing, batched stage, OOM backoff, cache key

- [ ] `pick_doctr_batch_sizes(device, n_pages_in_chunk) -> (det_bs, reco_bs)` next to
      `pick_concurrency` in `device.py`. `det_bs` scales with `mem_get_info` free VRAM
      (GPU) or a conservative constant (CPU); `reco_bs` scales with the chunk's page count
      (crop supply) under a high ceiling.
- [ ] Predictor cache key in `_ocr_local_impl` must include `(det_bs, reco_bs)` — today it
      is keyed only on `(det_path, reco_path)`, so two batch sizes would return a stale
      predictor.
- [ ] Batched stage impl (extend `_ocr_local_impl` or add `_ocr_batch_local_impl`):
      accept a list of image paths, run `predictor([…])`, return a list of page dicts.
      Wrap in the OOM-backoff loop (halve `det_bs`, rebuild via the cache, retry; floor →
      delegate to the CPU impl).
- [ ] `run_stage` / a `run_batch_stage` entry that the dispatcher exposes for multi-image
      calls (keep the single-image `run_stage` for back-compat; the batch path can be the
      primary going forward).
- [ ] Tests: OOM (mock the predictor to raise `OutOfMemoryError` once) halves `det_bs` and
      retries; det_bs=1 OOM falls back to CPU; non-OOM re-raises; cache returns distinct
      predictors per `(det_bs, reco_bs)`.

### 3. Consumers — chunked dispatch

- [ ] **simple-gui** `run_project`: replace the Phase-1 asyncio worker pool with the
      chunked loop above; one batched stage call per chunk; per-chunk failure isolation +
      progress callback. Rename `parallel_pages` → `batch_pages` on `CreateJobRequest` /
      `ProjectSpec` and the job-config form (semantics: pages per call, blank = auto).
- [ ] Other consumers (pdomain-ocr-cli, labeler-spa, trainer-spa) adopt the batch stage as
      they touch OCR; not required in the first cut but the API should not preclude them.

---

## Implications for other tools

The dispatcher is shared, so this benefits every OCR consumer:

- **pdomain-ocr-cli** processes whole books — chunked GPU batching is the biggest win there.
- **labeler-spa / trainer-spa** re-OCR pages on demand — they get VRAM-safe batching and
  OOM resilience for free once they route through the batch stage.
- The `pick_doctr_batch_sizes` + OOM-backoff helpers are device-detection siblings of
  `pick_device` / `pick_concurrency`, so they stay in `pdomain_ops.gpu.device` as the one
  place hardware policy lives.

## Open questions

- Default `chunk_size`: start at ~8 pages (balances overhead amortization vs
  retry-blast-radius); revisit after measuring real book runs.
- Whether to retire the single-image `run_stage` once all consumers move to the batch path,
  or keep it as a thin wrapper (`run_batch_stage([one])`).
- CPU `det_bs` default: 1 (simplest, torch threads parallelize spatial dims) vs a small
  constant (amortizes per-call overhead). Measure before fixing.
