"""Standalone: force-stops the game on both devices every 6 hours. Does nothing else.

Run on its own, separately from coordinator.py:  python force_quit.py
"""
import subprocess
import time

DEVICES = ["emulator-5554", "emulator-5574"]
GAME_PACKAGE = "com.Level5.YWP"
INTERVAL_SECONDS = 6 * 60 * 60
ADB_BIN = "adb"
ADB_TIMEOUT_SECONDS = 10.0


def restart_adb_server() -> None:
    for args in (["kill-server"], ["start-server"], ["devices"]):
        subprocess.run([ADB_BIN, *args], capture_output=True, check=False, timeout=ADB_TIMEOUT_SECONDS)


def force_quit(serial: str) -> None:
    try:
        subprocess.run([ADB_BIN, "connect", serial], capture_output=True, check=False, timeout=ADB_TIMEOUT_SECONDS)
        subprocess.run(
            [ADB_BIN, "-s", serial, "shell", "am", "force-stop", GAME_PACKAGE],
            capture_output=True,
            check=True,
            timeout=ADB_TIMEOUT_SECONDS,
        )
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} force-stopped {GAME_PACKAGE} on {serial}", flush=True)
    except Exception as exc:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} failed on {serial}: {exc}", flush=True)


def main() -> None:
    restart_adb_server()
    while True:
        time.sleep(INTERVAL_SECONDS)
        for serial in DEVICES:
            force_quit(serial)


if __name__ == "__main__":
    main()
