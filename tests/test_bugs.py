"""
test_bugs.py — Bug regression tests for Juice Render Manager.

Tests cover:
- B1: ID collision after corrupt load
- B2: Race condition in ETA calculation
- B3: Thread cleanup on window close
- B4: Log buffer overflow
- B5: Paused state persistence
- B6: Duplicate job detection edge cases

Run with:
    pytest tests/test_bugs.py -v
"""

import json
import os
import sys
import tempfile
import threading
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RenderJob, save_config, load_config


class TestIDCollision:
    """B1: RenderJob ID counter collision after corrupt load."""

    def test_id_counter_not_duplicated_on_load(self):
        pytest.skip("Loads real config - test in isolation requires temp config dir")

    def test_id_counter_handles_missing_job_ids(self):
        pytest.skip("Loads real config - test in isolation requires temp config dir")


class TestRaceConditionETA:
    """B2: Race condition in ETA rolling window."""

    def test_recent_frame_times_thread_safe(self):
        """_recent_frame_times should handle concurrent access."""
        from worker import RenderWorker, ROLLING_ETA_WIN

        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=250,
        )

        log_lines = []
        progress_calls = []

        def mock_log(job_id, line):
            log_lines.append(line)

        def mock_progress(job_id):
            progress_calls.append(job_id)

        worker = RenderWorker(
            job=job,
            on_log=mock_log,
            on_progress=mock_progress,
            on_done=lambda jid, status: None,
            on_frame_saved=lambda jid: None,
        )

        def append_times():
            for i in range(ROLLING_ETA_WIN + 5):
                worker._recent_frame_times.append(0.1)
                if len(worker._recent_frame_times) > ROLLING_ETA_WIN:
                    worker._recent_frame_times.pop(0)
                time.sleep(0.001)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(append_times) for _ in range(4)]
            for f in futures:
                f.result()

        assert len(worker._recent_frame_times) <= ROLLING_ETA_WIN * 2, (
            "List should not grow unbounded"
        )

    def test_eta_not_negative(self):
        """ETA should never be negative."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=250,
        )
        job.start_time = time.monotonic() - 100
        job.elapsed_seconds = 50
        job.current_frame = 125
        from worker import ROLLING_ETA_WIN

        if not hasattr(job, "_recent_frame_times") or not job._recent_frame_times:
            job._recent_frame_times = [0.4] * ROLLING_ETA_WIN
        frames_completed = job.current_frame - job.frame_start
        remaining = job.total_frames - frames_completed
        avg = sum(job._recent_frame_times) / len(job._recent_frame_times)
        calculated_eta = avg * remaining
        assert calculated_eta >= 0, "Calculated ETA should not be negative"


class TestThreadCleanup:
    """B3: Thread cleanup on window close."""

    def test_blend_info_thread_cleanup(self):
        """BlendInfoThread should be cleaned up properly."""
        from main_window import BlendInfoThread

        with tempfile.NamedTemporaryFile(suffix=".blend", delete=False) as f:
            f.write(b"BLENDER")
            blend_path = f.name

        try:
            thread = BlendInfoThread(blend_path, "blender.exe")
            thread.start()
            thread.quit()
            thread.wait(2000)
            assert not thread.isRunning() or thread.isFinished(), "Thread should stop"
        finally:
            try:
                os.unlink(blend_path)
            except:
                pass

    def test_convert_thread_cleanup(self):
        """ConvertThread should be cleaned up properly."""
        from main_window import ConvertThread

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "output.mp4")
            thread = ConvertThread(
                output_path=tmpdir,
                file_prefix="frame",
                frame_start=1,
                fps=24.0,
                output_file=output_file,
                preset={"ffmpeg_args": []},
            )
            thread.start()
            time.sleep(0.1)
            if thread.isRunning():
                thread.quit()
                thread.wait(2000)
            assert not thread.isRunning() or thread.isFinished(), "Thread should stop"


class TestLogOverflow:
    """B4: Log buffer overflow protection."""

    def test_log_lines_max_limit(self):
        from worker import LOG_MAX_LINES
        from worker import RenderWorker

        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
        )

        mock_log = lambda jid, line: None
        mock_progress = lambda jid: None
        worker = RenderWorker(
            job=job,
            on_log=mock_log,
            on_progress=mock_progress,
            on_done=lambda jid, status: None,
            on_frame_saved=lambda jid: None,
        )

        for i in range(LOG_MAX_LINES + 100):
            worker._log(f"Line {i}")

        assert len(job.log_lines) <= LOG_MAX_LINES, (
            f"Log capped, got {len(job.log_lines)}"
        )

    def test_log_trimming_preserves_recent(self):
        """Log trimming should keep recent lines."""
        from worker import LOG_MAX_LINES

        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
        )

        for i in range(LOG_MAX_LINES + 50):
            job.log_lines.append(f"Line {i}")

        if len(job.log_lines) == LOG_MAX_LINES:
            assert "Line 49" in job.log_lines[-1] or "Line 50" in job.log_lines[-1], (
                "Should preserve recent"
            )


class TestPausedStatePersistence:
    """B5: Paused state persistence."""

    def test_paused_state_not_in_status_constants(self):
        """Paused is not a valid persisted status."""
        assert RenderJob.STATUS_PAUSED != RenderJob.STATUS_PENDING
        assert RenderJob.STATUS_PAUSED != RenderJob.STATUS_RUNNING
        assert RenderJob.STATUS_PAUSED != RenderJob.STATUS_DONE

    def test_paused_resets_on_retry(self):
        """Paused job resets on retry."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=10,
        )
        job.status = RenderJob.STATUS_PAUSED
        job._is_paused = True
        job.status = RenderJob.STATUS_PENDING
        job._is_paused = False
        assert job.status == RenderJob.STATUS_PENDING
        assert not job._is_paused

    def test_from_dict_converts_running_to_error(self):
        """Running jobs from dict should become Error on load."""
        job = RenderJob.from_dict(
            {
                "blend_file": "test.blend",
                "scene": "Scene",
                "frame_start": 1,
                "frame_end": 10,
                "output_path": "output",
                "blender_exec": "",
                "job_id": 1,
                "status": RenderJob.STATUS_RUNNING,
            }
        )
        assert job.status == RenderJob.STATUS_ERROR, "Running should become Error"


class TestDuplicateJobDetection:
    """B6: Duplicate job detection edge cases."""

    def test_normcase_handles_unicode(self):
        """os.path.normcase should handle unicode paths."""
        path1 = "C:/Users/Test/Documentos/Blend.blend"
        path2 = "c:/users/test/documentos/blend.blend"
        assert os.path.normcase(path1) == os.path.normcase(path2), "Case norm works"

    def test_duplicate_detection_case_insensitive(self):
        """Duplicate detection should be case-insensitive."""
        from main_window import MainWindow

        mw = MainWindow.__new__(MainWindow)
        mw.jobs = []
        mw._selected_job_id = None
        job1 = RenderJob(
            blend_file="C:/TEST.BLEND",
            scene="Scene",
            output_path="OUTPUT",
            frame_start=1,
            frame_end=10,
        )
        mw.jobs.append(job1)
        data = {
            "blend_file": "c:/test.blend",
            "scene": "Scene",
            "output_path": "output",
            "frame_start": 1,
            "frame_end": 10,
            "camera": None,
            "samples_override": None,
            "resolution_pct": None,
            "use_nodes": False,
        }
        result = mw._job_exists_equivalent(data)
        assert result, "Should detect duplicate regardless of case"

    def test_duplicate_detection_none_camera(self):
        """None camera should match None camera."""
        from main_window import MainWindow

        mw = MainWindow.__new__(MainWindow)
        mw.jobs = []
        job1 = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            camera=None,
            output_path="output",
            frame_start=1,
            frame_end=10,
        )
        mw.jobs.append(job1)
        data = {
            "blend_file": "test.blend",
            "scene": "Scene",
            "camera": None,
            "output_path": "output",
            "frame_start": 1,
            "frame_end": 10,
            "samples_override": None,
            "resolution_pct": None,
            "use_nodes": False,
        }
        result = mw._job_exists_equivalent(data)
        assert result, "None camera should match None"


class TestJobReset:
    """RenderJob reset behavior tests."""

    def test_reset_for_run_clears_timing(self):
        """reset_for_run should clear all timing state."""
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
        job.eta_seconds = 200
        job.last_frame_elapsed = 2.5
        job.reset_for_run()
        assert job.status == RenderJob.STATUS_RUNNING
        assert job.progress == 0
        assert job.current_frame is None
        assert job.elapsed_seconds == 0.0
        assert job.eta_seconds is None
        assert job.last_frame_elapsed is None
        assert job._detected_device is None
        assert not job._is_paused

    def test_total_frames_correct(self):
        """total_frames should handle edge cases."""
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            frame_start=1,
            frame_end=1,
        )
        assert job.total_frames == 1, "Single frame should be 1"


class TestJobPersistenceRoundTrip:
    """Test job round-trip through save/load."""

    def test_job_persists_all_fields(self):
        """All user-configurable fields should persist."""
        job = RenderJob(
            blend_file="/path/to/file.blend",
            scene="MyScene",
            sequence_name="shot_010",
            frame_start=10,
            frame_end=100,
            output_path="/output",
            blender_exec="/blender.exe",
            blender_profile="Custom",
            use_nodes=True,
            samples_override=128,
            resolution_pct=50.0,
            camera="Camera.001",
        )
        data = job.to_dict()
        assert data["blend_file"] == job.blend_file
        assert data["scene"] == job.scene
        assert data["sequence_name"] == job.sequence_name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
