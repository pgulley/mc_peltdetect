from __future__ import annotations

import datetime as dt
from typing import Optional

import mediacloud.api
import pandas as pd


def _coerce_date(d: object) -> dt.date:
    if isinstance(d, dt.date) and not isinstance(d, dt.datetime):
        return d
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, str):
        return dt.date.fromisoformat(d[:10])
    raise TypeError(f"Unsupported date value: {d!r}")


def fetch_story_count_over_time(
    *,
    query: str,
    start_date: dt.date,
    end_date: dt.date,
    source_id: int,
    api_key: str,
    platform: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch per-day story counts from Media Cloud for a single source.

    Returns a DataFrame with:
    - date: datetime.date
    - volume: int (stories count for the query on that day)
    """

    search = mediacloud.api.SearchApi(api_key)
    results = search.story_count_over_time(
        query=query,
        start_date=start_date,
        end_date=end_date,
        source_ids=[source_id],
        platform=platform,
    )

    if not results:
        # Caller will still normalize to a full date range.
        return pd.DataFrame({"date": pd.to_datetime([]), "volume": pd.Series([], dtype=int)})

    df = pd.DataFrame(results)
    if "count" not in df.columns:
        raise KeyError(
            "Unexpected Media Cloud response: expected a `count` field. "
            f"Got columns: {list(df.columns)}"
        )

    df = df.rename(columns={"count": "volume"})
    df["date"] = df["date"].map(_coerce_date)
    df["volume"] = df["volume"].astype(int)
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "volume"]]

