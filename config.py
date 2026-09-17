import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file(Path(__file__).parent / ".env")

REFERENCES_DIR = Path(__file__).parent / "references"

DEVICE_A = "emulator-5554"
DEVICE_B = "emulator-5574"

POLL_INTERVAL_SECONDS = 0.25
MATCH_THRESHOLD = 0.80

INITIAL_POLL_DELAY_SECONDS = 18.0

STUCK_TIMEOUT_SECONDS = 45.0
RECOVERY_TIMEOUT_SECONDS = 60.0

# set in .env (see .env.example) or export DUAL_LOGIN_NTFY_URL directly
# left unset, notify.send() becomes a no-op and the coordinator runs without alerts
NTFY_URL = os.environ.get("DUAL_LOGIN_NTFY_URL", "")
ESCALATION_TIMEOUT_SECONDS = 240.0
ALERT_REPEAT_SECONDS = 300.0
ERROR_RETRY_SECONDS = 5.0

LOGIN_BUTTON_COORDS = (525, 1187)
STAGE_CLEAR_TAP_DELAY_SECONDS = 0.35

STAGE_CLEAR_TEMPLATE = "stage_clear"
CLEAR_BANNER_TEMPLATE = "clear_banner"
LOGIN_BUTTON_TEMPLATE = "login_button"

GAME_PACKAGE = "com.Level5.YWP"

STATS_INTERVAL_SECONDS = 300.0
STATS_CLEAR_SAMPLE_SIZE = 100
STATS_UPTIME_WINDOW_HOURS = 24.0

POINTS_PER_CLEAR = 15
FORECAST_TARGET_DATETIME = "2026-10-01 01:00:00"
