import sys

import cv2

import adb
import config


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python capture_reference.py <device_serial> <template_name>")
        sys.exit(1)

    serial, name = sys.argv[1], sys.argv[2]
    screen = adb.screencap(serial)
    x, y, w, h = cv2.selectROI("select region, then press ENTER", screen, showCrosshair=True)
    cv2.destroyAllWindows()
    if w == 0 or h == 0:
        print("no region selected, aborting")
        return

    crop = screen[y : y + h, x : x + w]
    config.REFERENCES_DIR.mkdir(exist_ok=True)
    out_path = config.REFERENCES_DIR / f"{name}.png"
    cv2.imwrite(str(out_path), crop)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
