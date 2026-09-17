import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import config

LOG_DIR = Path(__file__).parent / "logs"
LOG_BASENAME = "coordinator.log"

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (.*)$")
CLEAR_MARKER = "stage clear detected on"
STUCK_MARKER = "has not cleared a stage in"
STARTING_MARKER = "starting: active="


def _log_files() -> list[Path]:
    backups = sorted(
        LOG_DIR.glob(f"{LOG_BASENAME}.*"),
        key=lambda p: int(p.suffix.lstrip(".")),
        reverse=True,
    )
    base = LOG_DIR / LOG_BASENAME
    return backups + ([base] if base.exists() else [])


def _iter_lines():
    for path in _log_files():
        with open(path, "r", errors="ignore") as f:
            for line in f:
                match = LINE_RE.match(line)
                if not match:
                    continue
                ts = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
                yield ts, match.group(2).rstrip("\n")


def compute_stats() -> dict:
    now = datetime.now()
    window_start = now - timedelta(hours=config.STATS_UPTIME_WINDOW_HOURS)

    clear_durations: list[float] = []
    prev_clear_ts: datetime | None = None
    saw_stuck_since_last_clear = False
    stuck_start: datetime | None = None
    downtime = timedelta()

    for ts, msg in _iter_lines():
        if STARTING_MARKER in msg:
            # a restart is a clean boundary: close any dangling stuck episode here,
            # and don't let clear-interval math span across the restart
            if stuck_start is not None and ts > window_start:
                downtime += ts - max(stuck_start, window_start)
            stuck_start = None
            prev_clear_ts = None
            saw_stuck_since_last_clear = False
            continue

        if msg.startswith(CLEAR_MARKER):
            # only count this as a clean stage duration if nothing went wrong in between -
            # a stuck/recovery episode inflates the gap and is already tracked as downtime
            if prev_clear_ts is not None and not saw_stuck_since_last_clear:
                clear_durations.append((ts - prev_clear_ts).total_seconds())
            prev_clear_ts = ts
            saw_stuck_since_last_clear = False

            if stuck_start is not None:
                if ts > window_start:
                    downtime += ts - max(stuck_start, window_start)
                stuck_start = None
            continue

        if STUCK_MARKER in msg:
            saw_stuck_since_last_clear = True
            if stuck_start is None:
                stuck_start = ts

    if stuck_start is not None:
        downtime += now - max(stuck_start, window_start)

    recent = clear_durations[-config.STATS_CLEAR_SAMPLE_SIZE:]
    window_seconds = config.STATS_UPTIME_WINDOW_HOURS * 3600
    downtime_seconds = min(downtime.total_seconds(), window_seconds)
    uptime_pct = max(0.0, (window_seconds - downtime_seconds) / window_seconds * 100)

    avg_clear = sum(recent) / len(recent) if recent else None
    points_per_hour = config.POINTS_PER_CLEAR / avg_clear * 3600 if avg_clear else None

    forecast_target = datetime.strptime(config.FORECAST_TARGET_DATETIME, "%Y-%m-%d %H:%M:%S")
    hours_to_target = max(0.0, (forecast_target - now).total_seconds() / 3600)

    return {
        "sample_size": len(recent),
        "avg_clear": avg_clear,
        "fastest_clear": min(recent) if recent else None,
        "slowest_clear": max(recent) if recent else None,
        "uptime_pct": uptime_pct,
        "downtime_seconds": downtime_seconds,
        "points_next_hour": points_per_hour,
        "points_next_day": points_per_hour * 24 if points_per_hour else None,
        "points_to_target": points_per_hour * hours_to_target if points_per_hour else None,
    }


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes}m{secs}s"
    if minutes:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


def print_stats(stats: dict) -> None:
    print(f"=== dual-login stats ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    if stats["sample_size"]:
        print(
            f"clears (last {stats['sample_size']}): "
            f"avg {stats['avg_clear']:.1f}s | fastest {stats['fastest_clear']:.1f}s | slowest {stats['slowest_clear']:.1f}s"
        )
    else:
        print("clears: no data yet")
    print(
        f"uptime (last {int(config.STATS_UPTIME_WINDOW_HOURS)}h): {stats['uptime_pct']:.1f}% "
        f"| downtime {_format_duration(stats['downtime_seconds'])}"
    )
    if stats["points_next_hour"] is not None:
        print(
            f"points: next hour: ~{stats['points_next_hour']:.0f} "
            f"| next 24h: ~{stats['points_next_day']:.0f} "
            f"| by {config.FORECAST_TARGET_DATETIME}: ~{stats['points_to_target']:.0f}"
        )
    else:
        print("points: no data yet")
    print()


def run() -> None:
    while True:
        print_stats(compute_stats())
        time.sleep(config.STATS_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
