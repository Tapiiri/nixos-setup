"""Report on cached-check run history and statistics.

Usage::

    check-report            # latest attestation per check
    check-report --all      # all stored attestations
    check-report --stats    # per-check statistics (runs, failures, min/p50/mean/max)

Reads the attestation JSON files written by ``cached-check`` and prints
tables showing run history, pass/fail status, elapsed times, and aggregate
statistics. Useful for spotting slow, flaky, or failing checks.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from scripts_py.repo.context import repo_root_from_script_path

_STATE_REL = Path(".devenv") / "state"


def _load_attestations(state_dir: Path) -> list[dict[str, object]]:
    """Load all attestation JSON files from the state directory."""
    records: list[dict[str, object]] = []
    if not state_dir.is_dir():
        return records
    for p in sorted(state_dir.glob("*-attestations/*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            records.append(data)
        except (OSError, json.JSONDecodeError):
            continue
    return records


def _get_float(record: dict[str, object], key: str) -> float:
    """Safely extract a float from a JSON-loaded dict."""
    val = record.get(key, 0)
    return float(val) if isinstance(val, (int, float, str)) else 0.0


def _format_ts(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _print_report(
    records: list[dict[str, object]],
    *,
    show_all: bool,
    out: TextIO,
) -> None:
    if not records:
        print("No attestations found.", file=out)
        return

    if not show_all:
        # Keep only the latest attestation per check name.
        latest: dict[str, dict[str, object]] = {}
        for r in records:
            name = str(r.get("name", "?"))
            ts = _get_float(r, "ts")
            if name not in latest or ts > _get_float(latest[name], "ts"):
                latest[name] = r
        records = list(latest.values())

    # Sort by elapsed time descending (slowest first).
    records.sort(key=lambda r: -_get_float(r, "elapsed"))

    # Column widths.
    name_w = max(len(str(r.get("name", "?"))) for r in records)
    name_w = max(name_w, 5)  # "Check" header

    header = f"{'Check':<{name_w}}  {'Status':>6}  {'Elapsed':>8}  {'When':>19}"
    print(header, file=out)
    print("-" * len(header), file=out)

    for r in records:
        name = str(r.get("name", "?"))
        ok = bool(r.get("ok", False))
        elapsed = _get_float(r, "elapsed")
        ts = _get_float(r, "ts")
        status = "PASS" if ok else "FAIL"
        when = _format_ts(ts) if ts > 0 else "unknown"
        print(f"{name:<{name_w}}  {status:>6}  {elapsed:>7.1f}s  {when:>19}", file=out)


def _print_stats(
    records: list[dict[str, object]],
    *,
    out: TextIO,
) -> None:
    if not records:
        print("No attestations found.", file=out)
        return

    # Group by check name, excluding broken entries.
    by_name: dict[str, list[dict[str, object]]] = defaultdict(list)
    for r in records:
        name = str(r.get("name", "?"))
        if name == "?":
            continue
        by_name[name].append(r)

    if not by_name:
        print("No named attestations found.", file=out)
        return

    # Build stats per check.
    rows: list[tuple[str, int, int, float, float, float, float]] = []
    for name, entries in sorted(by_name.items()):
        times = [_get_float(e, "elapsed") for e in entries]
        fails = sum(1 for e in entries if not e.get("ok", False))
        t_min = min(times)
        t_max = max(times)
        t_mean = statistics.mean(times)
        t_p50 = statistics.median(times)
        rows.append((name, len(entries), fails, t_min, t_p50, t_mean, t_max))

    # Sort by mean elapsed descending.
    rows.sort(key=lambda r: -r[5])

    name_w = max(len(r[0]) for r in rows)
    name_w = max(name_w, 5)

    header = (
        f"{'Check':<{name_w}}  {'Runs':>4}  {'Fail':>4}  "
        f"{'Min':>6}  {'P50':>6}  {'Mean':>6}  {'Max':>6}"
    )
    print(header, file=out)
    print("-" * len(header), file=out)

    for name, count, fails, t_min, t_p50, t_mean, t_max in rows:
        fail_str = str(fails) if fails > 0 else "-"
        print(
            f"{name:<{name_w}}  {count:>4}  {fail_str:>4}  "
            f"{t_min:>5.1f}s  {t_p50:>5.1f}s  {t_mean:>5.1f}s  {t_max:>5.1f}s",
            file=out,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report timing and status of cached-check attestations.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Show all stored attestations, not just the latest per check.",
    )
    group.add_argument(
        "--stats",
        action="store_true",
        help="Show per-check statistics (runs, failures, min/p50/mean/max).",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = repo_root_from_script_path(Path(__file__))
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    state_dir = repo_root / _STATE_REL
    records = _load_attestations(state_dir)

    if args.stats:
        _print_stats(records, out=sys.stdout)
    else:
        _print_report(records, show_all=args.show_all, out=sys.stdout)
    return 0
