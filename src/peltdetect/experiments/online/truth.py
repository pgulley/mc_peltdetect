from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .eval_models import TruthEvent


SOURCE_DIR_RE = re.compile(r"^source_(\d+)$")


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


def _find_run_jsons(batch_dir: Path) -> List[Tuple[int, Path]]:
    out: List[Tuple[int, Path]] = []
    for p in sorted(batch_dir.iterdir()):
        if not p.is_dir():
            continue
        match = SOURCE_DIR_RE.match(p.name)
        if not match:
            continue
        source_id = int(match.group(1))
        run_json = p / "run_result.json"
        if run_json.is_file():
            out.append((source_id, run_json))
    return out


def _normalize_truth_types(truth_types: Sequence[str]) -> Set[str]:
    return {t.strip() for t in truth_types if t and t.strip()}


def extract_raw_truth_events(
    *,
    offline_batch_dir: Path,
    truth_types: Sequence[str],
    source_ids: Optional[Iterable[int]] = None,
) -> List[Tuple[int, str, dt.date]]:
    allowed_types = _normalize_truth_types(truth_types)
    source_filter = None if source_ids is None else {int(x) for x in source_ids}
    rows: List[Tuple[int, str, dt.date]] = []
    for source_id, run_json_path in _find_run_jsons(offline_batch_dir):
        if source_filter is not None and source_id not in source_filter:
            continue
        with run_json_path.open("r", encoding="utf-8") as f:
            payload: Dict[str, object] = json.load(f)
        json_source_id = payload.get("source_id")
        if isinstance(json_source_id, int):
            source_id = int(json_source_id)
        for alert in payload.get("alerts") or []:
            if not isinstance(alert, dict):
                continue
            alert_type = str(alert.get("type") or "").strip()
            if alert_type not in allowed_types:
                continue
            start_raw = alert.get("start")
            if not start_raw:
                continue
            rows.append((source_id, alert_type, _parse_date(str(start_raw))))
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    return rows


def cluster_truth_events(
    raw_events: Sequence[Tuple[int, str, dt.date]],
    *,
    truth_cluster_gap_days: int,
) -> List[TruthEvent]:
    if truth_cluster_gap_days < 0:
        raise ValueError("truth_cluster_gap_days must be >= 0")
    if not raw_events:
        return []
    clustered: List[TruthEvent] = []
    current_source_id, current_type, cluster_start = raw_events[0]
    prev_date = raw_events[0][2]
    support_count = 1
    for source_id, alert_type, event_date in raw_events[1:]:
        same_key = source_id == current_source_id and alert_type == current_type
        close_enough = (event_date - prev_date).days <= truth_cluster_gap_days
        if same_key and close_enough:
            support_count += 1
            prev_date = event_date
            continue
        clustered.append(
            TruthEvent(
                source_id=current_source_id,
                alert_type=current_type,
                truth_event_date=cluster_start,
                offline_support_count=support_count,
            )
        )
        current_source_id = source_id
        current_type = alert_type
        cluster_start = event_date
        prev_date = event_date
        support_count = 1
    clustered.append(
        TruthEvent(
            source_id=current_source_id,
            alert_type=current_type,
            truth_event_date=cluster_start,
            offline_support_count=support_count,
        )
    )
    return clustered


def build_truth_events(
    *,
    offline_batch_dir: Path,
    truth_types: Sequence[str],
    truth_cluster_gap_days: int,
    source_ids: Optional[Iterable[int]] = None,
) -> List[TruthEvent]:
    raw = extract_raw_truth_events(
        offline_batch_dir=offline_batch_dir,
        truth_types=truth_types,
        source_ids=source_ids,
    )
    return cluster_truth_events(raw, truth_cluster_gap_days=truth_cluster_gap_days)
