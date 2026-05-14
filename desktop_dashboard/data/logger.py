from __future__ import annotations

import csv
from pathlib import Path

from desktop_dashboard.data.models import CSV_HEADER, SensorFrame


class SessionLogger:
    def __init__(self) -> None:
        self._frames: list[SensorFrame] = []

    def clear(self) -> None:
        self._frames.clear()

    def add_frame(self, frame: SensorFrame) -> None:
        self._frames.append(frame)

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def export_csv(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(CSV_HEADER)
            for frame in self._frames:
                writer.writerow(frame.csv_row())
