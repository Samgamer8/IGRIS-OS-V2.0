import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector


def skeleton(scale_x, scale_y):
    bones = {
        'root': ((0, 0, 0), (0, 0, 0.12), None),
        'hips': ((-0.13, 0, 0.27), (-0.35, 0, 0.32), 'root'),
        'spine': ((-0.35, 0, 0.32), (-0.54, 0, 0.43), 'hips'),
        'chest': ((-0.54, 0, 0.43), (-0.69, 0, 0.57), 'spine'),
        'neck': ((-0.69, 0, 0.57), (-0.82, 0, 0.68), 'chest'),
        'head': ((-0.82, 0, 0.68), (-1.05, 0, 0.7), 'neck'),
        'jaw': ((-0.97, 0, 0.62), (-1.12, 0, 0.52), 'head'),
        'tail.1': ((-0.04, 0, 0.25), (0.33, 0, 0.17), 'hips'),
        'tail.2': ((0.33, 0, 0.17), (0.7, 0, 0.2), 'tail.1'),
        'tail.3': ((0.7, 0, 0.2), (1.1, 0.02, 0.26), 'tail.2'),
    }
    for side, sign in [('L', 1), ('R', -1)]:
        bones['wing.' + side] = ((-0.54, sign * 0.13, 0.56), (-0.37, sign * 0.45, 0.9), 'chest')
        bones['wingtip.' + side] = ((-0.37, sign * 0.45, 0.9), (0.08, sign * 0.78, 0.86), 'wing.' + side)
        bones['front.' + side] = ((-0.63, sign * 0.095, 0.39), (-0.69, sign * 0.125, 0.18), 'chest')
        bones['frontfoot.' + side] = ((-0.69, sign * 0.125, 0.18), (-0.78, sign * 0.1, 0.035), 'front.' + side)
        bones['rear.' + side] = ((-0.15, sign * 0.13, 0.3), (-0.23, sign * 0.2, 0.16), 'hips')
        bones['rearfoot.' + side] = ((-0.23, sign * 0.2, 0.16), (-0.32, sign * 0.18, 0.025), 'rear.' + side)
    return {name: (Vector((start[0] * scale_x, start[1] * scale_y, start[2])),
                   Vector((end[0] * scale_x, end[1] * scale_y, end[2])), parent)
            for name, (start, end, parent) in bones.items()}


def regions(point):
    side = 'L' if point.y >= 0 else 'R'
    if (abs(point.y) > 0.22 and point.z > 0.48) or (abs(point.y) > 0.14 and point.x > -0.61 and point.z > 0.7):
        return ['wing.' + side, 'wingtip.' + side, 'chest']
    if point.x > 0.02 and point.z < 0.44:
        return ['tail.1', 'tail.2', 'tail.3', 'hips']
    if point.x < -0.97 and point.z < 0.62:
        return ['jaw', 'head']
    if point.x < -0.86 and point.z > 0.43:
        return ['head', 'neck']
    if point.z < 0.3 and abs(point.y) > 0.045:
        return ['front.' + side, 'frontfoot.' + side, 'chest'] if point.x < -0.5 else ['rear.' + side, 'rearfoot.' + side, 'hips']
    return ['hips', 'spine', 'chest', 'neck', 'head']


def distance(point, start, end):
    direction = end - start
    ratio = min(1, max(0, (point - start).dot(direction) / direction.length_squared))
    return (point - start - direction * ratio).length


def rotate(rig, name, axis, angle):
    bone = rig.pose.bones[name]
    basis = bone.bone.matrix_local.to_quaternion()
    bone.rotation_quaternion = basis.inverted() @ Quaternion(Vector(axis), angle) @ basis


def clip(rig, name, duration):
    action = bpy.data.actions.new(name)
    rig.animation_data.action = action
    count = round(duration * 24)
    for frame in range(1, count + 2, 3):
        phase = min(1, (frame - 1) / count)
        cycle = math.sin(phase * math.tau)
        for bone in rig.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.location = (0, 0, 0)
        if name == 'Idle':
            rotate(rig, 'neck', (0, 1, 0), cycle * 0.015)
            rotate(rig, 'tail.1', (0, 0, 1), cycle * 0.035)
            rotate(rig, 'tail.2', (0, 0, 1), cycle * 0.035)
        elif name == 'Walk':
            for side, sign in [('L', 1), ('R', -1)]:
                rotate(rig, 'front.' + side, (0, 1, 0), cycle * sign * 0.09)
                rotate(rig, 'frontfoot.' + side, (0, 1, 0), -max(0, cycle * sign) * 0.09)
                rotate(rig, 'rear.' + side, (0, 1, 0), -cycle * sign * 0.1)
                rotate(rig, 'rearfoot.' + side, (0, 1, 0), -max(0, -cycle * sign) * 0.08)
            rotate(rig, 'tail.1', (0, 0, 1), cycle * 0.04)
        elif name == 'Attack':
            pulse = math.sin(phase * math.pi)
            rotate(rig, 'neck', (0, 1, 0), pulse * 0.08)
            rotate(rig, 'head', (0, 1, 0), -pulse * 0.04)
            rotate(rig, 'jaw', (0, 1, 0), pulse * 0.1)
            rotate(rig, 'wing.L', (1, 0, 0), pulse * 0.11)
            rotate(rig, 'wing.R', (1, 0, 0), -pulse * 0.11)
        elif name == 'Guard':
            pulse = math.sin(phase * math.pi)
            rotate(rig, 'wing.L', (1, 0, 0), pulse * 0.09)
            rotate(rig, 'wing.R', (1, 0, 0), -pulse * 0.09)
            rotate(rig, 'neck', (0, 1, 0), -pulse * 0.045)
        elif name == 'Reaction':
            pulse = math.sin(phase * math.pi)
            rotate(rig, 'spine', (0, 1, 0), -pulse * 0.035)
            rotate(rig, 'neck', (0, 1, 0), -pulse * 0.08)
            rotate(rig, 'tail.1', (0, 0, 1), pulse * 0.1)
        for bone in rig.pose.bones:
            bone.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            bone.keyframe_insert(data_path='location', frame=frame)
    action.use_fake_user = True
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 1, action)
    track.mute = True
    return action


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--variant', choices=['red', 'black'], required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    filename = 'dragon_' + args.variant
    if (output / (filename + '.blend')).exists():
        raise FileExistsError('No se sobrescribe el rig anterior')
    figure = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    points = [vertex.co for vertex in figure.data.vertices]
    width = max(point.x for point in points) - min(point.x for point in points)
    depth = max(point.y for point in points) - min(point.y for point in points)
    scale_x, scale_y = width / 2.2869177089691806, depth / 1.6839493634799425
    bones = skeleton(scale_x, scale_y)
    armature = bpy.data.armatures.new('Dragon_Rig_' + args.variant)
    rig = bpy.data.objects.new(armature.name, armature)
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (start, end, parent) in bones.items():
        bone = armature.edit_bones.new(name)
        bone.head, bone.tail = start, end
        if parent:
            bone.parent = armature.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    groups = {name: figure.vertex_groups.new(name=name) for name in bones}
    for vertex in figure.data.vertices:
        candidates = regions(Vector((vertex.co.x / scale_x, vertex.co.y / scale_y, vertex.co.z)))
        scored = sorted([(name, 1 / max(0.018, distance(vertex.co, bones[name][0], bones[name][1])) ** 4)
                         for name in candidates], key=lambda item: -item[1])[:2]
        total = sum(score for name, score in scored)
        for name, score in scored:
            groups[name].add([vertex.index], score / total, 'REPLACE')
    figure.parent = rig
    modifier = figure.modifiers.new('Dragon articulation', 'ARMATURE')
    modifier.object = rig
    rig.animation_data_create()
    bpy.context.scene.render.fps = 24
    actions = [clip(rig, name, duration) for name, duration in
               [('Idle', 2.5), ('Walk', 1.6), ('Attack', 2.6), ('Guard', 2.3), ('Reaction', 1.8)]]
    rig.animation_data.action = None
    for bone in rig.pose.bones:
        bone.rotation_quaternion = (1, 0, 0, 0)
        bone.location = (0, 0, 0)
    bpy.context.scene.frame_set(1)
    weighted = all(abs(sum(group.weight for group in vertex.groups) - 1) < 0.001 for vertex in figure.data.vertices)
    if not weighted:
        raise RuntimeError('Pesos incompletos en el dragon')
    bpy.ops.object.select_all(action='DESELECT')
    figure.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=str(output / (filename + '.glb')), export_format='GLB', use_selection=True,
                              export_animations=True, export_animation_mode='NLA_TRACKS', export_nla_strips=True, export_skins=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (filename + '.blend')))
    report = {'variant': args.variant, 'geometry_origin': 'User supplied Red Dragon GLB',
              'faces': len(figure.data.polygons), 'vertices': len(figure.data.vertices), 'bones': len(bones),
              'animations': [action.name for action in actions], 'weight_sums_valid': weighted,
              'rigged': True, 'board_ready': False, 'status': 'Experimental movement sample awaiting approval'}
    (output / (filename + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('IGRIS_DRAGON_RIG', json.dumps(report))


if __name__ == '__main__':
    main()