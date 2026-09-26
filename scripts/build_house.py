"""Stage 1 blockout for the Tipe 36/72 house.

Run:  blender -b -P build_house.py
Plan coordinates follow the floor plan: x = left→right (0..6 m), z = back→street (0..12 m).
Blender coordinates: X = x, Y = -z (street is toward -Y), Z = height.
"""
import bpy, bmesh, math, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_DIR = os.path.abspath(os.path.join(HERE, '..'))
PI, P2 = math.pi, math.pi / 2
WH, CEIL, T = 3.3, 3.0, 0.15
A1 = (0.95, 7.0, 2.05)   # bedroom 2 convex arc (cx, cz, r)
A2 = (4.05, 7.05, 1.05)  # terrace concave arc

# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'

def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c

C_UNIT = coll('Unit')           # repeated for the neighbours
C_INT = coll('Interior')        # furniture of the main unit only
C_SITE = coll('Site')
C_CAM = coll('Cameras')
C_ROOF = coll('Roof', C_UNIT)   # hidden for the 3D floor-plan view

# ---------------------------------------------------------------- materials (placeholders, replaced in stage 2)
MATS = {}
def mat(name, rgb, rough=0.6, metal=0.0, alpha=1.0, emit=None):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        if 'Transmission Weight' in b.inputs:
            b.inputs['Transmission Weight'].default_value = 1.0
    if emit:
        b.inputs['Emission Color'].default_value = (*emit[0], 1)
        b.inputs['Emission Strength'].default_value = emit[1]
    m.diffuse_color = (*rgb, alpha)
    MATS[name] = m
    return m

M = {
    'plaster': mat('Plaster', (0.86, 0.84, 0.80), 0.9),
    'plaster_ext': mat('PlasterExt', (0.78, 0.76, 0.72), 0.95),
    'brick': mat('Brick', (0.62, 0.26, 0.10), 0.6),
    'roster': mat('Roster', (0.66, 0.30, 0.12), 0.7),
    'roof': mat('RoofSlate', (0.16, 0.18, 0.19), 0.7),
    'fascia': mat('Fascia', (0.25, 0.28, 0.29), 0.8),
    'soffit': mat('Soffit', (0.92, 0.91, 0.89), 0.9),
    'floor': mat('FloorTile', (0.80, 0.76, 0.70), 0.25),
    'bath_tile': mat('BathTile', (0.45, 0.46, 0.45), 0.35),
    'terrace': mat('TerraceTile', (0.68, 0.65, 0.60), 0.5),
    'paver': mat('Paver', (0.30, 0.31, 0.32), 0.9),
    'grass': mat('Grass', (0.18, 0.30, 0.10), 1.0),
    'asphalt': mat('Asphalt', (0.12, 0.12, 0.13), 0.95),
    'concrete': mat('Concrete', (0.55, 0.54, 0.52), 0.9),
    'frame': mat('BlackAlu', (0.03, 0.03, 0.035), 0.35, 0.8),
    'glass': mat('Glass', (0.85, 0.9, 0.92), 0.02, 0.0, 0.25),
    'wood': mat('Oak', (0.55, 0.38, 0.22), 0.5),
    'walnut': mat('Walnut', (0.28, 0.17, 0.10), 0.5),
    'fabric': mat('FabricBeige', (0.75, 0.70, 0.62), 1.0),
    'fabric_olive': mat('FabricOlive', (0.36, 0.38, 0.24), 1.0),
    'white': mat('WhiteGloss', (0.92, 0.92, 0.90), 0.25),
    'car': mat('CarPaint', (0.30, 0.25, 0.20), 0.3, 0.6),
    'led': mat('LED', (1, 0.9, 0.75), 0.5, 0, 1, ((1.0, 0.78, 0.5), 8.0)),
    'plant': mat('PlantPlaceholder', (0.15, 0.35, 0.12), 0.8),
}

# ---------------------------------------------------------------- mesh helpers
def world_uv(me, arc=None):
    """UVs in metres: walls use (along-wall, height), floors use (x, y). Arcs use arc length."""
    uv = me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        n = p.normal
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.7:
                u, v = co.x, co.y
            elif arc:
                cx, cy, r = arc
                u, v = r * math.atan2(co.y - cy, co.x - cx), co.z
            elif abs(n.x) > abs(n.y):
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            else:
                u, v = co.x * (-1 if n.y > 0 else 1), co.z
            uv.data[li].uv = (u, v)

def mesh_obj(name, verts, faces, material, collection=C_UNIT, arc=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    world_uv(me, arc)
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob

def box(name, x0, x1, z0, z1, h0, h1, material, collection=C_UNIT):
    """Axis-aligned box in plan coordinates."""
    xs, ys, hs = (x0, x1), (-z1, -z0), (h0, h1)
    v = [(xs[i], ys[j], hs[k]) for k in (0, 1) for j in (0, 1) for i in (0, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return mesh_obj(name, v, f, material, collection)

def prism_x(name, x0, x1, profile, material, collection=C_UNIT):
    """Extrude a (z, h) plan profile between x0 and x1."""
    n = len(profile)
    v = [(x0, -z, h) for z, h in profile] + [(x1, -z, h) for z, h in profile]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh_obj(name, v, f, material, collection)

def arc_wall(name, cx, cz, r, a0, a1, h0, h1, t, material, collection=C_UNIT, n=40, m_inner=None):
    v, f = [], []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        for rr in (r + t / 2, r - t / 2):
            for h in (h0, h1):
                v.append((cx + rr * math.cos(a), -(cz + rr * math.sin(a)), h))
    for i in range(n):
        b, c = i * 4, (i + 1) * 4
        f += [(b, c, c + 1, b + 1), (b + 2, b + 3, c + 3, c + 2), (b + 1, c + 1, c + 3, b + 3), (b, b + 2, c + 2, c)]
    f += [(0, 1, 3, 2), (n * 4, n * 4 + 2, n * 4 + 3, n * 4 + 1)]
    ob = mesh_obj(name, v, f, material, collection, arc=(cx, -cz, r))
    if m_inner is not None:
        ob.data.materials.append(m_inner)
        for p in ob.data.polygons:
            if p.index < 4 * n and p.index % 4 == 1:
                p.material_index = 1
    return ob

def plan_poly(name, pts, h, material, collection=C_UNIT, flip=False):
    v = [(x, -z, h) for x, z in pts]
    face = tuple(range(len(pts)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], [face])
    world_uv(me)
    me.materials.append(material)
    for p in me.polygons:
        if (p.normal.z < 0) != flip:
            p.flip()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob

def arc_pts(cx, cz, r, a0, a1, n=28):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cz + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]

# ---------------------------------------------------------------- windows & doors
def window(name, horiz, cx, cz, w, y0, y1, c=C_UNIT):
    f, d = 0.05, 0.08
    if horiz:
        x0, x1, z0, z1 = cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2
        box(name + '_top', x0, x1, z0, z1, y1 - f, y1, M['frame'], c)
        box(name + '_bot', x0, x1, z0, z1, y0, y0 + f, M['frame'], c)
        box(name + '_l', x0, x0 + f, z0, z1, y0, y1, M['frame'], c)
        box(name + '_r', x1 - f, x1, z0, z1, y0, y1, M['frame'], c)
        if w > 1.0:
            box(name + '_m', cx - 0.02, cx + 0.02, z0, z1, y0, y1, M['frame'], c)
        box(name + '_glass', x0 + f, x1 - f, cz - 0.004, cz + 0.004, y0 + f, y1 - f, M['glass'], c)
    else:
        z0, z1, x0, x1 = cz - w / 2, cz + w / 2, cx - d / 2, cx + d / 2
        box(name + '_top', x0, x1, z0, z1, y1 - f, y1, M['frame'], c)
        box(name + '_bot', x0, x1, z0, z1, y0, y0 + f, M['frame'], c)
        box(name + '_l', x0, x1, z0, z0 + f, y0, y1, M['frame'], c)
        box(name + '_r', x0, x1, z1 - f, z1, y0, y1, M['frame'], c)
        box(name + '_glass', cx - 0.004, cx + 0.004, z0 + f, z1 - f, y0 + f, y1 - f, M['glass'], c)

def wall(name, ax, az, bx, bz, opens=(), mA=None, mB=None, h=WH, t=T):
    """Straight wall with openings. mA = face toward -x/-z, mB = face toward +x/+z."""
    horiz = az == bz
    L = (bx - ax) if horiz else (bz - az)
    def seg(u0, u1, y0, y1, tag):
        if u1 - u0 < 0.005 or y1 - y0 < 0.005:
            return
        if horiz:
            ob = box(f'{name}_{tag}', ax + u0, ax + u1, az - t / 2, az + t / 2, y0, y1, mA or M['plaster'])
        else:
            ob = box(f'{name}_{tag}', ax - t / 2, ax + t / 2, az + u0, az + u1, y0, y1, mA or M['plaster'])
        if mB and mB is not mA:
            ob.data.materials.append(mB)
            for p in ob.data.polygons:
                n = p.normal
                if (horiz and n.y < -0.5) or (not horiz and n.x > 0.5):  # +z face is -Y in Blender
                    p.material_index = 1
    cur = 0
    for i, o in enumerate(sorted(opens, key=lambda o: o['c'])):
        s, e = o['c'] - o['w'] / 2, o['c'] + o['w'] / 2
        sill = o.get('sill', 0); top = sill + o['h']
        seg(cur, s, 0, h, f's{i}')
        seg(s, e, 0, sill, f'sill{i}')
        seg(s, e, top, h, f'head{i}')
        if o['t'] == 'win':
            cx, cz = (ax + o['c'], az) if horiz else (ax, az + o['c'])
            window(f'{name}_win{i}', horiz, cx, cz, o['w'], sill, top)
        cur = e
    seg(cur, L, 0, h, 'end')

def door_leaf(name, hx, hz, angle, w, h=2.08, kind='wood', c=C_UNIT):
    """Door leaf hinged at (hx, hz); angle measured like the web tour (0 = +x, P2 = -z)."""
    if kind == 'wood':
        parts = [box(name, 0, w, -0.02, 0.02, 0, h, M['walnut'], c)]
    else:  # black aluminium frame with glass, like the render
        f = 0.055
        parts = [box(name + '_t', 0, w, -0.025, 0.025, h - f, h, M['frame'], c), box(name + '_b', 0, w, -0.025, 0.025, 0, f * 2, M['frame'], c),
                 box(name + '_l', 0, f, -0.025, 0.025, 0, h, M['frame'], c), box(name + '_r', w - f, w, -0.025, 0.025, 0, h, M['frame'], c),
                 box(name + '_m1', 0, w, -0.025, 0.025, 0.55, 0.59, M['frame'], c), box(name + '_m2', 0, w, -0.025, 0.025, 1.3, 1.34, M['frame'], c),
                 box(name + '_g', f, w - f, -0.004, 0.004, f * 2, h - f, M['glass'], c)]
    root = bpy.data.objects.new(name + '_hinge', None); c.objects.link(root)
    for ob in parts:
        ob.parent = root
    root.location = (hx, -hz, 0)
    root.rotation_euler = (0, 0, angle)
    return root

# ---------------------------------------------------------------- walls
pl, pe, br = M['plaster'], M['plaster_ext'], M['brick']
wall('PartyL', 0, 1.5, 0, 9.05)
wall('PartyR', 6, 1.5, 6, 6.0)
wall('YardL', 0, 0, 0, 1.5, h=2.4, mA=pe)
wall('YardR', 6, 0, 6, 1.5, h=2.4, mA=pe)
wall('YardBack', 0, 0, 6, 0, h=2.4, mA=pe)
wall('Back', 0, 1.5, 6, 1.5, mA=pe, mB=pl, opens=[
    dict(c=2.5, w=0.8, sill=1.0, h=1.2, t='win'),
    dict(c=3.525, w=0.75, h=2.1, t='door'),
    dict(c=4.5, w=0.8, sill=1.15, h=0.9, t='win')])
wall('Bed1Kitchen', 3, 1.5, 3, 4.5)
wall('Bed1Bath', 0, 4.5, 3, 4.5, opens=[dict(c=2.5, w=0.8, h=2.1, t='door')])
wall('BathCorr', 2.07, 4.5, 2.07, 6.0, t=0.12, opens=[dict(c=0.85, w=0.75, h=2.1, t='door')])
wall('BathBed2', 0, 6.0, 3, 6.0, opens=[dict(c=2.5, w=0.8, h=2.1, t='door')])
wall('Bed2Side', 3, 6.0, 3, 7.05, mA=pl, mB=br)
wall('GuestFront', 3, 6.0, 6, 6.0, mA=pl, mB=br, opens=[dict(c=1.725, w=1.35, h=2.4, t='door')])
wall('Bed2Front', 0, 9.05, 0.95, 9.05, mA=pl, mB=br, opens=[dict(c=0.5, w=0.72, sill=0.25, h=2.45, t='win')])
arc_wall('ArcBed2', *A1, 0, 1.05, 0, WH, 0.18, br, m_inner=pl)
arc_wall('ArcBed2_base', *A1, 1.05, P2, 0, 0.45, 0.18, br, m_inner=pl)
arc_wall('ArcBed2_roster', *A1, 1.05, P2, 0.45, 3.0, 0.18, M['roster'])
arc_wall('ArcBed2_top', *A1, 1.05, P2, 3.0, WH, 0.18, br, m_inner=pl)
arc_wall('ArcTerrace', *A2, PI, PI * 1.5, 0, WH, 0.16, pl, m_inner=br)

# doors (open for the interior renders)
door_leaf('Door_Bed1', 2.9, 4.5, P2, 0.8)
door_leaf('Door_Bed2', 2.9, 6.0, PI * 1.5, 0.8)
door_leaf('Door_Bath', 2.07, 5.725, PI, 0.75)
door_leaf('Door_FrontL', 4.05, 6.0, -P2, 0.675, 2.38, 'glass')
door_leaf('Door_FrontR', 5.4, 6.0, PI * 1.5, 0.675, 2.38, 'glass')
door_leaf('Door_Kitchen', 3.15, 1.5, -P2, 0.75, 2.08, 'glass')

# ---------------------------------------------------------------- floors, ceilings, ground
bed2 = [(0, 6), (3, 6)] + arc_pts(*A1, 0, P2) + [(0, 9.05)]
garden = [(0, 9.05), (0, 12), (3, 12)] + arc_pts(*A1, 0, P2)[:-1]
terrace = [(6, 6.0)] + arc_pts(*A2, PI * 1.5, PI, 16) + [(3, 7.25), (6, 7.25)]
plan_poly('Floor_Bed1', [(0, 1.5), (3, 1.5), (3, 4.5), (0, 4.5)], 0.0, M['floor'])
plan_poly('Floor_Living', [(2.07, 1.5), (6, 1.5), (6, 6), (2.07, 6)], 0.0, M['floor'])
plan_poly('Floor_Bath', [(0, 4.5), (2.07, 4.5), (2.07, 6), (0, 6)], 0.002, M['bath_tile'])
plan_poly('Floor_Bed2', bed2, 0.0, M['floor'])
plan_poly('Floor_Terrace', terrace, 0.0, M['terrace'])
plan_poly('Garden', garden, -0.02, M['grass'])
plan_poly('Carport', [(3, 7.25), (6, 7.25), (6, 12), (3, 12)], -0.02, M['paver'])
plan_poly('Yard', [(0, 0), (6, 0), (6, 1.5), (0, 1.5)], -0.02, M['paver'])
for nm, pts in [('Ceil_Bed1', [(0, 1.5), (3, 1.5), (3, 4.5), (0, 4.5)]), ('Ceil_Living', [(2.07, 1.5), (6, 1.5), (6, 6), (2.07, 6)]),
                ('Ceil_Bath', [(0, 4.5), (2.07, 4.5), (2.07, 6), (0, 6)]), ('Ceil_Bed2', bed2)]:
    plan_poly(nm, pts, CEIL, M['soffit'], flip=True)

# ---------------------------------------------------------------- roofs
# mansard over the bedrooms
mansard = prism_x('Roof_Mansard', 0, 3.22, [(9.6, 3.3), (9.55, 3.45), (8.45, 7.1), (2.55, 7.1), (1.3, 3.45), (1.25, 3.3)], M['roof'], C_ROOF)
cut = box('DormerCut', 1.12, 2.78, 8.55, 10.0, 4.05, 5.95, M['fascia'], C_ROOF)
mod = mansard.modifiers.new('Dormer', 'BOOLEAN'); mod.object = cut; mod.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = mansard
with bpy.context.temp_override(object=mansard, active_object=mansard, selected_objects=[mansard]):
    bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(cut)
box('Dormer_top', 1.12, 2.78, 8.55, 9.62, 5.93, 6.13, M['fascia'], C_ROOF)
box('Dormer_bot', 1.12, 2.78, 8.9, 9.62, 3.93, 4.08, M['fascia'], C_ROOF)
box('Dormer_l', 1.12, 1.28, 8.55, 9.62, 3.93, 6.13, M['fascia'], C_ROOF)
box('Dormer_r', 2.62, 2.78, 8.55, 9.62, 3.93, 6.13, M['fascia'], C_ROOF)
window('Dormer_win', True, 1.95, 9.0, 1.34, 4.08, 5.93, C_ROOF)
box('Dormer_back', 1.28, 2.62, 8.55, 8.6, 4.08, 5.93, M['soffit'], C_ROOF)
prism_x('Roof_Mansard_cheek', 3.0, 3.22, [(9.65, 3.25), (8.4, 7.2), (2.5, 7.2), (1.2, 3.25)], M['fascia'], C_ROOF)
box('Mansard_soffit', 0, 3.0, 1.25, 9.55, 3.3, 3.4, M['soffit'])
box('Mansard_led', 0, 3.0, 9.36, 9.44, 3.27, 3.3, M['led'])
# lower roof over living / terrace
prism_x('Roof_Low', 3.22, 6.0, [(7.35, 3.05), (7.3, 3.15), (6.3, 5.5), (2.35, 5.5), (1.3, 3.4), (1.25, 3.05)], M['roof'], C_ROOF)
box('Low_soffit', 3.0, 6.0, 1.25, 7.35, 3.05, 3.15, M['soffit'])
box('Low_led', 3.22, 5.8, 7.16, 7.24, 3.02, 3.05, M['led'])
box('Pier_center', 5.8, 6.0, 6.95, 7.35, 0, 3.2, M['fascia'])
box('Fin_corner', 2.86, 3.16, 9.2, 9.55, 0, 3.4, M['fascia'])
box('FrontDoor_head', 4.03, 5.42, 5.92, 6.08, 2.4, 2.46, M['frame'])
box('Curb', 2.95, 3.05, 7.05, 12.0, -0.02, 0.07, M['concrete'])

# ---------------------------------------------------------------- interior blockout (replaced by real assets in stage 3)
I = C_INT
box('Sofa', 5.0, 5.9, 3.73, 5.48, 0, 0.8, M['fabric'], I)
box('CoffeeTable', 4.0, 4.6, 4.0, 5.0, 0, 0.4, M['walnut'], I)
box('TVConsole', 3.075, 3.475, 2.95, 4.45, 0.22, 0.56, M['wood'], I)
box('TV', 3.12, 3.16, 3.13, 4.27, 1.1, 1.76, M['frame'], I)
box('DiningTable', 3.92, 4.68, 2.57, 3.33, 0, 0.75, M['wood'], I)
box('Counter', 3.9, 5.925, 1.575, 2.175, 0, 0.9, M['white'], I)
box('Bed1', 0.075, 2.18, 2.2, 3.7, 0, 0.55, M['fabric'], I)
box('Bed1_head', 0.075, 0.175, 2.15, 3.75, 0, 1.1, M['fabric_olive'], I)
box('Wardrobe1', 0.1, 1.95, 3.955, 4.425, 0, 2.4, M['wood'], I)
box('Bed2', 0.075, 2.18, 6.85, 8.35, 0, 0.55, M['fabric'], I)
box('Bed2_head', 0.075, 0.175, 6.8, 8.4, 0, 1.1, M['fabric_olive'], I)
box('Wardrobe2', 0.1, 1.95, 6.075, 6.545, 0, 2.4, M['wood'], I)
box('Toilet', 0.07, 0.75, 4.73, 5.17, 0, 0.78, M['white'], I)
box('Vanity', 1.2, 1.7, 4.57, 4.95, 0.7, 0.85, M['white'], I)
box('ShowerGlass', 0.075, 0.92, 5.26, 5.30, 0, 2.0, M['glass'], I)
box('Car', 3.4, 5.2, 7.3, 11.8, 0.15, 1.45, M['car'], I)
for i, (x, z, s) in enumerate([(0.45, 10.3, 1.0), (2.35, 9.85, 0.8), (1.5, 11.55, 0.9), (1.15, 10.9, 2.2), (0.4, 0.4, 1.2), (1.4, 0.6, 1.8)]):
    box(f'PlantPH{i}', x - 0.3, x + 0.3, z - 0.3, z + 0.3, 0, s, M['plant'], C_UNIT)

# ---------------------------------------------------------------- site
box('Ground', -40, 46, -30, 40, -0.2, -0.03, M['grass'], C_SITE)
box('Kerb', -40, 46, 12.0, 12.15, -0.03, 0.02, M['concrete'], C_SITE)
box('Drain', -40, 46, 12.15, 12.6, -0.12, -0.02, M['frame'], C_SITE)
box('Kerb2', -40, 46, 12.6, 12.75, -0.03, 0.02, M['concrete'], C_SITE)
box('Road', -40, 46, 12.75, 19.2, -0.04, -0.01, M['asphalt'], C_SITE)

# neighbours: mirrored instances of the Unit collection, like the render
for px, mirror in [(12, True), (0, True), (12, False), (-12, False)]:
    e = bpy.data.objects.new(f'Neighbour_{px}_{int(mirror)}', None)
    e.instance_type = 'COLLECTION'; e.instance_collection = C_UNIT
    e.location = (px, 0, 0); e.scale = (-1 if mirror else 1, 1, 1)
    C_SITE.objects.link(e)

# ---------------------------------------------------------------- cameras
CAMS = {
    #  name          position (x, z, h)       target (x, z, h)       lens  resolution
    'tampak_depan':  ((3.0, 24.5, 1.7),       (3.0, 8.0, 3.9),       24,  (1600, 1067)),
    'tampak_atas':   ((-7.0, 24.0, 15.0),     (3.0, 6.0, 1.0),       30,  (1600, 1067)),
    'denah_3d':      ((3.0, 6.0, 22.0),       None,                  0,   (900, 1600)),
    'ruang_tamu':    ((4.72, 5.85, 1.3),      (4.3, 1.8, 1.05),      15,  (1600, 1067)),
    'dapur':         ((4.95, 3.6, 1.45),      (4.55, 1.5, 1.05),     16,  (1600, 1067)),
    'kamar_tidur_1': ((2.85, 3.05, 1.45),     (0.0, 2.95, 0.9),      16,  (1600, 1067)),
    'kamar_tidur_2': ((2.55, 7.45, 1.45),     (0.0, 8.0, 0.9),       16,  (1600, 1067)),
    'kamar_mandi':   ((2.02, 5.35, 1.45),     (0.0, 5.15, 1.05),     14,  (1600, 1067)),
    'taman_belakang':((5.8, 1.35, 1.6),       (0.5, 0.0, 0.7),       16,  (1600, 1067)),
    'carport':       ((4.5, 15.8, 1.6),       (4.5, 7.0, 1.5),       24,  (1600, 1067)),
}
for name, (pos, target, lens, res) in CAMS.items():
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    C_CAM.objects.link(cam)
    cam.location = (pos[0], -pos[1], pos[2])
    cd.clip_start = 0.05; cd.clip_end = 400
    cd.sensor_width = 36
    if target is None:
        cd.type = 'ORTHO'; cd.ortho_scale = 13.5
        cam.rotation_euler = (0, 0, 0)
    else:
        cd.lens = lens
        d = Vector((target[0], -target[1], target[2])) - cam.location
        # keep verticals straight: level camera, frame height with lens shift
        yaw = math.atan2(d.y, d.x) - P2
        horiz = math.hypot(d.x, d.y)
        pitch = math.atan2(d.z, horiz)
        if name in ('tampak_atas',):
            cam.rotation_euler = (P2 + pitch, 0, yaw)
        else:
            cam.rotation_euler = (P2, 0, yaw)
            cd.shift_y = max(-0.3, min(0.3, math.tan(pitch) * lens / 36 * 0.9))
    cam['resolution'] = list(res)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RENDER_DIR, 'rumah_36_72.blend'))
print('SAVED', os.path.join(RENDER_DIR, 'rumah_36_72.blend'))
