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
    out_path: Optional[Path] = None,
    show: bool = False,
) -> None:
    dates_raw = list(result.get("dates", []))
    if not dates_raw:
        raise ValueError("Result has no dates; nothing to plot.")

    dates = [_parse_date(d) for d in dates_raw]
    x = [dt.datetime.combine(d, dt.time()) for d in dates]
    volume = [float(v) for v in result.get("volume", [])]
    log_volume = [float(v) for v in result.get("log_volume", [])]
    segments = list(result.get("segments", []))
    source_id = result.get("source_id", "unknown")

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(12, 7))

    for seg in segments[1:]:
        start_idx = int(seg.get("start_idx", -1))
        if 0 <= start_idx < len(dates):
            bx = dt.datetime.combine(dates[start_idx], dt.time())
            ax1.axvline(bx, linestyle="--", linewidth=1, alpha=0.6)
            ax2.axvline(bx, linestyle="--", linewidth=1, alpha=0.6)

    ax1.plot(x, volume, linewidth=1.5, color="C0")
    for seg in segments:
        start_idx = int(seg.get("start_idx", 0))
        end_idx = int(seg.get("end_idx", 0))
        xs = x[start_idx:end_idx]
        ys = [float(seg.get("mean_volume", 0.0))] * len(xs)
        ax1.plot(xs, ys, linewidth=2.0, alpha=0.85, color="C1")
    ax1.set_ylabel("Volume (stories/day)")
    ax1.set_title(f"PELT segments for source {source_id}")

    ax2.plot(x, log_volume, linewidth=1.5, color="C0")
    for seg in segments:
        start_idx = int(seg.get("start_idx", 0))
        end_idx = int(seg.get("end_idx", 0))
        xs = x[start_idx:end_idx]
        ys = [float(seg.get("mean_log_volume", 0.0))] * len(xs)
        ax2.plot(xs, ys, linewidth=2.0, alpha=0.85, color="C1")
    ax2.set_ylabel("log1p(Volume)")
    ax2.set_xlabel("Date")

    fig.autofmt_xdate()
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, bbox_inches="tight", dpi=160)
    if show:
        plt.show()
    else:
        plt.close(fig)
