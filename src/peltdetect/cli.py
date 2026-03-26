from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Optional


def _parse_date(value: str):
    # Keep parsing centralized to avoid duplicated logic across modules.
    import datetime as dt

    return dt.date.fromisoformat(value)


def _require_api_key(env_var: str) -> str:
    api_key = os.getenv(env_var)
    if not api_key:
        raise RuntimeError(
            f"Missing API key. Please set `{env_var}` in your environment."
        )
    return api_key


def cmd_run(args: argparse.Namespace) -> None:
    import peltdetect.api as api
    from peltdetect.mc_pelt import MCPelt
    from peltdetect.mc_pelt.io import save_result

    api_key = _require_api_key(args.api_key_env)

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    source_id = int(args.source_id)

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = Path("out/single") / f"source_{source_id}" / f"{start_date.isoformat()}_{end_date.isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fetch daily counts from Media Cloud.
    series = api.fetch_story_count_over_time(
        query=args.query,
        start_date=start_date,
        end_date=end_date,
        source_id=source_id,
        api_key=api_key,
    )

    detector = MCPelt(
        model=args.model,
        min_size=int(args.min_size),
        penalty="auto" if args.penalty is None else float(args.penalty),
        drop_threshold=args.drop_threshold,
        rise_threshold=args.rise_threshold,
        zero_threshold=args.zero_threshold,
        silence_multiplier=args.silence_multiplier,
    )
    # `peltdetect.mc_pelt.MCPelt` core output is metadata-free; wrapper attaches metadata for persistence.
    result = detector.detect_for_source(
        series,
        source_id=source_id,
        query=args.query,
        start_date=start_date,
        end_date=end_date,
    )
    save_result(result, out_dir=out_dir)

    # Provide quick human-readable output.
    print(f"Wrote run artifacts to: {out_dir}")
    print(json.dumps(result, indent=2, default=str))


def cmd_summarize(args: argparse.Namespace) -> None:
    from peltdetect.mc_pelt.io import load_result

    run_path = Path(args.run_json)
    summary = load_result(run_path)

    print(f"Run: {run_path}")
    # Print only the alert bits for quick inspection.
    if summary.get("alerts"):
        print("Alerts:")
        for a in summary["alerts"]:
            print(f"- {a['type']} starting {a['start']}")
    else:
        print("No alerts.")


def cmd_plot(args: argparse.Namespace) -> None:
    from peltdetect.charts.run import plot_result
    from peltdetect.mc_pelt.io import load_result

    run_path = Path(args.run_json)
    run = load_result(run_path)
    out_path: Optional[Path] = Path(args.output_plot) if args.output_plot else None

    plot_result(run, out_path=out_path, show=args.show)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="peltdetect", description="PELT feed activity harness")
    parser.add_argument(
        "--api-key-env",
        default="MEDIACLOUD_API_KEY",
        help="Environment variable that contains your Media Cloud API token.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_p = subparsers.add_parser("run", help="Fetch data, run PELT, detect alerts, save artifacts.")
    run_p.add_argument("--source-id", required=True, help="MediaCloud source/media id (int).")
    run_p.add_argument("--query", default="*", help="MediaCloud search query. Use `*` for all.")
    run_p.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD).")
    run_p.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD).")
    run_p.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write run artifacts (default: out/single/source_<id>/<start>_<end>).",
    )
    run_p.add_argument("--model", default="l2", help='Ruptures PELT model (e.g. "l2").')
    run_p.add_argument("--min-size", type=int, default=7, help="Minimum segment length (days).")
    run_p.add_argument("--penalty", type=float, default=None, help="PELT penalty (higher => fewer breakpoints).")
    run_p.add_argument("--drop-threshold", type=float, default=0.5, help="Relative drop threshold.")
    run_p.add_argument("--rise-threshold", type=float, default=1.5, help="Relative surge threshold.")
    run_p.add_argument("--zero-threshold", type=float, default=1.0, help="Near-zero volume threshold.")
    run_p.add_argument(
        "--silence-multiplier",
        type=float,
        default=5.0,
        help="If time since last post exceeds this * expected interval, mark silence.",
    )
    run_p.set_defaults(func=cmd_run)

    sum_p = subparsers.add_parser("summarize", help="Print quick summary for an existing run.")
    sum_p.add_argument("--run-json", required=True, help="Path to a saved run_result.json")
    sum_p.set_defaults(func=cmd_summarize)

    plot_p = subparsers.add_parser("plot", help="Plot a saved run (series + changepoints).")
    plot_p.add_argument("--run-json", required=True, help="Path to a saved run_result.json")
    plot_p.add_argument("--output-plot", default=None, help="Optional output image path (e.g. png).")
    plot_p.add_argument("--show", action="store_true", help="Display plot interactively.")
    plot_p.set_defaults(func=cmd_plot)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

