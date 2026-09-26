"""Stage 2: real materials (Poly Haven PBR + procedural tiles/brick) and lighting.
Run:  blender -b rumah_36_72.blend -P stage2_materials.py
"""
import bpy, os, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
TEX = os.path.join(ROOT, 'assets', 'textures')
HDRI = os.path.join(ROOT, 'assets', 'hdri')
DIMS = json.load(open(os.path.join(HERE, 'tex_dims.json')))
P2 = math.pi / 2

def img(path, color=True):
    im = bpy.data.images.load(path, check_existing=True)
    if not color:
        im.colorspace_settings.name = 'Non-Color'
    return im

def find(tex_id, *keys):
    folder = os.path.join(TEX, tex_id, 'textures')
    for k in keys:
        for f in sorted(os.listdir(folder)):
            if f'_{k}' in f:
                return os.path.join(folder, f)
    return None

class NB:
    """Small helper to build node trees."""
    def __init__(self, m):
        m.use_nodes = True
        self.nt = m.node_tree; self.n = self.nt.nodes; self.l = self.nt.links
        self.n.clear()
        self.out = self.n.new('ShaderNodeOutputMaterial'); self.out.location = (900, 0)
    def new(self, t, x=0, y=0, **kw):
        nd = self.n.new(t); nd.location = (x, y)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd
    def link(self, a, b):
        self.l.new(a, b)

def reset(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    return m, NB(m)

def box_mapping(nb, size_m, rot=0.0):
    tc = nb.new('ShaderNodeTexCoord', -900, 0)
    mp = nb.new('ShaderNodeMapping', -700, 0)
    mp.inputs['Scale'].default_value = (1 / size_m, 1 / size_m, 1 / size_m)
    mp.inputs['Rotation'].default_value = (0, 0, rot)
    nb.link(tc.outputs['UV'], mp.inputs['Vector'])
    return mp.outputs['Vector']

def img_node(nb, path, vec, color=True, y=0, box=True):
    t = nb.new('ShaderNodeTexImage', -450, y)
    t.image = img(path, color)
    nb.link(vec, t.inputs['Vector'])
    return t

def pbr(name, tex_id, size_m=None, hue=0.5, sat=1.0, val=1.0, tint=None, rough_add=0.0, normal=0.7, rot=0.0, spec=0.5):
    m, nb = reset(name)
    size_m = size_m or DIMS[tex_id][0] / 1000
    vec = box_mapping(nb, size_m, rot)
    bsdf = nb.new('ShaderNodeBsdfPrincipled', 500, 0)
    diff = img_node(nb, find(tex_id, 'diff', 'col'), vec, True, 300)
    hsv = nb.new('ShaderNodeHueSaturation', -150, 300)
    hsv.inputs['Hue'].default_value = hue; hsv.inputs['Saturation'].default_value = sat; hsv.inputs['Value'].default_value = val
    nb.link(diff.outputs['Color'], hsv.inputs['Color'])
    col = hsv.outputs['Color']
    if tint:
        mix = nb.new('ShaderNodeMix', 100, 300); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        nb.link(col, mix.inputs[6]); mix.inputs[7].default_value = (*tint, 1)
        col = mix.outputs[2]
    nb.link(col, bsdf.inputs['Base Color'])
    rp = find(tex_id, 'rough')
    if rp:
        r = img_node(nb, rp, vec, False, 0)
        add = nb.new('ShaderNodeMath', 100, 0); add.operation = 'ADD'; add.use_clamp = True
        add.inputs[1].default_value = rough_add
        nb.link(r.outputs['Color'], add.inputs[0]); nb.link(add.outputs[0], bsdf.inputs['Roughness'])
    npth = find(tex_id, 'nor_gl')
    if npth and normal > 0:
        n = img_node(nb, npth, vec, False, -300)
        nm = nb.new('ShaderNodeNormalMap', 100, -300); nm.inputs['Strength'].default_value = normal
        nb.link(n.outputs['Color'], nm.inputs['Color']); nb.link(nm.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Specular IOR Level'].default_value = spec
    nb.link(bsdf.outputs['BSDF'], nb.out.inputs['Surface'])
    return m

def tiles(name, size_m, grout_m, c1, c2, grout_col, rough=0.18, bump=0.25, offset=0.0, ratio=1.0):
    """Clean procedural large-format tiles (interior floor, bathroom)."""
    m, nb = reset(name)
    vec = box_mapping(nb, 1.0)
    br = nb.new('ShaderNodeTexBrick', -300, 200)
    br.offset = offset; br.squash = 1.0
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = size_m
    br.inputs['Row Height'].default_value = size_m * ratio
    br.inputs['Mortar Size'].default_value = grout_m
    br.inputs['Mortar Smooth'].default_value = 0.2
    br.inputs['Color1'].default_value = (*c1, 1); br.inputs['Color2'].default_value = (*c2, 1)
    br.inputs['Mortar'].default_value = (*grout_col, 1)
    nb.link(vec, br.inputs['Vector'])
    noise = nb.new('ShaderNodeTexNoise', -300, -150); noise.inputs['Scale'].default_value = 6; noise.inputs['Detail'].default_value = 8
    nb.link(vec, noise.inputs['Vector'])
    mix = nb.new('ShaderNodeMix', 0, 200); mix.data_type = 'RGBA'; mix.blend_type = 'OVERLAY'; mix.inputs['Factor'].default_value = 0.08
    nb.link(br.outputs['Color'], mix.inputs[6]); nb.link(noise.outputs['Color'], mix.inputs[7])
    bsdf = nb.new('ShaderNodeBsdfPrincipled', 500, 0)
    nb.link(mix.outputs[2], bsdf.inputs['Base Color'])
    rmap = nb.new('ShaderNodeMapRange', 200, -50)
    rmap.inputs['To Min'].default_value = 0.6; rmap.inputs['To Max'].default_value = rough
    nb.link(br.outputs['Fac'], rmap.inputs['Value']); nb.link(rmap.outputs['Result'], bsdf.inputs['Roughness'])
    bp = nb.new('ShaderNodeBump', 200, -250); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.003
    nb.link(br.outputs['Fac'], bp.inputs['Height']); nb.link(bp.outputs['Normal'], bsdf.inputs['Normal'])
    nb.link(bsdf.outputs['BSDF'], nb.out.inputs['Surface'])
    return m

def brick_facade(name):
    """Orange glazed brick like the render: tidy running bond, slight gloss, real bump from the scan."""
    m, nb = reset(name)
    vec = box_mapping(nb, 1.0)
    br = nb.new('ShaderNodeTexBrick', -300, 250)
    br.offset = 0.5; br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 0.2; br.inputs['Row Height'].default_value = 0.065
    br.inputs['Mortar Size'].default_value = 0.008; br.inputs['Bias'].default_value = 0.0
    br.inputs['Color1'].default_value = (0.62, 0.22, 0.07, 1); br.inputs['Color2'].default_value = (0.72, 0.30, 0.10, 1)
    br.inputs['Mortar'].default_value = (0.35, 0.22, 0.14, 1)
    nb.link(vec, br.inputs['Vector'])
    scan = img_node(nb, find('stacked_brick_wall', 'diff'), box_mapping(nb, 1.73), True, -100)
    bw = nb.new('ShaderNodeRGBToBW', -150, -100); nb.link(scan.outputs['Color'], bw.inputs['Color'])
    mix = nb.new('ShaderNodeMix', 50, 250); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 0.35
    nb.link(br.outputs['Color'], mix.inputs[6]); nb.link(scan.outputs['Color'], mix.inputs[7])
    bsdf = nb.new('ShaderNodeBsdfPrincipled', 500, 0)
    nb.link(mix.outputs[2], bsdf.inputs['Base Color'])
    rmap = nb.new('ShaderNodeMapRange', 250, 0); rmap.inputs['To Min'].default_value = 0.85; rmap.inputs['To Max'].default_value = 0.38
    nb.link(br.outputs['Fac'], rmap.inputs['Value']); nb.link(rmap.outputs['Result'], bsdf.inputs['Roughness'])
    bp = nb.new('ShaderNodeBump', 250, -250); bp.inputs['Strength'].default_value = 0.6; bp.inputs['Distance'].default_value = 0.01
    add = nb.new('ShaderNodeMath', 100, -300); add.operation = 'ADD'
    inv = nb.new('ShaderNodeMath', -50, -300); inv.operation = 'MULTIPLY'; inv.inputs[1].default_value = 0.3
    nb.link(bw.outputs['Val'], inv.inputs[0]); nb.link(br.outputs['Fac'], add.inputs[0]); nb.link(inv.outputs[0], add.inputs[1])
    nb.link(add.outputs[0], bp.inputs['Height']); nb.link(bp.outputs['Normal'], bsdf.inputs['Normal'])
    nb.link(bsdf.outputs['BSDF'], nb.out.inputs['Surface'])
    return m

def glass(name, tint=(0.9, 0.95, 0.96)):
    m, nb = reset(name)
    g = nb.new('ShaderNodeBsdfGlass', 200, 150); g.inputs['Roughness'].default_value = 0.0; g.inputs['IOR'].default_value = 1.45
    g.inputs['Color'].default_value = (*tint, 1)
    tr = nb.new('ShaderNodeBsdfTransparent', 200, -50); tr.inputs['Color'].default_value = (*tint, 1)
    lp = nb.new('ShaderNodeLightPath', -200, 100)
    mx = nb.new('ShaderNodeMath', 0, 100); mx.operation = 'MAXIMUM'
    mx2 = nb.new('ShaderNodeMath', 0, -100); mx2.operation = 'MAXIMUM'
    nb.link(lp.outputs['Is Shadow Ray'], mx.inputs[0]); nb.link(lp.outputs['Is Diffuse Ray'], mx.inputs[1])
    nb.link(mx.outputs[0], mx2.inputs[0]); nb.link(lp.outputs['Is Glossy Ray'], mx2.inputs[1])
    sh = nb.new('ShaderNodeMixShader', 500, 0)
    nb.link(mx2.outputs[0], sh.inputs['Fac']); nb.link(g.outputs['BSDF'], sh.inputs[1]); nb.link(tr.outputs['BSDF'], sh.inputs[2])
    nb.link(sh.outputs['Shader'], nb.out.inputs['Surface'])
    return m

def simple(name, rgb, rough=0.5, metal=0.0, emit=None, trans=0.0, alpha=1.0):
    m, nb = reset(name)
    b = nb.new('ShaderNodeBsdfPrincipled', 500, 0)
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit[0], 1); b.inputs['Emission Strength'].default_value = emit[1]
    if trans:
        b.inputs['Transmission Weight'].default_value = trans
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
    nb.link(b.outputs['BSDF'], nb.out.inputs['Surface'])
    return m

def plaster(name, rgb):
    """Smooth painted plaster: flat warm colour, only the fine relief comes from the scan."""
    m, nb = reset(name)
    vec = box_mapping(nb, 2.0)
    bsdf = nb.new('ShaderNodeBsdfPrincipled', 500, 0)
    bsdf.inputs['Base Color'].default_value = (*rgb, 1); bsdf.inputs['Roughness'].default_value = 0.85
    n = img_node(nb, find('painted_plaster_wall', 'nor_gl'), vec, False, -300)
    nm = nb.new('ShaderNodeNormalMap', 100, -300); nm.inputs['Strength'].default_value = 0.25
    nb.link(n.outputs['Color'], nm.inputs['Color']); nb.link(nm.outputs['Normal'], bsdf.inputs['Normal'])
    nb.link(bsdf.outputs['BSDF'], nb.out.inputs['Surface'])
    return m

def roster(name):
    """Terracotta breeze blocks with real see-through holes (alpha)."""
    m, nb = reset(name)
    vec = box_mapping(nb, 0.8)
    cp = os.path.join(ROOT, 'assets', 'custom', 'roster_col.png'); ap = os.path.join(ROOT, 'assets', 'custom', 'roster_alpha.png')
    c = img_node(nb, cp, vec, True, 200); a = img_node(nb, ap, vec, False, -100)
    bsdf = nb.new('ShaderNodeBsdfPrincipled', 300, 100); bsdf.inputs['Roughness'].default_value = 0.75
    nb.link(c.outputs['Color'], bsdf.inputs['Base Color'])
    tr = nb.new('ShaderNodeBsdfTransparent', 300, -200)
    mx = nb.new('ShaderNodeMixShader', 600, 0)
    nb.link(a.outputs['Color'], mx.inputs['Fac']); nb.link(tr.outputs['BSDF'], mx.inputs[1]); nb.link(bsdf.outputs['BSDF'], mx.inputs[2])
    nb.link(mx.outputs['Shader'], nb.out.inputs['Surface'])
    return m

# ---------------------------------------------------------------- materials (names match stage 1)
plaster('Plaster', (0.80, 0.76, 0.70))
pbr('PlasterExt', 'painted_plaster_wall', sat=0.1, val=1.05, tint=(0.93, 0.91, 0.87), normal=0.4)
brick_facade('Brick')
roster('Roster')
pbr('RoofSlate', 'roof_slates_02', sat=0.0, val=0.42, tint=(0.8, 0.88, 0.95), normal=1.0, rot=0)
pbr('Fascia', 'painted_concrete', sat=0.0, val=0.55, tint=(0.62, 0.68, 0.70), rough_add=0.1, normal=0.3)
simple('Soffit', (0.88, 0.87, 0.85), 0.8)
tiles('FloorTile', 0.6, 0.002, (0.80, 0.76, 0.69), (0.78, 0.74, 0.67), (0.62, 0.58, 0.52), rough=0.15)
tiles('BathTile', 0.6, 0.002, (0.42, 0.42, 0.41), (0.40, 0.40, 0.39), (0.30, 0.30, 0.30), rough=0.25, ratio=0.5)
pbr('TerraceTile', 'large_grey_tiles', sat=0.3, val=1.1)
pbr('Paver', 'interlocking_concrete_pavers', sat=0.0, val=0.75, tint=(0.85, 0.88, 0.9), normal=1.0)
pbr('Grass', 'leafy_grass', hue=0.58, sat=2.2, val=0.75, tint=(0.75, 1.0, 0.6), normal=0.8)
pbr('Asphalt', 'asphalt_02', val=0.8)
pbr('Concrete', 'painted_concrete', sat=0.0, val=0.9)
simple('BlackAlu', (0.02, 0.02, 0.022), 0.3, 0.9)
glass('Glass')
pbr('Oak', 'oak_veneer_01', val=1.05, normal=0.3, rough_add=0.05)
pbr('Walnut', 'oak_veneer_01', hue=0.49, sat=1.2, val=0.45, normal=0.3)
pbr('FabricBeige', 'rough_linen', sat=0.0, val=1.25, tint=(0.95, 0.89, 0.80), normal=0.8)
pbr('FabricOlive', 'rough_linen', sat=0.0, val=1.0, tint=(0.52, 0.55, 0.36), normal=0.8)
simple('WhiteGloss', (0.85, 0.85, 0.83), 0.2)
simple('CarPaint', (0.24, 0.19, 0.14), 0.25, 0.7)
simple('LED', (1, 0.9, 0.75), 0.5, 0, ((1.0, 0.72, 0.42), 12.0))
simple('PlantPlaceholder', (0.1, 0.25, 0.08), 0.8)
simple('Curtain', (0.93, 0.90, 0.85), 0.9, trans=0.35)
simple('DormerGlow', (0.95, 0.85, 0.7), 0.9, 0, ((1.0, 0.75, 0.45), 1.5))

# dormer back wall glows softly like a lit loft
db = bpy.data.objects.get('Dormer_back')
if db:
    db.data.materials.clear(); db.data.materials.append(bpy.data.materials['DormerGlow'])

# ---------------------------------------------------------------- worlds
def world(name, hdri, strength, rot, sat=1.0):
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    w.use_fake_user = True
    w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, rot)
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = img(os.path.join(HDRI, hdri))
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    hs = nt.nodes.new('ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = sat
    nt.links.new(env.outputs['Color'], hs.inputs['Color']); nt.links.new(hs.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return w

world('World_Dusk', 'qwantani_dusk_2_puresky_4k.hdr', 0.45, math.radians(90), sat=1.35)
world('World_Day', 'kloofendal_48d_partly_cloudy_puresky_4k.hdr', 1.0, math.radians(120))

# ---------------------------------------------------------------- lights
LC = bpy.data.collections.get('Lights') or bpy.data.collections.new('Lights')
if LC.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(LC)
for ob in list(LC.objects):
    bpy.data.objects.remove(ob)

WARM = (1.0, 0.78, 0.55)
def light(name, kind, loc, energy, color=WARM, size=0.1, rot=(0, 0, 0), spot=None, group='both'):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy; ld.color = color
    if kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = size
    if kind == 'AREA':
        ld.shape = 'RECTANGLE'; ld.size, ld.size_y = size if isinstance(size, tuple) else (size, size)
    if kind == 'SPOT' and spot:
        ld.spot_size = math.radians(spot); ld.spot_blend = 0.6
    ob = bpy.data.objects.new(name, ld); ob.location = (loc[0], -loc[1], loc[2]); ob.rotation_euler = rot
    ob['group'] = group
    LC.objects.link(ob)
    return ob

# interior downlights (warm, 3000K)
for i, (x, z) in enumerate([(1.5, 3.0), (4.5, 4.3), (4.8, 2.1), (2.55, 5.25), (1.0, 5.25), (1.4, 7.5), (4.3, 2.95)]):
    light(f'Down_{i}', 'SPOT', (x, z, 2.95), 60, WARM, 0.04, spot=110)
# terrace + facade washers (visible in the exterior renders)
light('Terrace_down', 'SPOT', (4.7, 6.65, 3.0), 90, WARM, 0.04, spot=120)
light('Soffit_wash', 'AREA', (1.5, 9.35, 3.25), 180, (1.0, 0.72, 0.45), (2.8, 0.08))
light('Terrace_wash', 'AREA', (4.5, 7.15, 3.0), 90, (1.0, 0.72, 0.45), (2.4, 0.08))
light('Dormer_in', 'POINT', (1.95, 8.8, 5.6), 25, WARM, 0.1)
light('Bed2_lamp', 'POINT', (1.2, 7.6, 2.4), 40, WARM, 0.2)
light('Garden_bollard1', 'POINT', (2.8, 9.8, 0.4), 6, WARM, 0.05)
light('Garden_bollard2', 'POINT', (2.8, 11.75, 0.4), 6, WARM, 0.05)
light('Yard_wall', 'SPOT', (3.0, 0.1, 2.2), 40, WARM, 0.05, spot=100, rot=(math.radians(-60), 0, 0))
# daylight sun for the interior scenes (enters through the back windows)
light('Sun_Day', 'SUN', (3, 6, 10), 3.5, (1.0, 0.95, 0.88), rot=(math.radians(55), 0, math.radians(200)), group='day')
bpy.data.lights['Sun_Day'].angle = math.radians(1.5)

# ---------------------------------------------------------------- render settings
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02
sc.cycles.max_bounces = 8; sc.cycles.diffuse_bounces = 4; sc.cycles.glossy_bounces = 4
sc.cycles.transmission_bounces = 8; sc.cycles.transparent_max_bounces = 16
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.cycles.sample_clamp_indirect = 8
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
sc.view_settings.view_transform = 'AgX'
try:
    sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass

# per-camera lighting mode
EXT = {'tampak_depan', 'tampak_atas', 'carport', 'denah_3d'}
for cam in [o for o in bpy.data.objects if o.type == 'CAMERA']:
    cam['mode'] = 'dusk' if cam.name in EXT else 'day'

bpy.ops.wm.save_mainfile()
print('STAGE2 SAVED')
