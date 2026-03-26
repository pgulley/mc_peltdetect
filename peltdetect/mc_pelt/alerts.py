from __future__ import annotations

import datetime as dt
from typing import List, Optional

import numpy as np

from .models import Alert, Segment


def compute_alerts(
    *,
    segments: List[Segment],
    volumes: np.ndarray,
    dates: List[dt.date],
    drop_threshold: float,
    rise_threshold: float,
    zero_threshold: float,
    silence_multiplier: float,
    silence_default_expected_interval_days: float = 7.0,
) -> List[Alert]:
    if len(dates) == 0:
        return []
    volumes_1d = np.asarray(volumes, dtype=float).reshape(-1)
    if len(volumes_1d) != len(dates):
        raise ValueError("`volumes` and `dates` must have the same length.")

    alerts: List[Alert] = []
    for i in range(1, len(segments)):
        prev = segments[i - 1]
        curr = segments[i]
        if prev.mean_volume > 0 and curr.mean_volume < prev.mean_volume:
            ratio = curr.mean_volume / prev.mean_volume
            if ratio < drop_threshold:
                alerts.append(
                    Alert(
                        type="drop",
                        from_segment=i - 1,
                        to_segment=i,
                        start=curr.start,
                        details={"ratio": float(ratio), "prev_mean": prev.mean_volume, "curr_mean": curr.mean_volume},
                    )
                )
        if prev.mean_volume > 0 and curr.mean_volume > prev.mean_volume:
            ratio = curr.mean_volume / prev.mean_volume
            if ratio > rise_threshold:
                alerts.append(
                    Alert(
                        type="surge",
                        from_segment=i - 1,
                        to_segment=i,
                        start=curr.start,
                        details={"ratio": float(ratio), "prev_mean": prev.mean_volume, "curr_mean": curr.mean_volume},
                    )
                )
        if curr.mean_volume <= float(zero_threshold):
            alerts.append(
                Alert(
                    type="near_zero",
                    from_segment=i - 1 if i - 1 >= 0 else None,
                    to_segment=i,
                    start=curr.start,
                    details={"mean_volume": curr.mean_volume, "zero_threshold": float(zero_threshold)},
                )
            )

    non_zero_idxs = np.where(volumes_1d > 0)[0]
    last_date = dates[-1]
    last_day_volume = float(volumes_1d[-1])
    expected_interval_days: Optional[float]
    if non_zero_idxs.size >= 2:
        expected_interval_days = float(np.median(np.diff(non_zero_idxs).astype(float)))
    elif non_zero_idxs.size == 1:
        expected_interval_days = float(silence_default_expected_interval_days)
    else:
        expected_interval_days = None

    if non_zero_idxs.size > 0:
        last_post_date = dates[int(non_zero_idxs[-1])]
        days_since_last_post = (last_date - last_post_date).days
    else:
        days_since_last_post = (last_date - dates[0]).days

    last_segment_mean = float(segments[-1].mean_volume) if segments else float(np.mean(volumes_1d))
    currently_dead = last_day_volume <= 0 and last_segment_mean <= float(zero_threshold)
    if expected_interval_days is None:
        silence_trigger = currently_dead
    else:
        silence_trigger = currently_dead and (days_since_last_post > silence_multiplier * expected_interval_days)

    if silence_trigger:
        alerts.append(
            Alert(
                type="silence",
                from_segment=len(segments) - 2 if len(segments) >= 2 else None,
                to_segment=len(segments) - 1 if len(segments) >= 1 else None,
                start=segments[-1].start if segments else dates[-1],
                details={
                    "days_since_last_post": int(days_since_last_post),
                    "expected_interval_days": None if expected_interval_days is None else float(expected_interval_days),
                    "silence_multiplier": float(silence_multiplier),
                },
            )
        )
    return alerts
