import bpy, math, os
sc = bpy.context.scene
cd = bpy.data.cameras.new('carcheck'); cam = bpy.data.objects.new('carcheck', cd); sc.collection.objects.link(cam)
cd.lens = 35; cam.location = (7.2, -13.2, 1.3); cam.rotation_euler = (math.radians(84), 0, math.radians(33))
sc.camera = cam; sc.world = bpy.data.worlds['World_Day']; sc.view_settings.exposure = 0.3
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1200, 800, 50
sc.cycles.samples = 32
sc.render.filepath = os.path.join(os.path.dirname(bpy.data.filepath), 'preview', 'car_check.jpg')
bpy.ops.render.render(write_still=True)
