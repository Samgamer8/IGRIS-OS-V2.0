import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector


BONES = {
    'root': ((0, 0, 0), (0, 0, 0.16), None),
    'hips': ((0.06, 0.05, 0.77), (0.06, 0.06, 0.95), 'root'),
    'spine': ((0.06, 0.06, 0.95), (0.06, 0.075, 1.13), 'hips'),
    'chest': ((0.06, 0.075, 1.13), (0.06, 0.075, 1.35), 'spine'),
    'head': ((0.06, 0.075, 1.35), (0.06, 0.075, 1.62), 'chest'),
    'upper_arm.L': ((-0.115, 0.085, 1.32), (-0.21, 0.02, 1.03), 'chest'),
    'forearm.L': ((-0.21, 0.02, 1.03), (-0.18, -0.06, 0.85), 'upper_arm.L'),
    'hand.L': ((-0.18, -0.06, 0.85), (-0.18, -0.06, 0.79), 'forearm.L'),
    'upper_arm.R': ((0.23, 0.105, 1.32), (0.35, 0.14, 1.11), 'chest'),
    'forearm.R': ((0.35, 0.14, 1.11), (0.405, 0.045, 1.2), 'upper_arm.R'),
    'hand.R': ((0.405, 0.045, 1.2), (0.405, 0.045, 1.26), 'forearm.R'),
    'thigh.L': ((-0.09, 0.045, 0.75), (-0.12, 0.015, 0.46), 'hips'),
    'shin.L': ((-0.12, 0.015, 0.46), (-0.14, 0.055, 0.1), 'thigh.L'),
    'foot.L': ((-0.14, 0.055, 0.1), (-0.14, -0.1, 0.045), 'shin.L'),
    'thigh.R': ((0.2, 0.06, 0.75), (0.24, 0.05, 0.46), 'hips'),
    'shin.R': ((0.24, 0.05, 0.46), (0.24, 0.055, 0.1), 'thigh.R'),
    'foot.R': ((0.24, 0.055, 0.1), (0.24, -0.1, 0.045), 'shin.R'),
}


def islands(mesh):
    parents = list(range(len(mesh.vertices)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for edge in mesh.edges:
        first, second = edge.vertices
        parents[find(second)] = find(first)
    groups = {}
    for vertex in mesh.vertices:
        groups.setdefault(find(vertex.index), []).append(vertex.index)
    return list(groups.values())


def region(point):
    if point.z > 1.445 and point.x < 0.32:
        return 'head'
    if point.x < -0.115 and point.z > 0.78:
        return 'upper_arm.L' if point.z > 1.04 else 'forearm.L'
    if point.x > 0.305 and point.z > 0.84:
        return 'forearm.R' if point.z < 1.18 else 'upper_arm.R'
    if point.z < 0.69:
        side = 'L' if point.x < 0.065 else 'R'
        return ('foot.' if point.z < 0.15 else 'shin.' if point.z < 0.52 else 'thigh.') + side
    return 'hips' if point.z < 0.98 else 'spine' if point.z < 1.15 else 'chest'


def distance(point, name):
    start, end, parent = BONES[name]
    start, end = Vector(start), Vector(end)
    direction = end - start
    ratio = max(0, min(1, (point - start).dot(direction) / direction.length_squared))
    return (point - (start + direction * ratio)).length


def rotate_world(rig, name, axis, angle):
    bone = rig.pose.bones[name]
    basis = bone.bone.matrix_local.to_quaternion()
    bone.rotation_mode = 'QUATERNION'
    bone.rotation_quaternion = basis.inverted() @ Quaternion(Vector(axis), angle) @ basis


def animate(rig, name, duration, fps):
    action = bpy.data.actions.new(name)
    rig.animation_data.action = action
    count = round(duration * fps)
    for frame in range(1, count + 2, 3):
        phase = min(1, (frame - 1) / count)
        for bone in rig.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.location = (0, 0, 0)
        if name == 'Idle':
            rotate_world(rig, 'chest', (0, 1, 0), math.sin(phase * math.tau) * 0.012)
            rotate_world(rig, 'head', (0, 0, 1), math.sin(phase * math.tau) * 0.02)
        elif name == 'Walk':
            stride = math.sin(phase * math.tau)
            for side, sign in [('L', 1), ('R', -1)]:
                rotate_world(rig, 'thigh.' + side, (1, 0, 0), stride * sign * 0.13)
                rotate_world(rig, 'shin.' + side, (1, 0, 0), max(0, stride * sign) * 0.13)
                rotate_world(rig, 'upper_arm.' + side, (1, 0, 0), -stride * sign * 0.065)
            rig.pose.bones['root'].location.z = abs(stride) * 0.012
        elif name == 'Attack':
            windup = math.sin(min(1, phase / 0.4) * math.pi / 2) * (1 - min(1, max(0, (phase - 0.65) / 0.35)))
            strike = math.sin(min(1, max(0, (phase - 0.38) / 0.35)) * math.pi)
            rotate_world(rig, 'upper_arm.R', (0, 0, 1), -windup * 0.24 + strike * 0.52)
            rotate_world(rig, 'forearm.R', (1, 0, 0), windup * 0.22)
            rotate_world(rig, 'chest', (0, 0, 1), -windup * 0.09 + strike * 0.14)
            rotate_world(rig, 'upper_arm.L', (0, 0, 1), strike * 0.12)
        elif name == 'Guard':
            raise_arm = math.sin(phase * math.pi) * 0.3
            rotate_world(rig, 'upper_arm.R', (1, 0, 0), raise_arm)
            rotate_world(rig, 'forearm.L', (0, 0, 1), -raise_arm * 0.6)
            rotate_world(rig, 'head', (1, 0, 0), raise_arm * 0.15)
        elif name == 'Reaction':
            recoil = math.sin(phase * math.pi)
            rotate_world(rig, 'spine', (1, 0, 0), -recoil * 0.1)
            rotate_world(rig, 'head', (1, 0, 0), recoil * 0.12)
            rotate_world(rig, 'upper_arm.L', (0, 0, 1), recoil * 0.15)
        for bone in rig.pose.bones:
            bone.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            bone.keyframe_insert(data_path='location', frame=frame)
    action.use_fake_user = True
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, 1, action)
    track.mute = True
    strip.extrapolation = 'NOTHING'
    return action


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'torre_articulada.blend').exists():
        raise FileExistsError('No se sobrescribe la muestra anterior')
    figure = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    armature = bpy.data.armatures.new('HeavyKnight_Rig')
    rig = bpy.data.objects.new('HeavyKnight_Rig', armature)
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (start, end, parent) in BONES.items():
        bone = armature.edit_bones.new(name)
        bone.head, bone.tail = start, end
        if parent:
            bone.parent = armature.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    groups = {name: figure.vertex_groups.new(name=name) for name in BONES}
    for indices in islands(figure.data):
        points = [figure.data.vertices[index].co for index in indices]
        minimum = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
        maximum = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
        center = (minimum + maximum) / 2
        weapon = ('hand.R' if minimum.x > 0.35 and maximum.y - minimum.y < 0.3
                  and (maximum.z - minimum.z > 0.55 or maximum.z > 1.47 or minimum.z < 0.04)
                  else 'hand.L' if minimum.x < -0.32 and maximum.z - minimum.z < 0.12 else None)
        if weapon or len(indices) < 350:
            chosen = weapon or region(center)
            groups[chosen].add(indices, 1, 'REPLACE')
        else:
            for index in indices:
                point = figure.data.vertices[index].co
                chosen = region(point)
                candidates = [chosen]
                parent = BONES[chosen][2]
                if parent and parent != 'root':
                    candidates.append(parent)
                scores = [1 / max(0.025, distance(point, name)) ** 3 for name in candidates]
                total = sum(scores)
                for name, score in zip(candidates, scores):
                    groups[name].add([index], score / total, 'REPLACE')
    figure.parent = rig
    modifier = figure.modifiers.new('Character armature', 'ARMATURE')
    modifier.object = rig
    rig.animation_data_create()
    scene = bpy.context.scene
    scene.render.fps = 24
    actions = [animate(rig, name, duration, 24) for name, duration in
               [('Idle', 2), ('Walk', 1.6), ('Attack', 2.6), ('Guard', 2.2), ('Reaction', 1.7)]]
    rig.animation_data.action = None
    for bone in rig.pose.bones:
        bone.rotation_quaternion = (1, 0, 0, 0)
        bone.location = (0, 0, 0)
    scene.frame_set(1)
    weighted = all(abs(sum(group.weight for group in vertex.groups) - 1) < 0.001 for vertex in figure.data.vertices)
    if not weighted:
        raise RuntimeError('Pesos de articulacion incompletos')
    bpy.ops.object.select_all(action='DESELECT')
    figure.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    glb = output / 'torre_articulada.glb'
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
                              export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_nla_strips=True, export_skins=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'torre_articulada.blend'))
    report = {'source_model': 'Approved Heavy Knight SKP geometry', 'bones': len(BONES),
              'vertices': len(figure.data.vertices), 'faces': len(figure.data.polygons),
              'weight_sums_valid': weighted, 'animations': [action.name for action in actions],
              'status': 'Movement sample awaiting visual approval', 'glb': str(glb)}
    (output / 'rig-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('IGRIS_RIG', json.dumps(report))


if __name__ == '__main__':
    main()