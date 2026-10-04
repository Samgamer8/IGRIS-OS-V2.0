import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import addon_utils
import bpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--addon', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    blend = output / 'torre_importada.blend'
    if blend.exists():
        raise FileExistsError('La prueba no sobrescribe un archivo Blender existente')
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    staging = output / 'staging'
    staging.mkdir(exist_ok=True)
    working = staging / 'torre_original.skp'
    shutil.copy2(source, working)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sys.path.insert(0, str(Path(args.addon).resolve()))
    addon_utils.enable('sketchup_importer', default_set=True, persistent=False)
    result = bpy.ops.import_scene.skp(filepath=str(working))
    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH' and len(obj.data.polygons)]
    report = {
        'blender': bpy.app.version_string,
        'source': str(source),
        'source_sha256': original_hash,
        'operator_result': sorted(result),
        'mesh_objects': len(meshes),
        'vertices': sum(len(obj.data.vertices) for obj in meshes),
        'faces': sum(len(obj.data.polygons) for obj in meshes),
        'objects': [{'name': obj.name, 'type': obj.type,
                     'instance_collection': obj.instance_collection.name if obj.instance_collection else None}
                    for obj in bpy.data.objects],
        'materials': [material.name for material in bpy.data.materials],
        'images': [{'name': image.name, 'size': list(image.size)} for image in bpy.data.images],
    }
    if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
        raise RuntimeError('El archivo original cambio durante la prueba')
    (output / 'import-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not meshes or report['vertices'] == 0:
        raise RuntimeError('No se importo geometria real; consulte import-report.json')
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    print('IGRIS_IMPORT_RESULT', json.dumps({key: report[key] for key in
        ('blender', 'mesh_objects', 'vertices', 'faces')}, ensure_ascii=True))
    print('IGRIS_BLEND', blend)


if __name__ == '__main__':
    main()