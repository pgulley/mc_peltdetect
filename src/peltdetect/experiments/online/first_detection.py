from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _parse_date(value: object) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _within_window(*, truth_date: dt.date, alert_date: dt.date, lead_tolerance_days: int, lag_tolerance_days: int) -> bool:
    delta = (alert_date - truth_date).days
    return (-lead_tolerance_days) <= delta <= lag_tolerance_days


def first_online_detection_for_truth(
    *,
    truth_event_date: dt.date,
    alert_type: str,
    online_alerts: Sequence[Dict[str, Any]],
    setting_id: str,
    source_id: int,
    lead_tolerance_days: int,
    lag_tolerance_days: int,
) -> Tuple[Optional[dt.date], Optional[dt.date], Optional[int]]:
    candidates: List[Tuple[dt.date, dt.date]] = []
    for row in online_alerts:
        if str(row.get("setting_id", "")) != setting_id:
            continue
        if int(row.get("source_id", -1)) != int(source_id):
            continue
        if str(row.get("alert_type", "")) != alert_type:
            continue
        try:
            a_start = _parse_date(row["alert_start_date"])
            run_d = _parse_date(row["run_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if not _within_window(
            truth_date=truth_event_date,
            alert_date=a_start,
            lead_tolerance_days=lead_tolerance_days,
            lag_tolerance_days=lag_tolerance_days,
        ):
            continue
        candidates.append((a_start, run_d))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda t: (t[0], t[1]))
    first_start, first_run = candidates[0]
    delay = (first_start - truth_event_date).days
    return first_start, first_run, delay


def truth_first_detection_table(
    *,
    truth_rows: Sequence[Dict[str, Any]],
    online_alert_rows: Sequence[Dict[str, Any]],
    setting_id: str,
    source_id: int,
    lead_tolerance_days: int,
    lag_tolerance_days: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in sorted(truth_rows, key=lambda r: (_parse_date(r["truth_event_date"]), str(r.get("alert_type", "")))):
        if int(row.get("source_id", -1)) != int(source_id):
            continue
        t_date = _parse_date(row["truth_event_date"])
        atype = str(row.get("alert_type", ""))
        first_start, first_run, delay = first_online_detection_for_truth(
            truth_event_date=t_date,
            alert_type=atype,
            online_alerts=online_alert_rows,
            setting_id=setting_id,
            source_id=source_id,
            lead_tolerance_days=lead_tolerance_days,
            lag_tolerance_days=lag_tolerance_days,
        )
        out.append(
            {
                "source_id": int(source_id),
                "setting_id": setting_id,
                "truth_event_date": t_date.isoformat(),
                "alert_type": atype,
                "first_online_alert_date": None if first_start is None else first_start.isoformat(),
                "first_online_run_date": None if first_run is None else first_run.isoformat(),
                "min_delay_days": delay,
            }
        )
    return out


def terminal_going_dark_truth_row(truth_rows: Sequence[Dict[str, Any]], *, source_id: int) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for row in truth_rows:
        if int(row.get("source_id", -1)) != int(source_id):
            continue
        atype = str(row.get("alert_type", ""))
        if atype not in ("near_zero", "silence"):
            continue
        candidates.append(row)
    if not candidates:
        return None
    return max(candidates, key=lambda r: _parse_date(r["truth_event_date"]))
