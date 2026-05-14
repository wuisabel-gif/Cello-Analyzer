from __future__ import annotations

from collections import deque
from math import floor

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


ACCENT = QColor("#c38bf2")
ACCENT_ALT = QColor("#f0b84b")
SURFACE = QColor("#171717")
SURFACE_ELEVATED = QColor("#232323")
TEXT = QColor("#f3f1f8")
MUTED = QColor("#aaa4b5")
GRID = QColor("#34303b")


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "--", subtitle: str = "") -> None:
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #232323; border: 1px solid #34303b; border-radius: 16px; }"
            "QLabel { color: #f3f1f8; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #bdb5cb; font-size: 12px; text-transform: uppercase;")
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 30px; font-weight: 700;")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet("color: #bdb5cb; font-size: 12px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)
        layout.addWidget(self.subtitle_label)

    def set_value(self, value: str, subtitle: str | None = None) -> None:
        self.value_label.setText(value)
        if subtitle is not None:
            self.subtitle_label.setText(subtitle)


class WaveformWidget(QWidget):
    def __init__(self, title: str = "Live Waveform") -> None:
        super().__init__()
        self._title = title
        self._samples = [0.0] * 64
        self.setMinimumHeight(200)

    def set_samples(self, samples: list[float]) -> None:
        if samples:
            self._samples = samples[:]
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), SURFACE_ELEVATED)

        painter.setPen(QPen(GRID, 1))
        for row in range(1, 4):
            y = int(self.height() * row / 4)
            painter.drawLine(0, y, self.width(), y)

        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(TEXT)
        painter.drawText(QRectF(16, 10, self.width() - 32, 24), self._title)

        plot_rect = QRectF(16, 44, self.width() - 32, self.height() - 60)
        painter.setPen(QPen(MUTED, 1))
        painter.drawRoundedRect(plot_rect, 10, 10)

        if not self._samples:
            return

        mid_y = plot_rect.center().y()
        path = QPainterPath()
        sample_count = len(self._samples)
        max_amp = max(0.05, max(abs(sample) for sample in self._samples))
        for index, sample in enumerate(self._samples):
            x = plot_rect.left() + (plot_rect.width() * index / max(1, sample_count - 1))
            y = mid_y - (sample / max_amp) * (plot_rect.height() * 0.42)
            point = QPointF(x, y)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)

        painter.setPen(QPen(ACCENT, 2.5))
        painter.drawPath(path)


class HistoryChartWidget(QWidget):
    def __init__(self, title: str, color: QColor = ACCENT, max_points: int = 120) -> None:
        super().__init__()
        self._title = title
        self._color = color
        self._history: deque[float] = deque(maxlen=max_points)
        self._unit = ""
        self.setMinimumHeight(180)

    def append_value(self, value: float, unit: str = "") -> None:
        self._history.append(value)
        self._unit = unit
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), SURFACE_ELEVATED)

        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(TEXT)
        painter.drawText(QRectF(16, 10, self.width() - 32, 24), self._title)

        plot_rect = QRectF(16, 44, self.width() - 32, self.height() - 60)
        painter.setPen(QPen(GRID, 1))
        painter.drawRoundedRect(plot_rect, 10, 10)
        for row in range(1, 4):
            y = plot_rect.top() + plot_rect.height() * row / 4
            painter.drawLine(plot_rect.left(), y, plot_rect.right(), y)

        if len(self._history) < 2:
            return

        values = list(self._history)
        low = min(values)
        high = max(values)
        if abs(high - low) < 0.01:
            high += 1.0
            low -= 1.0

        small_font = QFont()
        small_font.setPointSize(9)
        painter.setFont(small_font)
        painter.setPen(MUTED)
        painter.drawText(QRectF(plot_rect.left(), plot_rect.top() - 2, 120, 14), f"{high:.1f}{self._unit}")
        painter.drawText(QRectF(plot_rect.left(), plot_rect.bottom() - 14, 120, 14), f"{low:.1f}{self._unit}")

        path = QPainterPath()
        count = len(values)
        for index, value in enumerate(values):
            x = plot_rect.left() + (plot_rect.width() * index / max(1, count - 1))
            norm = (value - low) / (high - low)
            y = plot_rect.bottom() - norm * plot_rect.height()
            point = QPointF(x, y)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)

        painter.setPen(QPen(self._color, 2.5))
        painter.drawPath(path)


class OledPreviewWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._mode = "Performance"
        self._dynamic = "pp"
        self._volume = 0
        self._temperature = 23.2
        self._humidity = 55.4
        self._waveform = [0.0] * 64
        self._history_text = {
            "pp": 0,
            "p": 0,
            "mp": 0,
            "mf": 0,
            "f": 0,
            "ff": 0,
        }
        self._env_history = {
            "temp_high": 23.2,
            "temp_low": 23.2,
            "hum_high": 55.4,
            "hum_low": 55.4,
        }
        self.setMinimumSize(300, 260)

    def set_frame(self, frame, dynamic_history: dict[str, int], env_history: dict[str, float]) -> None:
        self._mode = frame.mode
        self._dynamic = frame.dynamic
        self._volume = frame.volume
        self._temperature = frame.temperature
        self._humidity = frame.humidity
        self._waveform = frame.waveform[:]
        self._history_text = dynamic_history
        self._env_history = env_history
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), SURFACE)

        screen = QRectF(24, 20, self.width() - 48, self.height() - 40)
        painter.setBrush(QColor("#0d0d0d"))
        painter.setPen(QPen(QColor("#403850"), 2))
        painter.drawRoundedRect(screen, 18, 18)

        scale_x = screen.width() / 64.0
        scale_y = screen.height() / 48.0
        painter.save()
        painter.translate(screen.topLeft())
        painter.scale(scale_x, scale_y)
        painter.setClipRect(QRectF(0, 0, 64, 48))

        painter.setPen(QPen(ACCENT, 1.2))
        oled_font = QFont("Courier New")
        oled_font.setPixelSize(4)
        oled_font.setBold(True)
        painter.setFont(oled_font)
        mode_key = self._mode.lower()
        if "trend" in mode_key and "environment" not in mode_key:
            painter.drawText(QRectF(2, 5, 60, 8), "Dyn Trend")
            row_y = [16, 28, 40]
            labels = [("pp", "p"), ("mp", "mf"), ("f", "ff")]
            for row, pair in zip(row_y, labels):
                left, right = pair
                painter.drawText(QRectF(2, row, 30, 8), f"{left}{self._history_text[left]}%")
                painter.drawText(QRectF(32, row, 30, 8), f"{right}{self._history_text[right]}%")
        elif "environment history" in mode_key:
            painter.drawText(QRectF(2, 5, 30, 8), "Temp")
            painter.drawText(QRectF(2, 13, 40, 8), f"H:{self._env_history['temp_high']:.1f}C")
            painter.drawText(QRectF(2, 21, 40, 8), f"L:{self._env_history['temp_low']:.1f}C")
            painter.drawText(QRectF(2, 31, 30, 8), "Hum")
            painter.drawText(QRectF(2, 39, 40, 8), f"H:{self._env_history['hum_high']:.0f}%")
            painter.drawText(QRectF(2, 46, 40, 8), f"L:{self._env_history['hum_low']:.0f}%")
        elif "environment" in mode_key:
            painter.drawText(QRectF(2, 5, 28, 8), "Temp:")
            painter.drawText(QRectF(2, 15, 40, 8), f"{self._temperature:.1f} C")
            painter.drawText(QRectF(2, 31, 28, 8), "Hum:")
            painter.drawText(QRectF(2, 41, 40, 8), f"{self._humidity:.1f}%")
        else:
            signal_range = max(0.1, max(self._waveform) - min(self._waveform))
            min_sample = min(self._waveform)
            for index in range(len(self._waveform) - 1):
                y0 = 2 + ((self._waveform[index] - min_sample) * 27) / signal_range
                y1 = 2 + ((self._waveform[index + 1] - min_sample) * 27) / signal_range
                painter.drawLine(index, 29 - y0, index + 1, 29 - y1)
            painter.drawText(QRectF(2, 42, 18, 8), self._dynamic)
            painter.drawText(QRectF(24, 42, 20, 8), f"{self._volume}%")

        painter.restore()


def dynamic_group_percentages(history: list[str]) -> dict[str, int]:
    labels = ["pp", "p", "mp", "mf", "f", "ff"]
    counts = {label: 0 for label in labels}
    if not history:
        return counts
    for label in history:
        counts[label] = counts.get(label, 0) + 1
    total = len(history)
    return {label: floor((counts[label] * 100) / total) for label in labels}
