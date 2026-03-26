from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd


def _coerce_date(d: object) -> dt.date:
    if isinstance(d, dt.date) and not isinstance(d, dt.datetime):
        return d
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, str):
        return dt.date.fromisoformat(d[:10])
    raise TypeError(f"Unsupported date value: {d!r}")


def prepare_series(
    series: pd.DataFrame,
    *,
    start_date: dt.date,
    end_date: dt.date,
) -> pd.DataFrame:
    if series is None or len(series) == 0:
        dates = pd.date_range(start_date, end_date, freq="D").date
        out = pd.DataFrame({"date": list(dates), "volume": np.zeros(len(dates), dtype=int)})
        out["log_volume"] = np.log1p(out["volume"].to_numpy(dtype=float))
        return out

    df = series.copy()
    if "date" not in df.columns or "volume" not in df.columns:
        raise ValueError(f"Expected columns `date` and `volume`, got: {list(df.columns)}")
    df["date"] = df["date"].map(_coerce_date)
    df["volume"] = df["volume"].astype(int)
    df = df.sort_values("date").reset_index(drop=True)
    full_dates = pd.date_range(start_date, end_date, freq="D").date
    df = df.set_index("date").reindex(full_dates, fill_value=0).reset_index()
    df = df.rename(columns={"index": "date"})
    df["log_volume"] = np.log1p(df["volume"].to_numpy(dtype=float))
    return df
