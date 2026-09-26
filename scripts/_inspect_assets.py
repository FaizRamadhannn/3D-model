import bpy, os, glob
from mathutils import Vector
root = os.path.join(os.path.dirname(bpy.data.filepath) or os.getcwd(), 'assets', 'models')
for d in sorted(os.listdir(root)):
    f = glob.glob(os.path.join(root, d, '*.blend'))[0]
    with bpy.data.libraries.load(f, link=False) as (src, dst):
        dst.objects = src.objects
    obs = [o for o in dst.objects if o is not None]
    mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3); meshes = 0
    for o in obs:
        if o.type != 'MESH': continue
        meshes += 1
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c); mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
    size = mx - mn
    print(f'ASSET {d:28s} obj={len(obs):3d} mesh={meshes:3d} size=({size.x:.2f},{size.y:.2f},{size.z:.2f}) min=({mn.x:.2f},{mn.y:.2f},{mn.z:.2f}) names={[o.name for o in obs][:4]}')
    for o in obs: bpy.data.objects.remove(o)
