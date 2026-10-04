import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector


def fabric(name, color):
    surface = bpy.data.materials.new(name)
    surface.use_nodes = True
    shader = next((node for node in surface.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
    if shader is None:
        shader = surface.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    output = next((node for node in surface.node_tree.nodes if node.type == 'OUTPUT_MATERIAL'), None)
    if output is None:
        output = surface.node_tree.nodes.new('ShaderNodeOutputMaterial')
    surface.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = 0.82
    shader.inputs['Metallic'].default_value = 0
    image = bpy.data.images.new(name + '_weave', width=256, height=256)
    pixels = []
    for row in range(256):
        for column in range(256):
            grain = (((row * 19349663) ^ (column * 73856093)) % 17 - 8) / 255
            weave = -0.08 if row % 4 == 0 or column % 4 == 0 else 0.015
            value = max(0.1, min(1, 0.85 + grain + weave))
            pixels.extend([component * value for component in color] + [1])
    image.pixels.foreach_set(pixels)
    image.pack()
    texture = surface.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    surface.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    return surface


def metal(name, color):
    surface = bpy.data.materials.new(name)
    surface.use_nodes = True
    shader = next((node for node in surface.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
    if shader is None:
        shader = surface.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    output = next((node for node in surface.node_tree.nodes if node.type == 'OUTPUT_MATERIAL'), None)
    if output is None:
        output = surface.node_tree.nodes.new('ShaderNodeOutputMaterial')
    surface.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = 0.7
    shader.inputs['Roughness'].default_value = 0.4
    return surface


def mesh_object(name, vertices, faces, surface):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(surface)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for face in mesh.polygons:
        face.use_smooth = True
    uv = mesh.uv_layers.new(name='UVMap')
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            point = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = (math.atan2(point.y - 0.06, point.x - 0.06) / math.tau + 0.5, point.z / 1.7)
    return obj


def cloth_robe(surface):
    profile = [(0.14, 0.245), (0.25, 0.26), (0.45, 0.245), (0.65, 0.215),
               (0.82, 0.19), (1.02, 0.17), (1.16, 0.195)]
    vertices, faces = [], []
    count = 64
    for height, radius in profile:
        for index in range(count):
            angle = index * math.tau / count
            fold = 0.012 * math.cos(angle * 12) * (1.2 - height / 2)
            vertices.append((0.06 + (radius + fold) * math.cos(angle),
                             0.06 + (radius + fold) * 0.73 * math.sin(angle), height))
    for ring in range(len(profile) - 1):
        for index in range(count):
            following = (index + 1) % count
            faces.append((ring * count + index, ring * count + following,
                          (ring + 1) * count + following, (ring + 1) * count + index))
    return mesh_object('Folded_robes', vertices, faces, surface)


def hood(surface):
    vertices, faces = [], []
    columns, rows = 48, 22
    for row in range(rows + 1):
        theta = 0.06 + row / rows * math.pi * 0.7
        for column in range(columns + 1):
            angle = -math.pi / 2 + 0.48 + column / columns * (math.tau - 0.96)
            vertices.append((0.06 + 0.115 * math.sin(theta) * math.cos(angle),
                             0.074 + 0.112 * math.sin(theta) * math.sin(angle),
                             1.48 + 0.17 * math.cos(theta)))
    for row in range(rows):
        for column in range(columns):
            start = row * (columns + 1) + column
            faces.append((start, start + 1, start + columns + 2, start + columns + 1))
    obj = mesh_object('Cloth_hood', vertices, faces, surface)
    solidify = obj.modifiers.new('Cloth thickness', 'SOLIDIFY')
    solidify.thickness = 0.006
    return obj


def rod(name, start, end, radius, surface):
    direction = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=direction.length,
                                        location=(Vector(start) + Vector(end)) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction)
    obj.data.materials.append(surface)
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--color', choices=['w', 'b'], required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    filename = 'alfil_blancas' if args.color == 'w' else 'alfil_negras'
    if (output / (filename + '.blend')).exists():
        raise FileExistsError('No se sobrescribe una propuesta existente')
    figure = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    figure.name = 'Derived_armored_body'
    topology = bmesh.new()
    topology.from_mesh(figure.data)
    visited = set()
    remove = []
    removed_parts = []
    for start in topology.verts:
        if start in visited:
            continue
        component = []
        pending = [start]
        visited.add(start)
        while pending:
            vertex = pending.pop()
            component.append(vertex)
            for edge in vertex.link_edges:
                following = edge.other_vert(vertex)
                if following not in visited:
                    visited.add(following)
                    pending.append(following)
        minimum = Vector(tuple(min(vertex.co[axis] for vertex in component) for axis in range(3)))
        maximum = Vector(tuple(max(vertex.co[axis] for vertex in component) for axis in range(3)))
        helmet = minimum.z > 1.33 and maximum.z > 1.55 and maximum.x < 0.32
        weapon = minimum.x > 0.35 and maximum.y - minimum.y < 0.31 and (
            maximum.z - minimum.z > 0.55 or maximum.z > 1.29 or minimum.z < 0.04)
        weapon = weapon or (minimum.x > 0.35 and 0.8 < minimum.z
                            and maximum.z < 1.14 and maximum.z - minimum.z > 0.25)
        belt_weapon = minimum.x < -0.32 and maximum.z - minimum.z < 0.12
        if helmet or weapon or belt_weapon:
            remove.extend(component)
            removed_parts.append({'vertices': len(component), 'part': 'helmet' if helmet else 'weapon'})
    bmesh.ops.delete(topology, geom=remove, context='VERTS')
    topology.to_mesh(figure.data)
    topology.free()
    robe = fabric('Ivory_cloth' if args.color == 'w' else 'Midnight_cloth',
                  (0.57, 0.5, 0.38) if args.color == 'w' else (0.025, 0.043, 0.085))
    trim = metal('Staff_silver', (0.25, 0.29, 0.34))
    cloth_robe(robe)
    hood(robe)
    face = metal('Face_under_hood', (0.38, 0.26, 0.2))
    face_shader = next(node for node in face.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    face_shader.inputs['Metallic'].default_value = 0
    face_shader.inputs['Roughness'].default_value = 0.72
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=1, location=(0.06, 0.057, 1.48))
    bpy.context.object.name = 'Shadowed_face'
    bpy.context.object.scale = (0.077, 0.067, 0.11)
    bpy.context.object.data.materials.append(face)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=1, location=(0.06, -0.02, 1.465))
    bpy.context.object.name = 'Face_nose'
    bpy.context.object.scale = (0.014, 0.022, 0.026)
    bpy.context.object.data.materials.append(face)
    eyes = metal('Eyes_in_shadow', (0.02, 0.016, 0.013))
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1,
                                            location=(0.06 + side * 0.027, -0.005, 1.498))
        bpy.context.object.name = 'Eye_' + str(side)
        bpy.context.object.scale = (0.008, 0.005, 0.005)
        bpy.context.object.data.materials.append(eyes)
    rod('Mage_staff', (-0.18, -0.06, 0.09), (-0.18, -0.06, 1.79), 0.014, trim)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.057, minor_radius=0.009, location=(-0.18, -0.06, 1.79), rotation=(math.pi / 2, 0, 0))
    bpy.context.object.name = 'Staff_crown'
    bpy.context.object.data.materials.append(trim)
    jewel = metal('Staff_crystal', (0.19, 0.055, 0.15) if args.color == 'w' else (0.03, 0.14, 0.28))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.041, location=(-0.18, -0.06, 1.79))
    bpy.context.object.name = 'Staff_crystal'
    bpy.context.object.data.materials.append(jewel)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.file.pack_all()
    bpy.ops.export_scene.gltf(filepath=str(output / (filename + '.glb')), export_format='GLB', use_selection=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (filename + '.blend')))
    report = {'design': filename, 'origin': 'Proposal derived from approved knight body plus new robe hood and staff',
              'reference': 'PIEZAS_AJEDREZ_SHAPR3D bishop images', 'rigged': False,
              'status': 'Appearance awaiting approval', 'revision': 3, 'removed_original_parts': removed_parts,
              'mesh_objects': sum(obj.type == 'MESH' for obj in bpy.data.objects)}
    (output / (filename + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('IGRIS_BISHOP_PROPOSAL', json.dumps(report))


if __name__ == '__main__':
    main()