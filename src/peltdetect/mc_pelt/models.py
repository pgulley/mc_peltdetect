from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, Dict, List, Optional


@dataclasses.dataclass(frozen=True)
class Segment:
    start_idx: int
    end_idx: int
    start: dt.date
    end: dt.date
    mean_volume: float
    mean_log_volume: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "mean_volume": self.mean_volume,
            "mean_log_volume": self.mean_log_volume,
        }


@dataclasses.dataclass(frozen=True)
class Alert:
    type: str
    from_segment: Optional[int]
    to_segment: Optional[int]
    start: dt.date
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "from": self.from_segment,
            "to": self.to_segment,
            "start": self.start.isoformat(),
            "details": self.details,
        }


@dataclasses.dataclass
class RunResult:
    query: str
    source_id: int
    start_date: dt.date
    end_date: dt.date
    model: str
    min_size: int
    penalty: float
    n_days: int
    dates: List[dt.date]
    volume: List[int]
    log_volume: List[float]
    segments: List[Segment]
    alerts: List[Alert] = dataclasses.field(default_factory=list)
