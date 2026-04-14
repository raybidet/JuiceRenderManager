import bpy
import sys

# Force minimal output
sys.stdout.write("SCRIPT_START\n")
sys.stdout.flush()

scenes = list(bpy.data.scenes.keys())
sys.stdout.write("SCENES:" + str(scenes) + "\n")
sys.stdout.flush()

for s in bpy.data.scenes:
    cams = [c.name for c in s.collection.all_objects if c.type == "CAMERA"]
    sys.stdout.write("CAM_" + s.name + ":" + str(cams) + "\n")
    sys.stdout.flush()

sys.stdout.write("SCRIPT_END\n")
sys.stdout.flush()
