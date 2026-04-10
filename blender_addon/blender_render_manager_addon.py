bl_info = {
    "name": "Juice | Render Manager for Blender Sender",
    "author": "BRM Integration",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BRM",
    "description": "Send current scene render settings to Juice | Render Manager for Blender",
    "category": "Render",
}

import bpy
import json
import socket
import subprocess
import sys
import time
from bpy.props import StringProperty, IntProperty


def _collect_payload(context):
    scene = context.scene
    samples = None
    if hasattr(scene, "cycles") and hasattr(scene.cycles, "samples"):
        try:
            samples = int(scene.cycles.samples)
        except Exception:
            samples = None

    return {
        "action": "add_job",
        "payload": {
            "blend_file": bpy.data.filepath or "",
            "scene": scene.name,
            "frame_start": int(scene.frame_start),
            "frame_end": int(scene.frame_end),
            "samples": samples,
            "resolution_pct": float(scene.render.resolution_percentage),
            "use_nodes": bool(scene.use_nodes),
            "sequence_name": "",
            "output_path": "",
        },
    }


def _send_json_line(host, port, data, timeout=1.5):
    raw = (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")
    with socket.create_connection((host, int(port)), timeout=timeout) as s:
        s.sendall(raw)
        s.settimeout(timeout)
        resp = b""
        while b"\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
    line = resp.split(b"\n", 1)[0].decode("utf-8").strip() if resp else ""
    if not line:
        return {"ok": False, "error": "Empty response"}
    try:
        return json.loads(line)
    except Exception as e:
        return {"ok": False, "error": f"Invalid response JSON: {e}"}


def _launch_brm(executable_path):
    if executable_path:
        cmd = [bpy.path.abspath(executable_path)]
    else:
        cmd = [sys.executable, bpy.path.abspath("//app.py")]
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0)


class BRMProperties(bpy.types.PropertyGroup):
    host: StringProperty(name="Host", default="127.0.0.1")
    port: IntProperty(name="Port", default=8765, min=1, max=65535)
    brm_path: StringProperty(
        name="BRM Executable/Python Script",
        subtype="FILE_PATH",
        default="",
        description="Path to Juice | Render Manager for Blender executable or app.py",
    )


class BRM_OT_SendToManager(bpy.types.Operator):
    bl_idname = "brm.send_to_manager"
    bl_label = "Send to Juice | Render Manager for Blender"
    bl_description = "Send current file/scene settings to Juice (opens Juice if needed)"

    def execute(self, context):
        props = context.scene.brm_props
        payload = _collect_payload(context)

        if not payload["payload"]["blend_file"]:
            self.report({"ERROR"}, "Guarda el .blend antes de enviar.")
            return {"CANCELLED"}

        # First attempt
        try:
            resp = _send_json_line(props.host, props.port, payload, timeout=1.5)
            if resp.get("ok"):
                self.report({"INFO"}, "Job enviado a Juice | Render Manager for Blender")
                return {"FINISHED"}
        except Exception:
            resp = {"ok": False}

        # Launch BRM and retry
        try:
            _launch_brm(props.brm_path)
        except Exception as e:
            self.report({"ERROR"}, f"No se pudo abrir BRM: {e}")
            return {"CANCELLED"}

        time.sleep(2.0)
        for _ in range(6):
            try:
                resp = _send_json_line(props.host, props.port, payload, timeout=1.5)
                if resp.get("ok"):
                    self.report({"INFO"}, "BRM abierto y job enviado.")
                    return {"FINISHED"}
            except Exception:
                pass
            time.sleep(1.0)

        self.report({"ERROR"}, "No se pudo conectar a BRM tras abrirlo.")
        return {"CANCELLED"}


class BRM_PT_Panel(bpy.types.Panel):
    bl_label = "Juice | Render Manager for Blender"
    bl_idname = "BRM_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BRM"

    def draw(self, context):
        layout = self.layout
        props = context.scene.brm_props
        scene = context.scene

        col = layout.column(align=True)
        col.label(text=f"Blend: {bpy.path.basename(bpy.data.filepath) or '(unsaved)'}")
        col.label(text=f"Scene: {scene.name}")
        col.label(text=f"Frames: {scene.frame_start} - {scene.frame_end}")

        samples_txt = "N/A"
        if hasattr(scene, "cycles") and hasattr(scene.cycles, "samples"):
            samples_txt = str(scene.cycles.samples)
        col.label(text=f"Samples: {samples_txt}")
        col.label(text=f"Resolution %: {scene.render.resolution_percentage}")
        col.label(text=f"Compositing Nodes: {'ON' if scene.use_nodes else 'OFF'}")

        layout.separator()
        layout.prop(props, "host")
        layout.prop(props, "port")
        layout.prop(props, "brm_path")
        layout.operator("brm.send_to_manager", icon="EXPORT")


classes = (
    BRMProperties,
    BRM_OT_SendToManager,
    BRM_PT_Panel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.brm_props = bpy.props.PointerProperty(type=BRMProperties)


def unregister():
    if hasattr(bpy.types.Scene, "brm_props"):
        del bpy.types.Scene.brm_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
