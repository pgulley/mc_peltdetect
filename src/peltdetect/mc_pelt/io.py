from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def save_result(result: Dict[str, Any], *, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_json_path = out_dir / "run_result.json"
    with run_json_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    segments_csv = out_dir / "segments.csv"
    with segments_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "start_idx",
                "end_idx",
                "start",
                "end",
                "mean_volume",
                "mean_log_volume",
            ],
        )
        writer.writeheader()
        for segment in result.get("segments", []):
            writer.writerow(
                {
                    "start_idx": segment.get("start_idx"),
                    "end_idx": segment.get("end_idx"),
                    "start": segment.get("start"),
                    "end": segment.get("end"),
                    "mean_volume": segment.get("mean_volume"),
                    "mean_log_volume": segment.get("mean_log_volume"),
                }
            )

    alerts_csv = out_dir / "alerts.csv"
    with alerts_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["type", "from", "to", "start", "details"],
        )
        writer.writeheader()
        for alert in result.get("alerts", []):
            writer.writerow(
                {
                    "type": alert.get("type"),
                    "from": alert.get("from"),
                    "to": alert.get("to"),
                    "start": alert.get("start"),
                    "details": json.dumps(alert.get("details", {})),
                }
            )

    series_csv = out_dir / "series.csv"
    dates = list(result.get("dates", []))
    volume = list(result.get("volume", []))
    log_volume = list(result.get("log_volume", []))
    with series_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "volume", "log_volume"])
        writer.writeheader()
        for d, v, lv in zip(dates, volume, log_volume):
            writer.writerow({"date": d, "volume": v, "log_volume": lv})


def load_result(run_json_path: Path) -> Dict[str, Any]:
    run_json_path = Path(run_json_path)
    with run_json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_dict_rows_csv(
    path: Path,
    *,
    fieldnames: List[str],
    rows: List[Dict[str, Any]],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})
