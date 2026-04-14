"""
worker.py — Background render thread + Blender GPU setup script builder.

GPU strategy
------------
Blender --background does NOT load userpref.blend, so GPU settings are reset
to CPU.  We inject a Python script (--python <tmpfile>) that:
  1. Calls bpy.ops.wm.read_userpref() to reload the preferences file.
  2. Calls cprefs.get_devices() to refresh the device list.
  3. Reads compute_device_type and enabled devices from the loaded prefs.
  4. Sets scene.cycles.device = 'GPU' if any GPU device is active.

This is the same sequence Blender performs when launched normally.
"""

from __future__ import annotations
import json
import os
import sys
import subprocess
import tempfile
import time
from typing import Callable, Optional

from models import RenderJob

LOG_MAX_LINES = 6000
TREE_THROTTLE = 0.25  # minimum seconds between tree-refresh signals
ROLLING_ETA_WIN = 8  # number of recent frames used for rolling ETA


def build_render_script(job: RenderJob) -> str:
    """Return the Python source that Blender will run before --render-anim."""
    use_nodes_val = "True" if job.use_nodes else "False"

    if job.samples_override is not None:
        samples_block = f"scene.cycles.samples = {job.samples_override}"
    else:
        samples_block = ""

    return f"""\
import bpy

scene = bpy.data.scenes.get('{job.scene}') or bpy.context.scene

# ── Compositing nodes ──────────────────────────────────────────────────────
scene.use_nodes = {use_nodes_val}

# If compositing nodes are enabled for this job, sync File Output base_path
# to the job output path (effective path includes optional sequence subfolder).
if {use_nodes_val}:
    try:
        _output_base = r'''{job.effective_output_path}'''
        _nt = scene.node_tree
        if _nt is not None:
            _targets = []

            # Prefer exact default node name first (as requested in TODO)
            _by_name = _nt.nodes.get('File Output')
            if _by_name and getattr(_by_name, 'bl_idname', '') == 'CompositorNodeOutputFile':
                _targets.append(_by_name)

            # Fallback: any File Output nodes by type (supports renamed nodes)
            for _n in _nt.nodes:
                if getattr(_n, 'bl_idname', '') == 'CompositorNodeOutputFile' and _n not in _targets:
                    _targets.append(_n)

            if not _targets:
                pass
            else:
                for _node in _targets:
                    _node.base_path = _output_base
    except Exception as _e:
        pass

# ── Sample override ────────────────────────────────────────────────────────
{samples_block}

# ── Re-apply scene-level overrides after prefs reload ──────────────────────
# Keep these after read_userpref() to avoid any accidental reset.
if {repr(job.samples_override)} is not None:
    scene.cycles.samples = {job.samples_override}

if {repr(job.resolution_pct)} is not None:
    _res_pct = int(round(float({job.resolution_pct})))
    _res_pct = max(0, min(100, _res_pct))
    scene.render.resolution_percentage = _res_pct

# ── Apply GPU from reloaded prefs ──────────────────────────────────────────
try:
    _cprefs = bpy.context.preferences.addons['cycles'].preferences
    _cprefs.get_devices()
    _ctype  = str(_cprefs.compute_device_type)
    _active = [d.name for d in _cprefs.devices if d.use]
    if _ctype != 'NONE' and _active:
        scene.cycles.device = 'GPU'
    else:
        scene.cycles.device = 'CPU'
except Exception as _e:
    scene.cycles.device = 'CPU'

# ── Camera selection ─────────────────────────────────────────────────────────
if {repr(job.camera)}:
    _cam = bpy.data.objects.get({repr(job.camera)})
    if _cam and _cam.type == 'CAMERA':
        scene.camera = _cam
else:
    pass
"""


def build_opengl_script(job: RenderJob) -> str:
    """Genera script para preview rapido con render real (EEVEE, 1 sample, 15%)."""
    camera_line = (
        f"cam = bpy.data.objects.get({repr(job.camera)})\n"
        f"if cam and cam.type == 'CAMERA':\n"
        f"    scene.camera = cam"
        if job.camera
        else "# use scene default camera"
    )
    frame_num = job.frame_start if job.frame_start else 1
    return f"""\
import bpy, tempfile, os

scene = bpy.data.scenes.get('{job.scene}') or bpy.context.scene
bpy.context.window.scene = scene

{camera_line}

scene.frame_set({frame_num})
scene.render.resolution_percentage = 15
scene.cycles.samples = 1
scene.render.engine = 'BLENDER_EEVEE_NEXT'

bpy.ops.render.render(animation=False)

tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
tmp.close()
bpy.data.images['Render Result'].save_render(tmp.name)
print('PREVIEW_IMAGE:' + tmp.name)
""".format(frame_num=frame_num)


def get_blend_info(blend_file: str, blender_exec: str) -> dict:
    """
    Query a .blend file for scene names, Cycles sample counts, FPS, and resolution %.
    Returns:
        {
            'scenes': [...],
            'samples': {scene_name: int},
            'fps': {scene_name: float},
            'resolution_pct': {scene_name: float},
        }
    Uses JSON output to avoid delimiter conflicts with scene names.
    Runs Blender headless — call from a worker thread only.
    """
    # JSON output avoids any delimiter collision with scene names.
    # chr(9) = tab used as record separator between scenes (safe: Blender
    # strips leading/trailing whitespace from scene names).
    script = (
        "import bpy, json;"
        "data=[{"
        "'name':s.name,"
        "'samples':getattr(s.cycles,'samples',128),"
        "'fps':round(s.render.fps/max(s.render.fps_base,0.001),3),"
        "'resolution_pct':float(s.render.resolution_percentage),"
        "'cameras':[c.name for c in s.collection.all_objects if c.type=='CAMERA']"
        "} for s in bpy.data.scenes];"
        "print('BLEND_INFO:'+json.dumps(data,ensure_ascii=False))"
    )
    fallback = {
        "scenes": ["Scene"],
        "samples": {"Scene": 128},
        "fps": {"Scene": 24.0},
        "resolution_pct": {"Scene": 100.0},
        "cameras": {"Scene": []},
    }
    try:
        r = subprocess.run(
            [blender_exec, "--background", blend_file, "--python-expr", script],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            creationflags=0,
        )
        for line in r.stdout.splitlines():
            if line.startswith("BLEND_INFO:"):
                raw = json.loads(line[len("BLEND_INFO:") :])
                scenes: list[str] = []
                samples: dict[str, int] = {}
                fps: dict[str, float] = {}
                resolution_pct: dict[str, float] = {}
                cameras: dict[str, list[str]] = {}
                for entry in raw:
                    name = str(entry.get("name", "Scene"))
                    scenes.append(name)
                    try:
                        samples[name] = int(entry.get("samples", 128))
                    except (ValueError, TypeError):
                        samples[name] = 128
                    try:
                        fps[name] = float(entry.get("fps", 24.0))
                    except (ValueError, TypeError):
                        fps[name] = 24.0
                    try:
                        resolution_pct[name] = float(entry.get("resolution_pct", 100.0))
                    except (ValueError, TypeError):
                        resolution_pct[name] = 100.0
                    try:
                        cameras[name] = list(entry.get("cameras", []))
                    except (ValueError, TypeError):
                        cameras[name] = []
                if scenes:
                    return {
                        "scenes": scenes,
                        "samples": samples,
                        "fps": fps,
                        "resolution_pct": resolution_pct,
                        "cameras": cameras,
                    }
    except Exception:
        pass
    return fallback


class RenderWorker:
    """
    Manages a single Blender render subprocess.
    All callbacks are invoked from the worker thread — callers must
    use Qt signals or queues to safely update the UI.
    """

    def __init__(
        self,
        job: RenderJob,
        on_log: Callable[[int, str], None],
        on_progress: Callable[[int], None],
        on_done: Callable[[int, str], None],  # job_id, final_status
        on_frame_saved: Callable[[int], None],
        blender_executable: Optional[str] = None,
    ):
        self.job = job
        self._on_log = on_log
        self._on_progress = on_progress
        self._on_done = on_done
        self._on_frame_saved = on_frame_saved
        self._blender_executable = blender_executable
        self._tmp_script: Optional[str] = None
        self._recent_frame_times: list[float] = []  # rolling ETA window

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Entry point — meant to be called from a QThread or threading.Thread."""
        job = self.job
        job.reset_for_run()

        os.makedirs(job.effective_output_path, exist_ok=True)
        file_prefix = job.sequence_name if job.sequence_name else "frame"
        output_template = os.path.join(job.effective_output_path, f"{file_prefix}_####")

        # Write GPU/setup script to a temp file
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix="_brm.py", delete=False, encoding="utf-8"
            ) as f:
                f.write(build_render_script(job))
                self._tmp_script = f.name
        except Exception as e:
            self._log(f"[ERROR] Cannot write temp script: {e}")
            self._finish(job.STATUS_ERROR)
            return

        exe = self._blender_executable or job.blender_exec
        cmd = [
            exe,
            "--background",
            job.blend_file,
            "--scene",
            job.scene,
            "--python",
            self._tmp_script,
            "--render-output",
            output_template,
            "--frame-start",
            str(job.frame_start),
            "--frame-end",
            str(job.frame_end),
            "--render-anim",
        ]

        self._log(f"[CMD] {' '.join(cmd)}")
        self._log(
            f"[INFO] Nodes: {'ON' if job.use_nodes else 'OFF'} | "
            f"Samples: {job.samples_override or 'scene default'} | "
            f"Res%: {job.resolution_pct if job.resolution_pct is not None else 'scene default'} | "
            f"Output: {job.effective_output_path}"
        )

        frames_completed = 0
        last_tree_refresh = 0.0

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=0,
            )
            job.process = proc

            for line in proc.stdout:
                line = line.rstrip("\n")

                if job.status == job.STATUS_CANCELLED:
                    proc.terminate()
                    break

                self._log(line)

                # ── Fra: line — Blender is rendering a frame ───────────────
                if line.startswith("Fra:"):
                    try:
                        frame_num = int(line.split()[0].split(":")[1])
                    except (ValueError, IndexError):
                        frame_num = None

                    if frame_num is not None:
                        # New frame started → previous frame is complete
                        if frame_num != job._prev_tracked_frame:
                            if job._prev_tracked_frame is not None:
                                frames_completed = (
                                    job._prev_tracked_frame - job.frame_start + 1
                                )
                                if job._frame_wall_start:
                                    ft = time.monotonic() - job._frame_wall_start
                                    job.last_frame_elapsed = ft
                                    # Rolling window: keep last ROLLING_ETA_WIN times
                                    self._recent_frame_times.append(ft)
                                    if len(self._recent_frame_times) > ROLLING_ETA_WIN:
                                        self._recent_frame_times.pop(0)
                            job._prev_tracked_frame = frame_num
                            job._frame_wall_start = time.monotonic()

                        job.current_frame = frame_num
                        job.progress = int(
                            min(frames_completed / job.total_frames * 100, 99)
                        )

                        if job.start_time:
                            job.elapsed_seconds = time.monotonic() - job.start_time
                            remaining = job.total_frames - frames_completed
                            if self._recent_frame_times:
                                # Rolling average of last N frames (adapts to scene complexity)
                                avg = sum(self._recent_frame_times) / len(
                                    self._recent_frame_times
                                )
                            elif frames_completed > 0:
                                # Fallback: global average until we have enough samples
                                avg = job.elapsed_seconds / frames_completed
                            else:
                                avg = None
                            if avg is not None:
                                job.eta_seconds = avg * remaining

                    # Throttle the tree/progress refresh signal
                    now = time.monotonic()
                    if now - last_tree_refresh >= TREE_THROTTLE:
                        last_tree_refresh = now
                        self._on_progress(job.job_id)

                # ── Frame saved to disk ────────────────────────────────────
                elif "Saved:" in line or "Saving:" in line:
                    if job._frame_wall_start:
                        job.last_frame_elapsed = (
                            time.monotonic() - job._frame_wall_start
                        )
                    self._on_frame_saved(job.job_id)

            proc.wait()

            if job.status != job.STATUS_CANCELLED:
                if proc.returncode == 0:
                    # Record last frame timing
                    if job._frame_wall_start:
                        job.last_frame_elapsed = (
                            time.monotonic() - job._frame_wall_start
                        )
                    job.progress = 100
                    job.eta_seconds = 0
                    self._finish(job.STATUS_DONE)
                else:
                    self._finish(job.STATUS_ERROR)
            else:
                self._finish(job.STATUS_CANCELLED)

        except FileNotFoundError:
            self._log(f"[ERROR] Blender not found: {exe}")
            self._log("[ERROR] Fix the executable path or profile in Blender settings.")
            self._finish(job.STATUS_ERROR)
        except Exception as e:
            self._log(f"[ERROR] {e}")
            self._finish(job.STATUS_ERROR)
        finally:
            self._cleanup_tmp()

    # ------------------------------------------------------------------
    def _log(self, text: str) -> None:
        self._on_log(self.job.job_id, text)
        self.job.log_lines.append(text)
        if len(self.job.log_lines) >= LOG_MAX_LINES:
            self.job.log_lines = self.job.log_lines[-(LOG_MAX_LINES - 100) :]

    def _finish(self, status: str) -> None:
        self.job.status = status
        self._on_done(self.job.job_id, status)

    def _cleanup_tmp(self) -> None:
        if self._tmp_script and os.path.exists(self._tmp_script):
            try:
                os.remove(self._tmp_script)
            except OSError:
                pass
