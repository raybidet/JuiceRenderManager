"""
main_window.py — PyQt6 main window for Juice | Render Manager for Blender.

PyQt6 runs the UI in the main thread but dispatches render work to QThreads.
Cross-thread communication uses Qt Signals, which are thread-safe by design —
no more Tkinter after() polling or event-loop starvation.
"""
from __future__ import annotations

import os
import sys
import subprocess
import time
import threading
import ctypes
import html as _html
import queue
import json

try:
    import winsound as _winsound
    _HAS_WINSOUND = True
except ImportError:
    _winsound = None
    _HAS_WINSOUND = False

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QObject, QTimer, QSize,
)
from PyQt6.QtGui import QColor, QPixmap, QImage, QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QSpinBox,
    QComboBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QGroupBox, QSizePolicy,
    QScrollArea, QCheckBox, QFrame, QStatusBar, QApplication,
    QDialog, QDialogButtonBox, QListWidget, QFormLayout,
)

from models import (
    RenderJob,
    save_config,
    load_config,
    DEFAULT_BLENDER,
    BlenderProfile,
    resolve_blender_exec,
)
from worker import RenderWorker, get_blend_info
from ipc_server import JuiceIPCServer
from video_presets import VIDEO_PRESETS, PREVIEW_PRESET, preset_names, preset_by_name





# ---------------------------------------------------------------------------
# Colour palette (Catppuccin Mocha)
# ---------------------------------------------------------------------------
C = {
    "bg":      "#1e1e2e",
    "surface": "#313244",
    "overlay": "#45475a",
    "text":    "#cdd6f4",
    "subtext": "#585b70",
    "accent":  "#89b4fa",
    "green":   "#a6e3a1",
    "red":     "#f38ba8",
    "peach":   "#fab387",
    "lavender":"#b4befe",
    "mauve":   "#cba6f7",
    "yellow":  "#f9e2af",
    "teal":    "#94e2d5",
}

# Sentinel label in profile combo for free-form blender.exe path
CUSTOM_PROFILE_LABEL = "Custom path…"

STATUS_COLOR = {
    RenderJob.STATUS_PENDING:   C["subtext"],
    RenderJob.STATUS_RUNNING:   C["peach"],
    RenderJob.STATUS_PAUSED:    C["yellow"],
    RenderJob.STATUS_DONE:      C["green"],
    RenderJob.STATUS_ERROR:     C["red"],
    RenderJob.STATUS_CANCELLED: C["overlay"],
}

STYLESHEET = f"""
QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: "Segoe UI";
    font-size: 10pt;
}}
QGroupBox {{
    border: 1px solid {C['surface']};
    border-radius: 6px;
    margin-top: 8px;
    padding: 6px;
    font-weight: bold;
    color: {C['accent']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: -4px;
}}
QPushButton {{
    background-color: {C['surface']};
    color: {C['text']};
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
}}
QPushButton:hover  {{ background-color: {C['accent']}; color: {C['bg']}; }}
QPushButton:pressed {{ background-color: {C['lavender']}; color: {C['bg']}; }}
QPushButton#accent {{
    background-color: {C['accent']};
    color: {C['bg']};
    font-weight: bold;
}}
QPushButton#accent:hover {{ background-color: {C['lavender']}; }}
QPushButton#danger {{ background-color: {C['surface']}; color: {C['red']}; }}
QPushButton#danger:hover {{ background-color: {C['red']}; color: {C['bg']}; }}
QPushButton#nodes_on  {{ background-color: {C['green']};  color: {C['bg']}; font-weight: bold; }}
QPushButton#nodes_off {{ background-color: {C['red']};    color: {C['bg']}; font-weight: bold; }}
QLineEdit, QSpinBox, QComboBox {{
    background-color: {C['surface']};
    color: {C['text']};
    border: 1px solid {C['overlay']};
    border-radius: 4px;
    padding: 3px 6px;
    selection-background-color: {C['accent']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {C['accent']};
}}
QComboBox QAbstractItemView {{
    background-color: {C['surface']};
    color: {C['text']};
    selection-background-color: {C['accent']};
    selection-color: {C['bg']};
}}
QProgressBar {{
    background-color: {C['surface']};
    border: none;
    border-radius: 4px;
    height: 12px;
    text-align: center;
    color: {C['bg']};
}}
QProgressBar::chunk {{
    background-color: {C['accent']};
    border-radius: 4px;
}}
QTreeWidget {{
    background-color: {C['surface']};
    alternate-background-color: {C['bg']};
    border: none;
    border-radius: 4px;
}}
QTreeWidget::item:selected {{
    background-color: {C['overlay']};
    color: {C['text']};
}}
QHeaderView::section {{
    background-color: {C['bg']};
    color: {C['accent']};
    font-weight: bold;
    border: none;
    padding: 4px;
}}
QTextEdit {{
    background-color: #181825;
    color: {C['green']};
    border: none;
    font-family: "Consolas";
    font-size: 9pt;
}}
QScrollBar:vertical {{
    background: {C['surface']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C['overlay']};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{
    background: {C['surface']};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {C['overlay']};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QSplitter::handle {{
    background: {C['overlay']};
    width: 4px;
    height: 4px;
}}
QStatusBar {{ color: {C['subtext']}; }}
QLabel#section_label {{
    color: {C['accent']};
    font-weight: bold;
}}
QLabel#value_label {{
    color: {C['text']};
    font-size: 10pt;
}}
"""


def fmt_duration(seconds) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


# ---------------------------------------------------------------------------
# Qt Signals bridge (runs in QThread, emits to main thread safely)
# ---------------------------------------------------------------------------

class WorkerSignals(QObject):
    log_line     = pyqtSignal(int, str)       # job_id, line
    progress     = pyqtSignal(int)            # job_id
    frame_saved  = pyqtSignal(int)            # job_id
    done         = pyqtSignal(int, str)       # job_id, status


class RenderThread(QThread):
    def __init__(
        self,
        job: RenderJob,
        signals: WorkerSignals,
        blender_executable: str | None = None,
    ):
        super().__init__()
        self.job                = job
        self.signals            = signals
        self._blender_executable = blender_executable

    def run(self):
        worker = RenderWorker(
            job=self.job,
            on_log=self.signals.log_line.emit,
            on_progress=self.signals.progress.emit,
            on_done=self.signals.done.emit,
            on_frame_saved=self.signals.frame_saved.emit,
            blender_executable=self._blender_executable,
        )
        worker.run()


class BlendInfoThread(QThread):
    """Queries blend file info without blocking the UI."""
    finished = pyqtSignal(dict)

    def __init__(self, blend_file: str, blender_exec: str):
        super().__init__()
        self.blend_file   = blend_file
        self.blender_exec = blender_exec

    def run(self):
        info = get_blend_info(self.blend_file, self.blender_exec)
        self.finished.emit(info)


class ConvertThread(QThread):
    """Converts a PNG sequence to a video file using FFmpeg (from PATH)."""
    finished = pyqtSignal(bool, str)   # success, message

    def __init__(
        self,
        output_path: str,
        file_prefix: str,
        frame_start: int,
        fps: float,
        output_file: str,
        preset: dict,
    ):
        super().__init__()
        self.output_path = output_path
        self.file_prefix = file_prefix
        self.frame_start = frame_start
        self.fps         = fps
        self.output_file = output_file
        self.preset      = preset

    def run(self):
        input_pattern = os.path.join(self.output_path, f"{self.file_prefix}_%04d.png")
        cmd = [
            "ffmpeg",
            "-framerate", str(self.fps),
            "-start_number", str(self.frame_start),
            "-i", input_pattern,
            *self.preset["ffmpeg_args"],
            "-y",
            self.output_file,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                self.finished.emit(True, f"Video guardado en: {self.output_file}")
            else:
                err = (result.stderr or "").strip()
                self.finished.emit(False, err[-800:] if err else "FFmpeg retornó error.")
        except FileNotFoundError:
            self.finished.emit(
                False,
                "FFmpeg no encontrado en PATH.\n"
                "Instalá FFmpeg y asegurate de que esté en las variables de entorno del sistema.",
            )
        except Exception as e:
            self.finished.emit(False, str(e))



# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Juice | Render Manager for Blender")
        self._set_app_icon()
        self.resize(1300, 820)
        self.setMinimumSize(1000, 660)
        self.setStyleSheet(STYLESHEET)

        self.jobs: list[RenderJob]                       = []
        self.threads: dict[int, RenderThread]            = {}
        self.signals: dict[int, WorkerSignals]           = {}
        self._selected_job_id: int | None                = None
        self._log_autoscroll: bool                       = True
        self._blend_info_cache: dict                     = {}
        self._blend_info_thread: BlendInfoThread | None  = None
        self._convert_thread: ConvertThread | None       = None
        self._blender_profiles: list[BlenderProfile]   = []
        self._form_dirty: bool                          = False
        self.job_list_has_focus: bool                   = False
        self._loading_job_into_form: bool               = False
        self._sequential_queue: list[int]               = []
        self._sequential_target_ids: set[int]           = set()

        self._ipc_server: JuiceIPCServer | None           = None
        self._ipc_queue: queue.Queue[dict]              = queue.Queue()

        self.setAcceptDrops(True)

        self._build_ui()
        self._load_jobs()
        self._start_ipc_server()

        # 1-second timer updates elapsed / ETA for running jobs
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_timers)
        self._timer.start(1000)

        self._ipc_timer = QTimer(self)
        self._ipc_timer.timeout.connect(self._drain_ipc_queue)
        self._ipc_timer.start(120)

    # ------------------------------------------------------------------ Icon

    def _set_app_icon(self) -> None:
        """Set window/app icon from project root (logo.ico preferred)."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, "logo.ico"),
            os.path.join(base_dir, "logo.png"),
        ]
        for icon_path in candidates:
            if os.path.isfile(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    app = QApplication.instance()
                    if isinstance(app, QApplication):
                        app.setWindowIcon(icon)
                    return

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 4)
        root_layout.setSpacing(6)

        # ── Top bar ──────────────────────────────────────────────────────
        top = QHBoxLayout()
        title = QLabel("Juice | Render Manager for Blender")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C['mauve']};")
        top.addWidget(title)
        top.addStretch()

        top.addWidget(QLabel("Blender profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(160)
        self.profile_combo.currentTextChanged.connect(self._on_profile_combo_changed)
        top.addWidget(self.profile_combo)

        self.blender_path_edit = QLineEdit(DEFAULT_BLENDER)
        self.blender_path_edit.setMinimumWidth(320)
        top.addWidget(self.blender_path_edit)
        btn_browse_blender = QPushButton("Browse")
        btn_browse_blender.clicked.connect(self._browse_blender)
        top.addWidget(btn_browse_blender)
        btn_reset_blender = QPushButton("Reset")
        btn_reset_blender.clicked.connect(self._reset_blender_path)
        top.addWidget(btn_reset_blender)
        btn_manage_profiles = QPushButton("Profiles…")
        btn_manage_profiles.setToolTip("Managing Blender routes (multiple versions)")
        btn_manage_profiles.clicked.connect(self._manage_profiles_dialog)
        top.addWidget(btn_manage_profiles)
        root_layout.addLayout(top)

        # ── Horizontal splitter: left (queue + form) | right (details) ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        root_layout.addWidget(splitter, stretch=1)

        # ── LEFT panel ───────────────────────────────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        splitter.addWidget(left_widget)

        # Queue table
        queue_group = QGroupBox("Render Queue")
        queue_layout = QVBoxLayout(queue_group)

        self.queue_tree = QTreeWidget()
        self.queue_tree.setAlternatingRowColors(True)
        self.queue_tree.setRootIsDecorated(False)
        self.queue_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        headers = [
            "#", "Blend File", "Scene", "Blender", "Samples", "Res %", "Sequence",
            "Frames", "Output", "Status", "%", "Frame",
        ]
        self.queue_tree.setHeaderLabels(headers)
        self.queue_tree.setColumnWidth(0, 32)
        self.queue_tree.setColumnWidth(1, 140)
        self.queue_tree.setColumnWidth(2, 72)
        self.queue_tree.setColumnWidth(3, 100)
        self.queue_tree.setColumnWidth(4, 52)
        self.queue_tree.setColumnWidth(5, 68)
        self.queue_tree.setColumnWidth(6, 88)
        self.queue_tree.setColumnWidth(7, 72)
        self.queue_tree.setColumnWidth(8, 120)
        self.queue_tree.setColumnWidth(9, 72)
        self.queue_tree.setColumnWidth(10, 36)
        self.queue_tree.setColumnWidth(11, 52)
        self.queue_tree.currentItemChanged.connect(self._on_job_select)
        queue_layout.addWidget(self.queue_tree)

        # Queue action buttons
        btn_row_top = QHBoxLayout()
        btn_row_bottom = QHBoxLayout()

        self._btn_start     = QPushButton("▶  Start Selected")
        self._btn_start_all = QPushButton("▶▶  Start All Pending")
        self._btn_start_all.setObjectName("accent")
        self._simul_checkbox = QCheckBox("Render all jobs simultaneously")
        self._simul_checkbox.setChecked(False)
        self._simul_checkbox.setToolTip(
            "ON: Launch all pending jobs at the same time.\n"
            "OFF: executes in sequential mode (one at a time)."
        )

        self._btn_cancel    = QPushButton("⏹  Cancel")
        self._btn_pause     = QPushButton("⏸  Pause")
        self._btn_remove    = QPushButton("🗑  Remove")
        self._btn_remove.setObjectName("danger")
        self._btn_retry     = QPushButton("🔁  Retry")
        self._btn_duplicate = QPushButton("📋  Duplicate")
        self._btn_move_up   = QPushButton("↑")
        self._btn_move_up.setFixedWidth(30)
        self._btn_move_down = QPushButton("↓")
        self._btn_move_down.setFixedWidth(30)
        self._btn_export_queue = QPushButton("📤  Export Render Queue")
        self._btn_import_queue = QPushButton("📥  Load Render Queue")
        self._btn_save         = QPushButton("💾  Manual Save")
        self._btn_save.setToolTip("Auto-save enabled - use only if needed.")

        self._btn_start.clicked.connect(self._start_selected)
        self._btn_start_all.clicked.connect(self._start_all_pending)
        self._btn_cancel.clicked.connect(self._cancel_selected)
        self._btn_pause.clicked.connect(self._toggle_pause_selected)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_retry.clicked.connect(self._retry_selected)
        self._btn_duplicate.clicked.connect(self._duplicate_selected)
        self._btn_move_up.clicked.connect(self._move_job_up)
        self._btn_move_down.clicked.connect(self._move_job_down)
        self._btn_export_queue.clicked.connect(self._export_render_queue)
        self._btn_import_queue.clicked.connect(self._import_render_queue)
        self._btn_save.clicked.connect(self._save_jobs)

        btn_row_top.addWidget(self._btn_start)
        btn_row_top.addWidget(self._btn_start_all)
        btn_row_top.addWidget(self._simul_checkbox)
        btn_row_top.addStretch()
        btn_row_top.addWidget(self._btn_export_queue)
        btn_row_top.addWidget(self._btn_import_queue)
        btn_row_top.addWidget(self._btn_save)

        for btn in (
            self._btn_cancel, self._btn_pause, self._btn_remove,
            self._btn_retry, self._btn_duplicate, self._btn_move_up, self._btn_move_down
        ):
            btn_row_bottom.addWidget(btn)
        btn_row_bottom.addStretch()

        queue_layout.addLayout(btn_row_top)
        queue_layout.addLayout(btn_row_bottom)
        left_layout.addWidget(queue_group, stretch=3)

        # Add-job form
        form_group = QGroupBox("Add Render Job")
        form = QGridLayout(form_group)
        form.setColumnStretch(1, 1)

        # .blend file
        form.addWidget(QLabel(".blend File:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.blend_edit = QLineEdit()
        form.addWidget(self.blend_edit, 0, 1)
        btn_browse_blend = QPushButton("Browse")
        btn_browse_blend.clicked.connect(self._browse_blend)
        form.addWidget(btn_browse_blend, 0, 2)

        # Scene
        form.addWidget(QLabel("Scene:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        scene_row = QHBoxLayout()
        self.scene_combo = QComboBox()
        self.scene_combo.setMinimumWidth(180)
        self.scene_combo.currentTextChanged.connect(self._on_scene_changed)
        scene_row.addWidget(self.scene_combo)
        btn_load = QPushButton("Load Scenes")
        btn_load.clicked.connect(self._load_blend_info_async)
        scene_row.addWidget(btn_load)
        scene_row.addStretch()
        form.addLayout(scene_row, 1, 1, 1, 2)

        # Sequence name
        form.addWidget(QLabel("Sequence Name:"), 2, 0, Qt.AlignmentFlag.AlignRight)
        seq_row = QHBoxLayout()
        self.sequence_edit = QLineEdit()
        self.sequence_edit.setPlaceholderText("e.g. shot_010_lighting  (used as output subfolder)")
        seq_row.addWidget(self.sequence_edit)
        form.addLayout(seq_row, 2, 1, 1, 2)

        # Frame range + samples
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Frame Start:"))
        self.frame_start_spin = QSpinBox()
        self.frame_start_spin.setRange(0, 999999)
        self.frame_start_spin.setValue(1)
        self.frame_start_spin.setFixedWidth(80)
        range_row.addWidget(self.frame_start_spin)
        range_row.addWidget(QLabel("End:"))
        self.frame_end_spin = QSpinBox()
        self.frame_end_spin.setRange(0, 999999)
        self.frame_end_spin.setValue(250)
        self.frame_end_spin.setFixedWidth(80)
        range_row.addWidget(self.frame_end_spin)
        range_row.addSpacing(20)
        range_row.addWidget(QLabel("Samples:"))
        self.samples_edit = QLineEdit()
        self.samples_edit.setPlaceholderText("scene default")
        self.samples_edit.setFixedWidth(70)
        range_row.addWidget(self.samples_edit)
        self._samples_hint = QLabel("")
        self._samples_hint.setStyleSheet(f"color: {C['mauve']}; font-size: 8pt;")
        range_row.addWidget(self._samples_hint)
        
        range_row.addSpacing(8)
        range_row.addWidget(QLabel("Res %:"))
        self.resolution_edit = QLineEdit()
        self.resolution_edit.setPlaceholderText("100")
        self.resolution_edit.setFixedWidth(60)
        range_row.addWidget(self.resolution_edit)
        self._resolution_hint = QLabel("")
        self._resolution_hint.setStyleSheet(f"color: {C['mauve']}; font-size: 8pt;")
        range_row.addWidget(self._resolution_hint)
        
        range_row.addStretch()
        form.addWidget(QLabel("Frames:"), 3, 0, Qt.AlignmentFlag.AlignRight)
        form.addLayout(range_row, 3, 1, 1, 2)

        # Output path + sequence toggle
        form.addWidget(QLabel("Output Path:"), 4, 0, Qt.AlignmentFlag.AlignRight)
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        output_row.addWidget(self.output_edit)
        btn_browse_out = QPushButton("Browse")
        btn_browse_out.clicked.connect(self._browse_output)
        output_row.addWidget(btn_browse_out)
        form.addLayout(output_row, 4, 1, 1, 2)

        # Use Nodes button
        self.use_nodes_btn = QPushButton("COMPOSITING NODES: OFF")
        self.use_nodes_btn.setObjectName("nodes_off")
        self.use_nodes_btn.setCheckable(True)
        self.use_nodes_btn.setChecked(False)
        self.use_nodes_btn.clicked.connect(self._toggle_use_nodes)
        self.use_nodes_btn.setStyle(self.use_nodes_btn.style())
        form.addWidget(self.use_nodes_btn, 5, 1)

        # Add / Apply row
        add_apply_row = QHBoxLayout()
        btn_add = QPushButton("＋  Add Job to Queue")
        btn_add.setObjectName("accent")
        btn_add.setFixedHeight(32)
        btn_add.clicked.connect(self._add_job)
        add_apply_row.addWidget(btn_add, stretch=1)
        self._btn_apply_to_job = QPushButton("💾  Apply to selected job")
        self._btn_apply_to_job.setFixedHeight(32)
        self._btn_apply_to_job.setToolTip(
            "Save the form changes to the selected job in the queue. "
            "Not available while the job is running."
        )
        self._btn_apply_to_job.setEnabled(False)
        self._btn_apply_to_job.clicked.connect(self._apply_changes_to_selected_job)
        add_apply_row.addWidget(self._btn_apply_to_job, stretch=1)
        form.addLayout(add_apply_row, 6, 0, 1, 3)

        left_layout.addWidget(form_group, stretch=0)

        # ── RIGHT panel ──────────────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # Progress panel
        prog_group = QGroupBox("Render Progress")
        prog_grid = QGridLayout(prog_group)
        prog_grid.setColumnStretch(1, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        prog_grid.addWidget(QLabel("Progress:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        prog_grid.addWidget(self.progress_bar, 0, 1)

        self._prog_vars: dict[str, QLabel] = {}
        rows = [
            ("current_frame", "Current Frame:", C["peach"]),
            ("elapsed",       "Elapsed:",       C["accent"]),
            ("eta",           "ETA:",           C["green"]),
            ("frame_time",    "Last Frame:",    C["mauve"]),
            ("frames_done",   "Frames Done:",   C["text"]),
            ("samples",       "Samples:",       C["yellow"]),
            ("device",        "Render Device:", C["teal"]),
        ]
        for i, (key, lbl, color) in enumerate(rows, start=1):
            prog_grid.addWidget(QLabel(lbl), i, 0, Qt.AlignmentFlag.AlignRight)
            val = QLabel("—")
            val.setStyleSheet(f"color: {color}; font-weight: bold;")
            prog_grid.addWidget(val, i, 1, Qt.AlignmentFlag.AlignLeft)
            self._prog_vars[key] = val

        right_layout.addWidget(prog_group)

        # Preview
        preview_group = QGroupBox("Last Rendered Frame")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("No preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(150)
        self.preview_label.setStyleSheet(f"background: #181825; color: {C['subtext']};")
        preview_layout.addWidget(self.preview_label)
        btn_refresh_preview = QPushButton("Refresh Preview")
        btn_refresh_preview.clicked.connect(self._refresh_preview)
        preview_layout.addWidget(btn_refresh_preview)
        right_layout.addWidget(preview_group)

        # Open folder button (above export)
        self._btn_open_folder = QPushButton("📂  Open Output Folder")
        self._btn_open_folder.setEnabled(False)
        self._btn_open_folder.clicked.connect(self._open_output_folder)
        right_layout.addWidget(self._btn_open_folder)

         # Export / Convert
        export_group = QGroupBox("Export Video")
        export_layout = QVBoxLayout(export_group)

        # Row 1: Preview button (for Running jobs)
        preview_row = QHBoxLayout()
        self._btn_preview = QPushButton("🎬  Preview")
        self._btn_preview.setToolTip(
            "Genera un MP4 rápido con los frames renderizados hasta el momento.\n"
            "Disponible mientras el job está en ejecución (Running).\n"
            "Requiere FFmpeg instalado y disponible en el PATH del sistema."
        )
        self._btn_preview.setEnabled(False)
        self._btn_preview.clicked.connect(self._preview_video)
        preview_row.addWidget(self._btn_preview)
        preview_row.addStretch()
        export_layout.addLayout(preview_row)

        # Row 2: Preset dropdown + Convert button (for Done jobs)
        convert_row = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(preset_names())
        self._preset_combo.setMinimumWidth(200)
        self._preset_combo.setEnabled(False)
        convert_row.addWidget(self._preset_combo)

        self._btn_convert = QPushButton("🎬  Convert Video")
        self._btn_convert.setToolTip(
            "Convierte la secuencia de PNGs del job seleccionado al formato elegido.\n"
            "Requiere FFmpeg instalado y disponible en el PATH del sistema.\n"
            "El FPS se toma automáticamente del archivo .blend."
        )
        self._btn_convert.setEnabled(False)
        self._btn_convert.clicked.connect(self._convert_video)
        convert_row.addWidget(self._btn_convert)
        export_layout.addLayout(convert_row)

        # Row 3: FPS info
        fps_row = QHBoxLayout()
        self._fps_label = QLabel("FPS: —")
        self._fps_label.setStyleSheet(f"color: {C['teal']}; font-size: 9pt;")
        fps_row.addWidget(self._fps_label)
        fps_row.addStretch()
        export_layout.addLayout(fps_row)

        right_layout.addWidget(export_group)

        # Log
        log_group = QGroupBox("Job Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setSpacing(4)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        _log_vscroll = self.log_edit.verticalScrollBar()
        if _log_vscroll is not None:
            _log_vscroll.valueChanged.connect(self._on_log_scrolled)
        log_layout.addWidget(self.log_edit)

        log_btn_row = QHBoxLayout()
        self._autoscroll_btn = QPushButton("⬇ Auto-scroll: ON")
        self._autoscroll_btn.setCheckable(True)
        self._autoscroll_btn.setChecked(True)
        self._autoscroll_btn.clicked.connect(self._toggle_autoscroll)
        self._autoscroll_btn.setStyleSheet(
            f"QPushButton {{ color: {C['accent']}; }}"
            f"QPushButton:checked {{ color: {C['subtext']}; }}"
        )
        btn_clear_log = QPushButton("Clear")
        btn_clear_log.clicked.connect(self.log_edit.clear)
        log_btn_row.addWidget(self._autoscroll_btn)
        log_btn_row.addWidget(btn_clear_log)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)

        right_layout.addWidget(log_group, stretch=1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

        self.resolution_edit.textChanged.connect(self._on_form_field_changed)
        self._connect_form_dirty_tracking()
        
        # Install keyboard shortcut tracking AFTER UI is built
        self._install_keyboard_focus_tracking()

    # ------------------------------------------------------------------ helpers

    @property
    def blender_exec(self) -> str:
        return self.blender_path_edit.text().strip()

    def _job_blender_display(self, job: RenderJob) -> str:
        """Short label for queue column: profile name or blender.exe basename."""
        if job.blender_profile:
            return job.blender_profile
        base = os.path.basename(job.blender_exec or "")
        return base or "custom"

    def _populate_profile_combo(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in self._blender_profiles:
            self.profile_combo.addItem(p.name)
        self.profile_combo.addItem(CUSTOM_PROFILE_LABEL)
        self.profile_combo.blockSignals(False)
        if self._blender_profiles:
            self.profile_combo.setCurrentIndex(0)
            self._sync_blender_path_from_combo(self.profile_combo.currentText())
        else:
            self.profile_combo.setCurrentIndex(self.profile_combo.count() - 1)
            self.blender_path_edit.setText(DEFAULT_BLENDER)

    def _sync_blender_path_from_combo(self, text: str) -> None:
        if text == CUSTOM_PROFILE_LABEL:
            return
        for p in self._blender_profiles:
            if p.name == text:
                self.blender_path_edit.setText(p.path)
                return

    def _on_profile_combo_changed(self, text: str) -> None:
        self._sync_blender_path_from_combo(text)

    def _select_custom_profile_combo(self) -> None:
        idx = self.profile_combo.findText(CUSTOM_PROFILE_LABEL)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

    def _reset_blender_path(self) -> None:
        idx = self.profile_combo.findText("Default")
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
            self._sync_blender_path_from_combo("Default")
        else:
            self._select_custom_profile_combo()
            self.blender_path_edit.setText(DEFAULT_BLENDER)

    def _new_job_blender_fields(self) -> tuple[str, str]:
        """Returns (executable path, profile name or '')."""
        text = self.profile_combo.currentText()
        if text == CUSTOM_PROFILE_LABEL:
            return self.blender_path_edit.text().strip(), ""
        for p in self._blender_profiles:
            if p.name == text:
                return p.path, p.name
        return self.blender_path_edit.text().strip(), ""

    def _manage_profiles_dialog(self) -> None:
        edited = [BlenderProfile(p.name, p.path) for p in self._blender_profiles]
        dlg = QDialog(self)
        dlg.setWindowTitle("Blender Profiles")
        dlg.setMinimumWidth(520)
        layout = QVBoxLayout(dlg)

        hint = QLabel(
            "Each profile is a name and the path to blender.exe. "
            "Jobs can be associated with a profile; if you change the path here, "
            "The renders will automatically use the new path."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C['subtext']}; font-size: 9pt;")
        layout.addWidget(hint)

        list_w = QListWidget()
        layout.addWidget(list_w)

        form = QFormLayout()
        name_edit = QLineEdit()
        path_edit = QLineEdit()
        form.addRow("Name:", name_edit)

        path_row = QHBoxLayout()
        path_row.addWidget(path_edit)
        btn_browse_dlg = QPushButton("Browse…")
        path_row.addWidget(btn_browse_dlg)
        form.addRow("Executable:", path_row)
        layout.addLayout(form)

        def refresh_list(select_name: str | None = None) -> None:
            list_w.clear()
            for p in edited:
                list_w.addItem(p.name)
            if not edited:
                name_edit.clear()
                path_edit.clear()
                return
            if select_name:
                found = False
                for i in range(list_w.count()):
                    it = list_w.item(i)
                    if it is not None and it.text() == select_name:
                        list_w.setCurrentRow(i)
                        found = True
                        break
                if not found:
                    list_w.setCurrentRow(0)
            else:
                list_w.setCurrentRow(0)
            on_select()

        def on_select() -> None:
            row = list_w.currentRow()
            if row < 0 or row >= len(edited):
                return
            name_edit.setText(edited[row].name)
            path_edit.setText(edited[row].path)

        def flush_row_from_fields() -> bool:
            row = list_w.currentRow()
            if row < 0 or row >= len(edited):
                return True
            n = name_edit.text().strip()
            if not n:
                QMessageBox.warning(dlg, "Name", "The name cannot be empty.")
                return False
            for i, p in enumerate(edited):
                if i != row and p.name == n:
                    QMessageBox.warning(dlg, "Name", "A profile with that name already exists.")
                    return False
            edited[row].name = n
            edited[row].path = path_edit.text().strip() or DEFAULT_BLENDER
            list_item = list_w.item(row)
            if list_item is not None:
                list_item.setText(edited[row].name)
            return True

        list_w.currentRowChanged.connect(lambda _r: on_select())

        def browse_dlg() -> None:
            path, _ = QFileDialog.getOpenFileName(
                dlg, "Select Blender", "",
                "Executable (*.exe);;All Files (*)",
            )
            if path:
                path_edit.setText(path)

        btn_browse_dlg.clicked.connect(browse_dlg)

        btn_add = QPushButton("Add Profile")
        btn_remove = QPushButton("Remove")

        def add_profile() -> None:
            if not flush_row_from_fields():
                return
            new = BlenderProfile(f"Profile {len(edited) + 1}", DEFAULT_BLENDER)
            edited.append(new)
            refresh_list(new.name)

        def remove_profile() -> None:
            if len(edited) <= 1:
                QMessageBox.information(
                    dlg, "Info", "There must be at least one Blender profile.",
                )
                return
            row = list_w.currentRow()
            if row < 0:
                return
            edited.pop(row)
            refresh_list(edited[0].name if edited else None)

        btn_add.clicked.connect(add_profile)
        btn_remove.clicked.connect(remove_profile)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)

        refresh_list(edited[0].name if edited else None)

        def on_ok() -> None:
            if not flush_row_from_fields():
                return
            names = [p.name for p in edited]
            if len(names) != len(set(names)):
                QMessageBox.warning(dlg, "Validation", "There are duplicate profile names.")
                return
            self._blender_profiles = edited
            self._populate_profile_combo()
            save_config(self.jobs, self._blender_profiles)
            self.status_bar.showMessage("Saved Blender profiles.")
            dlg.accept()

        buttons.accepted.connect(on_ok)
        buttons.rejected.connect(dlg.reject)

        dlg.exec()

    def _selected_job(self) -> RenderJob | None:
        item = self.queue_tree.currentItem()
        if not item:
            return None
        try:
            job_id = int(item.text(0))
        except ValueError:
            return None
        return next((j for j in self.jobs if j.job_id == job_id), None)

    def _selected_jobs(self) -> list[RenderJob]:
        """Return selected jobs in visual order (top-to-bottom in queue)."""
        selected_items = self.queue_tree.selectedItems()
        if not selected_items:
            job = self._selected_job()
            return [job] if job else []

        selected_ids: set[int] = set()
        for item in selected_items:
            try:
                selected_ids.add(int(item.text(0)))
            except ValueError:
                continue

        if not selected_ids:
            return []

        ordered: list[RenderJob] = []
        for i in range(self.queue_tree.topLevelItemCount()):
            it = self.queue_tree.topLevelItem(i)
            if not it:
                continue
            try:
                jid = int(it.text(0))
            except ValueError:
                continue
            if jid in selected_ids:
                job = next((j for j in self.jobs if j.job_id == jid), None)
                if job:
                    ordered.append(job)
        return ordered

    # ------------------------------------------------------------------ Browse

    def _browse_blender(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Blender Executable", "", "Executable (*.exe);;All Files (*)"
        )
        if path:
            self._select_custom_profile_combo()
            self.blender_path_edit.setText(path)

    def _browse_blend(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select .blend File", "", "Blender Files (*.blend);;All Files (*)"
        )
        if path:
            self._prepare_form_for_new_blend(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_edit.setText(path)

    # ------------------------------------------------------------------ Blend info

    def _prepare_form_for_new_blend(self, blend_path: str) -> None:
        """Reset form to New Job mode and load the selected .blend."""
        self._loading_job_into_form = True
        try:
            self._selected_job_id = None
            self.queue_tree.clearSelection()
            self._btn_apply_to_job.setEnabled(False)

            self.blend_edit.setText(blend_path)
            self.scene_combo.blockSignals(True)
            self.scene_combo.clear()
            self.scene_combo.blockSignals(False)

            self.sequence_edit.clear()
            self.output_edit.clear()
            self.frame_start_spin.setValue(1)
            self.frame_end_spin.setValue(250)
            self.samples_edit.clear()
            self.use_nodes_btn.setChecked(False)
            self._toggle_use_nodes()
            self._samples_hint.setText("")
        finally:
            self._loading_job_into_form = False
            self._set_form_dirty(False)

        self._load_blend_info_async()

    def _load_blend_info_async(self):
        blend = self.blend_edit.text().strip()
        if not blend or not os.path.isfile(blend):
            QMessageBox.warning(self, "Warning", "Please select a valid .blend file first.")
            return
        key = f"{blend}\n{self.blender_exec}"
        if key in self._blend_info_cache:
            self._apply_blend_info(self._blend_info_cache[key])
            return
        self.status_bar.showMessage("Reading .blend file info…")
        self.scene_combo.setEnabled(False)

        self._blend_info_thread = BlendInfoThread(blend, self.blender_exec)
        self._blend_info_thread.finished.connect(
            lambda info, k=key: self._on_blend_info_ready(info, k)
        )
        # deleteLater() schedules cleanup after the thread finishes, preventing
        # "QThread destroyed while still running" crashes
        self._blend_info_thread.finished.connect(self._blend_info_thread.deleteLater)
        self._blend_info_thread.start()

    def _on_blend_info_ready(self, info: dict, cache_key: str):
        self._blend_info_cache[cache_key] = info
        self._apply_blend_info(info)

    def _on_blend_info_ready_for_form(
        self, info: dict, cache_key: str, select_scene: str, job_id: int
    ):
        self._blend_info_cache[cache_key] = info
        if self._selected_job_id != job_id:
            return
        self._apply_blend_info(info, select_scene=select_scene)

    def _apply_blend_info(self, info: dict, select_scene: str | None = None):
        scenes = info.get("scenes", ["Scene"])
        self._current_samples_map = info.get("samples", {})
        self._current_fps_map     = info.get("fps", {})
        self._current_resolution_map = info.get("resolution_pct", {})
        self.scene_combo.setEnabled(True)
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        self.scene_combo.addItems(scenes)
        if scenes:
            if select_scene:
                idx = self.scene_combo.findText(select_scene)
                if idx >= 0:
                    self.scene_combo.setCurrentIndex(idx)
                else:
                    self.scene_combo.addItem(select_scene)
                    self.scene_combo.setCurrentIndex(self.scene_combo.count() - 1)
            else:
                self.scene_combo.setCurrentIndex(0)
        self.scene_combo.blockSignals(False)
        if scenes:
            self._update_samples_hint(self.scene_combo.currentText())
        self.status_bar.showMessage(f"Found {len(scenes)} scene(s).")

    def _load_blend_info_for_job_edit(self, job: RenderJob) -> None:
        """Load scene list from disk when populating the form for a queued job."""
        blend = job.blend_file.strip()
        scene = (job.scene or "Scene").strip()
        if not blend or not os.path.isfile(blend):
            self.scene_combo.setEnabled(True)
            self.scene_combo.blockSignals(True)
            self.scene_combo.clear()
            self.scene_combo.addItem(scene or "Scene")
            self.scene_combo.setCurrentIndex(0)
            self.scene_combo.blockSignals(False)
            self._current_samples_map = {}
            self._current_fps_map     = {}
            self._update_samples_hint(self.scene_combo.currentText())
            self.status_bar.showMessage(".blend file not found; scene shown without metadata.")
            return

        bexec = resolve_blender_exec(job, self._blender_profiles)
        key = f"{blend}\n{bexec}"
        if key in self._blend_info_cache:
            self._apply_blend_info(self._blend_info_cache[key], select_scene=scene)
            return

        self.status_bar.showMessage("Reading .blend file info…")
        self.scene_combo.setEnabled(False)

        self._blend_info_thread = BlendInfoThread(blend, bexec)
        snap_scene = scene
        snap_jid = job.job_id
        self._blend_info_thread.finished.connect(
            lambda info, k=key, sc=snap_scene, jid=snap_jid: self._on_blend_info_ready_for_form(
                info, k, sc, jid
            )
        )
        self._blend_info_thread.finished.connect(self._blend_info_thread.deleteLater)
        self._blend_info_thread.start()

    def _on_scene_changed(self, scene_name: str):
        self._update_samples_hint(scene_name)
        self._update_resolution_hint(scene_name)

    def _update_samples_hint(self, scene_name: str):
        sm = getattr(self, "_current_samples_map", {})
        if scene_name in sm:
            self._samples_hint.setText(f"(scene: {sm[scene_name]})")
        else:
            self._samples_hint.setText("")
        
    def _update_resolution_hint(self, scene_name: str):
        rm = getattr(self, "_current_resolution_map", {})
        if scene_name in rm:
            self._resolution_hint.setText(f"(scene: {rm[scene_name]:.0f}%)")
        else:
            self._resolution_hint.setText("")

    # ------------------------------------------------------------------ Toggle

    def _toggle_use_nodes(self):
        on = self.use_nodes_btn.isChecked()
        if on:
            self.use_nodes_btn.setText("COMPOSITING NODES: ON")
            self.use_nodes_btn.setObjectName("nodes_on")
        else:
            self.use_nodes_btn.setText("COMPOSITING NODES: OFF")
            self.use_nodes_btn.setObjectName("nodes_off")
        self.use_nodes_btn.setStyle(self.use_nodes_btn.style())

    def _sync_blender_ui_from_job(self, job: RenderJob) -> None:
        """Match profile combo and path line edit to a queued job."""
        self.profile_combo.blockSignals(True)
        try:
            if job.blender_profile:
                idx = self.profile_combo.findText(job.blender_profile)
                if idx >= 0:
                    self.profile_combo.setCurrentIndex(idx)
                    self._sync_blender_path_from_combo(job.blender_profile)
                    return
            self._select_custom_profile_combo()
            self.blender_path_edit.setText(job.blender_exec or DEFAULT_BLENDER)
        finally:
            self.profile_combo.blockSignals(False)

    def _load_job_into_form(self, job: RenderJob) -> None:
        """Fill the add-job form from a queued job (selection changed)."""
        self._loading_job_into_form = True
        try:
            self.blend_edit.setText(job.blend_file)
            self._sync_blender_ui_from_job(job)
            self.sequence_edit.setText(job.sequence_name)
            self.output_edit.setText(job.output_path)
            self.frame_start_spin.setValue(job.frame_start)
            self.frame_end_spin.setValue(job.frame_end)
            if job.samples_override is not None:
                self.samples_edit.setText(str(job.samples_override))
            else:
                self.samples_edit.clear()
            if job.resolution_pct is not None:
                self.resolution_edit.setText(f"{job.resolution_pct:.1f}")
            else:
                self.resolution_edit.clear()
            self.use_nodes_btn.setChecked(job.use_nodes)
            self._toggle_use_nodes()
            self._load_blend_info_for_job_edit(job)
        finally:
            self._loading_job_into_form = False
            self._set_form_dirty(False)

    def _read_job_form(self) -> tuple[dict | None, str | None]:
        """Validate form fields for add / apply. Returns (payload, error_en)."""
        blend = self.blend_edit.text().strip()
        scene = self.scene_combo.currentText().strip()
        seq = self.sequence_edit.text().strip()
        output = self.output_edit.text().strip()
        fs = self.frame_start_spin.value()
        fe = self.frame_end_spin.value()

        if not blend or not os.path.isfile(blend):
            return None, "Please select a valid .blend file."
        if not scene:
            return None, "Please select a scene."
        if not output:
            return None, "Please select an output directory."
        if fs > fe:
            return None, "Frame start must be ≤ frame end."

        samples_override: int | None = None
        raw = self.samples_edit.text().strip()
        if raw:
            try:
                samples_override = int(raw)
                if samples_override < 1:
                    raise ValueError
            except ValueError:
                return None, "Samples must be a positive integer (or leave empty)."

        bpath, bprof = self._new_job_blender_fields()
        if not bpath:
            return None, "Select a valid Blender path."
        if not os.path.isfile(bpath):
            return None, f"Blender executable was not found:\n{bpath}"

        resolution_pct: float | None = None
        raw_res = self.resolution_edit.text().strip()
        if raw_res:
            try:
                resolution_pct = float(raw_res)
                if not 0 <= resolution_pct <= 100:
                    raise ValueError
            except ValueError:
                return None, "Resolution % must be 0-100 (or leave empty for scene default)."

        return {
            "blend_file": blend,
            "scene": scene,
            "sequence_name": seq,
            "output_path": output,
            "frame_start": fs,
            "frame_end": fe,
            "samples_override": samples_override,
            "resolution_pct": resolution_pct,
            "blender_exec": bpath,
            "blender_profile": bprof,
            "use_nodes": self.use_nodes_btn.isChecked(),
        }, None

    # ------------------------------------------------------------------ IPC

    def _start_ipc_server(self) -> None:
        def _on_message(msg: dict) -> dict:
            action = (msg or {}).get("action")
            if action != "add_job":
                return {"ok": False, "error": "Unsupported action"}
            payload = (msg or {}).get("payload")
            if not isinstance(payload, dict):
                return {"ok": False, "error": "Missing payload object"}
            self._ipc_queue.put(payload)
            return {"ok": True, "queued": True}

        try:
            self._ipc_server = JuiceIPCServer(host="127.0.0.1", port=8765, on_message=_on_message)
            self._ipc_server.start()
            self.status_bar.showMessage("IPC listener activo en 127.0.0.1:8765", 2500)
        except Exception as e:
            self._ipc_server = None
            self.status_bar.showMessage(f"Could not start IPC: {e}", 5000)

    def _drain_ipc_queue(self) -> None:
        while True:
            try:
                payload = self._ipc_queue.get_nowait()
            except queue.Empty:
                return
            self._add_job_from_ipc_payload(payload)

    def _validate_ipc_payload(self, payload: dict) -> tuple[dict | None, str | None]:
        blend = str(payload.get("blend_file", "")).strip()
        scene = str(payload.get("scene", "Scene")).strip() or "Scene"

        if not blend or not os.path.isfile(blend):
            return None, "blend_file is invalid or does not exist."

        try:
            fs = int(payload.get("frame_start", 1))
            fe = int(payload.get("frame_end", 250))
        except Exception:
            return None, "frame_start/frame_end must be integers."

        if fs > fe:
            return None, "frame_start must be <= frame_end."

        samples_raw = payload.get("samples")
        samples_override = None
        if samples_raw is not None:
            try:
                samples_override = int(samples_raw)
                if samples_override < 1:
                    raise ValueError
            except Exception:
                return None, "samples must be a positive integer."

        res_raw = payload.get("resolution_pct")
        resolution_pct = None
        if res_raw is not None:
            try:
                resolution_pct = float(res_raw)
                if not 0 <= resolution_pct <= 100:
                    raise ValueError
            except Exception:
                return None, "resolution_pct must be between 0 and 100."

        use_nodes = bool(payload.get("use_nodes", False))
        seq_name = str(payload.get("sequence_name", "")).strip()

        bpath, bprof = self._new_job_blender_fields()
        if not bpath or not os.path.isfile(bpath):
            bpath = DEFAULT_BLENDER
            bprof = ""

        out_base = str(payload.get("output_path", "")).strip()
        if not out_base:
            out_base = os.path.join(os.path.dirname(blend), "brm_renders")

        return {
            "blend_file": blend,
            "scene": scene,
            "sequence_name": seq_name,
            "output_path": out_base,
            "frame_start": fs,
            "frame_end": fe,
            "samples_override": samples_override,
            "resolution_pct": resolution_pct,
            "blender_exec": bpath,
            "blender_profile": bprof,
            "use_nodes": use_nodes,
        }, None

    def _job_exists_equivalent(self, d: dict) -> bool:
        for j in self.jobs:
            if (
                os.path.normcase(j.blend_file) == os.path.normcase(d["blend_file"])
                and j.scene == d["scene"]
                and j.frame_start == d["frame_start"]
                and j.frame_end == d["frame_end"]
                and j.samples_override == d["samples_override"]
                and j.resolution_pct == d["resolution_pct"]
                and j.use_nodes == d["use_nodes"]
                and os.path.normcase(j.output_path) == os.path.normcase(d["output_path"])
            ):
                return True
        return False

    def _add_job_from_ipc_payload(self, payload: dict) -> None:
        data, err = self._validate_ipc_payload(payload)
        if err or not data:
            self.status_bar.showMessage(f"IPC discarded: {err}", 5000)
            return

        if self._job_exists_equivalent(data):
            self.status_bar.showMessage("IPC: duplicate job ignored.", 3500)
            return

        job = RenderJob(
            blend_file=data["blend_file"],
            scene=data["scene"],
            sequence_name=data["sequence_name"],
            frame_start=data["frame_start"],
            frame_end=data["frame_end"],
            output_path=data["output_path"],
            blender_exec=data["blender_exec"],
            blender_profile=data["blender_profile"],
            use_nodes=data["use_nodes"],
            samples_override=data["samples_override"],
            resolution_pct=data["resolution_pct"],
        )
        self.jobs.append(job)
        selected_ids, current_id = self._selection_snapshot()
        self._refresh_tree(selected_ids=selected_ids, current_id=current_id)
        self._auto_save_queue()
        self.status_bar.showMessage(
            f"IPC: Job #{job.job_id} added ({os.path.basename(job.blend_file)} / {job.scene}).",
            5000,
        )

    # ------------------------------------------------------------------ Add job

    def _connect_form_dirty_tracking(self) -> None:
        self.blend_edit.textChanged.connect(self._on_form_field_changed)
        self.blender_path_edit.textChanged.connect(self._on_form_field_changed)
        self.profile_combo.currentTextChanged.connect(self._on_form_field_changed)
        self.scene_combo.currentTextChanged.connect(self._on_form_field_changed)
        self.sequence_edit.textChanged.connect(self._on_form_field_changed)
        self.output_edit.textChanged.connect(self._on_form_field_changed)
        self.frame_start_spin.valueChanged.connect(self._on_form_field_changed)
        self.frame_end_spin.valueChanged.connect(self._on_form_field_changed)
        self.samples_edit.textChanged.connect(self._on_form_field_changed)
        self.resolution_edit.textChanged.connect(self._on_form_field_changed)
        self.use_nodes_btn.toggled.connect(self._on_form_field_changed)

    def _on_form_field_changed(self, *_args) -> None:
        if getattr(self, "_loading_job_into_form", False):
            return
        if getattr(self, "_selected_job_id", None) is None:
            self._set_form_dirty(False)
            return
        self._set_form_dirty(True)

    def _set_form_dirty(self, dirty: bool) -> None:
        self._form_dirty = bool(dirty)
        self._update_apply_button_style()

    def _update_apply_button_style(self) -> None:
        if not hasattr(self, "_btn_apply_to_job"):
            return
        if self._form_dirty:
            self._btn_apply_to_job.setStyleSheet(
                f"QPushButton {{ background-color: {C['red']}; color: {C['bg']}; font-weight: bold; }}"
                f"QPushButton:hover {{ background-color: {C['peach']}; color: {C['bg']}; }}"
            )
        else:
            self._btn_apply_to_job.setStyleSheet("")

    def _add_job(self):
        data, err = self._read_job_form()
        if err:
            QMessageBox.critical(self, "Error", err)
            return
        if not data:
            return

        job = RenderJob(
            blend_file=data["blend_file"],
            scene=data["scene"],
            sequence_name=data["sequence_name"],
            frame_start=data["frame_start"],
            frame_end=data["frame_end"],
            output_path=data["output_path"],
            blender_exec=data["blender_exec"],
            blender_profile=data["blender_profile"],
            use_nodes=data["use_nodes"],
            samples_override=data["samples_override"],
            resolution_pct=data.get("resolution_pct"),
        )
        self.jobs.append(job)
        self._refresh_tree()
        self._auto_save_queue()
        so = data["samples_override"]
        self.status_bar.showMessage(
            f"Job #{job.job_id} added — "
            f"Nodes: {'ON' if job.use_nodes else 'OFF'} | "
            f"Samples: {so or 'scene default'}"
        )

    def _apply_changes_to_selected_job(self) -> None:
        job = self._selected_job()
        if not job:
            QMessageBox.information(self, "Info", "Select a job in the queue.")
            return
        if job.status == RenderJob.STATUS_RUNNING:
            QMessageBox.warning(
                self, "No editable",
                "This job is running. Cancel it before editing its settings.",
            )
            return

        # Store selection ID before refresh
        old_selected_id = self._selected_job_id

        data, err = self._read_job_form()
        if err:
            QMessageBox.critical(self, "Error", err)
            return
        if not data:
            return

        job.blend_file      = data["blend_file"]
        job.scene           = data["scene"]
        job.sequence_name   = data["sequence_name"]
        job.frame_start     = data["frame_start"]
        job.frame_end       = data["frame_end"]
        job.output_path     = data["output_path"]
        job.blender_exec    = data["blender_exec"]
        job.blender_profile = data["blender_profile"]
        job.use_nodes       = data["use_nodes"]
        job.samples_override = data["samples_override"]
        job.resolution_pct  = data.get("resolution_pct")

        self._refresh_tree()
        self._auto_save_queue()

        # Explicitly preserve selection and refresh UI
        self.queue_tree.blockSignals(True)
        try:
            # Re-select the item
            selected_item = None
            for i in range(self.queue_tree.topLevelItemCount()):
                item = self.queue_tree.topLevelItem(i)
                if item and int(item.text(0)) == old_selected_id:
                    selected_item = item
                    self.queue_tree.setCurrentItem(item)
                    self.queue_tree.scrollToItem(item)
                    break

            # Reload form and right panel for updated job
            new_job = self._selected_job()
            if new_job and new_job.job_id == old_selected_id:
                self._selected_job_id = old_selected_id
                self._btn_apply_to_job.setEnabled(new_job.status != RenderJob.STATUS_RUNNING)
                self._load_job_into_form(new_job)
                self._update_progress_ui(new_job)
                self._load_preview(new_job.effective_output_path)
                self._update_export_ui(new_job)
                self._update_folder_btn(new_job)
                
                # Refresh log
                self.log_edit.clear()
                for line in new_job.log_lines:
                    self._append_log_line(line)
                if self._log_autoscroll:
                    self._scroll_log_to_bottom()
            else:
                # Job disappeared (unlikely) - clear selection
                self._selected_job_id = None
                self._btn_apply_to_job.setEnabled(False)
                self._clear_progress_ui()
                self.log_edit.clear()
        finally:
            self.queue_tree.blockSignals(False)
            self._set_form_dirty(False)

        self.status_bar.showMessage(f"Job #{old_selected_id} updated and selection preserved ✓")

    # ------------------------------------------------------------------ Remove

    def _remove_selected(self):
        jobs = self._selected_jobs()
        if not jobs:
            return

        running = [j for j in jobs if j.status == RenderJob.STATUS_RUNNING]
        if running:
            QMessageBox.warning(
                self, "Warning",
                "Hay jobs en ejecución dentro de la selección.\n"
                "Cancelalos antes de eliminarlos."
            )
            return

        if len(jobs) == 1:
            j = jobs[0]
            msg = (
                f"¿Eliminar Job #{j.job_id} ({os.path.basename(j.blend_file)})?\n"
                "Esta acción no se puede deshacer."
            )
        else:
            ids = ", ".join(f"#{j.job_id}" for j in jobs)
            msg = (
                f"¿Eliminar {len(jobs)} jobs seleccionados?\n"
                f"{ids}\n\n"
                "Esta acción no se puede deshacer."
            )

        answer = QMessageBox.question(
            self, "Confirmar eliminación",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        removed_ids = {j.job_id for j in jobs}
        self.jobs = [j for j in self.jobs if j.job_id not in removed_ids]

        if self._selected_job_id in removed_ids:
            self._selected_job_id = None
            self.log_edit.clear()
            self._clear_progress_ui()
            self._btn_apply_to_job.setEnabled(False)

        self._refresh_tree()
        self._auto_save_queue()
        self.status_bar.showMessage(f"{len(removed_ids)} job(s) eliminado(s).")

    # ------------------------------------------------------------------ Render control

    def _start_selected(self):
        selected = self._selected_jobs()
        pending_jobs = [j for j in selected if j.status == RenderJob.STATUS_PENDING]
        if not pending_jobs:
            QMessageBox.information(
                self, "Info",
                "Ningún job seleccionado está en estado Pending."
            )
            return

        # Track this specific selected batch so we can play the finish sound
        # when all selected jobs complete (Done/Error/Cancelled), even if other
        # queue jobs remain Pending.
        self._sequential_target_ids = {j.job_id for j in pending_jobs}

        if self._simul_checkbox.isChecked():
            for job in pending_jobs:
                self._start_job(job)
            return

        self._enqueue_sequential_jobs([j.job_id for j in pending_jobs])

    def _start_all_pending(self):
        pending_jobs = [j for j in self.jobs if j.status == RenderJob.STATUS_PENDING]
        if not pending_jobs:
            QMessageBox.information(self, "Info", "No pending jobs in the queue.")
            return

        if self._simul_checkbox.isChecked():
            for job in pending_jobs:
                self._start_job(job)
            return

        self._enqueue_sequential_jobs([j.job_id for j in pending_jobs])

    def _start_job(self, job: RenderJob):
        if job.status == RenderJob.STATUS_RUNNING:
            return

        signals = WorkerSignals()
        signals.log_line.connect(self._on_log_line)
        signals.progress.connect(self._on_progress_update)
        signals.frame_saved.connect(self._on_frame_saved)
        signals.done.connect(self._on_job_done)

        resolved = resolve_blender_exec(job, self._blender_profiles)
        thread = RenderThread(job, signals, blender_executable=resolved)
        self.threads[job.job_id] = thread
        self.signals[job.job_id] = signals

        # Clean up thread reference and schedule Qt destruction when done
        thread.finished.connect(lambda jid=job.job_id: self.threads.pop(jid, None))
        thread.finished.connect(thread.deleteLater)

        thread.start()
        self._refresh_tree()
        if self._selected_job_id == job.job_id:
            self._btn_apply_to_job.setEnabled(False)
        self.status_bar.showMessage(f"Job #{job.job_id} started.")

    def _enqueue_sequential_jobs(self, job_ids: list[int]) -> None:
        if any(j.status == RenderJob.STATUS_RUNNING for j in self.jobs):
            QMessageBox.information(
                self,
                "Info",
                "Ya hay un job en ejecución. Se encolaron los seleccionados para correr al terminar."
            )

        existing = set(self._sequential_queue)
        added = 0
        for jid in job_ids:
            if jid in existing:
                continue
            job = next((j for j in self.jobs if j.job_id == jid), None)
            if not job or job.status != RenderJob.STATUS_PENDING:
                continue
            self._sequential_queue.append(jid)
            existing.add(jid)
            added += 1

        if added == 0:
            QMessageBox.information(
                self, "Info",
                "No hay jobs Pending nuevos para encolar."
            )
            return

        self.status_bar.showMessage(f"Encolados {added} job(s) en modo secuencial.")
        self._start_next_queued_job()

    def _start_next_queued_job(self) -> None:
        if any(j.status == RenderJob.STATUS_RUNNING for j in self.jobs):
            return

        while self._sequential_queue:
            jid = self._sequential_queue.pop(0)
            job = next((j for j in self.jobs if j.job_id == jid), None)
            if not job:
                continue
            if job.status != RenderJob.STATUS_PENDING:
                continue
            self._start_job(job)
            return

    def _cancel_selected(self):
        jobs = self._selected_jobs()
        if not jobs:
            return

        running = [j for j in jobs if j.status == RenderJob.STATUS_RUNNING]
        if not running:
            QMessageBox.information(self, "Info", "No hay jobs seleccionados en estado Running.")
            return

        selected_ids, current_id = self._selection_snapshot()

        for job in running:
            if job.process:
                job.process.terminate()
            job.status = RenderJob.STATUS_CANCELLED

        self._refresh_tree(selected_ids=selected_ids, current_id=current_id)

        if self._selected_job_id in {j.job_id for j in running}:
            self._btn_apply_to_job.setEnabled(True)

        self.status_bar.showMessage(f"{len(running)} job(s) cancelado(s).")

    # ------------------------------------------------------------------ Signals from threads

    def _on_log_line(self, job_id: int, line: str):
        # Parse device confirmation line for the progress panel
        if job_id == self._selected_job_id:
            self._append_log_line(line)
        # Parse GPU device line
        if "[BRM] cycles.device" in line:
            device = line.split("=", 1)[-1].strip()
            job = next((j for j in self.jobs if j.job_id == job_id), None)
            if job:
                job._detected_device = device

    def _on_progress_update(self, job_id: int):
        job = next((j for j in self.jobs if j.job_id == job_id), None)
        if not job:
            return
        self._update_tree_item(job)
        if job_id == self._selected_job_id:
            self._update_progress_ui(job)

    def _on_frame_saved(self, job_id: int):
        job = next((j for j in self.jobs if j.job_id == job_id), None)
        if job and job_id == self._selected_job_id:
            self._load_preview(job.effective_output_path)

    def _on_job_done(self, job_id: int, status: str):
        job = next((j for j in self.jobs if j.job_id == job_id), None)
        if not job:
            return
        job._is_paused = False
        self._btn_pause.setText("⏸  Pause")
        self._update_tree_item(job)
        if job_id == self._selected_job_id:
            self._update_progress_ui(job)
            self._load_preview(job.effective_output_path)
            self._update_export_ui(job)
            self._update_folder_btn(job)
            self._btn_apply_to_job.setEnabled(job.status != RenderJob.STATUS_RUNNING)
        self.status_bar.showMessage(f"Job #{job_id} finished: {status}")
        self._auto_save_queue()

        self._start_next_queued_job()
        self._update_simultaneous_checkbox_enabled()

        # If START SELECTED was used, play sound when that selected batch finishes
        # (all target jobs are no longer Running/Pending), even if other jobs remain.
        if self._sequential_target_ids:
            targets = [j for j in self.jobs if j.job_id in self._sequential_target_ids]
            selected_active = [
                j for j in targets
                if j.status in (RenderJob.STATUS_RUNNING, RenderJob.STATUS_PENDING)
            ]
            if not selected_active:
                self.status_bar.showMessage("🎉 Jobs seleccionados finalizados — reproduciendo sonido…")
                self._play_queue_done_sound()
                self._sequential_target_ids.clear()

        # Existing behavior: when entire queue is finished, also play sound.
        active = [j for j in self.jobs
                  if j.status in (RenderJob.STATUS_RUNNING, RenderJob.STATUS_PENDING)]
        if not active and not self._sequential_queue:
            self.status_bar.showMessage("🎉 Cola completa — reproduciendo sonido…")
            self._play_queue_done_sound()

    # ------------------------------------------------------------------ Timer

    def _tick_timers(self):
        for job in self.jobs:
            if job.status == RenderJob.STATUS_RUNNING and job.start_time:
                job.elapsed_seconds = time.monotonic() - job.start_time
                if job.job_id == self._selected_job_id:
                    self._update_progress_ui(job)

    # ------------------------------------------------------------------ Tree

    def _selection_snapshot(self) -> tuple[set[int], int | None]:
        selected_ids: set[int] = set()
        for item in self.queue_tree.selectedItems():
            try:
                selected_ids.add(int(item.text(0)))
            except (ValueError, RuntimeError):
                continue

        current_id: int | None = None
        current = self.queue_tree.currentItem()
        if current:
            try:
                current_id = int(current.text(0))
            except (ValueError, RuntimeError):
                current_id = None

        if current_id is None:
            current_id = self._selected_job_id

        return selected_ids, current_id

    def _refresh_tree(self, selected_ids: set[int] | None = None, current_id: int | None = None):
        self.queue_tree.setUpdatesEnabled(False)
        self.queue_tree.blockSignals(True)
        self.queue_tree.clear()

        id_to_item: dict[int, QTreeWidgetItem] = {}

        for job in self.jobs:
            blend_short  = os.path.basename(job.blend_file)
            out_short    = ("…" + job.output_path[-17:]) if len(job.output_path) > 20 else job.output_path
            frame_str    = str(job.current_frame) if job.current_frame is not None else "—"
            samples_str  = str(job.samples_override) if job.samples_override else "def"
            res_str      = f"{job.resolution_pct:.0f}" if job.resolution_pct is not None else "def"
            blender_str  = self._job_blender_display(job)
            item = QTreeWidgetItem([
                str(job.job_id),
                blend_short,
                job.scene,
                blender_str,
                samples_str,
                res_str,
                job.sequence_name or "—",
                f"{job.frame_start}–{job.frame_end}",
                out_short,
                job.status,
                f"{job.progress}%",
                frame_str,
            ])
            id_to_item[job.job_id] = item
            item.setToolTip(1, job.blend_file)
            item.setToolTip(8, job.effective_output_path)
            color = QColor(STATUS_COLOR.get(job.status, C["text"]))
            item.setForeground(9, color)
            self.queue_tree.addTopLevelItem(item)

            combo = QComboBox(self.queue_tree)
            for p in self._blender_profiles:
                combo.addItem(p.name)
            combo.addItem(CUSTOM_PROFILE_LABEL)

            current = job.blender_profile if job.blender_profile else CUSTOM_PROFILE_LABEL
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentTextChanged.connect(
                lambda text, jid=job.job_id: self._on_table_blender_changed(jid, text)
            )
            self.queue_tree.setItemWidget(item, 3, combo)

        restore_ids = selected_ids if selected_ids is not None else set()
        restore_current = current_id if current_id is not None else self._selected_job_id

        for jid in restore_ids:
            it = id_to_item.get(jid)
            if it:
                it.setSelected(True)

        current_item = id_to_item.get(restore_current) if restore_current is not None else None
        if current_item is None and restore_ids:
            first_id = next(iter(restore_ids))
            current_item = id_to_item.get(first_id)

        if current_item is not None:
            self.queue_tree.setCurrentItem(current_item)
            try:
                self._selected_job_id = int(current_item.text(0))
            except (ValueError, RuntimeError):
                pass
        else:
            self._selected_job_id = None

        self.queue_tree.blockSignals(False)
        self.queue_tree.setUpdatesEnabled(True)

        self._update_simultaneous_checkbox_enabled()

    def _update_simultaneous_checkbox_enabled(self) -> None:
        has_running = any(j.status == RenderJob.STATUS_RUNNING for j in self.jobs)
        self._simul_checkbox.setEnabled(not has_running)

    def _update_tree_item(self, job: RenderJob):
        """Update a single row without rebuilding the whole tree."""
        frame_str = str(job.current_frame) if job.current_frame is not None else "—"
        for i in range(self.queue_tree.topLevelItemCount()):
            item = self.queue_tree.topLevelItem(i)
            if item and int(item.text(0)) == job.job_id:
                item.setText(9, job.status)
                item.setText(10, f"{job.progress}%")
                item.setText(11, frame_str)
                item.setToolTip(1, job.blend_file)
                item.setToolTip(8, job.effective_output_path)
                item.setForeground(9, QColor(STATUS_COLOR.get(job.status, C["text"])))
                return

    def _on_table_blender_changed(self, job_id: int, profile_name: str):
        job = next((j for j in self.jobs if j.job_id == job_id), None)
        if not job:
            return

        if profile_name == CUSTOM_PROFILE_LABEL:
            job.blender_profile = ""
            # conserva job.blender_exec actual en modo custom
        else:
            match = next((p for p in self._blender_profiles if p.name == profile_name), None)
            if not match:
                return
            job.blender_profile = match.name
            job.blender_exec = match.path

        self._refresh_tree()

        if self._selected_job_id == job.job_id:
            self._sync_blender_ui_from_job(job)
            self._update_export_ui(job)
            self._update_folder_btn(job)

        save_config(self.jobs, self._blender_profiles)
        self.status_bar.showMessage(
            f"Job #{job.job_id} actualizado desde selector Blender ({profile_name})."
        )

    def _update_pause_button_for_selection(self) -> None:
        selected_items = self.queue_tree.selectedItems()
        has_paused = False

        if selected_items:
            selected_ids: set[int] = set()
            for item in selected_items:
                try:
                    selected_ids.add(int(item.text(0)))
                except ValueError:
                    continue
            has_paused = any(
                j.job_id in selected_ids and j.status == RenderJob.STATUS_PAUSED
                for j in self.jobs
            )
        else:
            job = self._selected_job()
            has_paused = bool(job and job.status == RenderJob.STATUS_PAUSED)

        if has_paused:
            self._btn_pause.setText("▶  Resume")
        else:
            self._btn_pause.setText("⏸  Pause")

    def _on_job_select(self, current: QTreeWidgetItem | None, prev):
        if not current:
            self._selected_job_id = None
            self._btn_apply_to_job.setEnabled(False)
            self._set_form_dirty(False)
            self._btn_pause.setText("⏸  Pause")
            return

        try:
            new_job_id = int(current.text(0))
        except (ValueError, RuntimeError):
            return

        # Update Pause/Resume immediately from the newly selected item
        current_status = current.text(9)
        if current_status == RenderJob.STATUS_PAUSED:
            self._btn_pause.setText("▶  Resume")
        else:
            self._btn_pause.setText("⏸  Pause")

        prev_job_id = None
        if prev is not None:
            try:
                prev_job_id = int(prev.text(0))
            except (ValueError, RuntimeError):
                prev_job_id = None

        def _select_job_id_safely(target_job_id: int | None) -> None:
            if target_job_id is None:
                return
            self.queue_tree.blockSignals(True)
            try:
                for i in range(self.queue_tree.topLevelItemCount()):
                    it = self.queue_tree.topLevelItem(i)
                    if not it:
                        continue
                    try:
                        if int(it.text(0)) == target_job_id:
                            self.queue_tree.setCurrentItem(it)
                            break
                    except (ValueError, RuntimeError):
                        continue
            finally:
                self.queue_tree.blockSignals(False)

        if (
            self._form_dirty
            and self._selected_job_id is not None
            and new_job_id != self._selected_job_id
        ):
            origin_job_id = self._selected_job_id
            answer = QMessageBox.question(
                self,
                "Cambios pendientes",
                "Hay cambios sin aplicar en el formulario.\n\n"
                "¿Deseas aplicarlos al job actualmente seleccionado antes de cambiar?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )

            if answer == QMessageBox.StandardButton.Cancel:
                _select_job_id_safely(prev_job_id)
                return

            if answer == QMessageBox.StandardButton.Yes:
                _select_job_id_safely(origin_job_id)
                self._selected_job_id = origin_job_id
                self._apply_changes_to_selected_job()
                if self._form_dirty:
                    _select_job_id_safely(prev_job_id)
                    return
                _select_job_id_safely(new_job_id)
            else:
                self._set_form_dirty(False)

        job_id = new_job_id
        job = next((j for j in self.jobs if j.job_id == job_id), None)
        if not job:
            return
        self._selected_job_id = job_id
        self._btn_apply_to_job.setEnabled(job.status != RenderJob.STATUS_RUNNING)

        self.log_edit.clear()
        for line in job.log_lines:
            self._append_log_line(line)
        if self._log_autoscroll:
            self._scroll_log_to_bottom()

        self._update_progress_ui(job)
        self._load_preview(job.effective_output_path)
        self._update_export_ui(job)
        self._update_folder_btn(job)
        self._load_job_into_form(job)

    # ------------------------------------------------------------------ Progress UI

    def _update_progress_ui(self, job: RenderJob):
        self.progress_bar.setValue(job.progress)

        if job.current_frame is not None:
            self._prog_vars["current_frame"].setText(
                f"{job.current_frame}  ({job.progress}%)"
            )
        elif job.status == RenderJob.STATUS_DONE:
            self._prog_vars["current_frame"].setText("✓ Done")
        elif job.status == RenderJob.STATUS_ERROR:
            self._prog_vars["current_frame"].setText("✗ Error")
        else:
            self._prog_vars["current_frame"].setText("—")

        self._prog_vars["elapsed"].setText(
            fmt_duration(job.elapsed_seconds) if job.elapsed_seconds else "—"
        )
        self._prog_vars["eta"].setText(
            fmt_duration(job.eta_seconds) if job.eta_seconds is not None else "—"
        )
        if job.last_frame_elapsed is not None:
            self._prog_vars["frame_time"].setText(f"{job.last_frame_elapsed:.1f} s")
        else:
            self._prog_vars["frame_time"].setText("—")

        if job.status in (RenderJob.STATUS_RUNNING, RenderJob.STATUS_DONE):
            done = max(0, (job.current_frame or job.frame_start) - job.frame_start)
            self._prog_vars["frames_done"].setText(f"{done} / {job.total_frames}")
        else:
            self._prog_vars["frames_done"].setText("—")

        self._prog_vars["samples"].setText(
            str(job.samples_override) if job.samples_override else "scene default"
        )
        self._prog_vars["device"].setText(job._detected_device or "—")

    def _clear_progress_ui(self):
        self.progress_bar.setValue(0)
        for v in self._prog_vars.values():
            v.setText("—")

    # ------------------------------------------------------------------ Preview

    def _load_preview(self, output_path: str):
        if not output_path or not os.path.isdir(output_path):
            self.preview_label.setText("No preview available")
            return
        extensions = (".png", ".jpg", ".jpeg", ".tiff", ".tga", ".bmp")
        candidates = [
            (os.path.getmtime(os.path.join(output_path, f)), os.path.join(output_path, f))
            for f in os.listdir(output_path)
            if f.lower().endswith(extensions)
        ]
        if not candidates:
            self.preview_label.setText("No frames rendered yet")
            return
        img_path = max(candidates)[1]
        try:
            pixmap = QPixmap(img_path)
            if pixmap.isNull():
                # Try via Pillow for EXR etc.
                from PIL import Image
                import io
                img = Image.open(img_path).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                pixmap.loadFromData(buf.read())
            scaled = pixmap.scaled(
                380, 200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
        except Exception as e:
            self.preview_label.setText(f"Preview error: {e}")

    def _refresh_preview(self):
        job = self._selected_job()
        if job:
            self._load_preview(job.effective_output_path)
        else:
            self.preview_label.setText("No job selected")

    # ------------------------------------------------------------------ Log autoscroll

    def _scroll_log_to_bottom(self) -> None:
        sb = self.log_edit.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def _toggle_autoscroll(self):
        self._log_autoscroll = self._autoscroll_btn.isChecked()
        label = "⬇ Auto-scroll: ON" if self._log_autoscroll else "⏸ Auto-scroll: OFF"
        self._autoscroll_btn.setText(label)
        if self._log_autoscroll:
            self._scroll_log_to_bottom()

    def _on_log_scrolled(self, value: int):
        # If user scrolls away from bottom, pause autoscroll
        sb = self.log_edit.verticalScrollBar()
        if sb is None:
            return
        if value < sb.maximum() - 20 and self._log_autoscroll:
            self._log_autoscroll = False
            self._autoscroll_btn.setChecked(False)
            self._autoscroll_btn.setText("⏸ Auto-scroll: OFF")

    # ------------------------------------------------------------------ Pause / Resume

    def _toggle_pause_selected(self):
        """Pause Running jobs and Resume Paused jobs in current selection."""
        jobs = self._selected_jobs()
        if not jobs:
            return

        paused_count = 0
        resumed_count = 0

        try:
            PROCESS_ALL_ACCESS = 0x1F0FFF
            for job in jobs:
                if job.status not in (RenderJob.STATUS_RUNNING, RenderJob.STATUS_PAUSED):
                    continue
                if not job.process or job.process.pid is None:
                    continue

                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_ALL_ACCESS, False, job.process.pid
                )
                if not handle:
                    continue

                try:
                    if job.status == RenderJob.STATUS_PAUSED:
                        ctypes.windll.ntdll.NtResumeProcess(handle)
                        job._is_paused = False
                        job.status = RenderJob.STATUS_RUNNING
                        resumed_count += 1
                    else:
                        ctypes.windll.ntdll.NtSuspendProcess(handle)
                        job._is_paused = True
                        job.status = RenderJob.STATUS_PAUSED
                        paused_count += 1
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)

                self._update_tree_item(job)

            self._update_pause_button_for_selection()

            if paused_count == 0 and resumed_count == 0:
                QMessageBox.information(
                    self, "Info",
                    "No hay jobs Running/Paused válidos en la selección."
                )
                return

            self.status_bar.showMessage(
                f"Pause/Resume aplicado — pausados: {paused_count}, reanudados: {resumed_count}."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error al pausar/reanudar", str(e))

    # ------------------------------------------------------------------ Move Up / Down

    def _move_job_up(self):
        job = self._selected_job()
        if not job:
            return
        idx = self.jobs.index(job)
        if idx > 0:
            self.jobs[idx], self.jobs[idx - 1] = self.jobs[idx - 1], self.jobs[idx]
            self._refresh_tree()

    def _move_job_down(self):
        job = self._selected_job()
        if not job:
            return
        idx = self.jobs.index(job)
        if idx < len(self.jobs) - 1:
            self.jobs[idx], self.jobs[idx + 1] = self.jobs[idx + 1], self.jobs[idx]
            self._refresh_tree()

    # ------------------------------------------------------------------ Retry / Duplicate

    def _retry_selected(self):
        jobs = self._selected_jobs()
        if not jobs:
            return

        invalid = [
            j for j in jobs
            if j.status not in (RenderJob.STATUS_ERROR, RenderJob.STATUS_CANCELLED)
        ]
        if invalid:
            QMessageBox.information(
                self, "Info",
                "Solo se pueden reintentar jobs en estado Error o Cancelado.\n"
                "La selección incluye jobs no válidos."
            )
            return

        for job in jobs:
            job.status           = RenderJob.STATUS_PENDING
            job.progress         = 0
            job.current_frame    = None
            job.log_lines        = []
            job.elapsed_seconds  = 0.0
            job.eta_seconds      = None
            job.last_frame_elapsed = None
            job._is_paused       = False
            job._detected_device = None

        self._refresh_tree()
        self._auto_save_queue()

        if self._selected_job_id in {j.job_id for j in jobs}:
            self.log_edit.clear()
            self._clear_progress_ui()
            sel = self._selected_job()
            if sel:
                self._update_export_ui(sel)
                self._update_folder_btn(sel)
            self._btn_apply_to_job.setEnabled(True)

        self.status_bar.showMessage(f"{len(jobs)} job(s) reseteado(s) a Pending.")

    def _duplicate_selected(self):
        jobs = self._selected_jobs()
        if not jobs:
            return

        created: list[RenderJob] = []
        for job in jobs:
            new_job = RenderJob(
                blend_file=job.blend_file,
                scene=job.scene,
                sequence_name=job.sequence_name,
                frame_start=job.frame_start,
                frame_end=job.frame_end,
                output_path=job.output_path,
                blender_exec=job.blender_exec,
                blender_profile=job.blender_profile,
                use_nodes=job.use_nodes,
                samples_override=job.samples_override,
            )
            self.jobs.append(new_job)
            created.append(new_job)

        self._refresh_tree()
        self._auto_save_queue()
        self.status_bar.showMessage(f"{len(created)} job(s) duplicado(s).")

    def _install_keyboard_focus_tracking(self):
        """Install event filters on form widgets to track focus context."""
        from PyQt6.QtCore import QEvent
        widgets_to_track = [
            self.blend_edit, self.scene_combo, self.sequence_edit,
            self.output_edit, self.samples_edit, self.resolution_edit,
            self.frame_start_spin, self.frame_end_spin,
            self.blender_path_edit, self.profile_combo,
            self.use_nodes_btn
        ]
        for widget in widgets_to_track:
            widget.installEventFilter(self)
        self.queue_tree.installEventFilter(self)

        print("[BRM] Keyboard shortcuts tracking installed")

    def _update_focus_context(self, widget) -> None:
        """Update job_list_has_focus based on current widget focus."""
        self.job_list_has_focus = (
            isinstance(widget, QTreeWidget) and 
            widget == self.queue_tree
        )

    def eventFilter(self, a0, a1):
        """Override eventFilter for focus tracking."""
        from PyQt6.QtCore import QEvent
        if a1 is not None:
            etype = a1.type()
            if etype == QEvent.Type.FocusIn and a0 is not None:
                self._update_focus_context(a0)
            elif etype == QEvent.Type.FocusOut:
                fw = QApplication.focusWidget()
                if fw:
                    self._update_focus_context(fw)
        return super().eventFilter(a0, a1)

    def focusInEvent(self, a0):
        if a0 is not None:
            fw = self.focusWidget()
            if fw:
                self._update_focus_context(fw)
        super().focusInEvent(a0)

    def keyPressEvent(self, a0):
        """
        Keyboard shortcuts basados en focus context:
        
        JOB LIST (queue_tree focus):
        • Enter: Start Selected o Start All Pending
        • Delete: Remove selected  
        • Escape: Cancel selected
        • F5: Retry selected (Error/Cancelled)
        
        FORM focus:
        • Enter: Add Job o Apply changes
        """
        if a0 is None:
            return super().keyPressEvent(a0)
        if a0.isAutoRepeat():
            return super().keyPressEvent(a0)

        key = a0.key()

        # JOB LIST FOCUS
        if self.job_list_has_focus:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                selected = self._selected_jobs()
                if selected:
                    self._start_selected()
                else:
                    self._start_all_pending()
                a0.accept()
                return

            elif key == Qt.Key.Key_Delete:
                self._remove_selected()
                a0.accept()
                return

            elif key == Qt.Key.Key_Escape:
                self._cancel_selected()
                a0.accept()
                return

            elif key == Qt.Key.Key_F5:
                self._retry_selected()
                a0.accept()
                return

        # FORM FOCUS - Add/Edit job
        else:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._selected_job_id is not None:
                    self._apply_changes_to_selected_job()
                else:
                    self._add_job()
                a0.accept()
                return

        super().keyPressEvent(a0)

    # ------------------------------------------------------------------ Log colors

    @staticmethod
    def _log_line_color(line: str) -> str:
        """Return a hex color for a log line based on its prefix/content."""
        if "[ERROR]" in line:
            return C["red"]
        if line.startswith("Fra:"):
            return C["peach"]
        if "Saved:" in line or "Saving:" in line:
            return C["green"]
        if line.startswith("[CMD]"):
            return C["mauve"]
        if line.startswith("[INFO]"):
            return C["lavender"]
        if "[BRM]" in line:
            return C["teal"]
        return C["text"]

    def _append_log_line(self, line: str):
        """Append a single colored line to the log QTextEdit."""
        color   = self._log_line_color(line)
        escaped = _html.escape(line)
        self.log_edit.append(f'<span style="color:{color};">{escaped}</span>')
        if self._log_autoscroll:
            self._scroll_log_to_bottom()

    # ------------------------------------------------------------------ Sound

    def _play_queue_done_sound(self):
        """Play a sound when the entire render queue finishes.

        Strategy (most-reliable first):
        1. winsound.PlaySound with SND_FILENAME — plays chimes.wav directly,
           no dependency on the Windows sound scheme being configured.
        2. Fallback: winsound.Beep sequence.
        Runs in a daemon thread so the UI is never blocked.
        """
        if not _HAS_WINSOUND:
            return

        def _play():
            ws = _winsound
            if ws is None:
                return
            try:
                if sys.platform == "win32":
                    wav = r"C:\Windows\Media\chimes.wav"
                    if os.path.isfile(wav):
                        ws.PlaySound(wav, ws.SND_FILENAME)
                else:
                    # Fallback: generate tones
                    ws.Beep(800,  200)
                    time.sleep(0.08)
                    ws.Beep(1000, 200)
                    time.sleep(0.08)
                    ws.Beep(1200, 400)
            except Exception:
                pass

        threading.Thread(target=_play, daemon=True).start()

    # ------------------------------------------------------------------ Open folder

    def _open_output_folder(self):
        """Open the output folder of the selected job in Windows Explorer."""
        job = self._selected_job()
        if not job:
            return
        path = job.effective_output_path
        if not path:
            return
        os.makedirs(path, exist_ok=True)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta:\n{e}")

    def _update_folder_btn(self, job: RenderJob):
        """Enable the Open Folder button when the job has an output path."""
        self._btn_open_folder.setEnabled(bool(job.effective_output_path))

    # ------------------------------------------------------------------ Export / Convert

    def _update_export_ui(self, job: RenderJob):
        """Enable/disable export controls based on job status."""
        is_running = job.status == RenderJob.STATUS_RUNNING
        is_done    = job.status == RenderJob.STATUS_DONE

        # Preview: only while Running
        self._btn_preview.setEnabled(is_running)

        # Preset dropdown + Convert: only when Done
        self._preset_combo.setEnabled(is_done)
        self._btn_convert.setEnabled(is_done)

        if is_done or is_running:
            fps = self._get_fps_for_job(job)
            self._fps_label.setText(f"FPS: {fps:g}")
        else:
            self._fps_label.setText("FPS: —")

    def _get_fps_for_job(self, job: RenderJob) -> float:
        """Return the FPS for a job's scene from the blend info cache, or 24.0."""
        key = f"{job.blend_file}|{job.blender_exec}"
        fps_map = self._blend_info_cache.get(key, {}).get("fps", {})
        return fps_map.get(job.scene, 24.0)

    def _preview_video(self):
        """Generate a quick MP4 preview from frames rendered so far (Running job)."""
        job = self._selected_job()
        if not job or job.status != RenderJob.STATUS_RUNNING:
            QMessageBox.information(
                self, "Info",
                "Preview solo está disponible para jobs en ejecución (Running).",
            )
            return

        fps         = self._get_fps_for_job(job)
        file_prefix = job.sequence_name if job.sequence_name else "frame"
        output_file = os.path.join(job.output_path, f"{file_prefix}_preview.mp4")

        self._btn_preview.setEnabled(False)
        self._fps_label.setText(f"FPS: {fps:g}  ⏳ generando preview…")
        self.status_bar.showMessage(
            f"Generando preview MP4 a {fps:g} fps — {output_file}"
        )

        self._convert_thread = ConvertThread(
            output_path=job.effective_output_path,
            file_prefix=file_prefix,
            frame_start=job.frame_start,
            fps=fps,
            output_file=output_file,
            preset=PREVIEW_PRESET,
        )
        self._convert_thread.finished.connect(self._on_convert_done)
        self._convert_thread.finished.connect(self._convert_thread.deleteLater)
        self._convert_thread.start()

    def _convert_video(self):
        """Convert the PNG sequence of a Done job using the selected preset."""
        job = self._selected_job()
        if not job or job.status != RenderJob.STATUS_DONE:
            return

        preset_name = self._preset_combo.currentText()
        preset = preset_by_name(preset_name)
        if not preset:
            QMessageBox.critical(self, "Error", f"Preset no encontrado: {preset_name}")
            return

        fps         = self._get_fps_for_job(job)
        file_prefix = job.sequence_name if job.sequence_name else "frame"
        output_file = os.path.join(job.output_path, f"{file_prefix}{preset['extension']}")

        # Warn if output file already exists
        if os.path.isfile(output_file):
            answer = QMessageBox.question(
                self, "Archivo existente",
                f"Ya existe:\n{output_file}\n\n¿Sobreescribir?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._btn_convert.setEnabled(False)
        self._preset_combo.setEnabled(False)
        self._fps_label.setText(f"FPS: {fps:g}  ⏳ convirtiendo ({preset_name})…")
        self.status_bar.showMessage(
            f"Convirtiendo a {preset_name} a {fps:g} fps — {output_file}"
        )

        self._convert_thread = ConvertThread(
            output_path=job.effective_output_path,
            file_prefix=file_prefix,
            frame_start=job.frame_start,
            fps=fps,
            output_file=output_file,
            preset=preset,
        )
        self._convert_thread.finished.connect(self._on_convert_done)
        self._convert_thread.finished.connect(self._convert_thread.deleteLater)
        self._convert_thread.start()

    def _on_convert_done(self, success: bool, message: str):
        job = self._selected_job()
        if job:
            self._update_export_ui(job)
        else:
            self._btn_preview.setEnabled(False)
            self._btn_convert.setEnabled(False)
            self._preset_combo.setEnabled(False)
            self._fps_label.setText("FPS: —")

        if success:
            self.status_bar.showMessage(message)
            QMessageBox.information(self, "Conversión completada", message)
        else:
            self.status_bar.showMessage("Conversión fallida.")
            QMessageBox.critical(self, "Error de conversión", message)


    # ------------------------------------------------------------------ Persistence

    def _save_jobs(self):
        save_config(self.jobs, self._blender_profiles)
        self.status_bar.showMessage(f"Queue saved.")

    def _export_render_queue(self):
        default_name = "render_queue_export.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Render Queue",
            default_name,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            payload = {
                "version": 1,
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "jobs": [j.to_dict() for j in self.jobs],
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            self.status_bar.showMessage(
                f"Exported {len(self.jobs)} job(s) to: {file_path}", 5000
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"No se pudo exportar la cola:\n{e}")

    def _import_render_queue(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Render Queue",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        running_jobs = [j for j in self.jobs if j.status == RenderJob.STATUS_RUNNING]
        if running_jobs:
            QMessageBox.warning(
                self,
                "Import blocked",
                "Hay jobs en ejecución. Cancelalos antes de importar una cola.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Reemplazar cola actual",
            "Esta acción reemplazará la cola actual por la del archivo seleccionado.\n"
            "¿Deseas continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_jobs = None
            if isinstance(data, list):
                raw_jobs = data
            elif isinstance(data, dict) and isinstance(data.get("jobs"), list):
                raw_jobs = data.get("jobs")

            if raw_jobs is None:
                raise ValueError("Formato inválido: se esperaba una lista o un objeto con clave 'jobs'.")

            imported_jobs: list[RenderJob] = []
            for entry in raw_jobs:
                if not isinstance(entry, dict):
                    continue
                try:
                    imported_jobs.append(RenderJob.from_dict(entry))
                except Exception:
                    continue

            self.jobs = imported_jobs
            if self.jobs:
                RenderJob._id_counter = max(j.job_id for j in self.jobs)
            else:
                RenderJob._id_counter = 0

            self._selected_job_id = None
            self.log_edit.clear()
            self._clear_progress_ui()
            self._btn_apply_to_job.setEnabled(False)

            self._refresh_tree()
            self._auto_save_queue()
            self.status_bar.showMessage(
                f"Loaded {len(self.jobs)} job(s) from: {file_path}", 5000
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"No se pudo importar la cola:\n{e}")

    def _auto_save_queue(self):
        """Auto-save the queue after mutations (add/delete/finish)."""
        self._save_jobs()
        self.status_bar.showMessage("Queue auto-saved.", 2000)

    def _load_jobs(self):
        self.jobs, self._blender_profiles = load_config()
        self._populate_profile_combo()
        self._refresh_tree()
        if self.jobs:
            self.status_bar.showMessage(f"Loaded {len(self.jobs)} job(s).")

    # ------------------------------------------------------------------ Drag & Drop

    def dragEnterEvent(self, a0):
        """Accept drag if it contains at least one .blend file."""
        if a0 is None:
            return super().dragEnterEvent(a0)
        md = a0.mimeData()
        if md is None:
            a0.ignore()
            return
        if md.hasUrls():
            if any(
                u.toLocalFile().lower().endswith(".blend")
                for u in md.urls()
            ):
                a0.acceptProposedAction()
                return
        a0.ignore()

    def dropEvent(self, a0):
        """Load the first .blend file dropped onto the window."""
        if a0 is None:
            return super().dropEvent(a0)
        md = a0.mimeData()
        if md is None:
            return super().dropEvent(a0)
        blend_files = [
            u.toLocalFile()
            for u in md.urls()
            if u.toLocalFile().lower().endswith(".blend")
        ]
        if blend_files:
            self._prepare_form_for_new_blend(blend_files[0])
            self.status_bar.showMessage(f"Archivo cargado: {blend_files[0]}")

    # ------------------------------------------------------------------ Cleanup

    def closeEvent(self, a0):
        try:
            if hasattr(self, "_ipc_timer") and self._ipc_timer is not None:
                self._ipc_timer.stop()
        except Exception:
            pass
        try:
            if self._ipc_server is not None:
                self._ipc_server.stop()
        except Exception:
            pass

        for job in self.jobs:
            if job.status == RenderJob.STATUS_RUNNING and job.process:
                job.process.terminate()

        for thread in list(self.threads.values()):
            try:
                thread.quit()
                thread.wait(3000)
            except RuntimeError:
                pass

        try:
            t = self._blend_info_thread
            if t is not None and t.isRunning():
                t.quit()
                t.wait(3000)
        except RuntimeError:
            pass
        self._blend_info_thread = None

        try:
            t = self._convert_thread
            if t is not None and t.isRunning():
                t.quit()
                t.wait(3000)
        except RuntimeError:
            pass
        self._convert_thread = None

        if a0 is not None:
            a0.accept()
