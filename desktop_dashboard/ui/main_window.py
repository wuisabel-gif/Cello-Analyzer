from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_dashboard.data.logger import SessionLogger
from desktop_dashboard.data.mock_client import MockDataSource
from desktop_dashboard.data.serial_client import SerialDataSource
from desktop_dashboard.ui.widgets import (
    ACCENT,
    ACCENT_ALT,
    HistoryChartWidget,
    MetricCard,
    OledPreviewWidget,
    WaveformWidget,
    dynamic_group_percentages,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Cello Analyzer Desktop Dashboard")
        self.resize(1320, 880)

        self.logger = SessionLogger()
        self.recording_enabled = False
        self.dynamic_history: deque[str] = deque(maxlen=48)
        self.max_temp = -1000.0
        self.min_temp = 1000.0
        self.max_humidity = -1000.0
        self.min_humidity = 1000.0

        self.mock_source = MockDataSource()
        self.serial_source = SerialDataSource()
        self.active_source = None

        self.mock_source.frame_ready.connect(self._handle_frame)
        self.mock_source.status_changed.connect(self._log_status)
        self.serial_source.frame_ready.connect(self._handle_frame)
        self.serial_source.status_changed.connect(self._log_status)

        self._build_ui()
        self._set_dashboard_style()
        self._start_mock_source()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        title = QLabel("Cello Analyzer Desktop Dashboard")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #f3f1f8;")
        subtitle = QLabel(
            "Real-time waveform, dynamics, and cello environment monitoring from a Photon 2 system."
        )
        subtitle.setStyleSheet("font-size: 14px; color: #bdb5cb;")

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Mock Source", "Serial Source"])
        self.source_combo.currentIndexChanged.connect(self._change_source)

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("Serial port, e.g. /dev/tty.usbmodem1102")
        self.port_input.setEnabled(False)

        self.connect_button = QPushButton("Connect Serial")
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self._connect_serial)

        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self._toggle_recording)
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self._export_csv)

        for widget in [
            QLabel("Data Source"),
            self.source_combo,
            self.port_input,
            self.connect_button,
            self.record_button,
            self.export_button,
        ]:
            controls.addWidget(widget)
        controls.addStretch(1)

        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)
        root_layout.addLayout(controls)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        self.mode_card = MetricCard("Current Mode", "Performance", "Desktop view")
        self.dynamic_card = MetricCard("Dynamic", "pp", "Current musical dynamic")
        self.volume_card = MetricCard("Volume", "0%", "Normalized loudness")
        self.temperature_card = MetricCard("Temperature", "--.- C", "Current environment")
        self.humidity_card = MetricCard("Humidity", "--.- %", "Relative humidity")
        self.health_card = MetricCard("Cello Health", "Waiting...", "Environment interpretation")

        grid.addWidget(self.mode_card, 0, 0)
        grid.addWidget(self.dynamic_card, 0, 1)
        grid.addWidget(self.volume_card, 0, 2)
        grid.addWidget(self.temperature_card, 0, 3)
        grid.addWidget(self.humidity_card, 0, 4)
        grid.addWidget(self.health_card, 0, 5)

        self.waveform_widget = WaveformWidget("Live Waveform")
        self.volume_history_widget = HistoryChartWidget("Volume History", ACCENT)
        self.environment_history_widget = HistoryChartWidget("Temperature History", ACCENT_ALT)
        self.humidity_history_widget = HistoryChartWidget("Humidity History", ACCENT)
        self.oled_preview = OledPreviewWidget()

        grid.addWidget(self.waveform_widget, 1, 0, 1, 4)
        grid.addWidget(self.oled_preview, 1, 4, 2, 2)
        grid.addWidget(self.volume_history_widget, 2, 0, 1, 2)
        grid.addWidget(self.environment_history_widget, 2, 2, 1, 1)
        grid.addWidget(self.humidity_history_widget, 2, 3, 1, 1)

        root_layout.addLayout(grid)

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setPlaceholderText("Session log and connection status will appear here.")
        self.status_log.setMinimumHeight(140)
        root_layout.addWidget(self.status_log)

    def _set_dashboard_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #171717;
                color: #f3f1f8;
            }
            QLabel {
                color: #f3f1f8;
            }
            QComboBox, QLineEdit, QTextEdit {
                background: #232323;
                border: 1px solid #34303b;
                border-radius: 10px;
                padding: 8px 10px;
                color: #f3f1f8;
            }
            QPushButton {
                background: #c38bf2;
                color: #171717;
                font-weight: 700;
                border-radius: 10px;
                padding: 8px 14px;
            }
            QPushButton:disabled {
                background: #57505f;
                color: #c8c2d1;
            }
            """
        )

    def _start_mock_source(self) -> None:
        self.active_source = "mock"
        self.mock_source.start()

    def _stop_sources(self) -> None:
        self.mock_source.stop()
        self.serial_source.disconnect_port()

    def _change_source(self, index: int) -> None:
        source_name = self.source_combo.itemText(index)
        self._stop_sources()
        if source_name == "Serial Source":
            self.active_source = "serial"
            self.port_input.setEnabled(True)
            self.connect_button.setEnabled(True)
            self._log_status("Serial source selected")
        else:
            self.active_source = "mock"
            self.port_input.setEnabled(False)
            self.connect_button.setEnabled(False)
            self.mock_source.start()

    def _connect_serial(self) -> None:
        port_name = self.port_input.text().strip()
        if not port_name:
            ports = SerialDataSource.available_ports()
            if ports:
                port_name = ports[0]
                self.port_input.setText(port_name)
        if not port_name:
            QMessageBox.warning(self, "Serial Connection", "Enter a serial port name first.")
            return
        if self.serial_source.connect_port(port_name):
            self._log_status(f"Waiting for data on {port_name}")

    def _toggle_recording(self) -> None:
        self.recording_enabled = not self.recording_enabled
        if self.recording_enabled:
            self.logger.clear()
            self.record_button.setText("Stop Recording")
            self._log_status("Recording started")
        else:
            self.record_button.setText("Start Recording")
            self._log_status(f"Recording stopped with {self.logger.frame_count} frames")

    def _export_csv(self) -> None:
        if self.logger.frame_count == 0:
            QMessageBox.information(self, "Export CSV", "No recorded frames to export yet.")
            return
        default_name = f"cello-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", str(Path.home() / default_name), "CSV Files (*.csv)")
        if not path:
            return
        self.logger.export_csv(path)
        self._log_status(f"Exported session to {path}")

    def _handle_frame(self, frame) -> None:
        self.dynamic_history.append(frame.dynamic)
        self.max_temp = max(self.max_temp, frame.temperature)
        self.min_temp = min(self.min_temp, frame.temperature)
        self.max_humidity = max(self.max_humidity, frame.humidity)
        self.min_humidity = min(self.min_humidity, frame.humidity)

        if self.recording_enabled:
            self.logger.add_frame(frame)

        self.mode_card.set_value(frame.mode, "Active OLED/dashboard mode")
        self.dynamic_card.set_value(frame.dynamic, f"Alert: {frame.alert}")
        self.volume_card.set_value(f"{frame.volume}%", f"Raw amplitude {frame.raw}")
        self.temperature_card.set_value(f"{frame.temperature:.1f} C", f"Range {self.min_temp:.1f} to {self.max_temp:.1f}")
        self.humidity_card.set_value(f"{frame.humidity:.1f} %", f"Range {self.min_humidity:.1f} to {self.max_humidity:.1f}")
        self.health_card.set_value(frame.cello_health, frame.alert)

        self.waveform_widget.set_samples(frame.waveform)
        self.volume_history_widget.append_value(frame.volume, "%")
        self.environment_history_widget.append_value(frame.temperature, "C")
        self.humidity_history_widget.append_value(frame.humidity, "%")
        self.oled_preview.set_frame(
            frame,
            dynamic_group_percentages(list(self.dynamic_history)),
            {
                "temp_high": self.max_temp,
                "temp_low": self.min_temp,
                "hum_high": self.max_humidity,
                "hum_low": self.min_humidity,
            },
        )

    def _log_status(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_log.append(f"[{timestamp}] {message}")
