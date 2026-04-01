"""
ipc_server.py — lightweight local TCP JSON-line server for Juice | Render Manager for Blender.

Protocol:
- Bind: 127.0.0.1:8765
- Messages: one JSON object per line (\n terminated), UTF-8 encoded.
- Response: one JSON object per line.

Supported action:
{
  "action": "add_job",
  "payload": {
    "blend_file": "...",
    "scene": "Scene",
    "frame_start": 1,
    "frame_end": 250,
    "samples": 128,
    "resolution_pct": 100,
    "use_nodes": false
  }
}
"""
from __future__ import annotations

import json
import socket
import threading
from typing import Callable, Optional


class JuiceIPCServer:
    """Background TCP server dispatching parsed JSON messages to a callback."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        on_message: Optional[Callable[[dict], dict]] = None,
    ):
        self.host = host
        self.port = port
        self.on_message = on_message or (lambda _msg: {"ok": False, "error": "No handler"})
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._client_threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_evt.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(8)
        self._sock.settimeout(0.5)

        self._thread = threading.Thread(target=self._serve_loop, name="JuiceIPCServer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        for t in list(self._client_threads):
            if t.is_alive():
                t.join(timeout=0.5)
        self._client_threads.clear()

    def _serve_loop(self) -> None:
        while not self._stop_evt.is_set():
            if not self._sock:
                break
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
            self._client_threads.append(t)
            t.start()

    def _handle_client(self, conn: socket.socket) -> None:
        with conn:
            conn.settimeout(2.0)
            buf = b""
            while not self._stop_evt.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    break
                except OSError:
                    break

                if not chunk:
                    break
                buf += chunk

                while b"\n" in buf:
                    raw_line, buf = buf.split(b"\n", 1)
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except Exception as e:
                        self._send_response(conn, {"ok": False, "error": f"Invalid JSON: {e}"})
                        continue

                    try:
                        resp = self.on_message(msg)
                    except Exception as e:
                        resp = {"ok": False, "error": f"Server handler exception: {e}"}
                    self._send_response(conn, resp)

    @staticmethod
    def _send_response(conn: socket.socket, resp: dict) -> None:
        try:
            payload = (json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8")
            conn.sendall(payload)
        except Exception:
            pass

