from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .eval_models import MatchRow, MetricsRow


@dataclass(frozen=True)
class EvalScope:
    end_date: dt.date
    recent_truth_lookback_days: int = 120
    score_recent_only: bool = True
    n_sources: Optional[int] = None
    eval_start_date: Optional[dt.date] = None


def _passes_recent_filter(match: MatchRow, scope: EvalScope) -> bool:
    if not scope.score_recent_only:
        return True
    if match.truth_event_date is None:
        return False
    cutoff = scope.end_date - dt.timedelta(days=scope.recent_truth_lookback_days)
    return match.truth_event_date >= cutoff


def _derive_eval_years(scope: EvalScope) -> float:
    if scope.eval_start_date is None:
        return 1.0
    days = max(1, (scope.end_date - scope.eval_start_date).days + 1)
    return float(days) / 365.25


def _metrics_from_subset(*, setting_id: str, subset: Sequence[MatchRow], n_sources: int, eval_years: float) -> MetricsRow:
    matched = [r for r in subset if r.is_matched]
    matched_truth_count = len([r for r in matched if r.truth_event_date is not None])
    matched_alert_count = len([r for r in matched if r.alert_start_date is not None])
    unmatched_truth = len([r for r in subset if (not r.is_matched) and r.truth_event_date is not None])
    unmatched_alert = len([r for r in subset if (not r.is_matched) and r.alert_start_date is not None])
    n_truth_events = matched_truth_count + unmatched_truth
    n_online_alerts = matched_alert_count + unmatched_alert
    event_recall = 0.0 if n_truth_events == 0 else float(matched_truth_count) / float(n_truth_events)
    precision = 0.0 if n_online_alerts == 0 else float(matched_alert_count) / float(n_online_alerts)
    delays = [int(r.delay_days) for r in matched if r.delay_days is not None]
    median_delay_days = None if not delays else float(statistics.median(delays))

    def timely_recall_at(k: int) -> float:
        if n_truth_events == 0:
            return 0.0
        timely = len([d for d in delays if d <= k])
        return float(timely) / float(n_truth_events)

    denom = max(1.0, float(max(1, n_sources)) * max(eval_years, 1e-9))
    false_alerts_per_source_year = float(unmatched_alert) / denom
    return MetricsRow(
        setting_id=setting_id,
        n_truth_events=n_truth_events,
        n_online_alerts=n_online_alerts,
        event_recall=event_recall,
        precision=precision,
        median_delay_days=median_delay_days,
        timely_recall_at_0=timely_recall_at(0),
        timely_recall_at_3=timely_recall_at(3),
        timely_recall_at_7=timely_recall_at(7),
        timely_recall_at_14=timely_recall_at(14),
        false_alerts_per_source_year=false_alerts_per_source_year,
    )


def aggregate_metrics_by_setting(matches: Sequence[MatchRow], *, scope: EvalScope) -> List[MetricsRow]:
    filtered = [m for m in matches if _passes_recent_filter(m, scope)]
    by_setting: Dict[str, List[MatchRow]] = defaultdict(list)
    for row in filtered:
        by_setting[row.setting_id].append(row)
    eval_years = _derive_eval_years(scope)
    out: List[MetricsRow] = []
    for setting_id, rows in sorted(by_setting.items(), key=lambda x: x[0]):
        out.append(
            _metrics_from_subset(
                setting_id=setting_id,
                subset=rows,
                n_sources=max(1, scope.n_sources or 1),
                eval_years=eval_years,
            )
        )
    return out


def aggregate_metrics_by_setting_and_type(matches: Sequence[MatchRow], *, scope: EvalScope) -> List[Dict[str, object]]:
    filtered = [m for m in matches if _passes_recent_filter(m, scope)]
    by_key: Dict[Tuple[str, str], List[MatchRow]] = defaultdict(list)
    for row in filtered:
        by_key[(row.setting_id, row.alert_type)].append(row)
    eval_years = _derive_eval_years(scope)
    out: List[Dict[str, object]] = []
    for (setting_id, alert_type), rows in sorted(by_key.items(), key=lambda x: (x[0][0], x[0][1])):
        m = _metrics_from_subset(
            setting_id=setting_id,
            subset=rows,
            n_sources=max(1, scope.n_sources or 1),
            eval_years=eval_years,
        )
        row = m.to_dict()
        row["alert_type"] = alert_type
        out.append(row)
    return out


def summarize_match_counts(matches: Iterable[MatchRow]) -> Dict[str, int]:
    rows = list(matches)
    return {
        "n_rows": len(rows),
        "n_matched_rows": len([r for r in rows if r.is_matched]),
        "n_unmatched_truth_rows": len([r for r in rows if (not r.is_matched) and r.truth_event_date is not None]),
        "n_unmatched_alert_rows": len([r for r in rows if (not r.is_matched) and r.alert_start_date is not None]),
    }
