"""
peltdetect: Feed Activity Change Detection harness (PELT).

Entry points:
- `peltdetect.cli`: command line interface
"""

from .charts import plot_result
from .experiments.online.eval_models import (
    MatchRow,
    MetricsRow,
    OnlineAlertRow,
    OnlineEvalConfig,
    OnlineEvalSetting,
    TruthEvent,
    make_setting_id,
)
from .mc_pelt import MCPelt

__all__ = [
    "MCPelt",
    "plot_result",
    "OnlineEvalConfig",
    "OnlineEvalSetting",
    "TruthEvent",
    "OnlineAlertRow",
    "MatchRow",
    "MetricsRow",
    "make_setting_id",
]

