import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    blend = output / 'torre_original_muestra.blend'
    glb = output / 'torre_original.glb'
    if blend.exists() or glb.exists():
        raise FileExistsError('No se sobrescriben muestras existentes')
    candidates = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.visible_get()]
    candidates.sort(key=lambda obj: (obj.name != 'C-knight.glb', obj.name))
    if not candidates:
        raise RuntimeError('No hay una malla visible para exportar')
    original = candidates[0]
    source_object_name = original.name
    figure = original.copy()
    figure.data = original.data.copy()
    figure.matrix_world = original.matrix_world.copy()
    figure.parent = None
    figure.name = 'Heavy_Knight_original'
    for obj in list(bpy.data.objects):
        if obj != figure:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.scene.collection.objects.link(figure)
    bpy.context.view_layer.objects.active = figure
    figure.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    vertices = [vertex.co.copy() for vertex in figure.data.vertices]
    minimum = Vector(tuple(min(vertex[axis] for vertex in vertices) for axis in range(3)))
    maximum = Vector(tuple(max(vertex[axis] for vertex in vertices) for axis in range(3)))
    height = maximum.z - minimum.z
    if height <= 0:
        raise RuntimeError('Altura invalida del modelo')
    center = Vector(((minimum.x + maximum.x) / 2, (minimum.y + maximum.y) / 2, minimum.z))
    for vertex in figure.data.vertices:
        vertex.co = (vertex.co - center) * (1.65 / height)
    figure.location = (0, 0, 0)
    for polygon in figure.data.polygons:
        polygon.use_smooth = True
    figure.data.update()
    for surface in figure.data.materials:
        if not surface or not surface.use_nodes:
            continue
        for node in surface.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Roughness'].default_value = 0.5
                node.inputs['Metallic'].default_value = 0.35
    bpy.ops.file.pack_all()
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
                              export_materials='EXPORT', export_yup=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {'model': figure.name, 'source_object': source_object_name,
              'vertices': len(figure.data.vertices), 'faces': len(figure.data.polygons),
              'materials': [surface.name for surface in figure.data.materials if surface],
              'height_m': 1.65, 'rigged': False, 'geometry_origin': 'Imported from supplied SKP',
              'glb': str(glb), 'blend': str(blend)}
    (output / 'model-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('IGRIS_REAL_MODEL', json.dumps(report))


if __name__ == '__main__':
    main()