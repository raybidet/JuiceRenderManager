"""
test_models.py — Model and dataclass tests for Juice Render Manager.

Tests cover:
- RenderJob dataclass behavior
- BlenderProfile validation
- Config persistence
- Helper functions

Run with:
    pytest tests/test_models.py -v
"""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    RenderJob,
    BlenderProfile,
    save_config,
    load_config,
    resolve_blender_exec,
    default_blender_profiles,
)


class TestRenderJobCreation:
    """RenderJob creation tests."""

    def test_job_has_unique_id(self):
        """Each job should get a unique ID."""
        RenderJob._id_counter = 0
        job1 = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
        )
        job2 = RenderJob(
            blend_file="test2.blend",
            scene="Scene",
            output_path="output2",
            frame_start=1,
            frame_end=10,
        )

        assert job1.job_id != job2.job_id, "Jobs should have unique IDs"
        assert job1.job_id == 1, f"First job should have ID 1, got {job1.job_id}"
        assert job2.job_id == 2, f"Second job should have ID 2, got {job2.job_id}"

    def test_job_has_default_values(self):
        """Job should have sensible defaults."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
        )

        assert job.status == RenderJob.STATUS_PENDING
        assert job.progress == 0
        assert job.current_frame is None
        assert job.use_nodes is False
        assert job.samples_override is None
        assert job.resolution_pct is None

    def test_job_sets_default_blender(self):
        """Job should set default blender path."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
        )

        assert job.blender_exec != "", "Should have blender path"


class TestRenderJobProperties:
    """RenderJob property tests."""

    def test_effective_output_path_without_sequence(self):
        """effective_output_path returns base when no sequence."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="E:/renders",
            sequence_name="",
            frame_start=1,
            frame_end=10,
        )

        result = os.path.normpath(job.effective_output_path)
        expected = os.path.normpath("E:/renders")
        assert result == expected

    def test_effective_output_path_with_sequence(self):
        """effective_output_path includes sequence subfolder."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="E:/renders",
            sequence_name="shot_010",
            frame_start=1,
            frame_end=10,
        )

        result = os.path.normpath(job.effective_output_path)
        expected = os.path.normpath("E:/renders/shot_010")
        assert result == expected

    def test_total_frames(self):
        """total_frames calculates correctly."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=250,
        )

        assert job.total_frames == 250

    def test_total_frames_single_frame(self):
        """total_frames handles single frame."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=100,
            frame_end=100,
        )

        assert job.total_frames == 1

    def test_effective_resolution_pct(self):
        """effective_resolution_pct returns override or default."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            resolution_pct=50.0,
            frame_start=1,
            frame_end=10,
        )

        assert job.effective_resolution_pct == 50.0

        job2 = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            resolution_pct=None,
            frame_start=1,
            frame_end=10,
        )

        assert job2.effective_resolution_pct == 100.0


class TestBlenderProfile:
    """BlenderProfile tests."""

    def test_profile_creation(self):
        """Profile should store name and path."""
        profile = BlenderProfile("Test", "F:/blender.exe")

        assert profile.name == "Test"
        assert profile.path == "F:/blender.exe"

    def test_profile_to_dict(self):
        """Profile should serialize to dict."""
        profile = BlenderProfile("Custom", "F:/blender.exe")

        d = profile.to_dict()

        assert d["name"] == "Custom"
        assert d["path"] == "F:/blender.exe"

    def test_profile_from_dict(self):
        """Profile should deserialize from dict."""
        d = {"name": "Test", "path": "F:/blender.exe"}

        profile = BlenderProfile.from_dict(d)

        assert profile.name == "Test"
        assert profile.path == "F:/blender.exe"

    def test_profile_defaults(self):
        """Profile should handle missing fields."""
        profile = BlenderProfile.from_dict({})

        assert profile.name == "Profile"
        assert profile.path != ""


class TestConfigPersistence:
    """Config persistence tests."""

    def test_save_and_load_jobs(self):
        """Jobs should persist through save/load."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
            blender_exec="F:/blender.exe",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")

            with patch("models.CONFIG_FILE", config_file):
                save_config([job], [])
                loaded, _ = load_config()

                assert len(loaded) == 1
                assert loaded[0].blend_file == job.blend_file

    def test_save_and_load_profiles(self):
        """Profiles should persist."""
        profile = BlenderProfile("Test", "F:/blender.exe")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")

            with patch("models.CONFIG_FILE", config_file):
                save_config([], [profile])
                _, loaded = load_config()

                assert len(loaded) == 1
                assert loaded[0].name == "Test"

    def test_load_missing_config(self):
        """Missing config should return defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "nonexistent.json")

            with patch("models.CONFIG_FILE", config_file):
                jobs, profiles = load_config()

                assert isinstance(jobs, list)
                assert len(profiles) > 0

    def test_load_corrupt_config(self):
        """Corrupt config should not crash."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            config_path = f.name

        try:
            with patch("models.CONFIG_FILE", config_path):
                jobs, profiles = load_config()

                assert isinstance(jobs, list)
                assert len(profiles) > 0
        finally:
            os.unlink(config_path)


class TestResolveBlenderExec:
    """resolve_blender_exec tests."""

    def test_resolve_from_profile(self):
        """Should resolve from named profile."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
            blender_profile="TestProfile",
        )

        profiles = [
            BlenderProfile("TestProfile", "F:/test_blender.exe"),
            BlenderProfile("Other", "F:/other.exe"),
        ]

        resolved = resolve_blender_exec(job, profiles)

        assert resolved == "F:/test_blender.exe"

    def test_resolve_from_job_path(self):
        """Should use job path if no profile."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
            blender_exec="F:/custom_blender.exe",
            blender_profile="",
        )

        profiles = [BlenderProfile("Test", "F:/default.exe")]

        resolved = resolve_blender_exec(job, profiles)

        assert resolved == "F:/custom_blender.exe"

    def test_resolve_fallback_to_default(self):
        """Should fall back to default."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
            blender_exec="",
            blender_profile="",
        )

        profiles = []

        resolved = resolve_blender_exec(job, profiles)

        assert resolved != ""


class TestJobToDict:
    """Job serialization tests."""

    def test_to_dict_basic(self):
        """to_dict should serialize basic fields."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=10,
            frame_end=100,
        )

        d = job.to_dict()

        assert d["blend_file"] == "test.blend"
        assert d["scene"] == "Scene"
        assert d["frame_start"] == 10
        assert d["frame_end"] == 100

    def test_to_dict_respects_null_fields(self):
        """Null fields should serialize correctly."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
            samples_override=None,
            resolution_pct=None,
            camera=None,
        )

        d = job.to_dict()

        assert d["samples_override"] is None
        assert d["resolution_pct"] is None


class TestJobFromDict:
    """Job deserialization tests."""

    def test_from_dict_basic(self):
        """from_dict should deserialize basic fields."""
        d = {
            "blend_file": "test.blend",
            "scene": "Scene",
            "output_path": "output",
            "frame_start": 10,
            "frame_end": 100,
            "job_id": 5,
            "blender_exec": "F:/blender.exe",
        }

        job = RenderJob.from_dict(d)

        assert job.blend_file == "test.blend"
        assert job.scene == "Scene"
        assert job.frame_start == 10
        assert job.frame_end == 100
        assert job.job_id == 5

    def test_from_dict_defaults(self):
        """from_dict should use defaults for missing fields."""
        d = {
            "blend_file": "test.blend",
            "job_id": 1,
            "blender_exec": "F:/blender.exe",
        }

        job = RenderJob.from_dict(d)

        assert job.scene == "Scene"
        assert job.frame_start == 1
        assert job.frame_end == 250

    def test_from_dict_running_becomes_error(self):
        """Running status should become Error on load."""
        d = {
            "blend_file": "test.blend",
            "scene": "Scene",
            "job_id": 1,
            "status": RenderJob.STATUS_RUNNING,
            "blender_exec": "F:/blender.exe",
        }

        job = RenderJob.from_dict(d)

        assert job.status == RenderJob.STATUS_ERROR


class TestJobResetBehavior:
    """Job reset behavior tests."""

    def test_reset_for_run(self):
        """reset_for_run should reset all runtime state."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
        )

        job.status = RenderJob.STATUS_ERROR
        job.progress = 50
        job.current_frame = 5
        job.elapsed_seconds = 100
        job._detected_device = "GPU"
        job._is_paused = True

        job.reset_for_run()

        assert job.status == RenderJob.STATUS_RUNNING
        assert job.progress == 0
        assert job.current_frame is None
        assert job.elapsed_seconds == 0.0
        assert job._detected_device is None
        assert job._is_paused is False
        assert job.start_time is not None


class TestStatusConstants:
    """Status constant tests."""

    def test_all_statuses_defined(self):
        """All statuses should be defined."""
        assert RenderJob.STATUS_PENDING == "Pending"
        assert RenderJob.STATUS_RUNNING == "Running"
        assert RenderJob.STATUS_PAUSED == "Paused"
        assert RenderJob.STATUS_DONE == "Done"
        assert RenderJob.STATUS_ERROR == "Error"
        assert RenderJob.STATUS_CANCELLED == "Cancelled"

    def test_statuses_unique(self):
        """Statuses should be unique."""
        statuses = {
            RenderJob.STATUS_PENDING,
            RenderJob.STATUS_RUNNING,
            RenderJob.STATUS_PAUSED,
            RenderJob.STATUS_DONE,
            RenderJob.STATUS_ERROR,
            RenderJob.STATUS_CANCELLED,
        }

        assert len(statuses) == 6


class TestDefaultBlenderProfiles:
    """Default profile tests."""

    def test_default_profiles_exist(self):
        """Should always have at least one profile."""
        profiles = default_blender_profiles()

        assert len(profiles) >= 1
        assert profiles[0].name == "Default"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
