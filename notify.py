import subprocess

import config


def send(message: str, priority: str = "default") -> None:
    if not config.NTFY_URL:
        return
    subprocess.run(
        ["curl", "-s", "-H", f"Priority: {priority}", "-d", message, config.NTFY_URL],
        capture_output=True,
    )
