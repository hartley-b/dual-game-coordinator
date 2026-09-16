from pathlib import Path

import cv2
import numpy as np


def load_template(name: str, references_dir: Path) -> np.ndarray:
    path = references_dir / f"{name}.png"
    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        raise FileNotFoundError(f"no reference image at {path}")
    return template


def find(screen: np.ndarray, template: np.ndarray, threshold: float) -> tuple[int, int] | None:
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < threshold:
        return None
    h, w = template.shape[:2]
    return (max_loc[0] + w // 2, max_loc[1] + h // 2)
