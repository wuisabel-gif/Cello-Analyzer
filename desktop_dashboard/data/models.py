from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SensorFrame:
    timestamp: datetime
    raw: int
    peak: int
    volume: int
    dynamic: str
    temperature: float
    humidity: float
    alert: str
    cello_health: str
    mode: str = "Performance"
    waveform: list[float] = field(default_factory=list)

    def csv_row(self) -> list[str]:
        waveform_text = " ".join(f"{value:.3f}" for value in self.waveform)
        return [
            self.timestamp.isoformat(),
            str(self.raw),
            str(self.peak),
            str(self.volume),
            self.dynamic,
            f"{self.temperature:.2f}",
            f"{self.humidity:.2f}",
            self.alert,
            self.cello_health,
            self.mode,
            waveform_text,
        ]


CSV_HEADER = [
    "timestamp",
    "raw",
    "peak",
    "volume",
    "dynamic",
    "temperature_c",
    "humidity_percent",
    "alert",
    "cello_health",
    "mode",
    "waveform",
]
