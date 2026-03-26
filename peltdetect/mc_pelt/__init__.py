from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd

from .alerts import compute_alerts
from .detect import run_pelt, suggest_penalty
from .preprocess import prepare_series


def _as_dataframe(series: pd.DataFrame | Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    if isinstance(series, pd.DataFrame):
        df = series.copy()
    else:
        df = pd.DataFrame(list(series))
    if "date" not in df.columns:
        raise ValueError("Expected Media Cloud-like input with a `date` column.")
    if "volume" in df.columns:
        volume_col = "volume"
    elif "count" in df.columns:
        volume_col = "count"
    else:
        raise ValueError("Expected a `volume` or `count` column in input series.")
    return pd.DataFrame({"date": df["date"], "volume": df[volume_col]})


def _coerce_date(value: object) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    return dt.date.fromisoformat(str(value)[:10])


@dataclass(frozen=True)
class MCPelt:
    model: str = "l2"
    min_size: int = 7
    penalty: float | str = "auto"
    drop_threshold: float = 0.5
    rise_threshold: float = 1.5
    zero_threshold: float = 1.0
    silence_multiplier: float = 5.0

    def detect(
        self,
        series: pd.DataFrame | Sequence[Mapping[str, Any]],
        *,
        start_date: Optional[dt.date] = None,
        end_date: Optional[dt.date] = None,
    ) -> Dict[str, Any]:
        raw = _as_dataframe(series)
        if raw.empty:
            raise ValueError("Input series is empty.")
        coerced_dates = raw["date"].map(_coerce_date)
        effective_start = start_date or min(coerced_dates)
        effective_end = end_date or max(coerced_dates)
        if effective_start > effective_end:
            raise ValueError("start_date must be <= end_date")

        prepared = prepare_series(raw, start_date=effective_start, end_date=effective_end)
        penalty_value = (
            suggest_penalty(prepared["log_volume"].to_numpy())
            if str(self.penalty).lower() == "auto"
            else float(self.penalty)
        )

        run = run_pelt(
            start_date=effective_start,
            end_date=effective_end,
            dates=prepared["date"].to_list(),
            volume=prepared["volume"].to_numpy(),
            log_volume=prepared["log_volume"].to_numpy(),
            model=self.model,
            min_size=int(self.min_size),
            penalty=float(penalty_value),
        )

        alerts = compute_alerts(
            segments=run.segments,
            volumes=prepared["volume"].to_numpy(),
            dates=prepared["date"].to_list(),
            drop_threshold=float(self.drop_threshold),
            rise_threshold=float(self.rise_threshold),
            zero_threshold=float(self.zero_threshold),
            silence_multiplier=float(self.silence_multiplier),
        )

        # Core detection payload: detection window + segments + alerts.
        # No `source_id` / `query` metadata here; callers can attach it externally.
        return {
            "start_date": effective_start.isoformat(),
            "end_date": effective_end.isoformat(),
            "model": self.model,
            "min_size": int(self.min_size),
            "penalty_used": float(penalty_value),
            "alerts": [a.to_dict() for a in alerts],
            "breakpoints": [s.start.isoformat() for s in run.segments[1:]],
            "segments": [s.to_dict() for s in run.segments],
        }

    def detect_for_source(
        self,
        series: pd.DataFrame | Sequence[Mapping[str, Any]],
        *,
        source_id: int,
        query: str = "*",
        start_date: Optional[dt.date] = None,
        end_date: Optional[dt.date] = None,
    ) -> Dict[str, Any]:
        result = self.detect(series, start_date=start_date, end_date=end_date)
        # Metadata wrapper for persistence/reporting workflows.
        result.update({"source_id": int(source_id), "query": query})
        return result

    def __call__(
        self,
        series: pd.DataFrame | Sequence[Mapping[str, Any]],
        *,
        start_date: Optional[dt.date] = None,
        end_date: Optional[dt.date] = None,
    ) -> Dict[str, Any]:
        return self.detect(series, start_date=start_date, end_date=end_date)

    def detect_alerts(
        self,
        series: pd.DataFrame | Sequence[Mapping[str, Any]],
        *,
        start_date: Optional[dt.date] = None,
        end_date: Optional[dt.date] = None,
    ) -> List[Dict[str, Any]]:
        return self.detect(series, start_date=start_date, end_date=end_date)["alerts"]

    def chart_alerts(
        self,
        series: pd.DataFrame | Sequence[Mapping[str, Any]],
        alerts: Sequence[Mapping[str, Any]],
        *,
        start_date: Optional[dt.date] = None,
        end_date: Optional[dt.date] = None,
        max_alerts: int = 10,
    ) -> Any:
        """
        Create a matplotlib chart (Jupyter-renderable) of `volume` with vertical alert markers.

        `series` should match the input you would pass to `detect_alerts()`, and `alerts`
        should be the output list from `detect_alerts()`.
        """
        raw = _as_dataframe(series)
        if raw.empty:
            raise ValueError("Input series is empty.")

        coerced_dates = raw["date"].map(_coerce_date)
        effective_start = start_date or min(coerced_dates)
        effective_end = end_date or max(coerced_dates)
        if effective_start > effective_end:
            raise ValueError("start_date must be <= end_date")

        prepared = prepare_series(raw, start_date=effective_start, end_date=effective_end)
        dates = prepared["date"].to_list()
        volume = prepared["volume"].to_list()
        x = [dt.datetime.combine(d, dt.time()) for d in dates]

        index_by_date = {d: i for i, d in enumerate(dates)}

        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(x, volume, linewidth=1.6, color="C0")

        type_colors = {
            "drop": "gold",
            "near_zero": "orange",
            "silence": "red",
            "surge": "cornflowerblue",
        }

        seen_types: set[str] = set()
        for a in list(alerts)[:max_alerts]:
            a_type = str(a.get("type", ""))
            start_raw = a.get("start")
            if not start_raw:
                continue
            try:
                start_dt = _coerce_date(start_raw)
            except Exception:
                continue
            if start_dt not in index_by_date:
                continue

            idx = index_by_date[start_dt]
            color = type_colors.get(a_type, "black")
            label = a_type if a_type not in seen_types else None
            ax.axvline(x[idx], color=color, alpha=0.35, linestyle="--", linewidth=1.4, label=label)
            seen_types.add(a_type)

        if seen_types:
            ax.legend(loc="upper right", fontsize=9)

        ax.set_title("PELT volume with alert markers")
        ax.set_xlabel("Date")
        ax.set_ylabel("stories/day")

        if len(x) <= 14:
            ax.set_xticks(x)
            ax.set_xticklabels([d.isoformat() for d in dates], rotation=45, ha="right", fontsize=8)

        fig.tight_layout()
        return fig




__all__ = ["MCPelt"]
