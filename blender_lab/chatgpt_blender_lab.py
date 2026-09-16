"""Blender Lab: desktop add-on and headless, reproducible Blender job.
Creates a separate scene; never deletes or replaces the user's existing scene.
No network listener, telemetry, credentials, or arbitrary-code execution endpoint.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

import bpy
from mathutils import Vector

bl_info = {
    'name': 'ChatGPT Blender Lab',
    'author': 'Created with ChatGPT',
    'version': (1, 0, 0),
    'blender': (4, 0, 0),
    'location': '3D View > Sidebar > Blender Lab',
    'description': 'Create an editable Geometry Nodes double helix in a new scene',
    'category': 'Object',
}


def material(name, color, metallic=0.0, roughness=0.35):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return mat


def make_group():
    tree = bpy.data.node_groups.new('ChatGPT_Editable_Helix', 'GeometryNodeTree')
    tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    specs = [('Count', 'NodeSocketInt', 48, 3, 128),
             ('Radius', 'NodeSocketFloat', 1.65, 0.2, 5.0),
             ('Rise', 'NodeSocketFloat', 0.095, 0.01, 0.5),
             ('Twist', 'NodeSocketFloat', 0.34, 0.01, 3.14)]
    identifiers = {}
    for name, kind, default, low, high in specs:
        sock = tree.interface.new_socket(name=name, in_out='INPUT', socket_type=kind)
        sock.default_value, sock.min_value, sock.max_value = default, low, high
        identifiers[name] = sock.identifier
    sock = tree.interface.new_socket(name='Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    identifiers['Material'] = sock.identifier
    nodes, links = tree.nodes, tree.links
    inp = nodes.new('NodeGroupInput'); inp.location = (-950, 150)
    out = nodes.new('NodeGroupOutput'); out.location = (850, 150)
    line = nodes.new('GeometryNodeMeshLine'); line.location = (-700, 450)
    links.new(inp.outputs['Count'], line.inputs['Count'])
    index = nodes.new('GeometryNodeInputIndex'); index.location = (-950, -180)

    def math_node(operation, x, y, label):
        node = nodes.new('ShaderNodeMath')
        node.operation = operation
        node.label = label
        node.location = (x, y)
        return node

    angle = math_node('MULTIPLY', -700, -100, 'Index x Twist')
    links.new(index.outputs['Index'], angle.inputs[0])
    links.new(inp.outputs['Twist'], angle.inputs[1])
    cos = math_node('COSINE', -470, 30, 'cos(angle)')
    sin = math_node('SINE', -470, -150, 'sin(angle)')
    links.new(angle.outputs[0], cos.inputs[0]); links.new(angle.outputs[0], sin.inputs[0])
    xpos = math_node('MULTIPLY', -260, 30, 'Radius x cos(angle)')
    ypos = math_node('MULTIPLY', -260, -150, 'Radius x sin(angle)')
    zpos = math_node('MULTIPLY', -470, -340, 'Index x Rise')
    links.new(cos.outputs[0], xpos.inputs[0]); links.new(inp.outputs['Radius'], xpos.inputs[1])
    links.new(sin.outputs[0], ypos.inputs[0]); links.new(inp.outputs['Radius'], ypos.inputs[1])
    links.new(index.outputs['Index'], zpos.inputs[0]); links.new(inp.outputs['Rise'], zpos.inputs[1])
    pos = nodes.new('ShaderNodeCombineXYZ'); pos.location = (-40, -30)
    links.new(xpos.outputs[0], pos.inputs['X']); links.new(ypos.outputs[0], pos.inputs['Y'])
    links.new(zpos.outputs[0], pos.inputs['Z'])
    position = nodes.new('GeometryNodeSetPosition'); position.location = (160, 400)
    links.new(line.outputs['Mesh'], position.inputs['Geometry'])
    links.new(pos.outputs['Vector'], position.inputs['Position'])
    cube = nodes.new('GeometryNodeMeshCube'); cube.location = (-40, 620)
    cube.inputs['Size'].default_value = (0.66, 0.30, 0.20)
    rotation = nodes.new('ShaderNodeCombineXYZ'); rotation.location = (-40, -340)
    links.new(angle.outputs[0], rotation.inputs['Z'])
    instance = nodes.new('GeometryNodeInstanceOnPoints'); instance.location = (380, 400)
    links.new(position.outputs['Geometry'], instance.inputs['Points'])
    links.new(cube.outputs['Mesh'], instance.inputs['Instance'])
    links.new(rotation.outputs['Vector'], instance.inputs['Rotation'])
    realize = nodes.new('GeometryNodeRealizeInstances'); realize.location = (590, 400)
    links.new(instance.outputs['Instances'], realize.inputs['Geometry'])
    setmat = nodes.new('GeometryNodeSetMaterial'); setmat.location = (620, 100)
    links.new(realize.outputs['Geometry'], setmat.inputs['Geometry'])
    links.new(inp.outputs['Material'], setmat.inputs['Material'])
    links.new(setmat.outputs['Geometry'], out.inputs['Geometry'])
    return tree, identifiers


def mesh_object(scene, name, vertices, faces, mat=None):
    mesh = bpy.data.meshes.new(name + '_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    if mat is not None:
        mesh.materials.append(mat)
    return obj


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def build_scene(count=48, radius=1.65, rise=0.095, twist=0.34):
    count = int(count)
    if not 3 <= count <= 128 or not 0.2 <= radius <= 5.0 or not 0.01 <= rise <= 0.5 or not 0.01 <= twist <= 3.14:
        raise ValueError('Parameters outside supported bounds')
    scene = bpy.data.scenes.new('ChatGPT_Blender_Lab')
    if bpy.context.window is not None:
        bpy.context.window.scene = scene
    teal = material('Lab_Teal_Metal', (0.018, 0.40, 0.43), 0.72, 0.25)
    gold = material('Lab_Warm_Metal', (0.72, 0.31, 0.075), 0.76, 0.26)
    dark = material('Lab_Stage', (0.024, 0.031, 0.046), 0.20, 0.42)
    tree, identifiers = make_group()
    helices = []
    for number, mat in enumerate((teal, gold)):
        obj = mesh_object(scene, 'ChatGPT_Helix_' + str(number + 1), [], [])
        obj.rotation_euler[2] = number * math.pi
        obj.location.z = 0.18
        mod = obj.modifiers.new('Editable Geometry Nodes', 'NODES')
        mod.node_group = tree
        for name, value in [('Count', count), ('Radius', radius), ('Rise', rise), ('Twist', twist), ('Material', mat)]:
            mod[identifiers[name]] = value
        bevel = obj.modifiers.new('Rounded Edges', 'BEVEL')
        bevel.width, bevel.segments = 0.045, 3
        helices.append(obj)
    mesh_object(scene, 'Lab_Ground', [(-100,-100,-0.05),(100,-100,-0.05),(100,100,-0.05),(-100,100,-0.05)], [(0,1,2,3)], dark)
    # A small circular podium, constructed without context-sensitive operators.
    n = 96
    verts = [(2.45*math.cos(2*math.pi*i/n), 2.45*math.sin(2*math.pi*i/n), z) for z in (-0.04, 0.07) for i in range(n)]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    podium = mesh_object(scene, 'Lab_Podium', verts, faces, dark)
    bevel = podium.modifiers.new('Podium Edge', 'BEVEL'); bevel.width = 0.04; bevel.segments = 3
    center = (0, 0, count*rise*0.5)
    camera = bpy.data.objects.new('Lab_Camera', bpy.data.cameras.new('Lab_Camera'))
    scene.collection.objects.link(camera)
    camera.location = (8.4, -11.6, 7.7)
    point_at(camera, center)
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = max(7.5, count*rise*1.4, radius*3.7)
    scene.camera = camera
    for name, loc, power, size in [('Key',(4,-4,8),1800,5), ('Fill',(-4,-2,5),1300,4), ('Rim',(1,5,7),2100,3)]:
        data = bpy.data.lights.new('Lab_'+name, 'AREA'); data.energy = power; data.shape = 'DISK'; data.size = size
        light = bpy.data.objects.new('Lab_'+name, data); scene.collection.objects.link(light); light.location = loc; point_at(light, center)
    world = bpy.data.worlds.new('Lab_World'); world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.055,0.07,0.10,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.45
    scene.world = world
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'; scene.cycles.samples = 32; scene.cycles.use_denoising = True
    scene.render.resolution_x = 640; scene.render.resolution_y = 640; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    return scene, helices, tree, identifiers


def evaluated_width(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return max(v[0] for v in evaluated.bound_box) - min(v[0] for v in evaluated.bound_box)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='blender_output')
    parser.add_argument('--job')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    config = json.loads(Path(args.job).read_text()) if args.job else {}
    allowed = {'count', 'radius', 'rise', 'twist'}
    if set(config) - allowed:
        raise ValueError('Unsupported job settings: ' + str(set(config) - allowed))
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    scene, helices, tree, identifiers = build_scene(**config)
    obj = helices[0]; modifier = obj.modifiers['Editable Geometry Nodes']; key = identifiers['Radius']
    original = modifier[key]
    modifier[key] = 1.0; obj.update_tag(); small = evaluated_width(obj)
    modifier[key] = 2.0; obj.update_tag(); large = evaluated_width(obj)
    modifier[key] = original; obj.update_tag(); bpy.context.view_layer.update()
    assert large > small + 1.0, ('Geometry Nodes parameter control failed', small, large)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    vertices = len(evaluated.data.vertices)
    assert vertices > 0, 'Empty evaluated geometry'
    blend_path = out / 'chatgpt_blender_lab.blend'
    png_path = out / 'chatgpt_blender_lab.png'
    scene.render.filepath = str(png_path)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True, scene=scene.name)
    assert blend_path.is_file() and png_path.is_file()
    with zipfile.ZipFile(out / 'chatgpt_blender_lab_addon.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(Path(__file__).resolve(), 'chatgpt_blender_lab/__init__.py')
    proof = {
        'status': 'PASS', 'blender_version': bpy.app.version_string,
        'blender_build_hash': bpy.app.build_hash.decode(),
        'execution': 'real Blender, headless, Cycles CPU',
        'scene': scene.name, 'objects': [o.name for o in scene.objects],
        'node_group': tree.name, 'node_count': len(tree.nodes), 'link_count': len(tree.links),
        'evaluated_helix_vertices': vertices,
        'parameter_test': {'radius_1_width': small, 'radius_2_width': large, 'passed': large > small + 1.0},
        'render': {'width': 640, 'height': 640, 'samples': 32},
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (blend_path, png_path)},
    }
    (out / 'proof.json').write_text(json.dumps(proof, indent=2))
    print('BLENDER_EXECUTION_PROOF_BEGIN')
    print(json.dumps(proof, indent=2))
    print('BLENDER_EXECUTION_PROOF_END')


class CHATGPT_OT_build_lab(bpy.types.Operator):
    bl_idname = 'chatgpt.build_blender_lab'
    bl_label = 'Create Geometry Nodes Lab'
    bl_description = 'Create a separate, editable double-helix scene; keep existing scenes'
    bl_options = {'REGISTER', 'UNDO'}
    count: bpy.props.IntProperty(name='Segments per helix', default=48, min=3, max=128)
    radius: bpy.props.FloatProperty(name='Radius', default=1.65, min=0.2, max=5.0)
    def execute(self, context):
        build_scene(count=self.count, radius=self.radius)
        self.report({'INFO'}, 'Created a new Blender Lab scene')
        return {'FINISHED'}


class CHATGPT_PT_blender_lab(bpy.types.Panel):
    bl_label = 'ChatGPT Blender Lab'
    bl_idname = 'CHATGPT_PT_blender_lab'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Blender Lab'
    def draw(self, context):
        self.layout.label(text='Real, editable Geometry Nodes')
        self.layout.operator('chatgpt.build_blender_lab', icon='NODETREE')
        self.layout.label(text='Creates a new scene; keeps your work.')


CLASSES = (CHATGPT_OT_build_lab, CHATGPT_PT_blender_lab)

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    main()
