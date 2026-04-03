"""
models.py — RenderJob data model and JSON persistence for Juice | Render Manager for Blender.
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import shutil
DEFAULT_BLENDER = shutil.which("blender") or (
    "/Applications/Blender.app/Contents/MacOS/Blender"
    if sys.platform == "darwin" else
    r"F:\Program Files\blender.exe"
)


@dataclass
class BlenderProfile:
    """Named path to a Blender executable (e.g. different versions)."""
    name: str
    path: str

    def to_dict(self) -> dict:
        return {"name": self.name, "path": self.path}

    @classmethod
    def from_dict(cls, d: dict) -> BlenderProfile:
        return cls(
            name=str(d.get("name", "Profile")).strip() or "Profile",
            path=str(d.get("path", DEFAULT_BLENDER)).strip() or DEFAULT_BLENDER,
        )


def default_blender_profiles() -> list[BlenderProfile]:
    return [BlenderProfile(name="Default", path=DEFAULT_BLENDER or "")]

# When running as a PyInstaller frozen bundle the install dir may be read-only
# (e.g. C:\Program Files\…).  Store user data in %APPDATA% instead.
import sys as _sys
if getattr(_sys, "frozen", False):
    _cfg_dir = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "Juice",
    )
else:
    _cfg_dir = os.path.dirname(os.path.abspath(__file__))

os.makedirs(_cfg_dir, exist_ok=True)
CONFIG_FILE = os.path.join(_cfg_dir, "render_jobs.json")


@dataclass
class RenderJob:
    # ---- identity ----
    job_id: int = field(default=0, init=False)

    # ---- user config ----
    blend_file: str = ""
    scene: str = "Scene"
    sequence_name: str = ""        # user-defined label, used as output subfolder name
    frame_start: int = 1
    frame_end: int = 250
    output_path: str = ""          # base output directory
    blender_exec: str = DEFAULT_BLENDER
    blender_profile: str = ""      # name in BlenderProfile list; empty = custom path only
    use_nodes: bool = False
    samples_override: Optional[int] = None   # None = use scene default
    resolution_pct: Optional[float] = None      # None = use scene default (100%)

    # ---- runtime state (not persisted) ----
    status: str = field(default="Pending", init=False)
    progress: int = field(default=0, init=False)
    current_frame: Optional[int] = field(default=None, init=False)
    process: object = field(default=None, init=False, repr=False)
    log_lines: list[str] = field(default_factory=list, init=False, repr=False)

    # timing
    start_time: Optional[float] = field(default=None, init=False)
    elapsed_seconds: float = field(default=0.0, init=False)
    eta_seconds: Optional[float] = field(default=None, init=False)
    last_frame_elapsed: Optional[float] = field(default=None, init=False)
    _frame_wall_start: Optional[float] = field(default=None, init=False, repr=False)
    _prev_tracked_frame: Optional[int] = field(default=None, init=False, repr=False)

    # statuses
    STATUS_PENDING   = "Pending"
    STATUS_RUNNING   = "Running"
    STATUS_PAUSED    = "Paused"
    STATUS_DONE      = "Done"
    STATUS_ERROR     = "Error"
    STATUS_CANCELLED = "Cancelled"

    _id_counter: int = field(default=0, init=False, repr=False, compare=False)

    def __post_init__(self):
        RenderJob._id_counter += 1
        self.job_id = RenderJob._id_counter
        if not self.blender_exec:
            self.blender_exec = DEFAULT_BLENDER

    @property
    def effective_output_path(self) -> str:
        """Resolved output directory: base_path/sequence_name (if name given)."""
        if self.sequence_name:
            return os.path.join(self.output_path, self.sequence_name)
        return self.output_path

    @property
    def total_frames(self) -> int:
        return max(1, self.frame_end - self.frame_start + 1)

    def reset_for_run(self):
        self.status              = self.STATUS_RUNNING
        self.progress            = 0
        self.current_frame       = None
        self.log_lines           = []
        self.start_time          = time.monotonic()
        self.elapsed_seconds     = 0.0
        self.eta_seconds         = None
        self.last_frame_elapsed  = None
        self._frame_wall_start   = None
        self._prev_tracked_frame = None

    def to_dict(self) -> dict:
        return {
            "job_id":          self.job_id,
            "blend_file":      self.blend_file,
            "scene":           self.scene,
            "sequence_name":   self.sequence_name,
            "frame_start":     self.frame_start,
            "frame_end":       self.frame_end,
            "output_path":     self.output_path,
            "blender_exec":    self.blender_exec,
            "blender_profile": self.blender_profile,
            "use_nodes":       self.use_nodes,
            "samples_override": self.samples_override,
            "resolution_pct": self.resolution_pct if self.resolution_pct is not None else None,
            "status":          self.status,
        }

    @property
    def effective_resolution_pct(self) -> float:
        """Return resolution_pct override or scene default fallback (100.0)."""
        return self.resolution_pct if self.resolution_pct is not None else 100.0

    @classmethod
    def from_dict(cls, d: dict) -> RenderJob:
        job = cls(
            blend_file=d["blend_file"],
            scene=d.get("scene", "Scene"),
            sequence_name=d.get("sequence_name", ""),
            frame_start=d.get("frame_start", 1),
            frame_end=d.get("frame_end", 250),
            output_path=d.get("output_path", ""),
            blender_exec=d.get("blender_exec", DEFAULT_BLENDER or ""),
            blender_profile=d.get("blender_profile", ""),
            use_nodes=d.get("use_nodes", False),
            samples_override=d.get("samples_override"),
            resolution_pct=d.get("resolution_pct"),
        )
        job.job_id = d["job_id"]
        raw_status = d.get("status", cls.STATUS_PENDING)
        # Jobs that were "Running" when the app closed are considered interrupted
        job.status = cls.STATUS_ERROR if raw_status == cls.STATUS_RUNNING else raw_status
        return job


def resolve_blender_exec(job: RenderJob, profiles: list[BlenderProfile]) -> str:
    """Executable path for a job: named profile wins, else stored path."""
    if job.blender_profile:
        for p in profiles:
            if p.name == job.blender_profile:
                return p.path
    if job.blender_exec:
        return job.blender_exec
    return DEFAULT_BLENDER or ""


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_config(jobs: list[RenderJob], profiles: list[BlenderProfile]) -> None:
    payload = {
        "blender_profiles": [p.to_dict() for p in profiles],
        "jobs": [j.to_dict() for j in jobs],
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_config() -> tuple[list[RenderJob], list[BlenderProfile]]:
    # Migrate old config if exists
    old_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "BlenderRenderManager")
    old_config = os.path.join(old_dir, "render_jobs.json")
    if os.path.isfile(old_config) and not os.path.isfile(CONFIG_FILE):
        import shutil
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            shutil.copy2(old_config, CONFIG_FILE)
            print(f"[Juice] Migrated config from {old_config}")
        except Exception as e:
            print(f"[Juice] Config migration failed: {e}")

    if not os.path.isfile(CONFIG_FILE):
        return [], default_blender_profiles()
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return [], default_blender_profiles()

    profiles = default_blender_profiles()
    jobs: list[RenderJob] = []

    if isinstance(data, list):
        jobs = [RenderJob.from_dict(d) for d in data]
    elif isinstance(data, dict):
        raw_p = data.get("blender_profiles")
        if isinstance(raw_p, list) and raw_p:
            profiles = [BlenderProfile.from_dict(x) for x in raw_p]
        raw_jobs = data.get("jobs")
        if isinstance(raw_jobs, list):
            jobs = [RenderJob.from_dict(d) for d in raw_jobs]

    if jobs:
        RenderJob._id_counter = max(j.job_id for j in jobs)
    return jobs, profiles


def save_jobs(jobs: list[RenderJob]) -> None:
    """Save jobs only; keeps existing blender_profiles from disk when possible."""
    profiles = default_blender_profiles()
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("blender_profiles"), list):
                raw_p = data["blender_profiles"]
                if raw_p:
                    profiles = [BlenderProfile.from_dict(x) for x in raw_p]
        except Exception:
            pass
    save_config(jobs, profiles)


def load_jobs() -> list[RenderJob]:
    jobs, _ = load_config()
    return jobs

