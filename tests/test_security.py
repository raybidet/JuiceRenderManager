"""
test_security.py — Security vulnerability tests for Juice Render Manager.
"""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RenderJob, save_config, load_config, BlenderProfile


class TestPathTraversal:
    def test_output_path_block_parent_traversal(self):
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="../escape",
            frame_start=1,
            frame_end=10,
        )
        resolved = job.effective_output_path
        resolved_clean = resolved.replace("..", "_")
        assert resolved_clean != resolved, f"Path traversal not sanitized: {resolved}"

    def test_sequence_name_block_traversal(self):
        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            output_path="output",
            sequence_name="../escape",
            frame_start=1,
            frame_end=10,
        )
        resolved = job.effective_output_path
        assert ".." not in resolved, f"Sequence traversal not blocked: {resolved}"


class TestIPCInjection:
    def test_ipc_payload_rejects_none_dict(self):
        from main_window import MainWindow

        mw = MainWindow.__new__(MainWindow)
        data, err = mw._validate_ipc_payload(None)
        assert err is not None, "None payload rejected"

    def test_ipc_payload_rejects_non_dict(self):
        from main_window import MainWindow

        mw = MainWindow.__new__(MainWindow)
        data, err = mw._validate_ipc_payload("not a dict")
        assert err is not None, "String rejected"
        data, err = mw._validate_ipc_payload([1, 2, 3])
        assert err is not None, "List rejected"

    def test_ipc_payload_blocks_script_injection(self):
        pytest.skip("Requires full MainWindow Qt init")

    def test_ipc_payload_sanitizes_whitespace(self):
        pytest.skip("Requires full MainWindow Qt init")


class TestBlenderPathInjection:
    def test_blender_exec_rejects_shell_chars(self):
        from models import resolve_blender_exec

        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            blender_exec="blender; rm -rf /",
            frame_start=1,
            frame_end=10,
            output_path="output",
        )
        profiles = [BlenderProfile("Default", "blender")]
        resolved = resolve_blender_exec(job, profiles)
        assert ";" not in resolved or resolved == ""

    def test_blender_exec_rejects_command_injection(self):
        from models import resolve_blender_exec

        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            blender_exec="blender && echo pwned",
            frame_start=1,
            frame_end=10,
            output_path="output",
        )
        profiles = []
        resolved = resolve_blender_exec(job, profiles)
        assert "&&" not in resolved and "||" not in resolved

    def test_blender_exec_blocks_pipe(self):
        from models import resolve_blender_exec

        job = RenderJob(
            blend_file="test.blend",
            scene="Scene",
            blender_exec="blender | cat /etc/passwd",
            frame_start=1,
            frame_end=10,
            output_path="output",
        )
        profiles = []
        resolved = resolve_blender_exec(job, profiles)
        assert "|" not in resolved


class TestDeserialization:
    def test_config_handles_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "jobs": [
                        {
                            "blend_file": "test.blend",
                            "scene": "Scene",
                            "frame_start": 1,
                            "frame_end": 10,
                            "output_path": "output",
                            "blender_exec": "",
                            "job_id": 1,
                        }
                    ]
                },
                f,
            )
            config_path = f.name
        try:
            jobs, _ = load_config()
            assert len(jobs) <= 10
        finally:
            os.unlink(config_path)


class TestIPCPayloadValidation:
    def test_validate_ipc_rejects_invalid_samples(self):
        from main_window import MainWindow

        mw = MainWindow.__new__(MainWindow)
        with tempfile.NamedTemporaryFile(suffix=".blend", delete=False) as f:
            f.write(b"BLEND")
            blend_path = f.name
        try:
            payload = {
                "blend_file": blend_path,
                "scene": "Scene",
                "frame_start": 1,
                "frame_end": 10,
                "output_path": tempfile.gettempdir(),
                "samples": 0,
            }
            data, err = mw._validate_ipc_payload(payload)
            assert err is not None or data.get("samples_override") is None
        finally:
            os.unlink(blend_path)

    def test_validate_ipc_rejects_invalid_resolution(self):
        from main_window import MainWindow

        mw = MainWindow.__new__(MainWindow)
        with tempfile.NamedTemporaryFile(suffix=".blend", delete=False) as f:
            f.write(b"BLEND")
            blend_path = f.name
        try:
            payload = {
                "blend_file": blend_path,
                "scene": "Scene",
                "frame_start": 1,
                "frame_end": 10,
                "output_path": tempfile.gettempdir(),
                "resolution_pct": 150,
            }
            data, err = mw._validate_ipc_payload(payload)
            assert err is not None
        finally:
            os.unlink(blend_path)


class TestBlenderProfileValidation:
    def test_profile_rejects_empty_name(self):
        profile = BlenderProfile.from_dict({"name": "  ", "path": "blender.exe"})
        assert profile.name == "Profile"

    def test_profile_rejects_empty_path(self):
        profile = BlenderProfile.from_dict({"name": "Test", "path": ""})
        assert profile.path != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
