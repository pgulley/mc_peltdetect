from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
from typing import Any, Dict, List, Optional


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _stable_json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def make_setting_id(params: Dict[str, Any], *, prefix: str = "setting") -> str:
    stable = _stable_json_dumps(params)
    digest = hashlib.sha1(stable.encode("utf-8")).hexdigest()[:12]  # noqa: S324
    return f"{prefix}_{digest}"


@dataclasses.dataclass(frozen=True)
class OnlineEvalSetting:
    window_days: int
    min_size: int
    penalty: str | float
    drop_threshold: float
    rise_threshold: float
    zero_threshold: float
    silence_multiplier: float
    model: str = "l2"
    setting_id: Optional[str] = None

    def normalized_params(self) -> Dict[str, Any]:
        return {
            "window_days": int(self.window_days),
            "min_size": int(self.min_size),
            "penalty": self.penalty,
            "drop_threshold": float(self.drop_threshold),
            "rise_threshold": float(self.rise_threshold),
            "zero_threshold": float(self.zero_threshold),
            "silence_multiplier": float(self.silence_multiplier),
            "model": self.model,
        }

    def resolved_setting_id(self) -> str:
        return self.setting_id or make_setting_id(self.normalized_params())

    def to_dict(self) -> Dict[str, Any]:
        payload = self.normalized_params()
        payload["setting_id"] = self.resolved_setting_id()
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OnlineEvalSetting":
        return cls(
            window_days=int(payload["window_days"]),
            min_size=int(payload["min_size"]),
            penalty=payload["penalty"],
            drop_threshold=float(payload["drop_threshold"]),
            rise_threshold=float(payload["rise_threshold"]),
            zero_threshold=float(payload["zero_threshold"]),
            silence_multiplier=float(payload["silence_multiplier"]),
            model=str(payload.get("model", "l2")),
            setting_id=payload.get("setting_id"),
        )


@dataclasses.dataclass(frozen=True)
class OnlineEvalConfig:
    experiment_name: str
    offline_batch_dir: str
    output_dir: str
    source_ids: List[int]
    start_date: dt.date
    end_date: dt.date
    truth_alert_types: List[str]
    truth_cluster_gap_days: int
    lead_tolerance_days: int
    lag_tolerance_days: int
    recent_truth_lookback_days: int = 120
    score_recent_only: bool = True
    settings: List[OnlineEvalSetting] = dataclasses.field(default_factory=list)
    created_at_utc: Optional[str] = None
    code_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "offline_batch_dir": self.offline_batch_dir,
            "output_dir": self.output_dir,
            "source_ids": [int(sid) for sid in self.source_ids],
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "truth_alert_types": list(self.truth_alert_types),
            "truth_cluster_gap_days": int(self.truth_cluster_gap_days),
            "lead_tolerance_days": int(self.lead_tolerance_days),
            "lag_tolerance_days": int(self.lag_tolerance_days),
            "recent_truth_lookback_days": int(self.recent_truth_lookback_days),
            "score_recent_only": bool(self.score_recent_only),
            "settings": [setting.to_dict() for setting in self.settings],
            "created_at_utc": self.created_at_utc,
            "code_version": self.code_version,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OnlineEvalConfig":
        return cls(
            experiment_name=str(payload["experiment_name"]),
            offline_batch_dir=str(payload["offline_batch_dir"]),
            output_dir=str(payload["output_dir"]),
            source_ids=[int(sid) for sid in payload.get("source_ids", [])],
            start_date=_parse_date(payload["start_date"]),
            end_date=_parse_date(payload["end_date"]),
            truth_alert_types=[str(x) for x in payload.get("truth_alert_types", [])],
            truth_cluster_gap_days=int(payload["truth_cluster_gap_days"]),
            lead_tolerance_days=int(payload["lead_tolerance_days"]),
            lag_tolerance_days=int(payload["lag_tolerance_days"]),
            recent_truth_lookback_days=int(payload.get("recent_truth_lookback_days", 120)),
            score_recent_only=bool(payload.get("score_recent_only", True)),
            settings=[OnlineEvalSetting.from_dict(x) for x in payload.get("settings", [])],
            created_at_utc=payload.get("created_at_utc"),
            code_version=payload.get("code_version"),
        )


@dataclasses.dataclass(frozen=True)
class TruthEvent:
    source_id: int
    alert_type: str
    truth_event_date: dt.date
    offline_support_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": int(self.source_id),
            "alert_type": self.alert_type,
            "truth_event_date": self.truth_event_date.isoformat(),
            "offline_support_count": int(self.offline_support_count),
        }


@dataclasses.dataclass(frozen=True)
class OnlineAlertRow:
    setting_id: str
    source_id: int
    run_date: dt.date
    alert_type: str
    alert_start_date: dt.date
    details_json: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "setting_id": self.setting_id,
            "source_id": int(self.source_id),
            "run_date": self.run_date.isoformat(),
            "alert_type": self.alert_type,
            "alert_start_date": self.alert_start_date.isoformat(),
            "details_json": self.details_json,
        }


@dataclasses.dataclass(frozen=True)
class MatchRow:
    setting_id: str
    source_id: int
    alert_type: str
    truth_event_date: Optional[dt.date]
    alert_start_date: Optional[dt.date]
    delay_days: Optional[int]
    is_matched: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "setting_id": self.setting_id,
            "source_id": int(self.source_id),
            "alert_type": self.alert_type,
            "truth_event_date": None if self.truth_event_date is None else self.truth_event_date.isoformat(),
            "alert_start_date": None if self.alert_start_date is None else self.alert_start_date.isoformat(),
            "delay_days": self.delay_days,
            "is_matched": bool(self.is_matched),
        }


@dataclasses.dataclass(frozen=True)
class MetricsRow:
    setting_id: str
    n_truth_events: int
    n_online_alerts: int
    event_recall: float
    precision: float
    median_delay_days: Optional[float]
    timely_recall_at_0: float
    timely_recall_at_3: float
    timely_recall_at_7: float
    timely_recall_at_14: float
    false_alerts_per_source_year: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "setting_id": self.setting_id,
            "n_truth_events": int(self.n_truth_events),
            "n_online_alerts": int(self.n_online_alerts),
            "event_recall": float(self.event_recall),
            "precision": float(self.precision),
            "median_delay_days": self.median_delay_days,
            "timely_recall_at_0": float(self.timely_recall_at_0),
            "timely_recall_at_3": float(self.timely_recall_at_3),
            "timely_recall_at_7": float(self.timely_recall_at_7),
            "timely_recall_at_14": float(self.timely_recall_at_14),
            "false_alerts_per_source_year": float(self.false_alerts_per_source_year),
        }
