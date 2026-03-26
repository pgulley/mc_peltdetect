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

    def __call__(
        self,
        series: pd.DataFrame | Sequence[Mapping[str, Any]],
        *,
        source_id: int,
        query: str = "*",
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
            query=query,
            source_id=int(source_id),
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
        return {
            "source_id": int(source_id),
            "query": query,
            "start_date": effective_start.isoformat(),
            "end_date": effective_end.isoformat(),
            "model": self.model,
            "min_size": int(self.min_size),
            "penalty_used": float(penalty_value),
            "dates": [d.isoformat() for d in prepared["date"].to_list()],
            "volume": [int(v) for v in prepared["volume"].to_list()],
            "log_volume": [float(x) for x in prepared["log_volume"].to_list()],
            "alerts": [a.to_dict() for a in alerts],
            "breakpoints": [s.start.isoformat() for s in run.segments[1:]],
            "segments": [s.to_dict() for s in run.segments],
        }

    def detect_alerts(
        self,
        series: pd.DataFrame | Sequence[Mapping[str, Any]],
        *,
        source_id: int,
        query: str = "*",
        start_date: Optional[dt.date] = None,
        end_date: Optional[dt.date] = None,
    ) -> List[Dict[str, Any]]:
        return self(
            series,
            source_id=source_id,
            query=query,
            start_date=start_date,
            end_date=end_date,
        )["alerts"]


__all__ = ["MCPelt"]
