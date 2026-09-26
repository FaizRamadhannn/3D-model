import bpy
for cn in ['tree_small_02','grass_clump','island_tree','shrubs','fern_02','anthurium_botany_01']:
    c=bpy.data.collections.get(cn)
    if not c: print('missing',cn); continue
    print('==',cn,'offset',tuple(round(v,2) for v in c.instance_offset),'n',len(c.objects))
    for o in list(c.objects)[:12]:
        print('   ',o.name,'loc',tuple(round(v,2) for v in o.location),'dims',tuple(round(v,2) for v in o.dimensions),'parent',o.parent.name if o.parent else None)
