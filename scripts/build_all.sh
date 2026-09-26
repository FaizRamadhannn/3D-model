#!/bin/sh
# Rebuild the whole scene from scratch: blockout -> materials/lights -> furniture.
cd "$(dirname "$0")/.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
"$B" -b -P scripts/build_house.py 2>&1 | grep -E "SAVED|Traceback|Error:|line [0-9]+"
"$B" -b rumah_36_72.blend -P scripts/stage2_materials.py 2>&1 | grep -E "STAGE2|Traceback|Error:|line [0-9]+"
"$B" -b rumah_36_72.blend -P scripts/stage3_furnish.py 2>&1 | grep -E "STAGE3|Traceback|Error:|line [0-9]+"
