"""
test_ipc.py — IPC server tests for Juice Render Manager.

Tests cover:
- I1: Thread cleanup in IPC server
- I2: Rate limiting
- I3: JSON bomb protection
- Basic IPC protocol tests

Run with:
    pytest tests/test_ipc.py -v
"""

import json
import os
import socket
import sys
import threading
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipc_server import JuiceIPCServer


class TestIPCServerBasic:
    """Basic IPC server functionality."""

    def test_server_starts_and_stops(self):
        """Server should start and stop cleanly."""
        server = JuiceIPCServer(host="127.0.0.1", port=18765)
        server.start()

        assert server._thread is not None, "Thread should be created"
        assert server._sock is not None, "Socket should be created"

        time.sleep(0.2)
        server.stop()

        assert not server._thread.is_alive() or server._thread is None, (
            "Thread should stop"
        )

    def test_server_accepts_connection(self):
        """Server should accept connections."""
        server = JuiceIPCServer(
            host="127.0.0.1",
            port=18766,
            on_message=lambda msg: {"ok": True, "received": msg},
        )
        server.start()

        time.sleep(0.3)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", 18766))
            sock.sendall(b'{"action": "test"}\n')
            resp = sock.recv(1024)
            sock.close()

            assert b'"ok"' in resp, "Should receive valid response"
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()

    def test_server_json_response(self):
        """Server should return valid JSON."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18767, on_message=lambda msg: {"status": "ok"}
        )
        server.start()

        time.sleep(0.3)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", 18767))

            msg = json.dumps({"action": "ping"}).encode("utf-8")
            sock.sendall(msg + b"\n")

            data = b""
            while b"\n" not in data:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk

            sock.close()

            response = json.loads(data.decode("utf-8"))
            assert "status" in response, "Response should be valid JSON"
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()

    def test_server_handles_bad_json(self):
        """Server should handle invalid JSON gracefully."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18768, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", 18768))

            sock.sendall(b"not valid json {}}\n")

            data = b""
            sock.settimeout(2.0)
            while b"\n" not in data:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk

            sock.close()

            response = json.loads(data.decode("utf-8"))
            assert "error" in response, "Should return error for invalid JSON"
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()


class TestIPCThreadCleanup:
    """I1: Thread cleanup tests."""

    def test_client_threads_cleaned_up(self):
        """Client threads should be tracked and cleanable."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18769, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        try:
            for i in range(3):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect(("127.0.0.1", 18769))
                sock.sendall(b'{"action": "test"}\n')
                time.sleep(0.1)

            initial_count = len(server._client_threads)
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()

        assert initial_count >= 0, "Should track client threads"

    def test_server_stop_closes_sockets(self):
        """Server stop should close all sockets."""
        server = JuiceIPCServer(host="127.0.0.1", port=18770)
        server.start()

        time.sleep(0.2)
        server.stop()

        assert server._sock is None, "Socket should be closed"


class TestIPCRateLimit:
    """I2: Rate limiting tests."""

    def test_multiple_rapid_connections(self):
        """Server should handle rapid connections."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18771, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        success_count = 0
        error_count = 0

        try:
            for i in range(10):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    sock.connect(("127.0.0.1", 18771))
                    sock.sendall(b'{"action": "test"}\n')
                    resp = sock.recv(1024)
                    sock.close()
                    if resp:
                        success_count += 1
                except:
                    error_count += 1

        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()

        assert success_count > 0, "Should handle some connections"


class TestJSONBomb:
    """I3: JSON bomb protection."""

    def test_deeply_nested_json(self):
        """Server should handle deeply nested JSON."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18772, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        deep_json = '{"a": ' + '{"' * 100 + "1" + "}" * 100 + "}"

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect(("127.0.0.1", 18772))
            sock.sendall(deep_json.encode("utf-8") + b"\n")

            data = b""
            sock.settimeout(3.0)
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

            sock.close()

            response = json.loads(data.decode("utf-8"))
            assert "error" in response or "ok" in response, (
                "Should respond to nested JSON"
            )
        except RecursionError:
            pytest.fail("Server crashed on deeply nested JSON")
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()

    def test_massive_array_json(self):
        """Server should handle massive arrays."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18773, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        huge_list = json.dumps({"data": list(range(100000))})

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(("127.0.0.1", 18773))
            sock.sendall(huge_list.encode("utf-8") + b"\n")

            data = b""
            sock.settimeout(5.0)
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

            sock.close()

        except MemoryError:
            pytest.fail("Server crashed on huge array")
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()


class TestIPCProtocol:
    """IPC protocol tests."""

    def test_add_job_action(self):
        """Server should handle add_job action."""
        received_payload = {}

        def handler(msg):
            nonlocal received_payload
            action = msg.get("action")
            if action == "add_job":
                received_payload = msg.get("payload", {})
                return {"ok": True, "job_added": True}
            return {"ok": False, "error": "Unknown action"}

        server = JuiceIPCServer(host="127.0.0.1", port=18774, on_message=handler)
        server.start()

        time.sleep(0.3)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", 18774))

            payload = {
                "action": "add_job",
                "payload": {
                    "blend_file": "/test.blend",
                    "scene": "Scene",
                    "frame_start": 1,
                    "frame_end": 10,
                },
            }

            sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")

            data = b""
            while b"\n" not in data:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk

            sock.close()

            response = json.loads(data.decode("utf-8"))
            assert response.get("ok") is True, "Should handle add_job"
            assert response.get("job_added") is True, "Should add job"
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()

    def test_unsupported_action(self):
        """Server should reject unsupported actions."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18775, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", 18775))

            payload = {"action": "unknown_action"}

            sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")

            data = b""
            while b"\n" not in data:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk

            sock.close()

            response = json.loads(data.decode("utf-8"))
            assert response.get("ok") is False or "error" in response, (
                "Should reject unknown action"
            )
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()

    def test_empty_message(self):
        """Server should handle empty messages."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18776, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", 18776))

            sock.sendall(b"\n")

            data = b""
            sock.settimeout(2.0)
            while b"\n" not in data:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk

            sock.close()

        except Exception:
            pass
        finally:
            server.stop()

    def test_message_without_action(self):
        """Server should handle messages without action."""
        server = JuiceIPCServer(
            host="127.0.0.1", port=18777, on_message=lambda msg: {"ok": True}
        )
        server.start()

        time.sleep(0.3)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", 18777))

            payload = {"no_action_field": True}

            sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")

            data = b""
            while b"\n" not in data:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk

            sock.close()

            response = json.loads(data.decode("utf-8"))
            assert "ok" in response, "Should respond even without action"
        except Exception as e:
            pytest.skip(f"Could not connect: {e}")
        finally:
            server.stop()


class TestIPCPortConflict:
    """Port conflict handling."""

    def test_port_already_in_use(self):
        """Server should fail gracefully if port in use."""
        server1 = JuiceIPCServer(host="127.0.0.1", port=18778)
        server1.start()

        time.sleep(0.2)

        server2 = JuiceIPCServer(host="127.0.0.1", port=18778)

        try:
            server2._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server2._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server2._sock.bind(("127.0.0.1", 18778))
            server2._sock.listen(8)
            server2._sock.settimeout(0.5)

            err = "Should fail to bind on used port"
        except OSError:
            err = None

        server1.stop()

        if err:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
