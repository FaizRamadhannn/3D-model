"""Quick preview of every camera.
Run:  blender -b rumah_36_72.blend -P preview.py -- [workbench|cycles|final] [scale%] [camera names...]
"final" = full-quality Cycles render into render/final as PNG.
"""
import bpy, os, sys, time

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
engine = args[0] if args else 'workbench'
scale = int(args[1]) if len(args) > 1 else 50
only = set(args[2:])

scene = bpy.context.scene
out_dir = os.path.join(os.path.dirname(bpy.data.filepath), 'final' if engine == 'final' else 'preview')
os.makedirs(out_dir, exist_ok=True)

if engine == 'workbench':
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'
    sh.show_shadows = True; sh.show_cavity = True; sh.cavity_type = 'BOTH'
    scene.display.shadow_focus = 0.6
else:
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    if engine == 'final':
        scene.cycles.samples = 512
        scene.cycles.adaptive_threshold = 0.01
        scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        scene.cycles.denoising_prefilter = 'ACCURATE'

scene.render.resolution_percentage = scale
if engine == 'final':
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
else:
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 88

roof = bpy.data.collections.get('Roof')
for cam in [o for o in bpy.data.objects if o.type == 'CAMERA']:
    if only and cam.name not in only:
        continue
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = cam['resolution']
    top_view = cam.name == 'denah_3d'
    for ob in bpy.data.objects:
        if top_view and (ob.name.startswith(('Ceil_', 'Mansard_', 'Low_')) or (roof and ob.name in roof.objects)):
            ob.hide_render = True
        elif cam.name == 'kamar_mandi' and ob.name == 'Door_Bath':
            ob.hide_render = True
        elif ob.type != 'CAMERA':
            ob.hide_render = False
    if engine in ('cycles', 'final'):
        mode = cam.get('mode', 'day')
        scene.world = bpy.data.worlds['World_Dusk' if mode == 'dusk' else 'World_Day']
        sun = bpy.data.objects.get('Sun_Day')
        if sun:
            sun.hide_render = mode != 'day'
        scene.view_settings.exposure = cam.get('exposure', 0.0 if mode == 'dusk' else 0.8)
    ext = 'png' if engine == 'final' else 'jpg'
    scene.render.filepath = os.path.join(out_dir, f'{cam.name}.{ext}' if engine == 'final' else f'{engine}_{cam.name}.{ext}')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('RENDERED', scene.render.filepath, f'{time.time() - t0:.0f}s', flush=True)
