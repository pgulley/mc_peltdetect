from __future__ import annotations

import datetime as dt
from typing import Dict, List, Sequence, Tuple

from .eval_models import MatchRow, OnlineAlertRow, TruthEvent


def _within_window(*, truth_date: dt.date, alert_date: dt.date, lead_tolerance_days: int, lag_tolerance_days: int) -> bool:
    delta = (alert_date - truth_date).days
    return (-lead_tolerance_days) <= delta <= lag_tolerance_days


def _group_truth_events(truth_events: Sequence[TruthEvent]) -> Dict[Tuple[int, str], List[TruthEvent]]:
    grouped: Dict[Tuple[int, str], List[TruthEvent]] = {}
    for event in truth_events:
        key = (int(event.source_id), event.alert_type)
        grouped.setdefault(key, []).append(event)
    for rows in grouped.values():
        rows.sort(key=lambda r: r.truth_event_date)
    return grouped


def _group_online_alerts(alerts: Sequence[OnlineAlertRow]) -> Dict[Tuple[str, int, str], List[OnlineAlertRow]]:
    grouped: Dict[Tuple[str, int, str], List[OnlineAlertRow]] = {}
    for alert in alerts:
        key = (alert.setting_id, int(alert.source_id), alert.alert_type)
        grouped.setdefault(key, []).append(alert)
    for rows in grouped.values():
        rows.sort(key=lambda r: (r.alert_start_date, r.run_date))
    return grouped


def match_truth_to_online_alerts(
    *,
    truth_events: Sequence[TruthEvent],
    online_alerts: Sequence[OnlineAlertRow],
    lead_tolerance_days: int,
    lag_tolerance_days: int,
) -> List[MatchRow]:
    if lead_tolerance_days < 0 or lag_tolerance_days < 0:
        raise ValueError("lead_tolerance_days and lag_tolerance_days must be >= 0")
    by_truth = _group_truth_events(truth_events)
    by_alert = _group_online_alerts(online_alerts)
    out: List[MatchRow] = []
    for (setting_id, source_id, alert_type), alerts in by_alert.items():
        truths = by_truth.get((source_id, alert_type), [])
        used_alert_idx: set[int] = set()
        used_truth_idx: set[int] = set()
        for t_idx, truth in enumerate(truths):
            candidates = sorted(
                [
                    (abs((alerts[a_idx].alert_start_date - truth.truth_event_date).days), a_idx)
                    for a_idx in range(len(alerts))
                    if a_idx not in used_alert_idx
                    and _within_window(
                        truth_date=truth.truth_event_date,
                        alert_date=alerts[a_idx].alert_start_date,
                        lead_tolerance_days=lead_tolerance_days,
                        lag_tolerance_days=lag_tolerance_days,
                    )
                ],
                key=lambda x: (x[0], alerts[x[1]].alert_start_date, alerts[x[1]].run_date),
            )
            if not candidates:
                continue
            chosen_alert_idx = candidates[0][1]
            used_alert_idx.add(chosen_alert_idx)
            used_truth_idx.add(t_idx)
            chosen_alert = alerts[chosen_alert_idx]
            delay_days = (chosen_alert.alert_start_date - truth.truth_event_date).days
            out.append(
                MatchRow(
                    setting_id=setting_id,
                    source_id=source_id,
                    alert_type=alert_type,
                    truth_event_date=truth.truth_event_date,
                    alert_start_date=chosen_alert.alert_start_date,
                    delay_days=delay_days,
                    is_matched=True,
                )
            )
        for t_idx, truth in enumerate(truths):
            if t_idx in used_truth_idx:
                continue
            out.append(
                MatchRow(
                    setting_id=setting_id,
                    source_id=source_id,
                    alert_type=alert_type,
                    truth_event_date=truth.truth_event_date,
                    alert_start_date=None,
                    delay_days=None,
                    is_matched=False,
                )
            )
        for a_idx, alert in enumerate(alerts):
            if a_idx in used_alert_idx:
                continue
            out.append(
                MatchRow(
                    setting_id=setting_id,
                    source_id=source_id,
                    alert_type=alert_type,
                    truth_event_date=None,
                    alert_start_date=alert.alert_start_date,
                    delay_days=None,
                    is_matched=False,
                )
            )
    out.sort(
        key=lambda r: (
            r.setting_id,
            r.source_id,
            r.alert_type,
            r.truth_event_date or dt.date(1900, 1, 1),
            r.alert_start_date or dt.date(1900, 1, 1),
            0 if r.is_matched else 1,
        )
    )
    return out
