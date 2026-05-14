from PySide6.QtWidgets import QApplication

from desktop_dashboard.ui.main_window import MainWindow


def main() -> int:
    app = QApplication([])
    app.setApplicationName("Cello Analyzer Desktop Dashboard")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
