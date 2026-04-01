"""
app.py — Entry point for Juice | Render Manager for Blender.

Usage:
    python app.py
"""
import sys
import subprocess

def _check_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        _app = QApplication(sys.argv)
        answer = QMessageBox.question(
            None,
            "Missing Dependency",
            "Pillow is required for image previews.\nInstall it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
        else:
            sys.exit(1)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    from main_window import MainWindow

    _check_pillow()

    app = QApplication(sys.argv)
    app.setApplicationName("Juice | Render Manager for Blender")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
