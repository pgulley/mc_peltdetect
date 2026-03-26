from __future__ import annotations

import datetime as dt
from typing import List

import numpy as np
import ruptures as rpt

from .models import RunResult, Segment


def suggest_penalty(log_volume: np.ndarray, *, penalty_scale: float = 1.0) -> float:
    n = int(len(log_volume))
    if n <= 1:
        return 1.0
    var = float(np.var(log_volume))
    penalty = float(penalty_scale * np.log(max(n, 2)) * var)
    if not np.isfinite(penalty) or penalty <= 0:
        penalty = 1.0
    return penalty


def segments_from_breakpoints(
    *,
    breakpoints: List[int],
    dates: List[dt.date],
    volume: np.ndarray,
    log_volume: np.ndarray,
) -> List[Segment]:
    n = len(volume)
    if len(dates) != n:
        raise ValueError("`dates`, `volume`, and `log_volume` must have the same length.")
    if not breakpoints:
        breakpoints = [n]
    if breakpoints[-1] != n:
        breakpoints = list(breakpoints) + [n]

    segments: List[Segment] = []
    prev = 0
    for bp in breakpoints:
        start_idx = prev
        end_idx = int(bp)
        if end_idx <= start_idx:
            prev = end_idx
            continue
        seg_slice = slice(start_idx, end_idx)
        segments.append(
            Segment(
                start_idx=start_idx,
                end_idx=end_idx,
                start=dates[start_idx],
                end=dates[end_idx - 1],
                mean_volume=float(np.mean(volume[seg_slice])),
                mean_log_volume=float(np.mean(log_volume[seg_slice])),
            )
        )
        prev = end_idx
    return segments


def run_pelt(
    *,
    start_date: dt.date,
    end_date: dt.date,
    dates: List[dt.date],
    volume: np.ndarray,
    log_volume: np.ndarray,
    model: str,
    min_size: int,
    penalty: float,
) -> RunResult:
    if len(log_volume) == 0:
        raise ValueError("Cannot run PELT on an empty series.")
    if penalty <= 0:
        raise ValueError("`penalty` must be > 0 for ruptures.")

    log_volume_1d = np.asarray(log_volume, dtype=float).reshape(-1)
    volume_1d = np.asarray(volume, dtype=float).reshape(-1)
    algo = rpt.Pelt(model=model, min_size=int(min_size)).fit(log_volume_1d)
    breakpoints = algo.predict(pen=float(penalty))
    segments = segments_from_breakpoints(
        breakpoints=breakpoints,
        dates=dates,
        volume=volume_1d,
        log_volume=log_volume_1d,
    )
    return RunResult(
        start_date=start_date,
        end_date=end_date,
        model=model,
        min_size=int(min_size),
        penalty=float(penalty),
        n_days=int(len(log_volume_1d)),
        dates=dates,
        volume=[int(x) for x in volume_1d.tolist()],
        log_volume=[float(x) for x in log_volume_1d.tolist()],
        segments=segments,
        alerts=[],
    )
