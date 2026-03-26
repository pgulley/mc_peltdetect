from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt


def _parse_date(value: object) -> dt.date:
    return dt.date.fromisoformat(str(value)[:10])


def plot_result(
    result: Dict[str, Any],
    *,
    volume_values: Optional[Any] = None,
    volume_dates: Optional[Any] = None,
    out_path: Optional[Path] = None,
    show: bool = False,
) -> None:
    segments = list(result.get("segments", []))
    source_id = result.get("source_id", "unknown")

    dates_raw = list(result.get("dates", []))
    if dates_raw:
        dates = [_parse_date(d) for d in dates_raw]
        x = [dt.datetime.combine(d, dt.time()) for d in dates]
    else:
        if not segments:
            raise ValueError("Result has no per-day dates and no segments; nothing to plot.")
        segments_sorted = sorted(segments, key=lambda s: int(s.get("start_idx", 0)))
        n_days = max(int(s.get("end_idx", 0)) for s in segments_sorted)
        first_seg = segments_sorted[0]
        first_start_idx = int(first_seg.get("start_idx", 0))
        first_start_date = _parse_date(first_seg["start"])
        base_date = first_start_date - dt.timedelta(days=first_start_idx)
        dates = [base_date + dt.timedelta(days=i) for i in range(n_days)]
        x = [dt.datetime.combine(d, dt.time()) for d in dates]

    volume: list[float] = []
    if volume_values is not None and volume_dates is not None:
        # Caller-provided series; expected to align to the same x-axis.
        volume = [float(v) for v in volume_values]
        # We intentionally ignore `volume_dates` for now and trust x reconstructed above.
        # If caller provides mismatched lengths, we just skip the raw curve.

    fig, ax1 = plt.subplots(1, 1, figsize=(12, 5))

    for seg in segments[1:]:
        start_idx = int(seg.get("start_idx", -1))
        if 0 <= start_idx < len(dates):
            bx = dt.datetime.combine(dates[start_idx], dt.time())
            ax1.axvline(bx, linestyle="--", linewidth=1, alpha=0.6)

    if volume and len(volume) == len(x):
        ax1.plot(x, volume, linewidth=1.5, color="C0")
    for seg in segments:
        start_idx = int(seg.get("start_idx", 0))
        end_idx = int(seg.get("end_idx", 0))
        xs = x[start_idx:end_idx]
        ys = [float(seg.get("mean_volume", 0.0))] * len(xs)
        ax1.plot(xs, ys, linewidth=2.0, alpha=0.85, color="C1")
    ax1.set_ylabel("Volume (stories/day)")
    ax1.set_title(f"PELT segments for source {source_id}")
    ax1.set_xlabel("Date")

    fig.autofmt_xdate()
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, bbox_inches="tight", dpi=160)
    if show:
        plt.show()
    else:
        plt.close(fig)
