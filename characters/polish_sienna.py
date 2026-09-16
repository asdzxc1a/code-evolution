"""Apply reviewed v1.2 visual corrections to the reproducible Sienna builder.
Usage: python3 polish_sienna.py input_builder.py output_builder.py
The output is a complete, readable standalone Blender script.
"""
from pathlib import Path
import sys

source=Path(sys.argv[1]).read_text()
patches={
"(.040,.012,.009),.31)":"(.040,.012,.009),.36)",
"(.105,.035,.022),.34)":"(.068,.022,.014),.38)",
"(.34,.11,.51)":"(.34,.11,.45)",
"(-.67,.02,.51)":"(-.67,.02,.45)",
"uv('Body | foot '+label,(xx,yy-.08,.35),(.135,.25,.18),skin,rot=(.50,0,0))":"uv('Pump | upper '+label,(xx,yy-.07,.345),(.137,.23,.155),black,rot=(.50,0,0))",
"(3.18,.62,.35,.075,0),(3.23,.628,.353,.075,0),(3.47,.666,.373,.07,0),(3.76,.72,.39,.064,0),(4.02,.728,.388,.05,0),(4.22,.668,.36,.025,0)":"(3.18,.823,.463,.035,0),(3.23,.824,.464,.035,0),(3.47,.825,.465,.035,0),(3.76,.805,.445,.04,0),(4.02,.778,.425,.035,0),(4.22,.690,.385,.020,0)",
"curve('Dress | tailored seam '+str(sign),[(sign*.29,-.31,5.54),(sign*.25,-.265,5.13),(sign*.22,-.245,4.80),(sign*.29,-.286,4.39),(sign*.40,-.315,4.01),(sign*.385,-.32,3.50)],.008,burgundy)":"pass  # Avoid decorative curves floating above the smooth dress surface.",
}
for old,new in patches.items():
    if old not in source: raise ValueError('Missing expected patch anchor: '+old[:80])
    source=source.replace(old,new)
anchor='    # Group controls are intentionally simple and non-destructive, not a fake rig.'
addition='''    # Preserve editable construction meshes, then blend skin joins for the final sculpt.
    construction=bpy.data.collections.new('00  Construction meshes - hidden backup')
    SCENE.collection.children.link(construction)
    construction.hide_render=True; construction.hide_viewport=True
    skinparts=[o for o in COL.objects if o.type=='MESH' and (o.name.startswith('Body |') or o.name.startswith('Hand | palm') or o.name.startswith('Hand | thumb'))]
    for original in skinparts:
        backup=original.copy(); backup.data=original.data.copy()
        construction.objects.link(backup); backup.name='SOURCE | '+original.name
    def fuse_parts(parts, name, voxel):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts:
            obj.select_set(True); bpy.context.view_layer.objects.active=obj
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            for mod in list(obj.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.context.view_layer.objects.active=parts[0]; bpy.ops.object.join()
        obj=bpy.context.object; obj.name=name
        rem=obj.modifiers.new('Continuous sculpt surface','REMESH'); rem.mode='VOXEL'
        rem.voxel_size=voxel; rem.use_smooth_shade=True
        bpy.ops.object.modifier_apply(modifier=rem.name)
        sm=obj.modifiers.new('Gentle sculpt polish','SMOOTH'); sm.factor=.65; sm.iterations=3
        bpy.ops.object.modifier_apply(modifier=sm.name)
        sub=obj.modifiers.new('Sculpt finish','SUBSURF'); sub.levels=1; sub.render_levels=1
        return obj
    fuse_parts(skinparts,'Body | continuous skin sculpt',.018)
    for side in ['L','R']:
        parts=[o for o in COL.objects if o.type=='MESH' and o.name in ['Pump | upper '+side,'Pump | shoe '+side,'Pump | stiletto '+side]]
        fuse_parts(parts,'Pump | seamless shoe '+side,.010)
'''
if anchor not in source: raise ValueError('Missing surface polish anchor')
source=source.replace(anchor,addition+'\n'+anchor)
source=source.replace('Collection 01 contains editable character surfaces, jewelry and hair curves.','Collection 00 holds hidden construction meshes. Collection 01 contains editable character surfaces, jewelry and hair curves.')
Path(sys.argv[2]).write_text(source)
print('Wrote polished standalone builder:',sys.argv[2])
