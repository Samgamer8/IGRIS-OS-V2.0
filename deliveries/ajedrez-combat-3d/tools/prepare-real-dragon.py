import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--variant', choices=['red', 'black'], required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    filename = 'dragon_' + args.variant
    if (output / (filename + '.glb')).exists() or (output / (filename + '.blend')).exists():
        raise FileExistsError('No se sobrescriben muestras de dragon anteriores')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        raise RuntimeError('No se importo una malla real')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    points = [vertex.co.copy() for obj in meshes for vertex in obj.data.vertices]
    minimum = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    maximum = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    height = maximum.z - minimum.z
    if height <= 0:
        raise RuntimeError('La altura de la malla no es valida')
    center = Vector(((minimum.x + maximum.x) / 2, (minimum.y + maximum.y) / 2, minimum.z))
    scale = 1.05 / height
    for obj in meshes:
        obj.name = 'Original_dragon_' + args.variant
        for vertex in obj.data.vertices:
            vertex.co = (vertex.co - center) * scale
        obj.data.update()
    bpy.ops.file.pack_all()
    glb = output / (filename + '.glb')
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
                              export_materials='EXPORT', export_animations=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (filename + '.blend')))
    report = {'variant': args.variant, 'source': str(source), 'source_sha256': source_hash,
              'geometry_origin': 'User supplied Red Dragon GLB',
              'faces': sum(len(obj.data.polygons) for obj in meshes),
              'vertices': sum(len(obj.data.vertices) for obj in meshes),
              'materials': len({surface.name for obj in meshes for surface in obj.data.materials if surface}),
              'height_m': 1.05, 'width_m': (maximum.x - minimum.x) * scale,
              'depth_m': (maximum.y - minimum.y) * scale, 'rigged': False,
              'status': 'Appearance review; pose not adapted to chess square',
              'textures': [{'name': image.name, 'size': list(image.size), 'packed': bool(image.packed_file)}
                           for image in bpy.data.images if image.type == 'IMAGE']}
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError('El GLB original cambio durante la conversion')
    (output / (filename + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('IGRIS_DRAGON_SAMPLE', json.dumps(report))


if __name__ == '__main__':
    main()