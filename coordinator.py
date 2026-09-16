import logging
import logging.handlers
import time
from pathlib import Path

import numpy as np

import adb
import config
import notify
import vision

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log = logging.getLogger("coordinator")
log.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
log.addHandler(_console_handler)

_file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "coordinator.log", maxBytes=5 * 1024 * 1024, backupCount=5
)
_file_handler.setFormatter(_formatter)
log.addHandler(_file_handler)


def detect_roles(login_button: np.ndarray) -> tuple[str, str]:
    a_screen = adb.screencap(config.DEVICE_A)
    b_screen = adb.screencap(config.DEVICE_B)
    a_idle = vision.find(a_screen, login_button, config.MATCH_THRESHOLD) is not None
    b_idle = vision.find(b_screen, login_button, config.MATCH_THRESHOLD) is not None

    if a_idle and not b_idle:
        return config.DEVICE_B, config.DEVICE_A
    if b_idle and not a_idle:
        return config.DEVICE_A, config.DEVICE_B

    log.warning(
        "could not tell devices apart from login screen (a_idle=%s b_idle=%s), defaulting to A=active",
        a_idle, b_idle,
    )
    return config.DEVICE_A, config.DEVICE_B


def wait_for_login(serial: str, login_button: np.ndarray, timeout: float) -> tuple[int, int] | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        screen = adb.screencap(serial)
        match = vision.find(screen, login_button, config.MATCH_THRESHOLD)
        if match:
            return match
        time.sleep(config.POLL_INTERVAL_SECONDS)
    return None


def tap_login(serial: str, x: int, y: int, login_button: np.ndarray) -> bool:
    for attempt in range(1, config.LOGIN_TAP_RETRIES + 1):
        adb.tap(serial, x, y)
        time.sleep(config.LOGIN_TAP_VERIFY_DELAY_SECONDS)
        screen = adb.screencap(serial)
        if vision.find(screen, login_button, config.MATCH_THRESHOLD) is None:
            log.info("login tap confirmed on %s (attempt %d/%d)", serial, attempt, config.LOGIN_TAP_RETRIES)
            return True
        log.warning("%s still at login after tap attempt %d/%d", serial, attempt, config.LOGIN_TAP_RETRIES)
    return False


def bring_idle_to_active(idle: str, login_button: np.ndarray) -> bool:
    x, y = config.LOGIN_BUTTON_COORDS
    log.info("tapping login on %s at (%d, %d)", idle, x, y)
    if tap_login(idle, x, y, login_button):
        return True

    log.warning("%s did not confirm login at the known coordinate, attempting full recovery", idle)
    idle_screen = adb.screencap(idle)
    match = ensure_at_login(idle, login_button, idle_screen)
    if match is None:
        log.warning("%s could not be recovered to login, will retry next cycle", idle)
        return False

    x, y = match
    if tap_login(idle, x, y, login_button):
        return True
    log.error("%s failed to leave the login screen after recovery, will retry next cycle", idle)
    return False


def ensure_at_login(serial: str, login_button: np.ndarray, screen: np.ndarray) -> tuple[int, int] | None:
    match = vision.find(screen, login_button, config.MATCH_THRESHOLD)
    if match:
        return match
    log.warning("%s not at login screen, force-stopping to recover", serial)
    adb.force_stop(serial, config.GAME_PACKAGE)
    match = wait_for_login(serial, login_button, config.RECOVERY_TIMEOUT_SECONDS)
    if match is None:
        log.error("%s did not return to login within %.0fs of recovery attempt", serial, config.RECOVERY_TIMEOUT_SECONDS)
    return match


def run() -> None:
    stage_clear = vision.load_template(config.STAGE_CLEAR_TEMPLATE, config.REFERENCES_DIR)
    clear_banner = vision.load_template(config.CLEAR_BANNER_TEMPLATE, config.REFERENCES_DIR)
    login_button = vision.load_template(config.LOGIN_BUTTON_TEMPLATE, config.REFERENCES_DIR)

    active, idle = detect_roles(login_button)
    log.info("starting: active=%s idle=%s", active, idle)
    # backdated so the first cycle polls immediately instead of waiting out the initial delay
    active_since = time.time() - config.INITIAL_POLL_DELAY_SECONDS
    stuck_since: float | None = None
    last_alert_at: float | None = None

    while True:
        elapsed = time.time() - active_since
        if elapsed < config.INITIAL_POLL_DELAY_SECONDS:
            time.sleep(config.INITIAL_POLL_DELAY_SECONDS - elapsed)
            continue

        screen = adb.screencap(active)

        if elapsed > config.STUCK_TIMEOUT_SECONDS:
            log.warning("%s has not cleared a stage in %.0fs, assuming it's stuck", active, config.STUCK_TIMEOUT_SECONDS)
            if stuck_since is None:
                stuck_since = time.time()

            match = ensure_at_login(active, login_button, screen)
            if match:
                x, y = match
                log.info("retapping login on %s at (%d, %d) to recover", active, x, y)
                adb.tap(active, x, y)

            stuck_elapsed = time.time() - stuck_since
            if stuck_elapsed > config.ESCALATION_TIMEOUT_SECONDS:
                if last_alert_at is None or time.time() - last_alert_at > config.ALERT_REPEAT_SECONDS:
                    log.error("%s still stuck after %.0fs, sending alert", active, stuck_elapsed)
                    notify.send(
                        f"🚨 dual-login stuck: {active} has not cleared a stage in {int(stuck_elapsed)}s, self-recovery failing",
                        priority="urgent",
                    )
                    last_alert_at = time.time()

            active_since = time.time()
            time.sleep(config.SWAP_COOLDOWN_SECONDS)
            continue

        cleared = vision.find(screen, stage_clear, config.MATCH_THRESHOLD) or vision.find(
            screen, clear_banner, config.MATCH_THRESHOLD
        )
        if cleared:
            log.info("stage clear detected on %s", active)
            if bring_idle_to_active(idle, login_button):
                log.info("force-stopping %s on %s to skip results animation", config.GAME_PACKAGE, active)
                adb.force_stop(active, config.GAME_PACKAGE)

                if last_alert_at is not None:
                    log.info("recovered after being stuck for %.0fs", time.time() - stuck_since)
                    notify.send(f"✅ dual-login recovered: {active} is clearing stages again", priority="default")
                stuck_since = None
                last_alert_at = None

                active, idle = idle, active
                active_since = time.time()
                time.sleep(config.SWAP_COOLDOWN_SECONDS)
            else:
                time.sleep(config.POLL_INTERVAL_SECONDS)
            continue
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
