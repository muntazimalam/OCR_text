# Trade-offs, Assumptions & Design Decisions

This document records the deliberate assumptions, simplifications, and trade-offs made while building the Intelligent Media Processing Pipeline, and the reasoning behind each one.

---

## 1. Memory vs. Accuracy (512 MB free-tier constraint)

**Problem:** OCR inference (ONNX PP-OCRv4) peaked at ~500 MB RSS on a single image — enough to crash Render's free 512 MB instances.

**Decisions made:**
- OCR input capped at **1000 px** (was 1600 px) — measured inference peak dropped from ~420 MB to ~245 MB. Larger text is unaffected; only very small/ distant plates lose a little accuracy.
- **Plate-ROI re-crops are conditional**: they only run when the full-image OCR pass did not already produce a valid plate. Each crop costs a fresh ONNX inference (~+150 MB peak), so paying for it only when it can help keeps memory bounded.
- CLAHE contrast enhancement runs on a **single gray channel** (3× less memory) with patches capped at **480 px** (was 900 px).
- ONNX **recognition/cls batch sizes halved (6 → 2)** and det `max_candidates` bounded (1000 → 200) — negligible accuracy impact since the engine is called per-crop anyway.
- `OMP_NUM_THREADS=1`, `OMP_WAIT_POLICY=PASSIVE`, `MALLOC_ARENA_MAX=2` bound thread workspaces and glibc malloc arenas.

**Accepted cost:** text-dense non-plate images (posters, street signs) still peak ~400 MB. This is a headroom/trade-off we accept rather than spawning heavy GPU workers.

**Measured results:**
| Image type | Peak RSS |
| :--- | :--- |
| Typical vehicle photo with plate | ~240–280 MB |
| 12 MP worst-case (noise) | ~270 MB |
| Text-dense poster (no plate) | ~400 MB |

---

## 2. Local SQLite fallback over guaranteed PostgreSQL

**Decision:** The app connects to PostgreSQL when available, but automatically falls back to SQLite (`media_pipeline.db`) on connection failure.

**Why:** Keeps the API alive on free cloud tiers where PostgreSQL provisioning or network allowlists may fail (e.g. connection refused). Zero-dependency local development.

**Accepted cost:**
- SQLite data is **lost on redeploy** (ephemeral disk) — Postgres is the intended production store.
- No concurrent write scaling — fine for single-instance deployments, not for multi-node horizontal scaling.

---

## 3. FastAPI BackgroundTasks over a guaranteed Celery/Redis queue

**Decision:** If Celery/Redis is unreachable, processing runs synchronously *within the request lifecycle* via FastAPI `BackgroundTasks` — but still returns `201 Created` immediately so the client never blocks.

**Why:** Removes the operational requirement for Redis on free tiers while preserving asynchronous UX.

**Accepted cost:**
- Background tasks share the web process's CPU/RAM (this is why the memory budget in §1 matters).
- The pipeline is **serialized with a process-wide lock** — concurrent uploads queue up instead of running in parallel.
- No retry/dead-letter machinery; a crash mid-analysis fails the job permanently (the record is marked `failed`).

---

## 4. Heuristic quality scoring over deep quality models

**Decision:** Blur (Laplacian variance), lighting (mean intensity), and duplicates (SHA-256 + pHash) use classical OpenCV heuristics instead of deep neural network quality-assessment models.

**Why:** Tiny RAM/CPU footprint (fits the 512 MB budget), zero download latency, deterministic and testable.

**Accepted cost:**
- A Laplacian variance threshold (`< 100`) is a coarse proxy for perceptual blur — motion blur and soft focus can occasionally be misjudged.
- We mitigate the worst case: dark/overexposed images are **not** flagged "blurry" because low contrast from lighting explains the low score (smart attribution).

---

## 5. Regex-based plate validation instead of government DMV lookups

**Decision:** Plates are validated structurally (regex + token joining + brand-word filtering), not against any live vehicle database.

**Why:** No external credentials, offline-capable, zero latency.

**Accepted cost:**
- A structurally valid but unregistered plate passes validation (e.g. `KA01AB1234`).
- False positives on text that *looks* like a plate (poster text, phone numbers) are possible; the brand/phone filters reduce but do not eliminate these.

---

## 6. 9-character (not strictly 10) Indian plate length rule

**Decision:** Valid plates must be **9–10 characters** (Indian Standard/BH), not exactly 10.

**Why:** Real-world two-wheeler plates like `KA53EK529` are 9 characters and were being wrongly rejected by a strict 10-character rule (found while testing against real scooter photos).

**Accepted cost:** Slightly looser gate than before — 9-character alphanumeric strings are more likely to appear in scene text. The format regex still excludes obvious noise (7-character US/EU formats are intentionally rejected).

---

## 7. Multi-line plate joining is heuristic

**Decision:** Stacked two-line bike plates (`KA05` + `EX5678` → `KA05EX5678`) are joined by spatial-adjacency and format matching, not by a trained detector.

**Why:** Avoids a heavy object-detection model on a memory-constrained host.

**Accepted cost:** The joining heuristic can merge unrelated nearby tokens when a photo contains dense scene text.

---

## 8. Upload & storage assumptions

- **Max upload size:** 15 MB per image.
- **Accepted types:** `image/jpeg`, `image/png`, `image/webp`.
- **Storage:** local filesystem hierarchy (`/uploads/YYYY/MM/UUID.ext`) — chosen for zero-dependency reproducibility.
- **Accepted cost:** local storage does not scale horizontally; a production rollout needs S3/GCS + CDN (§10).

---

## 9. What a "failed" image means

A job is marked `failed` when any of: no valid plate detected, image is blurry, or lighting is suboptimal (very dark / overexposed). This is a deliberate product decision — this pipeline validates *plates on vehicle photos*, so a poster or a dark frame is a failure, not a pass.

---

## 10. What we would improve with more time

1. **Fine-tuned plate detector** (YOLOv8/v10) for tighter localization before OCR — better accuracy on distant/small plates and lower dependence on the conditional-crop heuristic.
2. **Deep Moiré / deepfake detection models** for tampering and screen re-photography beyond FFT heuristics.
3. **DMV / Vahan API verification** to cross-check extracted plates against registered vehicles.
4. **S3-compatible storage + CDN** for horizontal scaling.
5. **GPU-accelerated Celery workers with autoscaling** for production throughput.
6. **Dead-letter queue / retry machinery** for poison-pill images.
7. **Monkey-patched or vendored RapidOCR session options** if we later need per-image thread-count control (the installed 1.2.3 package does not expose `intra_op_num_threads`).

---

*This document is maintained alongside the README and reflects the state of the repository as of the final update.*
