from __future__ import annotations

import json
import re
from datetime import datetime

from PySide6.QtCore import QObject, Signal

try:
    from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
except ImportError:  # pragma: no cover
    QSerialPort = None
    QSerialPortInfo = None

from desktop_dashboard.data.models import SensorFrame


AMP_PATTERN = re.compile(
    r"Amp:(?P<raw>-?\d+)\s*\|\s*Peak:(?P<peak>-?\d+)\s*\|\s*Vol:(?P<vol>\d+)%\s*\|\s*Dyn:(?P<dynamic>[a-z]+)",
    re.IGNORECASE,
)


class SerialDataSource(QObject):
    frame_ready = Signal(object)
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._port = None if QSerialPort is None else QSerialPort(self)
        self._buffer = bytearray()
        self._latest_temperature = 23.0
        self._latest_humidity = 55.0
        self._latest_alert = "OK"
        self._latest_health = "Waiting..."
        self._latest_mode = "Performance"
        if self._port is not None:
            self._port.readyRead.connect(self._read_available)

    @staticmethod
    def available_ports() -> list[str]:
        if QSerialPortInfo is None:
            return []
        return [info.portName() for info in QSerialPortInfo.availablePorts()]

    def connect_port(self, port_name: str, baud_rate: int = 9600) -> bool:
        if self._port is None:
            self.status_changed.emit("QtSerialPort is not available in this PySide6 build")
            return False
        if self._port.isOpen():
            self._port.close()
        self._port.setPortName(port_name)
        self._port.setBaudRate(baud_rate)
        if not self._port.open(QSerialPort.ReadOnly):
            self.status_changed.emit(f"Failed to open serial port: {port_name}")
            return False
        self.status_changed.emit(f"Connected to serial port: {port_name}")
        return True

    def disconnect_port(self) -> None:
        if self._port is not None and self._port.isOpen():
            port_name = self._port.portName()
            self._port.close()
            self.status_changed.emit(f"Disconnected from serial port: {port_name}")

    def _read_available(self) -> None:
        if self._port is None:
            return
        self._buffer.extend(bytes(self._port.readAll()))
        while b"\n" in self._buffer:
            line, _, self._buffer = self._buffer.partition(b"\n")
            self._parse_line(line.decode("utf-8", errors="ignore").strip())

    def _parse_line(self, line: str) -> None:
        if not line:
            return

        if line.startswith("{"):
            self._parse_json_line(line)
            return

        if line.lower().startswith("env"):
            self._parse_environment_line(line)
            return

        match = AMP_PATTERN.search(line)
        if not match:
            self.status_changed.emit(f"Serial: {line}")
            return

        raw = int(match.group("raw"))
        peak = int(match.group("peak"))
        volume = int(match.group("vol"))
        dynamic = match.group("dynamic")
        waveform = self._synthetic_waveform(raw)
        frame = SensorFrame(
            timestamp=datetime.now(),
            raw=raw,
            peak=peak,
            volume=volume,
            dynamic=dynamic,
            temperature=self._latest_temperature,
            humidity=self._latest_humidity,
            alert=self._latest_alert,
            cello_health=self._latest_health,
            mode=self._latest_mode,
            waveform=waveform,
        )
        self.frame_ready.emit(frame)

    def _parse_json_line(self, line: str) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            self.status_changed.emit(f"Invalid JSON: {line}")
            return

        self._latest_temperature = float(payload.get("temperature", self._latest_temperature))
        self._latest_humidity = float(payload.get("humidity", self._latest_humidity))
        self._latest_alert = str(payload.get("alert", self._latest_alert))
        self._latest_health = str(payload.get("celloHealth", self._latest_health))
        self._latest_mode = str(payload.get("mode", self._latest_mode))
        raw = int(payload.get("raw", 0))
        volume = int(payload.get("volume", 0))
        dynamic = str(payload.get("dynamic", "pp"))
        waveform = payload.get("waveform", self._synthetic_waveform(raw))
        frame = SensorFrame(
            timestamp=datetime.now(),
            raw=raw,
            peak=int(payload.get("peak", raw * 0.35)),
            volume=volume,
            dynamic=dynamic,
            temperature=self._latest_temperature,
            humidity=self._latest_humidity,
            alert=self._latest_alert,
            cello_health=self._latest_health,
            mode=self._latest_mode,
            waveform=list(map(float, waveform)),
        )
        self.frame_ready.emit(frame)

    def _parse_environment_line(self, line: str) -> None:
        temp_match = re.search(r"temp[:=]\s*([0-9.]+)", line, re.IGNORECASE)
        hum_match = re.search(r"hum(?:idity)?[:=]\s*([0-9.]+)", line, re.IGNORECASE)
        alert_match = re.search(r"alert[:=]\s*([A-Za-z]+)", line, re.IGNORECASE)
        if temp_match:
            self._latest_temperature = float(temp_match.group(1))
        if hum_match:
            self._latest_humidity = float(hum_match.group(1))
        if alert_match:
            self._latest_alert = alert_match.group(1).upper()
        self.status_changed.emit(f"Environment update: {line}")

    @staticmethod
    def _synthetic_waveform(raw: int) -> list[float]:
        amplitude = max(0.08, min(1.0, raw / 7000.0))
        return [amplitude * 0.6 * __import__("math").sin(index * 0.32) for index in range(64)]
