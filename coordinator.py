import logging
import logging.handlers
import time
from pathlib import Path

import numpy as np

import adb
import config
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
    active_since = time.time()

    while True:
        screen = adb.screencap(active)

        if time.time() - active_since > config.STUCK_TIMEOUT_SECONDS:
            log.warning("%s has not cleared a stage in %.0fs, assuming it's stuck", active, config.STUCK_TIMEOUT_SECONDS)
            match = ensure_at_login(active, login_button, screen)
            if match:
                x, y = match
                log.info("retapping login on %s at (%d, %d) to recover", active, x, y)
                adb.tap(active, x, y)
            active_since = time.time()
            time.sleep(config.SWAP_COOLDOWN_SECONDS)
            continue

        cleared = vision.find(screen, stage_clear, config.MATCH_THRESHOLD) or vision.find(
            screen, clear_banner, config.MATCH_THRESHOLD
        )
        if cleared:
            log.info("stage clear detected on %s", active)
            idle_screen = adb.screencap(idle)
            match = ensure_at_login(idle, login_button, idle_screen)
            if match:
                x, y = match
                log.info("tapping login on %s at (%d, %d)", idle, x, y)
                if tap_login(idle, x, y, login_button):
                    log.info("force-stopping %s on %s to skip results animation", config.GAME_PACKAGE, active)
                    adb.force_stop(active, config.GAME_PACKAGE)

                    active, idle = idle, active
                    active_since = time.time()
                    time.sleep(config.SWAP_COOLDOWN_SECONDS)
                else:
                    log.error(
                        "%s failed to leave the login screen after %d tap attempts, will retry next cycle",
                        idle, config.LOGIN_TAP_RETRIES,
                    )
                    time.sleep(config.POLL_INTERVAL_SECONDS)
            else:
                log.warning("%s could not be recovered to login, will retry next cycle", idle)
                time.sleep(config.POLL_INTERVAL_SECONDS)
            continue
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
