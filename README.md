# peltdetect (package)

Python package + CLI for PELT-based **daily story-volume** changepoint detection on Media Cloud sources.

**Full project documentation (layout, scripts, batch workflow, timeline semantics, caveats):** see **[`../README.md`](../README.md)** in the repo root.

---

## Install

```bash
cd peltdetect
pip install -e .
export MEDIACLOUD_API_KEY="..."
```

## Single-source CLI

```bash
python -m peltdetect.cli run \
  --source-id 123 \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --query "*" \
  --rise-threshold 1.5
```

```bash
python -m peltdetect.cli summarize --run-json ./out/run_result.json
python -m peltdetect.cli plot --run-json ./out/run_result.json --show
```

## Canonical Experiment Entrypoints (from repo root `PELT_tests/`)

```bash
# Offline: single source
python -m peltdetect.cli run --source-id 123 --start-date 2024-01-01 --end-date 2024-03-31

# Offline: collection/batch
python3 peltdetect/scripts/run_batch_collection_pelt.py --collection-id 34412234 --start-date ... --end-date ...

# Optional override: run batch on explicit source list (e.g. obituary shortlist)
python3 peltdetect/scripts/run_batch_collection_pelt.py --collection-id 34412234 --source-list source_obituary_janfeb2026.csv --start-date ... --end-date ...

# Online eval: single source (full integrated pipeline)
python3 peltdetect/scripts/run_online_eval_single_source.py --source-id ... --start-date ... --end-date ... --query "*" --out-dir ...
```

See root **[`README.md`](../README.md)** for details.

