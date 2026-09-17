import struct
import subprocess
import time

import cv2
import numpy as np

ADB_BIN = "adb"
TAP_SETTLE_SECONDS = 0.25
ADB_TIMEOUT_SECONDS = 10.0


def connect(serial: str) -> None:
    subprocess.run([ADB_BIN, "connect", serial], capture_output=True, check=False, timeout=ADB_TIMEOUT_SECONDS)


def screencap(serial: str) -> np.ndarray:
    result = subprocess.run(
        [ADB_BIN, "-s", serial, "exec-out", "screencap"],
        capture_output=True,
        check=True,
        timeout=ADB_TIMEOUT_SECONDS,
    )
    raw = result.stdout
    width, height = struct.unpack_from("<II", raw, 0)
    header_size = len(raw) - width * height * 4
    pixels = np.frombuffer(raw, dtype=np.uint8, offset=header_size)
    rgba = pixels.reshape((height, width, 4))
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)


def tap(serial: str, x: int, y: int) -> None:
    subprocess.run(
        [ADB_BIN, "-s", serial, "shell", "input", "tap", str(x), str(y)],
        capture_output=True,
        check=True,
        timeout=ADB_TIMEOUT_SECONDS,
    )
    time.sleep(TAP_SETTLE_SECONDS)


def force_stop(serial: str, package: str) -> None:
    subprocess.run(
        [ADB_BIN, "-s", serial, "shell", "am", "force-stop", package],
        capture_output=True,
        check=True,
        timeout=ADB_TIMEOUT_SECONDS,
    )
