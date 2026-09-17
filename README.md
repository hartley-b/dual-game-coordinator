# dual-login

Coordinates two BlueStacks instances running Yo-kai Watch Puni Puni so that only one
device plays a stage at a time. Each device runs its own in-game macro (Smart
AutoClicker / Klick'r) that plays stages and navigates menus. This tool watches both
screens over ADB and, when the active device clears a stage, taps login on the idle
device (promoting it to active) and force-stops the device that just cleared (demoting
it to idle). Detection uses OpenCV template matching against reference screenshots
rather than fixed timers, so handoffs occur immediately on detection.

The tool also includes automatic recovery for a device that stops progressing,
optional push alerts via ntfy.sh when recovery fails, and a standalone stats reader
that reports clear speed and uptime from the log.

It reduces normal stage completion times up-to 2x | 40s to 21s

## Benchmarking & Iteration

### Speed

**Handoff latency**
- Improvement: Removed approximately one second of latency from every stage-clear handoff.
- Fix: The login tap and the force-stop of the cleared device now fire immediately, and roles swap unconditionally, with no verification step in the handoff path.
- Problem: The previous implementation tapped login on the idle device, waited on a verify delay and a confirmation screenshot, and only then force-stopped the cleared device.

**Failed-handoff recovery**
- Improvement: A failed handoff is still detected and retried, without adding latency to successful handoffs.
- Fix: The device promoted to active is covered by the existing stuck-device watchdog, so a failed tap is retried automatically within `STUCK_TIMEOUT_SECONDS`.
- Problem: Removing the handoff verification step meant a failed tap was no longer confirmed at the moment it occurred.

**Login tap targeting**
- Improvement: Removed one screenshot-and-match round trip from every handoff.
- Fix: The login tap uses a fixed coordinate (`LOGIN_BUTTON_COORDS`) instead of locating the button by template match beforehand.
- Problem: The button's on-screen position was identical across every session in the log, making the match step unnecessary.

### Resource Usage

**Screenshot format**
- Improvement: Reduced per-poll latency and removed image-encoding overhead from both the emulator and the host.
- Fix: Screenshots are captured with `adb exec-out screencap` (raw, uncompressed RGBA), decoded directly into a numpy array, and converted to BGR for OpenCV.
- Problem: `adb exec-out screencap -p` returns a PNG, requiring the device to encode and the host to decode a compressed image on every poll, adding overhead to a loop running several times per second.

**Polling window**
- Improvement: Reduced the number of ADB calls issued during the period a stage cannot yet have cleared.
- Fix: After a device becomes active, the coordinator waits `INITIAL_POLL_DELAY_SECONDS` before polling for a stage clear, rather than polling continuously from the moment the device becomes active.
- Problem: Continuous polling from the start of a stage produced screenshots and template matches during a window where a clear was not yet possible, adding ADB and CPU load with no chance of a positive detection.

### Consistency

**Input ordering**
- Improvement: Removed the risk of the game server processing two inputs out of order.
- Fix: Added a fixed delay (`STAGE_CLEAR_TAP_DELAY_SECONDS`) between detecting a stage clear and firing the login tap.
- Problem: The two inputs were previously sent with no gap between them.

### Failsafes

**Unhandled device failure**
- Improvement: A device going offline no longer terminates the coordinator.
- Fix: The main loop is wrapped in a try/except that logs the failure, sends a rate-limited ntfy alert, and continues retrying.
- Problem: Every `adb` call used `check=True` with no exception handling. An offline device raised an uncaught exception that killed the entire process, including monitoring of the unaffected device.

**Unresponsive ADB connections**
- Improvement: A frozen device is detected and alerted on through the same path as an outright crash.
- Fix: Added a timeout to every `adb` subprocess call.
- Problem: A frozen BlueStacks instance does not always report as offline; the ADB connection can hang instead, which previously raised no exception and produced no alert.

**Idle-device monitoring**
- Improvement: A crashed idle device is detected without waiting for the next handoff attempt.
- Fix: Added a second watchdog for the idle device, using the same `STUCK_TIMEOUT_SECONDS` retry cadence and `ESCALATION_TIMEOUT_SECONDS`/`ALERT_REPEAT_SECONDS` alert cadence as the active-device watchdog. It acts only on the idle device and does not swap roles.
- Problem: The original watchdog monitored only the active device; the idle device was never checked until a handoff targeted it.

**Watchdog coverage**
- Improvement: Both devices are checked on every loop iteration.
- Fix: Restructured the main loop so the active-device and idle-device checks run independently.
- Problem: The idle-device check was placed after the active-device stuck branch's `continue` statement, so it was skipped entirely whenever the active device was stuck.

###
## Requirements

- Python 3.10+
- `adb` installed and on `PATH`
- Two BlueStacks instances running the game, each already configured with a working
  macro that plays stages and returns to a login/save-select screen when relaunched
- macOS, Linux, or Windows, provided `adb` is available; commands below assume a
  Unix-like shell

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. Identify each BlueStacks instance's adb serial (`adb devices`, or
   `lsof -i TCP:5555,5575 -sTCP:LISTEN` to map ports to instances) and set them in
   `config.py`:

   ```python
   DEVICE_A = "emulator-5554"
   DEVICE_B = "emulator-5574"
   ```

3. Set `LOGIN_BUTTON_COORDS` in `config.py` to the tap coordinates for the login
   button. This coordinate is used for the fast-path tap; the template match is used
   only for detection and recovery.

4. Optionally enable push alerts.

## Running

Each component runs as a separate foreground process.
```bash
# 1. the coordinator
caffeinate -i -s .venv/bin/python3 coordinator.py
```

```bash
# 2. stats — average/fastest/slowest clear time, uptime, points forecast
.venv/bin/python3 stats.py
```

```bash
# 3. an external crash-watchdog, if one is configured, e.g.:
/path/to/your/watchdog.sh
```

Logs are written to `logs/coordinator.log`, rotated at 5MB with 5 backups retained.
