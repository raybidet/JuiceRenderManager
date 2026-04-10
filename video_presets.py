"""
video_presets.py — FFmpeg video export preset definitions for Juice | Render Manager.

Each preset is a dict with:
    name          : str   — human-readable label shown in the dropdown
    extension     : str   — file extension including dot (e.g. ".mp4")
    ffmpeg_args   : list  — FFmpeg output arguments inserted between -i <input> and <output>
    supports_alpha: bool  — True if the codec preserves an alpha channel
"""
from __future__ import annotations

VIDEO_PRESETS: list[dict] = [
    {
        "name": "H.264 MP4",
        "extension": ".mp4",
        "ffmpeg_args": ["-c:v", "libx264", "-pix_fmt", "yuv420p"],
        "supports_alpha": False,
    },
    {
        "name": "H.265 / HEVC MP4",
        "extension": ".mp4",
        "ffmpeg_args": ["-c:v", "libx265", "-pix_fmt", "yuv420p", "-tag:v", "hvc1"],
        "supports_alpha": False,
    },
    {
        "name": "Apple ProRes 422 HQ",
        "extension": ".mov",
        "ffmpeg_args": ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"],
        "supports_alpha": False,
    },
    {
        "name": "Apple ProRes 4444 XQ",
        "extension": ".mov",
        "ffmpeg_args": ["-c:v", "prores_ks", "-profile:v", "5", "-pix_fmt", "yuva444p10le"],
        "supports_alpha": False,
    },
    {
        "name": "Apple ProRes 4444 XQ + Alpha",
        "extension": ".mov",
        "ffmpeg_args": ["-c:v", "prores_ks", "-profile:v", "5", "-pix_fmt", "yuva444p10le"],
        "supports_alpha": True,
    },
    {
        "name": "QuickTime Animation (.mov)",
        "extension": ".mov",
        "ffmpeg_args": ["-c:v", "qtrle", "-pix_fmt", "argb"],
        "supports_alpha": True,
    },
    {
        "name": "DNxHR HQ (.mov)",
        "extension": ".mov",
        "ffmpeg_args": ["-c:v", "dnxhd", "-profile:v", "dnxhr_hq", "-pix_fmt", "yuv422p"],
        "supports_alpha": False,
    },
    {
        "name": "DNxHR 444 (.mov)",
        "extension": ".mov",
        "ffmpeg_args": ["-c:v", "dnxhd", "-profile:v", "dnxhr_444", "-pix_fmt", "yuv444p10le"],
        "supports_alpha": False,
    },
    {
        "name": "AVI (Uncompressed)",
        "extension": ".avi",
        "ffmpeg_args": ["-c:v", "rawvideo", "-pix_fmt", "bgr24"],
        "supports_alpha": False,
    },
    {
        "name": "AVI (MJPEG)",
        "extension": ".avi",
        "ffmpeg_args": ["-c:v", "mjpeg", "-q:v", "2", "-pix_fmt", "yuvj422p"],
        "supports_alpha": False,
    },
]

# Quick-preview preset (always H.264 MP4 for speed and compatibility)
PREVIEW_PRESET: dict = VIDEO_PRESETS[0]


def preset_names() -> list[str]:
    """Return the display names for all presets (for populating a QComboBox)."""
    return [p["name"] for p in VIDEO_PRESETS]


def preset_by_name(name: str) -> dict | None:
    """Look up a preset by its display name. Returns None if not found."""
    for p in VIDEO_PRESETS:
        if p["name"] == name:
            return p
    return None
