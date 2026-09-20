from pathlib import Path

import cv2
import numpy as np


def load_template(name: str, references_dir: Path) -> np.ndarray:
    path = references_dir / f"{name}.png"
    # cv2.imread() can't handle non-ASCII characters in a file path on Windows;
    # reading the bytes ourselves and decoding avoids that entirely
    data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    template = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if template is None:
        raise FileNotFoundError(f"could not decode reference image at {path}")
    return template


def find(screen: np.ndarray, template: np.ndarray, threshold: float) -> tuple[int, int] | None:
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < threshold:
        return None
    h, w = template.shape[:2]
    return (max_loc[0] + w // 2, max_loc[1] + h // 2)
