#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import mediacloud.api

from peltdetect.api import fetch_story_count_over_time
from peltdetect.mc_pelt import MCPelt
from peltdetect.mc_pelt.io import save_result


def _parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _load_source_ids(path: Path) -> List[int]:
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [int(item["id"]) for item in data if "id" in item]

    if path.suffix.lower() == ".csv":
        ids: List[int] = []
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id"):
                    ids.append(int(row["id"]))
        return ids

    raise ValueError("Unsupported source list format. Use .json or .csv")


def _load_source_ids_from_collection(
    *,
    directory_api: mediacloud.api.DirectoryApi,
    collection_id: int,
    page_size: int = 1000,
) -> List[int]:
    source_ids: List[int] = []
    offset = 0
    while True:
        resp = directory_api.source_list(collection_id=int(collection_id), limit=int(page_size), offset=offset)
        page = resp.get("results", []) or []
        if not page:
            break
        for row in page:
            sid = row.get("id")
            if sid is None:
                continue
            source_ids.append(int(sid))
        if resp.get("next") is None:
            break
        offset += len(page)
    # preserve order while deduplicating
    unique_ids = list(dict.fromkeys(source_ids))
    return unique_ids


def _iter_source_ids(ids: List[int], limit: int | None, offset: int) -> Iterable[int]:
    sliced = ids[offset:]
    if limit is not None:
        sliced = sliced[:limit]
    for sid in sliced:
        yield sid


def _ensure_package_importable(repo_root: Path) -> None:
    # Supports running this script directly from repo root without installation.
    import sys

    src_path = repo_root / "peltdetect" / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def _run_one(
    *,
    directory_api: mediacloud.api.DirectoryApi,
    api_key: str,
    source_id: int,
    start_date: dt.date,
    end_date: dt.date,
    query: str,
    detector: MCPelt,
    out_root: Path,
) -> Tuple[bool, Dict[str, Any]]:
    per_source_dir = out_root / f"source_{source_id}"
    per_source_dir.mkdir(parents=True, exist_ok=True)

    source_meta: Dict[str, Any] = {}
    try:
        # Pull richer metadata by source id to make outputs human-readable.
        source_meta = directory_api.source(source_id)
        with (per_source_dir / "source_metadata.json").open("w", encoding="utf-8") as f:
            json.dump(source_meta, f, indent=2)
    except Exception as meta_exc:  # noqa: BLE001
        source_meta = {"id": source_id, "metadata_error": str(meta_exc)}

    try:
        series = fetch_story_count_over_time(
            query=query,
            start_date=start_date,
            end_date=end_date,
            source_id=source_id,
            api_key=api_key,
        )
        result = detector.detect_for_source(
            series,
            source_id=source_id,
            query=query,
            start_date=start_date,
            end_date=end_date,
        )
        save_result(result, out_dir=per_source_dir)

        info = {
            "source_id": source_id,
            "source_name": source_meta.get("name"),
            "source_label": source_meta.get("label"),
            "source_url": source_meta.get("url"),
            "source_platform": source_meta.get("platform"),
            "status": "ok",
            "n_segments": len(result.get("segments", [])),
            "n_alerts": len(result.get("alerts", [])),
            "alert_types": [str(a.get("type", "")) for a in result.get("alerts", [])],
            "out_dir": str(per_source_dir),
        }
        return True, info
    except Exception as exc:  # noqa: BLE001
        info = {
            "source_id": source_id,
            "source_name": source_meta.get("name"),
            "source_label": source_meta.get("label"),
            "source_url": source_meta.get("url"),
            "source_platform": source_meta.get("platform"),
            "status": "error",
            "error": str(exc),
            "out_dir": str(per_source_dir),
        }
        return False, info


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run peltdetect across many sources in a collection (or optional source-list override)."
    )
    p.add_argument("--collection-id", required=True, type=int, help="Media Cloud collection id.")
    p.add_argument(
        "--source-list",
        default=None,
        help="Optional path to source list JSON/CSV with an `id` column; overrides collection source fetch.",
    )
    p.add_argument("--page-size", type=int, default=1000, help="Pagination size for collection source fetch.")
    p.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--query", default="*", help="Media Cloud query (default: '*').")
    p.add_argument("--api-key-env", default="MEDIACLOUD_API_KEY", help="Env var holding API token.")
    p.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: peltdetect/out/batch/collection_<id>/<start>_<end>).",
    )
    p.add_argument("--model", default="l2", help="ruptures PELT model.")
    p.add_argument("--min-size", type=int, default=7, help="Minimum segment length.")
    p.add_argument("--penalty", type=float, default=None, help="Optional fixed penalty (default: auto).")
    p.add_argument("--drop-threshold", type=float, default=0.5, help="Drop threshold ratio.")
    p.add_argument("--rise-threshold", type=float, default=1.5, help="Surge threshold ratio.")
    p.add_argument("--zero-threshold", type=float, default=1.0, help="Near-zero threshold.")
    p.add_argument("--silence-multiplier", type=float, default=5.0, help="Silence gap multiplier.")
    p.add_argument("--limit", type=int, default=None, help="Optional max number of sources to process.")
    p.add_argument("--offset", type=int, default=0, help="Skip first N source ids.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    if end_date < start_date:
        raise ValueError("end-date must be >= start-date")

    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing API key in env var: {args.api_key_env}")

    if args.out_dir:
        out_root = Path(args.out_dir)
    else:
        out_root = Path("peltdetect/out/batch") / f"collection_{int(args.collection_id)}" / f"{start_date.isoformat()}_{end_date.isoformat()}"
    out_root.mkdir(parents=True, exist_ok=True)

    directory_api = mediacloud.api.DirectoryApi(api_key)
    if args.source_list:
        source_list_path = Path(args.source_list)
        source_ids = _load_source_ids(source_list_path)
    else:
        source_ids = _load_source_ids_from_collection(
            directory_api=directory_api,
            collection_id=int(args.collection_id),
            page_size=int(args.page_size),
        )
    run_ids = list(_iter_source_ids(source_ids, args.limit, args.offset))

    summary_rows: List[Dict[str, Any]] = []
    ok_count = 0
    err_count = 0
    detector = MCPelt(
        model=args.model,
        min_size=int(args.min_size),
        penalty="auto" if args.penalty is None else float(args.penalty),
        drop_threshold=float(args.drop_threshold),
        rise_threshold=float(args.rise_threshold),
        zero_threshold=float(args.zero_threshold),
        silence_multiplier=float(args.silence_multiplier),
    )

    for idx, source_id in enumerate(run_ids, start=1):
        print(f"[{idx}/{len(run_ids)}] source_id={source_id}")
        ok, info = _run_one(
            directory_api=directory_api,
            api_key=api_key,
            source_id=source_id,
            start_date=start_date,
            end_date=end_date,
            query=args.query,
            detector=detector,
            out_root=out_root,
        )
        summary_rows.append(info)
        if ok:
            ok_count += 1
        else:
            err_count += 1
            print(f"  ERROR: {info.get('error')}")

    summary = {
        "collection_id": int(args.collection_id),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "query": args.query,
        "n_total": len(run_ids),
        "n_ok": ok_count,
        "n_error": err_count,
        "results": summary_rows,
    }

    summary_json = out_root / "batch_summary.json"
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    summary_csv = out_root / "batch_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source_id",
                "source_name",
                "source_label",
                "source_url",
                "source_platform",
                "status",
                "n_segments",
                "n_alerts",
                "alert_types",
                "error",
                "out_dir",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(
                {
                    "source_id": row.get("source_id"),
                    "source_name": row.get("source_name"),
                    "source_label": row.get("source_label"),
                    "source_url": row.get("source_url"),
                    "source_platform": row.get("source_platform"),
                    "status": row.get("status"),
                    "n_segments": row.get("n_segments"),
                    "n_alerts": row.get("n_alerts"),
                    "alert_types": ",".join(row.get("alert_types", [])),
                    "error": row.get("error"),
                    "out_dir": row.get("out_dir"),
                }
            )

    print("\nBatch complete.")
    print(f"Processed: {len(run_ids)} | ok: {ok_count} | error: {err_count}")
    print(f"Summary JSON: {summary_json}")
    print(f"Summary CSV:  {summary_csv}")


if __name__ == "__main__":
    # Ensure direct script run works from repo root.
    _ensure_package_importable(Path(__file__).resolve().parents[2])
    main()

