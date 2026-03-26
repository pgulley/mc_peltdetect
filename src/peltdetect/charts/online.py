from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_frontier(metrics_rows: Sequence[Dict[str, object]], out_path: Path) -> None:
    import matplotlib.pyplot as plt

    if not metrics_rows:
        return
    xs: List[float] = []
    ys: List[float] = []
    labels: List[str] = []
    for row in metrics_rows:
        try:
            xs.append(float(row["false_alerts_per_source_year"]))
            ys.append(float(row["timely_recall_at_7"]))
            labels.append(str(row["setting_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not xs:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(xs, ys, s=55, alpha=0.9, edgecolors="#1f1f1f", linewidths=0.5, color="#2980b9")
    for i, label in enumerate(labels):
        ax.annotate(label, (xs[i], ys[i]), textcoords="offset points", xytext=(4, 3), fontsize=7)
    ax.set_xlabel("False Alerts per Source-Year")
    ax.set_ylabel("Timely Recall @7")
    ax.set_title("Online Evaluation Frontier")
    ax.grid(alpha=0.25)
    _ensure_parent(out_path)
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def plot_recall_precision_heatmap(
    metrics_rows: Sequence[Dict[str, object]],
    settings_rows: Sequence[Dict[str, object]],
    out_path: Path,
    *,
    x_param: str = "window_days",
    y_param: str = "drop_threshold",
    value_key: str = "timely_recall_at_7",
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    if not metrics_rows or not settings_rows:
        return
    setting_to_metrics: Dict[str, Dict[str, object]] = {str(r["setting_id"]): r for r in metrics_rows}
    points: List[Tuple[float, float, float]] = []
    for s in settings_rows:
        sid = str(s.get("setting_id", ""))
        m = setting_to_metrics.get(sid)
        if not m:
            continue
        try:
            points.append((float(s[x_param]), float(s[y_param]), float(m[value_key])))
        except (KeyError, TypeError, ValueError):
            continue
    if not points:
        return
    x_vals = sorted({p[0] for p in points})
    y_vals = sorted({p[1] for p in points})
    x_idx = {v: i for i, v in enumerate(x_vals)}
    y_idx = {v: i for i, v in enumerate(y_vals)}
    grid = np.full((len(y_vals), len(x_vals)), np.nan, dtype=float)
    for x, y, v in points:
        grid[y_idx[y], x_idx[x]] = v
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(grid, origin="lower", aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(x_vals)))
    ax.set_xticklabels([str(int(x)) if float(x).is_integer() else str(x) for x in x_vals], rotation=45, ha="right")
    ax.set_yticks(range(len(y_vals)))
    ax.set_yticklabels([str(y) for y in y_vals])
    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"Heatmap: {value_key}")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(value_key)
    _ensure_parent(out_path)
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def plot_delay_cdf(
    matches_rows: Sequence[Dict[str, object]],
    out_path: Path,
    *,
    setting_ids: Optional[Sequence[str]] = None,
) -> None:
    import matplotlib.pyplot as plt

    if not matches_rows:
        return
    by_setting: Dict[str, List[int]] = {}
    for row in matches_rows:
        sid = str(row.get("setting_id", ""))
        if setting_ids and sid not in setting_ids:
            continue
        is_matched = str(row.get("is_matched", "")).strip().lower() == "true" or bool(row.get("is_matched") is True)
        delay_raw = row.get("delay_days")
        if not is_matched or delay_raw in (None, ""):
            continue
        by_setting.setdefault(sid, []).append(int(delay_raw))
    if not by_setting:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    for sid, delays in sorted(by_setting.items()):
        delays_sorted = sorted(delays)
        n = len(delays_sorted)
        ys = [(i + 1) / n for i in range(n)]
        ax.step(delays_sorted, ys, where="post", label=sid)
    ax.set_xlabel("Detection Delay (days)")
    ax.set_ylabel("CDF")
    ax.set_title("Delay CDF by Setting")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="lower right")
    _ensure_parent(out_path)
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def plot_source_timeline_overlay(
    truth_events: Sequence[Dict[str, object]],
    online_alerts: Sequence[Dict[str, object]],
    out_path: Path,
    *,
    source_id: int,
    setting_id: Optional[str] = None,
    source_name: Optional[str] = None,
) -> None:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    truth = [r for r in truth_events if int(r.get("source_id", -1)) == int(source_id)]
    alerts = [
        r
        for r in online_alerts
        if int(r.get("source_id", -1)) == int(source_id)
        and (setting_id is None or str(r.get("setting_id", "")) == setting_id)
    ]
    if not truth and not alerts:
        return
    type_colors = {"drop": "#f1c40f", "near_zero": "#e67e22", "silence": "#e74c3c", "surge": "#3498db"}
    default_color = "#7f7f7f"
    fig, ax = plt.subplots(figsize=(12, 4))
    for row in truth:
        d = _parse_date(str(row["truth_event_date"]))
        t = str(row.get("alert_type", "unknown"))
        ax.scatter(mdates.date2num(d), 1.0, marker="D", s=70, color=type_colors.get(t, default_color), edgecolors="#222222", linewidths=0.5, alpha=0.95)
    for row in alerts:
        d = _parse_date(str(row["alert_start_date"]))
        t = str(row.get("alert_type", "unknown"))
        ax.scatter(mdates.date2num(d), 0.0, marker="o", s=50, color=type_colors.get(t, default_color), edgecolors="#222222", linewidths=0.5, alpha=0.9)
    ax.set_yticks([0.0, 1.0])
    ax.set_yticklabels(["online_alert", "truth_event"])
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    label = (source_name or "").strip()
    title = f"{label} (source_id={source_id}) — truth vs online timeline" if label else f"Source {source_id} — truth vs online timeline"
    if setting_id is not None:
        title += f"\nsetting {setting_id}"
    ax.set_title(title, fontsize=11)
    ax.grid(alpha=0.25, axis="x")
    fig.autofmt_xdate()
    _ensure_parent(out_path)
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def plot_source_volume_with_events(
    *,
    dates: Sequence[dt.date],
    volume: Sequence[int | float],
    truth_events: Sequence[Dict[str, object]],
    online_alerts: Sequence[Dict[str, object]],
    out_path: Path,
    source_id: int,
    setting_id: Optional[str] = None,
    source_name: Optional[str] = None,
) -> None:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    if not dates or not volume or len(dates) != len(volume):
        return
    truth = [r for r in truth_events if int(r.get("source_id", -1)) == int(source_id)]
    alerts = [
        r
        for r in online_alerts
        if int(r.get("source_id", -1)) == int(source_id)
        and (setting_id is None or str(r.get("setting_id", "")) == setting_id)
    ]
    type_colors = {"drop": "#f1c40f", "near_zero": "#e67e22", "silence": "#e74c3c", "surge": "#3498db"}
    default_color = "#7f7f7f"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    x = [mdates.date2num(d) for d in dates]
    y = [float(v) for v in volume]
    ax1.plot(x, y, color="#2c3e50", linewidth=1.4, alpha=0.95, label="daily volume")
    ax1.fill_between(x, y, [0.0] * len(y), color="#95a5a6", alpha=0.18)
    ax1.set_ylabel("Daily Volume")
    ax1.grid(alpha=0.2)
    label = (source_name or "").strip()
    title = f"{label} (source_id={source_id}) — volume with truth/online markers" if label else f"Source {source_id} — volume with truth/online markers"
    if setting_id is not None:
        title += f"\nsetting {setting_id}"
    ax1.set_title(title, fontsize=11)
    for row in truth:
        d = _parse_date(str(row["truth_event_date"]))
        t = str(row.get("alert_type", "unknown"))
        ax1.axvline(mdates.date2num(d), color=type_colors.get(t, default_color), alpha=0.18, linewidth=1.1)
        ax2.scatter(mdates.date2num(d), 1.0, marker="D", s=70, color=type_colors.get(t, default_color), edgecolors="#222222", linewidths=0.5, alpha=0.95)
    for row in alerts:
        d = _parse_date(str(row["alert_start_date"]))
        t = str(row.get("alert_type", "unknown"))
        ax1.axvline(mdates.date2num(d), color=type_colors.get(t, default_color), alpha=0.12, linewidth=0.9, linestyle="--")
        ax2.scatter(mdates.date2num(d), 0.0, marker="o", s=50, color=type_colors.get(t, default_color), edgecolors="#222222", linewidths=0.5, alpha=0.9)
    ax2.set_yticks([0.0, 1.0])
    ax2.set_yticklabels(["online_alert", "truth_event"])
    ax2.grid(alpha=0.2, axis="x")
    ax2.set_xlabel("Date")
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    _ensure_parent(out_path)
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def load_metrics_rows(path: Path) -> List[Dict[str, object]]:
    rows = _read_csv_rows(path)
    out: List[Dict[str, object]] = []
    for r in rows:
        row: Dict[str, object] = dict(r)
        for k in [
            "n_truth_events",
            "n_online_alerts",
            "event_recall",
            "precision",
            "median_delay_days",
            "timely_recall_at_0",
            "timely_recall_at_3",
            "timely_recall_at_7",
            "timely_recall_at_14",
            "false_alerts_per_source_year",
        ]:
            v = row.get(k)
            if v in (None, ""):
                row[k] = None
                continue
            try:
                row[k] = float(v)
            except ValueError:
                row[k] = None
        out.append(row)
    return out


def load_generic_rows(path: Path) -> List[Dict[str, object]]:
    return [dict(r) for r in _read_csv_rows(path)]
