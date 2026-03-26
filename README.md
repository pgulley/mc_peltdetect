# peltdetect

`peltdetect` is a Media Cloud changepoint detection harness focused on per-source daily story-volume health.
It uses PELT (`ruptures`) on a `log1p(volume)` signal and emits segment/alert artifacts for offline and online-style evaluation workflows.

---

## What It Does

1. Fetch daily story counts for a source from Media Cloud.
2. Normalize to continuous daily series and run PELT segmentation.
3. Emit rule-based alerts (`drop`, `surge`, `near_zero`, `silence`).
4. Persist run artifacts (`run_result.json`, `segments.csv`, `alerts.csv`). `series.csv` is optional and is only written when the persisted `run_result.json` includes per-day `dates`/`volume`/`log_volume` (older runs).
5. Run online evaluation for a source by deriving offline truth, simulating online alerts in-memory, and scoring matches.

---

## Install

```bash
cd peltdetect
pip install -e .
export MEDIACLOUD_API_KEY="..."
```

Python 3.10+.

Dependencies are defined in `pyproject.toml`:
- `mediacloud`
- `ruptures`
- `numpy`
- `pandas`
- `matplotlib`

---

## Canonical Entrypoints

### 1) Offline, single source

```bash
python -m peltdetect.cli run \
  --source-id 123 \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --query "*"
```

Default output directory:
- `out/single/source_<id>/<start>_<end>/`

Inspect results:

```bash
python -m peltdetect.cli summarize --run-json out/single/source_123/2024-01-01_2024-03-31/run_result.json
python -m peltdetect.cli plot --run-json out/single/source_123/2024-01-01_2024-03-31/run_result.json --show
```

### 2) Offline, collection batch

```bash
python3 scripts/run_batch_collection_pelt.py \
  --collection-id 34412234 \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --query "*"
```

Default output directory:
- `out/batch/collection_<id>/<start>_<end>/`

Optional shortlist override (e.g. custom obituary sources):

```bash
python3 scripts/run_batch_collection_pelt.py \
  --collection-id 34412234 \
  --source-list source_obituary_janfeb2026.csv \
  --start-date 2024-01-01 \
  --end-date 2024-03-31
```

### 3) Online eval, single source

```bash
python3 scripts/run_online_eval_single_source.py \
  --source-id 123 \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --query "*"
```

Default output directory:
- `out/online_eval/source_<id>/<start>_<end>/`

Notes:
- The script is self-contained (no offline-batch-dir input required).
- It computes one offline baseline reference and persists it under:
  - `.../offline_reference/`
- Online simulation inner runs are evaluated in-memory.

---

## Output Artifacts

For offline run folders:
- `run_result.json`
- `segments.csv`
- `alerts.csv`
- `series.csv` (optional)

For online eval folders:
- `truth_events.csv`
- `online_alerts.csv`
- `matches.csv`
- `settings.csv`
- `metrics_by_setting.csv`
- `metrics_by_setting_and_type.csv`
- `truth_first_detection_delays.csv`
- `online_eval_manifest.json`
- `online_eval_summary.txt`
- `figures/` (timeline/volume overlays and optional delay CDF)
- `offline_reference/` (offline baseline run artifacts)

---

## Package Layout

Key modules:
- `peltdetect/mc_pelt/` — detector + storage primitives
- `peltdetect/experiments/online/` — online evaluation models/matching/metrics/simulation/truth helpers
- `peltdetect/charts/` — run and online plotting helpers
- `peltdetect/cli.py` — single-source CLI

Scripts:
- `scripts/run_batch_collection_pelt.py`
- `scripts/run_online_eval_single_source.py`

