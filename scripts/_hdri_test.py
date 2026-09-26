import bpy, math, os
sc=bpy.context.scene; cam=bpy.data.objects['tampak_depan']; sc.camera=cam
sc.render.resolution_x, sc.render.resolution_y = cam['resolution']; sc.render.resolution_percentage=20
sc.world=bpy.data.worlds['World_Dusk']; bpy.data.objects['Sun_Day'].hide_render=True
sc.cycles.samples=16
mp=[n for n in sc.world.node_tree.nodes if n.type=='MAPPING'][0]
for deg in (0,90,180,270):
    mp.inputs['Rotation'].default_value=(0,0,math.radians(deg))
    sc.render.filepath=os.path.join(os.path.dirname(bpy.data.filepath),'preview',f'hdri_{deg}.jpg')
    bpy.ops.render.render(write_still=True)
