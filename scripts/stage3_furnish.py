"""Stage 3: replace the blockout boxes with real assets and modelled furniture.
Run:  blender -b rumah_36_72.blend -P stage3_furnish.py
Coordinates: plan (x, z) as in the floor plan; Blender Y = -z.
"""
import bpy, bmesh, os, glob, math, re, random
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
MODELS = os.path.join(ROOT, 'assets', 'models')
TEX = os.path.join(ROOT, 'assets', 'textures')
PI, P2 = math.pi, math.pi / 2
FACE = {'ny': 0.0, 'px': P2, 'py': PI, 'nx': -P2}   # asset front is -Y

sc = bpy.context.scene
C_UNIT = bpy.data.collections['Unit']
C_INT = bpy.data.collections['Interior']
C_SITE = bpy.data.collections['Site']
LC = bpy.data.collections['Lights']
MAT = bpy.data.materials

# ------------------------------------------------------------ clean previous runs / blockout
for name in ['Sofa', 'CoffeeTable', 'TVConsole', 'TV', 'DiningTable', 'Counter', 'Bed1', 'Bed1_head', 'Wardrobe1', 'Bed2', 'Bed2_head',
             'Wardrobe2', 'Toilet', 'Vanity', 'ShowerGlass', 'Car'] + [f'PlantPH{i}' for i in range(10)]:
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob)
for cname in ['AssetLib', 'Furnish', 'Garden', 'Landscape']:
    c = bpy.data.collections.get(cname)
    if c:
        for ob in list(c.all_objects):
            bpy.data.objects.remove(ob)
        for ch in list(c.children_recursive):
            bpy.data.collections.remove(ch)
        bpy.data.collections.remove(c)
for ob in [o for o in LC.objects if o.get('stage') == 3]:
    bpy.data.objects.remove(ob)

def coll(name, parent):
    c = bpy.data.collections.new(name); parent.children.link(c); return c
LIB = coll('AssetLib', sc.collection)
FURN = coll('Furnish', C_INT)
GARDEN = coll('Garden', C_UNIT)       # repeats on the neighbours
LAND = coll('Landscape', C_SITE)
sc.view_layers[0].layer_collection.children['AssetLib'].exclude = True

# ------------------------------------------------------------ asset loading
def load_asset(aid, keep=None, key=None):
    """Append a Poly Haven .blend. Its variants sit side by side in the source file, so objects are grouped
    by location and every group becomes its own library collection. Returns the list of variant collections."""
    key = key or aid
    if key in VARIANTS:
        return VARIANTS[key]
    path = glob.glob(os.path.join(MODELS, aid, '*.blend'))[0]
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if (keep(n) if keep else ('LOD' not in n or 'LOD0' in n))]
    groups = {}
    for ob in dst.objects:
        if ob is None or ob.type not in ('MESH', 'EMPTY', 'CURVE'):
            continue
        k = (round(ob.location.x, 1), round(ob.location.y, 1))
        groups.setdefault(k, []).append(ob)
    out = []
    for i, (k, obs) in enumerate(sorted(groups.items(), key=lambda kv: math.hypot(*kv[0]))):
        c = bpy.data.collections.new(f'{key}_{i}'); LIB.children.link(c)
        mn, mx = Vector((1e9,) * 3), Vector((-1e9,) * 3)
        for ob in obs:
            c.objects.link(ob)
            if ob.type == 'MESH':
                for v in ob.bound_box:
                    w = ob.matrix_basis @ Vector(v); mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
        c.instance_offset = ((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z)
        out.append(c)
    for im in bpy.data.images:
        if im.filepath and not os.path.exists(bpy.path.abspath(im.filepath)):
            cand = glob.glob(os.path.join(MODELS, '*', 'textures', os.path.basename(im.filepath)))
            if cand:
                im.filepath = cand[0]
    VARIANTS[key] = out
    return out
VARIANTS = {}

def place(asset, x, z, face='ny', scale=1.0, h=0.0, parent=FURN, name=None, tilt=0.0, variant=0):
    vs = asset if isinstance(asset, list) else load_asset(asset)
    c = vs[variant % len(vs)]
    e = bpy.data.objects.new(name or f'{c.name}_inst', None)
    e.instance_type = 'COLLECTION'; e.instance_collection = c
    e.location = (x, -z, h)
    e.rotation_euler = (0, tilt, FACE[face] if isinstance(face, str) else face)
    e.scale = scale if isinstance(scale, tuple) else (scale,) * 3
    parent.objects.link(e)
    return e

# ------------------------------------------------------------ modelling helpers
def world_uv(me):
    uv = me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        n = p.normal
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.7:
                u, v = co.x, co.y
            elif abs(n.x) > abs(n.y):
                u, v = co.y, co.z
            else:
                u, v = co.x, co.z
            uv.data[li].uv = (u, v)

def finish(ob, material, bevel=0.0, seg=3, parent=FURN, smooth=True):
    me = ob.data
    world_uv(me)
    if isinstance(material, (list, tuple)):
        for m in material:
            me.materials.append(m)
    else:
        me.materials.append(material)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if bevel:
        b = ob.modifiers.new('Bevel', 'BEVEL'); b.width = bevel; b.segments = seg; b.limit_method = 'ANGLE'; b.harden_normals = True
    parent.objects.link(ob)
    return ob

def cube(name, x0, x1, z0, z1, h0, h1, material, bevel=0.0, seg=3, parent=FURN):
    """Box in plan coordinates with optional rounded edges."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
        v.co.y = -z1 + (v.co.y + 0.5) * (z1 - z0)
        v.co.z = h0 + (v.co.z + 0.5) * (h1 - h0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return finish(bpy.data.objects.new(name, me), material, bevel, seg, parent)

def cyl(name, x, z, r, h0, h1, material, n=32, bevel=0.0, parent=FURN, sx=1.0, sy=1.0, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=r, radius2=r if r2 is None else r2, depth=h1 - h0)
    for v in bm.verts:
        v.co.x = x + v.co.x * sx; v.co.y = -z + v.co.y * sy; v.co.z += (h0 + h1) / 2
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return finish(bpy.data.objects.new(name, me), material, bevel, 3, parent)

def prism(name, profile, x0, x1, material, bevel=0.0, seg=3, parent=FURN):
    """Extrude a (y, z) profile (Blender local) between x0 and x1."""
    n = len(profile)
    v = [(x0, y, zz) for y, zz in profile] + [(x1, y, zz) for y, zz in profile]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    me = bpy.data.meshes.new(name); me.from_pydata(v, [], f)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    return finish(bpy.data.objects.new(name, me), material, bevel, seg, parent)

def curtain(name, x0, x1, z0, z1, h0, h1, folds=6, depth=0.035):
    """Wavy sheer curtain panel between two plan points."""
    N = 60; v = []; f = []
    for i in range(N + 1):
        t = i / N
        x = x0 + (x1 - x0) * t; z = z0 + (z1 - z0) * t
        off = math.sin(t * folds * 2 * PI) * depth
        dx, dz = (z1 - z0), -(x1 - x0); L = math.hypot(dx, dz) or 1
        v += [(x + dx / L * off, -(z + dz / L * off), h0), (x + dx / L * off, -(z + dz / L * off), h1)]
    for i in range(N):
        f.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    me = bpy.data.meshes.new(name); me.from_pydata(v, [], f)
    return finish(bpy.data.objects.new(name, me), curtain_mat)

def light(name, kind, loc, energy, color=(1.0, 0.76, 0.52), size=0.05, spot=None, rot=(0, 0, 0)):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
    if kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = size
    if kind == 'AREA':
        ld.shape = 'RECTANGLE'; ld.size, ld.size_y = size
    if spot:
        ld.spot_size = math.radians(spot); ld.spot_blend = 0.7
    ob = bpy.data.objects.new(name, ld); ob.location = (loc[0], -loc[1], loc[2]); ob.rotation_euler = rot
    ob['stage'] = 3; LC.objects.link(ob); return ob

def pmat(name, rgb, rough=0.5, metal=0.0, emit=None, coat=0.0, trans=0.0):
    m = MAT.get(name) or MAT.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if coat:
        b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = 0.03
    if emit:
        b.inputs['Emission Color'].default_value = (*emit[0], 1); b.inputs['Emission Strength'].default_value = emit[1]
    if trans:
        b.inputs['Transmission Weight'].default_value = trans
    return m

def tinted(src, name, rgb):
    """Copy a textured material and multiply its colour."""
    m = MAT.get(name)
    if m:
        return m
    m = MAT[src].copy(); m.name = name
    nt = m.node_tree
    hs = [n for n in nt.nodes if n.type == 'HUE_SAT']
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1
    bsdf = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    link = bsdf.inputs['Base Color'].links[0]
    nt.links.new(link.from_socket, mix.inputs[6]); mix.inputs[7].default_value = (*rgb, 1)
    nt.links.new(mix.outputs[2], bsdf.inputs['Base Color'])
    return m

oak, walnut, fab, olive = MAT['Oak'], MAT['Walnut'], MAT['FabricBeige'], MAT['FabricOlive']
white = pmat('Lacquer', (0.86, 0.85, 0.82), 0.35)
quartz = pmat('Quartz', (0.90, 0.89, 0.86), 0.12, coat=0.3)
ceramic = pmat('Ceramic', (0.93, 0.93, 0.91), 0.06, coat=0.6)
blackmat = pmat('MatteBlack', (0.02, 0.02, 0.022), 0.45, 0.6)
steel = pmat('Steel', (0.75, 0.76, 0.77), 0.22, 1.0)
mirror = pmat('Mirror', (0.95, 0.95, 0.95), 0.0, 1.0)
screen = pmat('Screen', (0.005, 0.005, 0.006), 0.05, 0.0, coat=1.0)
ledw = pmat('LEDStrip', (1, 0.9, 0.8), 0.5, emit=((1.0, 0.8, 0.55), 6.0))
shade = pmat('LampShade', (0.95, 0.9, 0.82), 0.9, trans=0.4, emit=((1.0, 0.78, 0.5), 1.2))
curtain_mat = pmat('CurtainSheer', (0.93, 0.9, 0.85), 0.9, trans=0.45)
sheet = tinted('FabricBeige', 'Sheet', (1.08, 1.08, 1.1))
jute = tinted('FabricBeige', 'Jute', (0.72, 0.58, 0.40))
rugmat = tinted('FabricBeige', 'RugGrey', (0.78, 0.76, 0.72))
headb = tinted('FabricBeige', 'Headboard', (0.86, 0.80, 0.70))

# ============================================================ LIVING ROOM
# oak slat wall behind the TV (like the reference)
z = 2.9
while z < 4.5:
    cube('Slat', 3.075, 3.1, z, z + 0.045, 0, 2.98, oak, 0.003)
    z += 0.075
cube('SlatBack', 3.075, 3.079, 2.9, 4.5, 0, 2.98, walnut)
place('modern_wooden_cabinet', 3.29, 3.7, 'px', (0.6, 0.6, 0.62), name='TVConsole')
cube('TV', 3.1, 3.14, 3.12, 4.28, 1.08, 1.75, blackmat, 0.004)
cube('TVScreen', 3.141, 3.142, 3.14, 4.26, 1.1, 1.73, screen)
place('sofa_03', 5.47, 4.6, 'nx', (0.64, 0.93, 0.82), name='Sofa')
for ob in VARIANTS['sofa_03'][0].objects:
    if ob.type == 'MESH':
        ob.data.materials.clear(); ob.data.materials.append(tinted('FabricBeige', 'SofaFabric', (0.95, 0.92, 0.87)))
place('throw_pillows_01', 5.62, 3.95, 'nx', 0.9, h=0.42, name='Pillows1')
place('throw_pillows_01', 5.62, 5.25, 'nx', 0.9, h=0.42, name='Pillows2')
for i, ob in enumerate(o for c in VARIANTS['throw_pillows_01'] for o in c.objects if o.type == 'MESH'):
    ob.data.materials.clear(); ob.data.materials.append(olive if i % 2 else tinted('FabricBeige', 'PillowCream', (1.0, 0.97, 0.9)))
place('modern_coffee_table_01', 4.3, 4.55, 'px', 0.82, name='CoffeeTable')
place('ceramic_vase_01', 4.3, 4.35, 'ny', 0.6, h=0.32)
place('decorative_book_set_01', 4.25, 4.8, 'px', 0.8, h=0.32, tilt=P2)
cube('RugLiving', 3.55, 5.35, 3.55, 5.6, 0.0, 0.012, rugmat, 0.004)
place('pachira_aquatica_01', 5.6, 5.75, 'nx', 0.95, name='TreeIndoor')
place('hanging_picture_frame_01', 5.915, 4.6, 'nx', (1.0, 1.0, 0.8), h=1.65)
curtain('CurtainLivingL', 3.6, 4.02, 5.86, 5.86, 0.02, 2.62)
curtain('CurtainLivingR', 5.43, 5.9, 5.86, 5.86, 0.02, 2.62)
cube('CurtainRod', 3.55, 5.92, 5.84, 5.87, 2.62, 2.64, blackmat)

# ============================================================ DINING + KITCHEN
place('round_wooden_table_01', 4.3, 2.95, 'ny', (0.57, 0.57, 0.74), name='DiningTable')
place('dining_chair_02', 4.3, 2.43, 'ny', 1.0)
place('dining_chair_02', 4.3, 3.5, 'py', 1.0)
place('modern_ceiling_lamp_01', 4.3, 2.95, 'ny', 1.0, h=3.0 - 1.17, name='Pendant')
light('Pendant_bulb', 'POINT', (4.3, 2.95, 1.95), 25, size=0.08)
place('potted_plant_04', 4.3, 2.95, 'ny', 1.0, h=0.745)
# base cabinets with oak fronts
cube('Plinth', 3.9, 5.925, 1.62, 2.12, 0, 0.1, blackmat)
cube('BaseCarcass', 3.9, 5.925, 1.575, 2.13, 0.1, 0.86, white)
x = 3.9
for w in (0.5, 0.5, 0.5, 0.525):
    cube('BaseDoor', x + 0.003, x + w - 0.003, 2.13, 2.15, 0.105, 0.855, oak, 0.003)
    cube('BaseHandle', x + w / 2 - 0.08, x + w / 2 + 0.08, 2.15, 2.165, 0.8, 0.812, blackmat)
    x += w
cube('Worktop', 3.88, 5.925, 1.575, 2.19, 0.86, 0.9, quartz, 0.004)
cube('Sink', 4.28, 4.72, 1.72, 2.08, 0.8, 0.901, steel, 0.01)
cyl('FaucetBase', 4.5, 1.66, 0.022, 0.9, 1.2, blackmat, 20)
cube('FaucetSpout', 4.49, 4.51, 1.66, 1.86, 1.18, 1.2, blackmat, 0.004)
cube('Cooktop', 5.1, 5.7, 1.63, 2.1, 0.9, 0.906, screen, 0.004)
for cx, cz in ((5.25, 1.75), (5.55, 1.95)):
    cyl('Burner', cx, cz, 0.09, 0.906, 0.907, blackmat, 32)
cube('Hood', 5.1, 5.7, 1.575, 2.05, 1.62, 1.72, steel, 0.005)
cube('HoodChimney', 5.3, 5.5, 1.575, 1.8, 1.72, 3.0, steel, 0.003)
cube('UpperCab', 3.9, 4.08, 1.575, 1.93, 1.5, 2.4, oak, 0.004)
cube('UpperCabR', 5.72, 5.925, 1.575, 1.93, 1.5, 2.4, oak, 0.004)
cube('UnderLED', 5.72, 5.9, 1.6, 1.62, 1.49, 1.5, ledw)
place('potted_plant_04', 4.05, 1.72, 'ny', 1.0, h=0.9)
place('ceramic_vase_01', 5.83, 1.72, 'ny', 0.55, h=0.9)
light('KitchenUnder', 'AREA', (4.9, 1.8, 2.35), 30, size=(1.9, 0.3))

# ============================================================ BEDROOMS
def bedroom(tag, zc, rug_round=False):
    """Queen bed against the party wall (x=0), headboard + slat panel, nightstand, wardrobe."""
    z0, z1 = zc - 0.78, zc + 0.78
    cube(f'{tag}_panel', 0.075, 0.1, z0 - 0.35, z1 + 0.35, 0, 1.25, oak, 0.002)
    cube(f'{tag}_headboard', 0.1, 0.2, z0 - 0.05, z1 + 0.05, 0.25, 1.15, headb, 0.035, 4)
    cube(f'{tag}_frame', 0.2, 2.2, z0, z1, 0.08, 0.34, oak, 0.015)
    for a in (0.3, 2.1):
        for b in (z0 + 0.08, z1 - 0.08):
            cube(f'{tag}_leg', a - 0.03, a + 0.03, b - 0.03, b + 0.03, 0, 0.08, blackmat)
    cube(f'{tag}_mattress', 0.22, 2.18, z0 + 0.02, z1 - 0.02, 0.34, 0.58, sheet, 0.06, 5)
    cube(f'{tag}_duvet', 0.85, 2.21, z0 - 0.01, z1 + 0.01, 0.56, 0.64, sheet, 0.04, 4)
    cube(f'{tag}_runner', 1.6, 1.95, z0 - 0.03, z1 + 0.03, 0.62, 0.66, olive, 0.02, 3)
    for pz in (zc - 0.38, zc + 0.38):
        cube(f'{tag}_pillow', 0.24, 0.6, pz - 0.33, pz + 0.33, 0.58, 0.8, sheet, 0.08, 5)
    p = cube(f'{tag}_cushion', 0.52, 0.72, zc - 0.22, zc + 0.22, 0.6, 0.9, olive, 0.06, 5)
    return z0, z1

z0, z1 = bedroom('Bed1', 2.95)
cube('NS1', 0.08, 0.5, 1.63, 2.08, 0.1, 0.52, oak, 0.01)
cube('NS1_drawer', 0.5, 0.505, 1.66, 2.05, 0.3, 0.48, walnut)
cyl('Lamp1_base', 0.28, 1.86, 0.07, 0.52, 0.72, ceramic, 32, 0.01)
cyl('Lamp1_shade', 0.28, 1.86, 0.13, 0.72, 0.92, shade, 32, r2=0.11)
light('Lamp1', 'POINT', (0.28, 1.86, 0.82), 12, size=0.06)
cube('Wardrobe1', 0.1, 1.95, 3.955, 4.425, 0, 2.45, oak, 0.004)
for xx in (0.72, 1.34):
    cube('W1_gap', xx - 0.002, xx + 0.002, 3.945, 3.956, 0.02, 2.43, blackmat)
for xx in (0.64, 0.8, 1.26, 1.42):
    cube('W1_handle', xx - 0.008, xx + 0.008, 3.93, 3.945, 0.9, 1.3, blackmat)
place('hanging_picture_frame_01', 0.105, 2.95, 'px', (0.9, 1.0, 0.65), h=1.85)
curtain('CurtainBed1L', 1.7, 2.15, 1.64, 1.64, 0.9, 2.62)
curtain('CurtainBed1R', 2.85, 2.95, 1.64, 1.64, 0.9, 2.62)
cube('RodBed1', 1.65, 2.95, 1.62, 1.65, 2.62, 2.64, blackmat)
cyl('RugBed1', 1.9, 2.95, 1.0, 0, 0.012, rugmat, 64)
place('potted_plant_02', 2.6, 1.85, 'ny', 0.8)

z0, z1 = bedroom('Bed2', 7.6)
cube('Wardrobe2', 0.1, 1.95, 6.075, 6.545, 0, 2.45, oak, 0.004)
for xx in (0.72, 1.34):
    cube('W2_gap', xx - 0.002, xx + 0.002, 6.544, 6.555, 0.02, 2.43, blackmat)
for xx in (0.64, 0.8, 1.26, 1.42):
    cube('W2_handle', xx - 0.008, xx + 0.008, 6.555, 6.57, 0.9, 1.3, blackmat)
cube('NS2', 0.08, 0.5, 8.45, 8.85, 0.1, 0.5, oak, 0.01)
cyl('Lamp2_base', 0.28, 8.65, 0.06, 0.5, 0.68, ceramic, 32, 0.01)
cyl('Lamp2_shade', 0.28, 8.65, 0.12, 0.68, 0.86, shade, 32, r2=0.1)
light('Lamp2', 'POINT', (0.28, 8.65, 0.77), 12, size=0.06)
cyl('RugBed2', 1.9, 7.6, 0.85, 0, 0.012, jute, 64)
place('potted_plant_01', 2.35, 8.1, 'ny', 0.85)
curtain('CurtainBed2', 0.08, 0.35, 8.95, 8.95, 0.25, 2.8)
place('hanging_picture_frame_01', 0.105, 7.6, 'px', (0.9, 1.0, 0.65), h=1.85)

# ============================================================ BATHROOM
bath_wall = MAT['BathTile']
cube('BathWall_L', 0.075, 0.085, 4.575, 5.925, 0, 2.6, bath_wall)
cube('BathWall_B', 0.075, 2.0, 4.575, 4.585, 0, 2.6, bath_wall)
cube('BathWall_F', 0.075, 2.0, 5.915, 5.925, 0, 2.6, bath_wall)
cube('BathWall_R', 1.995, 2.005, 4.575, 4.97, 0, 2.6, bath_wall)
# wall-hung toilet
cube('WC_tank_box', 0.085, 0.22, 4.72, 5.18, 0, 1.05, bath_wall)
cube('WC_flush', 0.219, 0.222, 4.88, 5.02, 0.9, 1.0, blackmat, 0.004)
cyl('WC_bowl', 0.47, 4.95, 0.19, 0.3, 0.42, ceramic, 48, 0.03, sx=1.35)
cube('WC_back', 0.22, 0.32, 4.8, 5.1, 0.3, 0.42, ceramic, 0.03)
cyl('WC_seat', 0.47, 4.95, 0.195, 0.42, 0.45, ceramic, 48, 0.012, sx=1.35)
# floating vanity + vessel basin + round mirror
cube('Vanity', 1.1, 1.8, 4.585, 5.05, 0.55, 0.85, walnut, 0.01)
cyl('Basin', 1.45, 4.82, 0.2, 0.85, 0.97, ceramic, 48, 0.02, sy=0.8)
cyl('BasinTap', 1.45, 4.62, 0.012, 0.97, 1.13, blackmat, 16)
cube('BasinSpout', 1.44, 1.46, 4.62, 4.74, 1.11, 1.13, blackmat)
bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=64, radius=0.34)
for v in bm.verts:
    v.co = Vector((1.45 + v.co.x, -4.59, 1.62 + v.co.y))
me = bpy.data.meshes.new('MirrorDisk'); bm.to_mesh(me); bm.free()
finish(bpy.data.objects.new('Mirror', me), mirror, smooth=False)
# shower
cube('ShowerGlass', 0.085, 0.92, 5.26, 5.27, 0.02, 2.05, MAT['Glass'])
cube('ShowerFrameTop', 0.085, 0.92, 5.255, 5.275, 2.03, 2.05, blackmat)
cube('ShowerHead', 0.2, 0.46, 5.47, 5.73, 2.18, 2.2, blackmat, 0.003)
cube('ShowerArm', 0.085, 0.33, 5.59, 5.61, 2.2, 2.22, blackmat)
cube('ShowerMixer', 0.085, 0.1, 5.55, 5.65, 1.05, 1.15, blackmat, 0.004)
cube('Niche', 0.08, 0.1, 5.4, 5.8, 1.2, 1.5, MAT['Soffit'])
cube('NicheLED', 0.085, 0.1, 5.4, 5.8, 1.495, 1.5, ledw)
cube('Drain', 0.4, 0.6, 5.55, 5.75, 0.003, 0.006, steel)
cube('TowelBar', 1.3, 1.9, 5.9, 5.915, 1.35, 1.37, blackmat)
cube('Towel', 1.4, 1.8, 5.89, 5.905, 0.95, 1.37, tinted('FabricBeige', 'Towel', (0.95, 0.93, 0.9)), 0.01)
place('potted_plant_04', 1.75, 4.8, 'ny', 0.9, h=0.85)

# ============================================================ TERRACE, GARDENS
place('potted_plant_01', 5.65, 6.55, 'ny', 0.9, parent=GARDEN)
place('potted_plant_02', 3.35, 6.6, 'ny', 0.7, parent=GARDEN)
# front garden (outside the curved wall) — repeated on neighbours
for aid, x, z, s, f in [('anthurium_botany_01', 0.45, 10.2, 1.2, 'ny'), ('calathea_orbifolia_01', 2.4, 9.8, 1.3, 'nx'),
                        ('fern_02', 1.6, 11.6, 1.1, 'px'), ('calathea_orbifolia_01', 0.4, 11.5, 1.1, 'ny'),
                        ('anthurium_botany_01', 2.6, 11.2, 0.9, 'py'), ('fern_02', 0.35, 9.4, 0.8, 'nx')]:
    place(aid, x, z, f, s, parent=GARDEN, variant=random.randrange(3))
import random
random.seed(5)
place('tree_small_02', 1.25, 10.6, 'ny', 0.62, parent=GARDEN)
stones = load_asset('stone_01', keep=lambda n: n == 'stone_01_LOD0')
for x, z, s, r in [(2.0, 10.7, 3.5, 0.3), (2.7, 11.75, 2.8, 1.2), (0.9, 11.8, 3.0, 2.1), (2.55, 10.25, 2.2, 0.8)]:
    place(stones, x, z, r, s, parent=GARDEN)
grass = load_asset('grass_medium_01', keep=lambda n: n.endswith('LOD0') and 'geonodes' not in n and 'tiny' not in n, key='grass_clump')
import random
random.seed(11)
count = 0
while count < 160:
    x, z = random.uniform(0.1, 2.9), random.uniform(7.2, 11.95)
    if math.hypot(x - 0.95, z - 7.0) < 2.25 or (x < 0.95 and z < 9.25):
        continue
    place(grass, x, z, random.uniform(0, 6.28), random.uniform(1.4, 2.2), parent=GARDEN, variant=random.randrange(len(grass)))
    count += 1
for bz in (9.8, 11.75):
    cyl('Bollard', 2.8, bz, 0.045, 0, 0.45, blackmat, 20, parent=GARDEN)
    cyl('BollardLED', 2.8, bz, 0.04, 0.39, 0.44, ledw, 20, parent=GARDEN)
# back yard: grass, planting along the wall, small tree, AC unit, wall light
yard = bpy.data.objects.get('Yard')
if yard:
    yard.data.materials.clear(); yard.data.materials.append(MAT['Grass'])
shrub = load_asset('shrub_01', keep=lambda n: n.endswith('LOD0'), key='shrubs')
for i in range(8):
    place(shrub, 0.35 + i * 0.75, 0.3, random.uniform(0, 6.28), random.uniform(3.0, 4.0), parent=GARDEN, variant=random.randrange(len(shrub)))
place('fern_02', 1.1, 0.45, 'ny', 0.9, parent=GARDEN)
place('calathea_orbifolia_01', 4.6, 0.45, 'py', 1.2, parent=GARDEN)
place('tree_small_02', 0.7, 0.55, 'ny', 0.55, parent=GARDEN)
ac = load_asset('exterior_aircon_unit', keep=lambda n: n == 'exterior_aircon_unit', key='ac_unit')
place(ac, 5.35, 1.3, 'py', 0.85, h=0.3, parent=GARDEN)
cube('YardLamp', 3.0, 3.12, 0.075, 0.1, 2.1, 2.3, blackmat, 0.005, parent=GARDEN)

# ============================================================ LANDSCAPE (behind the houses, across the road)
trees = load_asset('island_tree_01', keep=lambda n: n == 'island_tree_01_LOD0', key='island_tree')
for x, z, s, r in [(-5, -5, 1.4, 0.3), (1.5, -7, 1.6, 1.4), (8.5, -5.5, 1.3, 2.2), (14, -8, 1.7, 0.9), (-11, -8, 1.5, 2.9),
                   (20, -6, 1.4, 4.0), (-4, 27, 1.5, 1.0), (7, 28, 1.7, 2.0), (18, 27, 1.4, 3.0), (-15, 26, 1.6, 0.5)]:
    place(trees, x, z, r, s, parent=LAND)

# ============================================================ CAR (lofted sedan body + subdivision)
paint = pmat('CarPaint', (0.30, 0.24, 0.17), 0.24, 0.85, coat=1.0)
cglass = pmat('CarGlass', (0.012, 0.014, 0.016), 0.02, 0.0, coat=1.0)
rubber = pmat('Rubber', (0.018, 0.018, 0.018), 0.8)
alloy = pmat('Alloy', (0.55, 0.56, 0.58), 0.22, 1.0)
trim = pmat('CarTrim', (0.01, 0.01, 0.01), 0.35, 0.2)
chrome = pmat('Chrome', (0.9, 0.9, 0.9), 0.05, 1.0)
headl = pmat('Headlight', (1, 1, 1), 0.05, emit=((1.0, 0.95, 0.85), 1.5))
taill = pmat('Taillight', (0.35, 0.01, 0.01), 0.1, emit=((1.0, 0.04, 0.02), 1.5))
CAR = coll('Car', C_INT)

def lerp_pts(pts, y):
    for (y0, v0), (y1, v1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0) if y1 != y0 else 0
            t = t * t * (3 - 2 * t)        # smooth step between key points
            return v0 + (v1 - v0) * t
    return pts[-1][1] if y > pts[-1][0] else pts[0][1]

# key curves along the length (y: -2.25 front bumper → +2.25 rear); front faces -Y (the street)
Z_BOT = [(-2.25, 0.42), (-2.05, 0.3), (1.95, 0.3), (2.25, 0.45)]
Z_SH = [(-2.25, 0.62), (-2.1, 0.72), (-1.0, 0.9), (1.6, 0.97), (2.05, 0.98), (2.25, 0.86)]
Z_RF = [(-2.25, 0.62), (-1.05, 0.92), (-0.25, 1.4), (0.85, 1.44), (1.62, 1.0), (2.25, 0.86)]
W_SH = [(-2.25, 0.84), (-2.05, 0.89), (-1.0, 0.9), (1.2, 0.9), (2.0, 0.89), (2.25, 0.84)]
W_RF = [(-1.05, 0.8), (-0.3, 0.64), (0.9, 0.64), (1.62, 0.78)]
N = 72; verts = []; zones = []
def section(w, cw, zb, zs, zr):
    """Closed cross-section: rounded lower body (superellipse) + tapered glasshouse."""
    pts = []
    mid = (zb + zs) / 2; hh = (zs - zb) / 2
    for j in range(9):                       # right lower body: bottom centre-ish -> shoulder
        t = -P2 + PI * j / 8
        c, s_ = math.cos(t), math.sin(t)
        pts.append((w * math.copysign(abs(c) ** 0.35, c) * (0.8 if j == 0 else 1.0), mid + hh * math.copysign(abs(s_) ** 0.6, s_)))
    for j in range(1, 5):                    # right glasshouse side, rounding into the roof
        t = j / 4
        x = w * 0.97 + (cw - w * 0.97) * t; z = zs + (zr - zs) * (1 - (1 - t) ** 1.6)
        pts.append((x, z))
    pts += [(cw * 0.6, zr + 0.012), (-cw * 0.6, zr + 0.012)]
    left = [(-x, z) for x, z in reversed(pts[:13])]
    return pts[:13] + [(cw * 0.6, zr + 0.012), (-cw * 0.6, zr + 0.012)] + left
ring = len(section(0.88, 0.64, 0.3, 0.9, 1.4))
for i in range(N + 1):
    y = -2.25 + 4.5 * i / N
    zb, zs = lerp_pts(Z_BOT, y), lerp_pts(Z_SH, y)
    zr = max(lerp_pts(Z_RF, y), zs + 0.015)
    w = lerp_pts(W_SH, y)
    cw = lerp_pts(W_RF, y) if -1.05 <= y <= 1.62 else w * 0.95
    verts += [(x, y, z) for x, z in section(w, cw, zb, zs, zr)]
    zones.append(y)
faces, mats = [], []
for i in range(N):
    yc = (zones[i] + zones[i + 1]) / 2
    for k in range(ring):
        a_, b_ = i * ring + k, i * ring + (k + 1) % ring
        faces.append((a_, b_, b_ + ring, a_ + ring))
        side = k in (9, 10, 11, 12) or k in (ring - 14, ring - 13, ring - 12, ring - 11)
        top = 13 <= k <= 15
        m = 0
        if -1.03 < yc < -0.3 and (side or top):
            m = 1
        elif -0.3 <= yc < 0.95 and side and not (0.28 < yc < 0.42) and k not in (9, ring - 11):
            m = 1
        elif 0.95 <= yc < 1.6 and top:
            m = 1
        if k in (0, ring - 1):
            m = 2
        mats.append(m)
faces.append(tuple(range(ring - 1, -1, -1))); mats.append(0)
faces.append(tuple(N * ring + k for k in range(ring))); mats.append(0)
me = bpy.data.meshes.new('CarBody'); me.from_pydata(verts, [], faces)
bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
for p, m in zip(me.polygons, mats):
    p.material_index = m
body = bpy.data.objects.new('CarBody', me)
finish(body, [paint, cglass, trim], parent=CAR)
WHEELS = [(-1.38, 1), (-1.38, -1), (1.32, 1), (1.32, -1)]
cutters = []
for wy, sx in WHEELS:
    c = cyl('ArchCut', 0, 0, 0.39, -0.3, 0.3, trim, 48, parent=CAR); c.rotation_euler = (0, P2, 0); c.location = (sx * 0.9, wy, 0.34)
    c.hide_render = True; c.display_type = 'WIRE'; cutters.append(c)
    bo = body.modifiers.new('Arch', 'BOOLEAN'); bo.object = c; bo.operation = 'DIFFERENCE'; bo.solver = 'EXACT'
    t = cyl('Tire', 0, 0, 0.33, -0.115, 0.115, rubber, 48, 0.05, parent=CAR); t.rotation_euler = (0, P2, 0); t.location = (sx * 0.745, wy, 0.33)
    r = cyl('Rim', 0, 0, 0.215, -0.01, 0.01, alloy, 48, 0.005, parent=CAR); r.rotation_euler = (0, P2, 0); r.location = (sx * 0.86, wy, 0.33)
    hub = cyl('Hub', 0, 0, 0.05, -0.02, 0.02, chrome, 24, parent=CAR); hub.rotation_euler = (0, P2, 0); hub.location = (sx * 0.875, wy, 0.33)
    for sp in range(5):
        ang = sp * 2 * PI / 5
        spoke = cube('Spoke', -0.012, 0.012, -0.02, 0.02, 0.05, 0.2, alloy, 0.004, parent=CAR)
        spoke.rotation_euler = (ang, 0, 0); spoke.location = (sx * 0.875, wy, 0.33)
# lamps, grille, mirrors, handles
for sx in (-1, 1):
    cube('HeadLamp', sx * 0.6 - 0.2, sx * 0.6 + 0.2, 2.2, 2.27, 0.6, 0.66, headl, 0.015, parent=CAR)
    cube('TailLamp', sx * 0.55 - 0.26, sx * 0.55 + 0.26, -2.25, -2.21, 0.78, 0.84, taill, 0.015, parent=CAR)
    mir = cube('WingMirror', sx * 0.93 - 0.05, sx * 0.93 + 0.05, 0.93, 1.0, 0.93, 1.0, trim, 0.02, parent=CAR)
    for hy in (0.0, 0.85):
        cube('Handle', sx * 0.89 - 0.01, sx * 0.89 + 0.01, -hy - 0.07, -hy + 0.07, 0.86, 0.885, chrome, 0.005, parent=CAR)
cube('Grille', -0.45, 0.45, 2.2, 2.26, 0.4, 0.58, trim, 0.03, parent=CAR)
cube('Emblem', -0.05, 0.05, 2.255, 2.265, 0.47, 0.53, chrome, 0.01, parent=CAR)
cube('PlateF', -0.26, 0.26, 2.25, 2.26, 0.33, 0.44, white, parent=CAR)
cube('PlateR', -0.26, 0.26, -2.28, -2.27, 0.5, 0.61, white, parent=CAR)
car_root = bpy.data.objects.new('CarRoot', None); CAR.objects.link(car_root)
for ob in CAR.objects:
    if ob is not car_root:
        ob.parent = car_root
car_root.location = (4.3, -9.55, 0)   # nose (-Y) points to the street
light('CarportDown', 'SPOT', (4.5, 8.0, 3.0), 0, spot=100)

bpy.ops.wm.save_mainfile()
print('STAGE3 SAVED')
