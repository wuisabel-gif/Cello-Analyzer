from __future__ import annotations

import math
import random
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from desktop_dashboard.data.models import SensorFrame


class MockDataSource(QObject):
    frame_ready = Signal(object)
    status_changed = Signal(str)

    def __init__(self, interval_ms: int = 250) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._emit_frame)
        self._tick = 0
        self._phase = 0.0
        self._temperature = 23.2
        self._humidity = 55.4
        self._mode_names = [
            "Performance",
            "Trend",
            "Environment",
            "Environment History",
        ]

    def start(self) -> None:
        self._timer.start()
        self.status_changed.emit("Mock source running")

    def stop(self) -> None:
        self._timer.stop()
        self.status_changed.emit("Mock source stopped")

    def _emit_frame(self) -> None:
        self._tick += 1
        self._phase += 0.18

        envelope = 0.5 + 0.5 * math.sin(self._phase * 0.25)
        bow_accent = max(0.0, math.sin(self._phase * 0.8))
        loudness = min(1.0, 0.12 + 0.58 * envelope + 0.30 * bow_accent)
        waveform = []
        for index in range(64):
            x = self._phase + index * 0.23
            sample = (
                math.sin(x * 1.3) * 0.62
                + math.sin(x * 2.7) * 0.24
                + math.sin(x * 5.1) * 0.09
                + random.uniform(-0.035, 0.035)
            )
            waveform.append(sample * loudness)

        raw = int(1200 + loudness * 5400 + random.randint(-120, 120))
        peak = int(raw * 0.35)
        volume = max(0, min(100, int((raw / 7000) * 100)))
        dynamic = self._dynamic_from_volume(volume)

        self._temperature += random.uniform(-0.03, 0.03)
        self._humidity += random.uniform(-0.09, 0.09)
        alert, cello_health = self._environment_state(self._temperature, self._humidity)
        mode = self._mode_names[(self._tick // 20) % len(self._mode_names)]

        frame = SensorFrame(
            timestamp=datetime.now(),
            raw=raw,
            peak=peak,
            volume=volume,
            dynamic=dynamic,
            temperature=self._temperature,
            humidity=self._humidity,
            alert=alert,
            cello_health=cello_health,
            mode=mode,
            waveform=waveform,
        )
        self.frame_ready.emit(frame)

    @staticmethod
    def _dynamic_from_volume(volume: int) -> str:
        if volume < 10:
            return "pp"
        if volume < 20:
            return "p"
        if volume < 40:
            return "mp"
        if volume < 65:
            return "mf"
        if volume < 85:
            return "f"
        return "ff"

    @staticmethod
    def _environment_state(temperature: float, humidity: float) -> tuple[str, str]:
        temp_out = temperature < 15.0 or temperature > 30.0
        humidity_out = humidity < 40.0 or humidity > 60.0
        if temp_out and humidity_out:
            return "ALERT", "Temp and humidity out of range"
        if humidity < 40.0:
            return "WARN", "Dry air"
        if humidity > 60.0:
            return "WARN", "Humid air"
        if temperature < 15.0:
            return "WARN", "Too cold"
        if temperature > 30.0:
            return "WARN", "Too warm"
        return "OK", "Cello safe"
