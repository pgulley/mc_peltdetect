#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import itertools
import json
from pathlib import Path
from typing import Dict, List, Sequence


def _ensure_package_importable(repo_root: Path) -> None:
    # Supports running this script directly from repo root without installation.
    import sys

    pkg_path = repo_root / "peltdetect"
    if str(pkg_path) not in sys.path:
        sys.path.insert(0, str(pkg_path))


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _parse_int_list(raw: str) -> List[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_float_list(raw: str) -> List[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_penalty_list(raw: str) -> List[str | float]:
    out: List[str | float] = []
    for x in [s.strip() for s in raw.split(",") if s.strip()]:
        if x.lower() == "auto":
            out.append("auto")
        else:
            out.append(float(x))
    return out


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fieldnames})


def _write_text_summary(
    *,
    out_path: Path,
    source_id: int,
    source_display_name: str,
    start_date: dt.date,
    end_date: dt.date,
    n_settings: int,
    truth_types: Sequence[str],
    truth_cluster_gap_days: int,
    lead_tolerance_days: int,
    lag_tolerance_days: int,
    recent_truth_lookback_days: int,
    n_truth_events: int,
    n_online_alert_rows: int,
    n_match_rows: int,
    top_setting_id: str | None,
    top_setting_metrics: Dict[str, object] | None,
    truth_first_detection_lines: Sequence[str],
    terminal_going_dark_line: str,
    files: Dict[str, str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("Online Evaluation Experiment Summary")
    lines.append("=" * 36)
    lines.append("")
    lines.append("Scope")
    lines.append("-----")
    lines.append(f"- Source ID: {source_id}")
    if source_display_name:
        lines.append(f"- Source name/label: {source_display_name}")
    lines.append(f"- Date range: {start_date.isoformat()} to {end_date.isoformat()}")
    lines.append(f"- Settings evaluated: {n_settings}")
    lines.append("")
    lines.append("Truth + Matching")
    lines.append("---------------")
    lines.append(f"- Truth types: {', '.join(truth_types)}")
    lines.append(f"- Truth cluster gap days: {truth_cluster_gap_days}")
    lines.append(f"- Matching lead tolerance days: {lead_tolerance_days}")
    lines.append(f"- Matching lag tolerance days: {lag_tolerance_days}")
    lines.append(f"- Recent truth lookback days: {recent_truth_lookback_days}")
    lines.append("")
    lines.append("Run Counts")
    lines.append("----------")
    lines.append(f"- Truth events: {n_truth_events}")
    lines.append(f"- Online alert rows: {n_online_alert_rows}")
    lines.append(f"- Match rows: {n_match_rows}")
    lines.append("")
    lines.append("Top Setting")
    lines.append("-----------")
    lines.append(f"- setting_id: {top_setting_id or 'N/A'}")
    if top_setting_metrics:
        lines.append(f"- timely_recall_at_7: {top_setting_metrics.get('timely_recall_at_7')}")
        lines.append(f"- false_alerts_per_source_year: {top_setting_metrics.get('false_alerts_per_source_year')}")
        lines.append(f"- precision: {top_setting_metrics.get('precision')}")
        lines.append(f"- median_delay_days: {top_setting_metrics.get('median_delay_days')}")
    lines.append("")
    lines.append("Ground truth → first online detection (top setting)")
    lines.append("-" * 46)
    lines.append(
        "For each offline truth event: earliest online alert of the same type within "
        f"[truth − {lead_tolerance_days}d, truth + {lag_tolerance_days}d] (top setting only)."
    )
    if truth_first_detection_lines:
        for line in truth_first_detection_lines:
            lines.append(line)
    else:
        lines.append("(no rows; missing top setting or no truth events)")
    lines.append("")
    lines.append("Terminal alert (going dark)")
    lines.append("-------------------------")
    lines.append(terminal_going_dark_line)
    lines.append("")
    lines.append("Stored Outputs")
    lines.append("--------------")
    for key in sorted(files.keys()):
        lines.append(f"- {key}: {files[key]}")
    lines.append("")
    lines.append("Figures")
    lines.append("-------")
    lines.append("- timeline_overlay_top_setting.png")
    lines.append("- volume_with_events_top_setting.png")
    lines.append("(optional: delay_cdf_top_settings.png if --plot-delay-cdf)")
    lines.append("")

    with out_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run end-to-end online eval sweep for one source and produce visualizations."
    )
    p.add_argument("--source-id", required=True, type=int, help="Single source id to evaluate")
    p.add_argument("--start-date", required=True, help="Backtest start date (YYYY-MM-DD)")
    p.add_argument("--end-date", required=True, help="Backtest end date (YYYY-MM-DD)")
    p.add_argument("--out-dir", default=None, help="Output directory (default: peltdetect/out/online_eval/source_<id>/<start>_<end>)")
    p.add_argument("--query", default="*", help="Media Cloud query (default: '*').")
    p.add_argument("--api-key-env", default="MEDIACLOUD_API_KEY", help="Environment variable with API key.")
    p.add_argument("--window-days", default="30,45,60,90", help="Comma-separated window days")
    p.add_argument("--min-sizes", default="7", help="Comma-separated min_size values")
    p.add_argument("--penalties", default="auto", help='Comma-separated penalties ("auto" or float)')
    p.add_argument("--drop-thresholds", default="0.4,0.5,0.6", help="Comma-separated drop thresholds")
    p.add_argument("--rise-thresholds", default="1.5", help="Comma-separated rise thresholds")
    p.add_argument("--zero-thresholds", default="1.0", help="Comma-separated zero thresholds")
    p.add_argument("--silence-multipliers", default="3,5,7", help="Comma-separated silence multipliers")
    p.add_argument("--model", default="l2", help="PELT model")
    p.add_argument("--truth-types", default="drop,near_zero,silence,surge", help="Truth alert types")
    p.add_argument("--truth-cluster-gap-days", type=int, default=7, help="Truth clustering gap days")
    p.add_argument("--lead-tolerance-days", type=int, default=3, help="Matching lead tolerance")
    p.add_argument("--lag-tolerance-days", type=int, default=14, help="Matching lag tolerance")
    p.add_argument("--recent-truth-lookback-days", type=int, default=120, help="Recent scorecard horizon")
    p.add_argument("--day-stride", type=int, default=1, help="Simulate every Nth day")
    p.add_argument(
        "--plot-delay-cdf",
        action="store_true",
        help="Also write delay_cdf_top_settings.png (off by default).",
    )
    p.add_argument("--top-k-delay-cdf", type=int, default=5, help="Number of top settings for delay CDF when --plot-delay-cdf")
    return p.parse_args()


def _load_source_display_name(meta: Dict[str, object]) -> str:
    name = (meta.get("name") or "").strip()
    label = (meta.get("label") or "").strip()
    if label and name and label != name:
        return f"{label} / {name}"
    return label or name or ""


def _format_truth_delay_lines(rows: List[Dict[str, object]]) -> List[str]:
    out: List[str] = []
    for r in rows:
        t = r.get("truth_event_date")
        at = r.get("alert_type")
        fo = r.get("first_online_alert_date")
        d = r.get("min_delay_days")
        if fo is None or d is None:
            out.append(
                f"- {t} [{at}]: no online detection of same type in match window "
                f"(first_online=N/A, min_delay=N/A)"
            )
        else:
            sign = "+" if (isinstance(d, int) and d > 0) else ""
            out.append(
                f"- {t} [{at}]: first_online={fo}, min_delay={sign}{d} days"
            )
    return out


def _select_top_setting(metrics_rows: List[Dict[str, object]]) -> str | None:
    if not metrics_rows:
        return None
    ordered = sorted(
        metrics_rows,
        key=lambda r: (
            -float(r.get("timely_recall_at_7", 0.0) or 0.0),
            float(r.get("false_alerts_per_source_year", 0.0) or 0.0),
            str(r.get("setting_id", "")),
        ),
    )
    return str(ordered[0].get("setting_id", "")) if ordered else None


def main() -> None:
    args = parse_args()
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    if end_date < start_date:
        raise SystemExit("end-date must be >= start-date")

    # Anchor default output under the repository's `peltdetect/out/` directory.
    # This avoids accidentally creating `peltdetect/peltdetect/out/...` when the script
    # is executed with a working directory inside `peltdetect/`.
    out_base = Path(__file__).resolve().parents[1] / "out" / "online_eval"
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (
        out_base / f"source_{args.source_id}" / f"{start_date.isoformat()}_{end_date.isoformat()}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    import os
    import mediacloud.api
    from peltdetect.api import fetch_story_count_over_time
    from peltdetect.charts.online import plot_delay_cdf, plot_source_timeline_overlay, plot_source_volume_with_events
    from peltdetect.mc_pelt import MCPelt
    from peltdetect.mc_pelt.io import save_result, write_dict_rows_csv
    from peltdetect.mc_pelt.preprocess import prepare_series
    from peltdetect.experiments.online.eval_models import OnlineEvalSetting
    from peltdetect.experiments.online.first_detection import (
        first_online_detection_for_truth,
        terminal_going_dark_truth_row,
        truth_first_detection_table,
    )
    from peltdetect.experiments.online.match import match_truth_to_online_alerts
    from peltdetect.experiments.online.metrics import (
        EvalScope,
        aggregate_metrics_by_setting,
        aggregate_metrics_by_setting_and_type,
    )
    from peltdetect.experiments.online.sim import SourceSeries, simulate_online_alerts_for_setting
    from peltdetect.experiments.online.truth import cluster_truth_events
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key in env var: {args.api_key_env}")
    directory_api = mediacloud.api.DirectoryApi(api_key)
    try:
        source_meta = directory_api.source(int(args.source_id))
    except Exception:
        source_meta = {}
    source_display_name = _load_source_display_name(source_meta)

    series_df = fetch_story_count_over_time(
        query=args.query,
        start_date=start_date,
        end_date=end_date,
        source_id=int(args.source_id),
        api_key=api_key,
    )
    offline_result = MCPelt().detect_for_source(
        series_df,
        source_id=int(args.source_id),
        query=args.query,
        start_date=start_date,
        end_date=end_date,
    )
    save_result(offline_result, out_dir=out_dir / "offline_reference")

    prepared_series = prepare_series(series_df, start_date=start_date, end_date=end_date)
    series = SourceSeries(
        source_id=int(args.source_id),
        query=str(offline_result.get("query", "*")),
        dates=[dt.date.fromisoformat(str(d)[:10]) for d in prepared_series["date"].to_list()],
        volume=[int(v) for v in prepared_series["volume"].to_list()],
        log_volume=[float(v) for v in prepared_series["log_volume"].to_list()],
    )
    source_series = {int(args.source_id): series}

    truth_types = [x.strip() for x in args.truth_types.split(",") if x.strip()]
    raw_truth_events = []
    for alert in offline_result.get("alerts", []):
        atype = str(alert.get("type", ""))
        if atype not in truth_types:
            continue
        start_raw = alert.get("start")
        if not start_raw:
            continue
        raw_truth_events.append((int(args.source_id), atype, dt.date.fromisoformat(str(start_raw)[:10])))
    raw_truth_events.sort(key=lambda x: (x[0], x[1], x[2]))
    truth_events = cluster_truth_events(raw_truth_events, truth_cluster_gap_days=args.truth_cluster_gap_days)
    truth_rows = [t.to_dict() for t in truth_events]
    truth_csv = out_dir / "truth_events.csv"
    write_dict_rows_csv(
        truth_csv,
        fieldnames=["source_id", "alert_type", "truth_event_date", "offline_support_count"],
        rows=truth_rows,
    )

    settings: List[OnlineEvalSetting] = []
    for combo in itertools.product(
        _parse_int_list(args.window_days),
        _parse_int_list(args.min_sizes),
        _parse_penalty_list(args.penalties),
        _parse_float_list(args.drop_thresholds),
        _parse_float_list(args.rise_thresholds),
        _parse_float_list(args.zero_thresholds),
        _parse_float_list(args.silence_multipliers),
    ):
        settings.append(
            OnlineEvalSetting(
                window_days=combo[0],
                min_size=combo[1],
                penalty=combo[2],
                drop_threshold=combo[3],
                rise_threshold=combo[4],
                zero_threshold=combo[5],
                silence_multiplier=combo[6],
                model=args.model,
            )
        )

    all_alert_rows = []
    sim_rows: List[Dict[str, object]] = []
    for setting in settings:
        alert_rows, sim_summary = simulate_online_alerts_for_setting(
            source_series=source_series,
            setting=setting,
            start_date=start_date,
            end_date=end_date,
            day_stride=args.day_stride,
        )
        all_alert_rows.extend(alert_rows)
        sim_rows.append(
            {
                **setting.to_dict(),
                **sim_summary.to_dict(),
            }
        )

    online_alert_rows = [r.to_dict() for r in all_alert_rows]
    online_alerts_csv = out_dir / "online_alerts.csv"
    write_dict_rows_csv(
        online_alerts_csv,
        fieldnames=["setting_id", "source_id", "run_date", "alert_type", "alert_start_date", "details_json"],
        rows=online_alert_rows,
    )

    settings_csv = out_dir / "settings.csv"
    _write_csv(
        settings_csv,
        fieldnames=[
            "setting_id",
            "window_days",
            "min_size",
            "penalty",
            "drop_threshold",
            "rise_threshold",
            "zero_threshold",
            "silence_multiplier",
            "model",
            "n_sources",
            "n_runs_attempted",
            "n_runs_skipped_insufficient_history",
            "n_alert_rows",
        ],
        rows=sim_rows,
    )

    matches = match_truth_to_online_alerts(
        truth_events=truth_events,
        online_alerts=all_alert_rows,
        lead_tolerance_days=args.lead_tolerance_days,
        lag_tolerance_days=args.lag_tolerance_days,
    )
    match_rows = [m.to_dict() for m in matches]
    matches_csv = out_dir / "matches.csv"
    write_dict_rows_csv(
        matches_csv,
        fieldnames=["setting_id", "source_id", "alert_type", "truth_event_date", "alert_start_date", "delay_days", "is_matched"],
        rows=match_rows,
    )

    scope = EvalScope(
        end_date=end_date,
        recent_truth_lookback_days=args.recent_truth_lookback_days,
        score_recent_only=True,
        n_sources=1,
        eval_start_date=start_date,
    )
    metrics_by_setting = aggregate_metrics_by_setting(matches, scope=scope)
    metrics_rows = [m.to_dict() for m in metrics_by_setting]
    if not metrics_rows:
        # Fallback for sparse recent windows: still produce comparative plots.
        scope_full = EvalScope(
            end_date=end_date,
            recent_truth_lookback_days=args.recent_truth_lookback_days,
            score_recent_only=False,
            n_sources=1,
            eval_start_date=start_date,
        )
        metrics_by_setting = aggregate_metrics_by_setting(matches, scope=scope_full)
        metrics_rows = [m.to_dict() for m in metrics_by_setting]
    metrics_csv = out_dir / "metrics_by_setting.csv"
    write_dict_rows_csv(
        metrics_csv,
        fieldnames=[
            "setting_id",
            "n_truth_events",
            "n_online_alerts",
            "event_recall",
            "precision",
            "median_delay_days",
            "timely_recall_at_0",
            "timely_recall_at_3",
            "timely_recall_at_7",
            "timely_recall_at_14",
            "false_alerts_per_source_year",
        ],
        rows=metrics_rows,
    )
    metrics_by_type = aggregate_metrics_by_setting_and_type(matches, scope=scope)
    metrics_type_csv = out_dir / "metrics_by_setting_and_type.csv"
    write_dict_rows_csv(
        metrics_type_csv,
        fieldnames=[
            "setting_id",
            "alert_type",
            "n_truth_events",
            "n_online_alerts",
            "event_recall",
            "precision",
            "median_delay_days",
            "timely_recall_at_0",
            "timely_recall_at_3",
            "timely_recall_at_7",
            "timely_recall_at_14",
            "false_alerts_per_source_year",
        ],
        rows=metrics_by_type,
    )

    top_setting_id = _select_top_setting(metrics_rows)
    top_setting_metrics = None
    if top_setting_id:
        for row in metrics_rows:
            if str(row.get("setting_id", "")) == top_setting_id:
                top_setting_metrics = row
                break

    truth_delay_table: List[Dict[str, object]] = []
    if top_setting_id:
        truth_delay_table = truth_first_detection_table(
            truth_rows=truth_rows,
            online_alert_rows=online_alert_rows,
            setting_id=top_setting_id,
            source_id=args.source_id,
            lead_tolerance_days=args.lead_tolerance_days,
            lag_tolerance_days=args.lag_tolerance_days,
        )
    truth_delay_csv = out_dir / "truth_first_detection_delays.csv"
    write_dict_rows_csv(
        truth_delay_csv,
        fieldnames=[
            "source_id",
            "setting_id",
            "truth_event_date",
            "alert_type",
            "first_online_alert_date",
            "first_online_run_date",
            "min_delay_days",
        ],
        rows=truth_delay_table,
    )

    terminal_row = terminal_going_dark_truth_row(truth_rows, source_id=args.source_id)
    terminal_going_dark_line = ""
    terminal_stdout = ""
    if top_setting_id and terminal_row:
        t_date = str(terminal_row["truth_event_date"])
        t_type = str(terminal_row["alert_type"])

        first_start, _first_run, delay = first_online_detection_for_truth(
            truth_event_date=dt.date.fromisoformat(t_date[:10]),
            alert_type=t_type,
            online_alerts=online_alert_rows,
            setting_id=top_setting_id,
            source_id=args.source_id,
            lead_tolerance_days=args.lead_tolerance_days,
            lag_tolerance_days=args.lag_tolerance_days,
        )
        if first_start is None:
            terminal_going_dark_line = (
                f"Latest terminal-class truth: {t_date} ({t_type}). "
                f"No first online {t_type} alert in "
                f"[−{args.lead_tolerance_days}d, +{args.lag_tolerance_days}d] window (top setting)."
            )
            terminal_stdout = (
                f"Terminal alert ({t_type} @ {t_date}): first online N/A "
                f"(no detection in window for setting {top_setting_id})"
            )
        else:
            sign = "+" if (delay is not None and delay > 0) else ""
            terminal_going_dark_line = (
                f"Latest terminal-class truth: {t_date} ({t_type}). "
                f"First online {t_type}: {first_start.isoformat()}; "
                f"min_delay={sign}{delay} days (top setting {top_setting_id})."
            )
            terminal_stdout = (
                f"Terminal alert ({t_type} @ {t_date}): first online {first_start.isoformat()}, "
                f"min_delay={sign}{delay} days"
            )
    elif terminal_row and not top_setting_id:
        terminal_going_dark_line = (
            f"Latest terminal-class truth: {terminal_row['truth_event_date']} ({terminal_row['alert_type']}). "
            "No top setting selected; run truth_first_detection_delays.csv manually."
        )
        terminal_stdout = terminal_going_dark_line
    else:
        terminal_going_dark_line = (
            "No terminal-class ground truth (near_zero/silence) for this source in truth_events."
        )
        terminal_stdout = terminal_going_dark_line

    if args.plot_delay_cdf:
        ranked_for_cdf = sorted(
            metrics_rows,
            key=lambda r: (
                -float(r.get("timely_recall_at_7", 0.0) or 0.0),
                float(r.get("false_alerts_per_source_year", 0.0) or 0.0),
            ),
        )[: max(1, args.top_k_delay_cdf)]
        cdf_setting_ids = [str(r.get("setting_id", "")) for r in ranked_for_cdf]
        plot_delay_cdf(
            matches_rows=match_rows,
            out_path=figures_dir / "delay_cdf_top_settings.png",
            setting_ids=cdf_setting_ids,
        )

    plot_source_timeline_overlay(
        truth_events=truth_rows,
        online_alerts=online_alert_rows,
        out_path=figures_dir / "timeline_overlay_top_setting.png",
        source_id=args.source_id,
        setting_id=top_setting_id,
        source_name=source_display_name or None,
    )
    plot_source_volume_with_events(
        dates=series.dates,
        volume=series.volume,
        truth_events=truth_rows,
        online_alerts=online_alert_rows,
        out_path=figures_dir / "volume_with_events_top_setting.png",
        source_id=args.source_id,
        setting_id=top_setting_id,
        source_name=source_display_name or None,
    )

    manifest = {
        "query": args.query,
        "source_id": int(args.source_id),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "n_settings": len(settings),
        "n_truth_events": len(truth_rows),
        "n_online_alert_rows": len(online_alert_rows),
        "n_matches_rows": len(match_rows),
        "top_setting_id": top_setting_id,
        "source_display_name": source_display_name,
        "terminal_going_dark_summary": terminal_stdout,
        "files": {
            "truth_events_csv": str(truth_csv),
            "truth_first_detection_delays_csv": str(truth_delay_csv),
            "online_alerts_csv": str(online_alerts_csv),
            "matches_csv": str(matches_csv),
            "settings_csv": str(settings_csv),
            "metrics_by_setting_csv": str(metrics_csv),
            "metrics_by_setting_and_type_csv": str(metrics_type_csv),
            "figures_dir": str(figures_dir),
        },
    }
    manifest_path = out_dir / "online_eval_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    summary_txt = out_dir / "online_eval_summary.txt"
    _write_text_summary(
        out_path=summary_txt,
        source_id=args.source_id,
        source_display_name=source_display_name,
        start_date=start_date,
        end_date=end_date,
        n_settings=len(settings),
        truth_types=truth_types,
        truth_cluster_gap_days=args.truth_cluster_gap_days,
        lead_tolerance_days=args.lead_tolerance_days,
        lag_tolerance_days=args.lag_tolerance_days,
        recent_truth_lookback_days=args.recent_truth_lookback_days,
        n_truth_events=len(truth_rows),
        n_online_alert_rows=len(online_alert_rows),
        n_match_rows=len(match_rows),
        top_setting_id=top_setting_id,
        top_setting_metrics=top_setting_metrics,
        truth_first_detection_lines=_format_truth_delay_lines(truth_delay_table),
        terminal_going_dark_line=terminal_going_dark_line,
        files=manifest["files"],
    )

    print(f"Source id: {args.source_id}")
    if source_display_name:
        print(f"Source name: {source_display_name}")
    print(f"Settings: {len(settings)}")
    print(f"Truth events: {len(truth_rows)}")
    print(f"Online alerts: {len(online_alert_rows)}")
    print(f"Match rows: {len(match_rows)}")
    print(f"Top setting id: {top_setting_id}")
    print(terminal_stdout)
    print(f"Wrote manifest: {manifest_path}")
    print(f"Wrote summary: {summary_txt}")
    print(f"Figures: {figures_dir}")


if __name__ == "__main__":
    # Ensure direct script run works from repo root.
    _ensure_package_importable(Path(__file__).resolve().parents[2])
    main()

