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
import os
import sys
import subprocess
import tempfile
import time
from typing import Callable, Optional

from models import RenderJob

LOG_MAX_LINES = 6000
TREE_THROTTLE    = 0.25   # minimum seconds between tree-refresh signals
ROLLING_ETA_WIN  = 8      # number of recent frames used for rolling ETA


def build_render_script(job: RenderJob) -> str:
    """Return the Python source that Blender will run before --render-anim."""
    use_nodes_val = "True" if job.use_nodes else "False"

    if job.samples_override is not None:
        samples_block = (
            f"scene.cycles.samples = {job.samples_override}\n"
            f"print('[BRM] Samples override:', {job.samples_override})"
        )
    else:
        samples_block = (
            "print('[BRM] Samples: scene default =', scene.cycles.samples)"
        )

    return f"""\
import bpy

scene = bpy.data.scenes.get('{job.scene}') or bpy.context.scene

# ── Compositing nodes ──────────────────────────────────────────────────────
scene.use_nodes = {use_nodes_val}
print('[BRM] use_nodes =', scene.use_nodes)

# ── Sample override ────────────────────────────────────────────────────────
{samples_block}

# ── Reload user preferences (GPU config lives here) ────────────────────────
# --background skips userpref.blend; we force-reload it so that
# compute_device_type and per-device .use flags are restored.
try:
    bpy.ops.wm.read_userpref()
    print('[BRM] User prefs reloaded OK.')
except Exception as _e:
    print('[BRM] WARNING: prefs reload error:', _e)

# ── Re-apply scene-level overrides after prefs reload ──────────────────────
# Keep these after read_userpref() to avoid any accidental reset.
if {repr(job.samples_override)} is not None:
    scene.cycles.samples = {job.samples_override}
    print('[BRM] Samples override (post-prefs):', {job.samples_override})
else:
    print('[BRM] Samples: scene default =', scene.cycles.samples)

if {repr(job.resolution_pct)} is not None:
    _res_pct = int(round(float({job.resolution_pct})))
    _res_pct = max(0, min(100, _res_pct))
    scene.render.resolution_percentage = _res_pct
    print('[BRM] Resolution % override (post-prefs):', _res_pct)
else:
    print('[BRM] Resolution %: scene default =', scene.render.resolution_percentage)

# ── Apply GPU from reloaded prefs ──────────────────────────────────────────
try:
    _cprefs = bpy.context.preferences.addons['cycles'].preferences
    # get_devices() MUST be called after a prefs reload to populate device list
    _cprefs.get_devices()
    _ctype  = str(_cprefs.compute_device_type)
    _active = [d.name for d in _cprefs.devices if d.use]
    if _ctype != 'NONE' and _active:
        scene.cycles.device = 'GPU'
        print('[BRM] Compute type  :', _ctype)
        print('[BRM] Active devices:', ', '.join(_active))
    else:
        scene.cycles.device = 'CPU'
        print('[BRM] No GPU devices active — CPU render.')
except Exception as _e:
    scene.cycles.device = 'CPU'
    print('[BRM] GPU setup error:', _e)

print('[BRM] cycles.device  =', scene.cycles.device)
print('[BRM] render.engine  =', scene.render.engine)
print('[BRM] resolution_percentage =', scene.render.resolution_percentage)
print('[BRM] resolution_x =', scene.render.resolution_x)
print('[BRM] resolution_y =', scene.render.resolution_y)
"""

def get_blend_info(blend_file: str, blender_exec: str) -> dict:

    """
    Query a .blend file for scene names, Cycles sample counts, and FPS.
    Returns {'scenes': [...], 'samples': {scene_name: int}, 'fps': {scene_name: float}}.
    Runs Blender headless — call from a worker thread only.
    """
    script = (
        "import bpy;"
        "rows=[];"
        "[rows.append("
        "  s.name"
        "  +'|'+str(getattr(s.cycles,'samples',128))"
        "  +'|'+str(round(s.render.fps/max(s.render.fps_base,0.001),3))"
        ") for s in bpy.data.scenes];"
        "print('BLEND_INFO:'+';'.join(rows))"
    )
    fallback = {"scenes": ["Scene"], "samples": {"Scene": 128}, "fps": {"Scene": 24.0}}
    try:
        r = subprocess.run(
            [blender_exec, "--background", blend_file, "--python-expr", script],
            capture_output=True, encoding="utf-8", errors="replace", timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        for line in r.stdout.splitlines():
            if line.startswith("BLEND_INFO:"):
                scenes, samples, fps = [], {}, {}
                for entry in line[len("BLEND_INFO:"):].split(";"):
                    parts = entry.split("|")
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        scenes.append(name)
                        try:
                            samples[name] = int(parts[1])
                        except (ValueError, IndexError):
                            samples[name] = 128
                        try:
                            fps[name] = float(parts[2])
                        except (ValueError, IndexError):
                            fps[name] = 24.0
                if scenes:
                    return {"scenes": scenes, "samples": samples, "fps": fps}
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
        on_done: Callable[[int, str], None],   # job_id, final_status
        on_frame_saved: Callable[[int], None],
        blender_executable: Optional[str] = None,
    ):
        self.job               = job
        self._on_log           = on_log
        self._on_progress      = on_progress
        self._on_done          = on_done
        self._on_frame_saved   = on_frame_saved
        self._blender_executable = blender_executable
        self._tmp_script: Optional[str] = None
        self._recent_frame_times: list[float] = []   # rolling ETA window

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
            "--background", job.blend_file,
            "--scene",      job.scene,
            "--python",     self._tmp_script,
            "--render-output", output_template,
            "--frame-start",   str(job.frame_start),
            "--frame-end",     str(job.frame_end),
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
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
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
                            job._frame_wall_start   = time.monotonic()

                        job.current_frame = frame_num
                        job.progress = int(
                            min(frames_completed / job.total_frames * 100, 99)
                        )

                        if job.start_time:
                            job.elapsed_seconds = time.monotonic() - job.start_time
                            remaining = job.total_frames - frames_completed
                            if self._recent_frame_times:
                                # Rolling average of last N frames (adapts to scene complexity)
                                avg = sum(self._recent_frame_times) / len(self._recent_frame_times)
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
                    job.progress    = 100
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
        if len(self.job.log_lines) > LOG_MAX_LINES:
            self.job.log_lines = self.job.log_lines[-LOG_MAX_LINES:]

    def _finish(self, status: str) -> None:
        self.job.status = status
        self._on_done(self.job.job_id, status)

    def _cleanup_tmp(self) -> None:
        if self._tmp_script and os.path.exists(self._tmp_script):
            try:
                os.remove(self._tmp_script)
            except OSError:
                pass
