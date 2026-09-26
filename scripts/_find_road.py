import bpy
from collections import Counter
dg = bpy.context.evaluated_depsgraph_get()
cnt = Counter()
for inst in dg.object_instances:
    m = inst.matrix_world.translation
    if -19 < m.y < -12.7 and 0 < m.x < 6:
        cnt[inst.object.name.split('.')[0]] += 1
print('ROAD', cnt.most_common(15))
