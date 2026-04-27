"""
Smoke test: tail Game.log and report any line containing 'mission' (case-insensitive).
Press Ctrl+C to stop.
"""

import sys
import time
from pathlib import Path

LOG_PATH = Path(r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log")

def tail_log(path: Path):
    if not path.is_file():
        print(f"[WARN] Log file not found: {path}")
        print("       Waiting for it to appear...")

    while not path.is_file():
        time.sleep(1.0)

    print(f"[OK]   Watching: {path}")
    print("       Reporting lines that contain 'Contract Shared:' and a MissionId ...\n")

    with path.open("rb") as fh:
        fh.seek(0, 2)  # start at end of file
        offset = fh.tell()

    while True:
        try:
            current_size = path.stat().st_size
        except OSError:
            time.sleep(0.5)
            continue

        if current_size < offset:
            print("[INFO] Log file was reset/rotated, seeking to start.")
            offset = 0

        if current_size > offset:
            with path.open("rb") as fh:
                fh.seek(offset)
                blob = fh.read(current_size - offset)
                offset = fh.tell()

            for raw in blob.splitlines():
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                if "missionid" in line.lower() and "Contract Shared:" in line:
                    print(f"[HIT]  {line}")

        time.sleep(0.2)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        LOG_PATH = Path(sys.argv[1])

    try:
        tail_log(LOG_PATH)
    except KeyboardInterrupt:
        print("\n[STOP] Smoke test stopped.")
