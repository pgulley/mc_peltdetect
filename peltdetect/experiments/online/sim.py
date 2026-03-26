from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from ...mc_pelt import MCPelt
from .eval_models import OnlineAlertRow, OnlineEvalSetting


SOURCE_DIR_RE = re.compile(r"^source_(\d+)$")


@dataclass(frozen=True)
class SourceSeries:
    source_id: int
    query: str
    dates: List[dt.date]
    volume: List[int]
    log_volume: List[float]


@dataclass(frozen=True)
class SimulationSummary:
    setting_id: str
    n_sources: int
    n_runs_attempted: int
    n_runs_skipped_insufficient_history: int
    n_alert_rows: int

    def to_dict(self) -> Dict[str, int | str]:
        return {
            "setting_id": self.setting_id,
            "n_sources": self.n_sources,
            "n_runs_attempted": self.n_runs_attempted,
            "n_runs_skipped_insufficient_history": self.n_runs_skipped_insufficient_history,
            "n_alert_rows": self.n_alert_rows,
        }


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


def _find_run_jsons(batch_dir: Path) -> List[Tuple[int, Path]]:
    out: List[Tuple[int, Path]] = []
    for p in sorted(batch_dir.iterdir()):
        if not p.is_dir():
            continue
        match = SOURCE_DIR_RE.match(p.name)
        if not match:
            continue
        source_id = int(match.group(1))
        run_json = p / "run_result.json"
        if run_json.is_file():
            out.append((source_id, run_json))
    return out


def load_offline_source_series(
    *,
    offline_batch_dir: Path,
    source_ids: Optional[Iterable[int]] = None,
) -> Dict[int, SourceSeries]:
    source_filter = None if source_ids is None else {int(x) for x in source_ids}
    out: Dict[int, SourceSeries] = {}
    for source_id, run_json_path in _find_run_jsons(offline_batch_dir):
        if source_filter is not None and source_id not in source_filter:
            continue
        with run_json_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        json_source_id = int(payload.get("source_id", source_id))
        if source_filter is not None and json_source_id not in source_filter:
            continue
        dates = [_parse_date(str(d)) for d in payload.get("dates", [])]
        volume = [int(x) for x in payload.get("volume", [])]
        log_volume = [float(x) for x in payload.get("log_volume", [])]
        if not dates or len(dates) != len(volume) or len(volume) != len(log_volume):
            continue
        out[json_source_id] = SourceSeries(
            source_id=json_source_id,
            query=str(payload.get("query", "*")),
            dates=dates,
            volume=volume,
            log_volume=log_volume,
        )
    return out


def _run_date_indexes(
    dates: List[dt.date],
    *,
    start_date: dt.date,
    end_date: dt.date,
    day_stride: int,
) -> List[int]:
    if day_stride <= 0:
        raise ValueError("day_stride must be >= 1")
    idxs: List[int] = []
    for idx, d in enumerate(dates):
        if d < start_date or d > end_date:
            continue
        idxs.append(idx)
    return idxs[::day_stride]


def simulate_online_alerts_for_setting(
    *,
    source_series: Dict[int, SourceSeries],
    setting: OnlineEvalSetting,
    start_date: dt.date,
    end_date: dt.date,
    day_stride: int = 1,
) -> Tuple[List[OnlineAlertRow], SimulationSummary]:
    setting_id = setting.resolved_setting_id()
    rows: List[OnlineAlertRow] = []
    n_runs_attempted = 0
    n_runs_skipped_insufficient_history = 0
    for series in source_series.values():
        detector = MCPelt(
            model=setting.model,
            min_size=int(setting.min_size),
            penalty=setting.penalty,
            drop_threshold=float(setting.drop_threshold),
            rise_threshold=float(setting.rise_threshold),
            zero_threshold=float(setting.zero_threshold),
            silence_multiplier=float(setting.silence_multiplier),
        )
        run_idxs = _run_date_indexes(series.dates, start_date=start_date, end_date=end_date, day_stride=day_stride)
        for run_idx in run_idxs:
            n_runs_attempted += 1
            window_start_idx = max(0, run_idx - int(setting.window_days) + 1)
            win_len = run_idx - window_start_idx + 1
            if win_len < max(2, int(setting.min_size)):
                n_runs_skipped_insufficient_history += 1
                continue
            dates_slice = series.dates[window_start_idx : run_idx + 1]
            vol_slice = np.asarray(series.volume[window_start_idx : run_idx + 1], dtype=float)
            window_df = pd.DataFrame({"date": dates_slice, "volume": vol_slice.astype(int)})
            # Core detection output is metadata-free; online simulation already tracks `series.source_id` / `series.query`.
            result = detector(
                window_df,
                start_date=dates_slice[0],
                end_date=dates_slice[-1],
            )
            for alert in result["alerts"]:
                rows.append(
                    OnlineAlertRow(
                        setting_id=setting_id,
                        source_id=series.source_id,
                        run_date=dates_slice[-1],
                        alert_type=str(alert["type"]),
                        alert_start_date=_parse_date(str(alert["start"])),
                        details_json=json.dumps(alert.get("details", {}), sort_keys=True),
                    )
                )
    summary = SimulationSummary(
        setting_id=setting_id,
        n_sources=len(source_series),
        n_runs_attempted=n_runs_attempted,
        n_runs_skipped_insufficient_history=n_runs_skipped_insufficient_history,
        n_alert_rows=len(rows),
    )
    return rows, summary
