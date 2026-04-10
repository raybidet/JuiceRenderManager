from PyQt6.QtWidgets import QWidget, QSlider, QDoubleSpinBox, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional

class ResolutionSliderWidget(QWidget):
    value_changed = pyqtSignal(float)

    def __init__(self, default_pct: float = 100.0):
        super().__init__()
        self.default_pct = default_pct
        self.override_pct: Optional[float] = None
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(default_pct))
        self.slider.valueChanged.connect(self._on_slider_change)
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(0.0, 100.0)
        self.spinbox.setSingleStep(1.0)
        self.spinbox.setDecimals(1)
        self.spinbox.setValue(default_pct)
        self.spinbox.valueChanged.connect(self._on_spinbox_change)
        self.spinbox.hide()

        self.label = QLabel("def")
        self.label.setStyleSheet("color: gray; font-style: italic;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spinbox)

        self.show_default()

    def show_default(self):
        self.label.setText(f"{self.default_pct:g}%")
        self.slider.hide()
        self.spinbox.hide()
        self.label.show()

    def show_override(self):
        self.label.hide()
        self.slider.show()
        self.spinbox.show()

    def _on_slider_change(self, value: int):
        pct = float(value)
        self.spinbox.setValue(pct)
        self.override_pct = pct
        self.value_changed.emit(pct)

    def _on_spinbox_change(self, pct: float):
        self.slider.setValue(int(pct))
        self.override_pct = pct
        self.value_changed.emit(pct)

    def set_override(self, pct: Optional[float]):
        if pct is None:
            self.show_default()
        else:
            self.override_pct = pct
            self.slider.setValue(int(pct))
            self.spinbox.setValue(pct)
            self.show_override()

    def get_value(self) -> Optional[float]:
        return self.override_pct

    def mousePressEvent(self, event):
        if self.label.isVisible():
            self.show_override()
        super().mousePressEvent(event)
