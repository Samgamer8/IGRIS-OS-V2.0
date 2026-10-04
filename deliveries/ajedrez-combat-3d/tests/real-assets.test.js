import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function readGlb(relative) {
  const data = readFileSync(new URL('../public/models/' + relative, import.meta.url));
  assert.equal(data.toString('ascii', 0, 4), 'glTF');
  assert.equal(data.readUInt32LE(4), 2);
  assert.equal(data.readUInt32LE(8), data.length);
  assert.equal(data.readUInt32LE(16), 0x4e4f534a);
  return JSON.parse(data.toString('utf8', 20, 20 + data.readUInt32LE(12)));
}

test('tower has exported skin five clips and four textures', () => {
  const document = readGlb('real-tower-rig-01/torre_articulada.glb');
  assert.equal(document.skins.length, 1);
  assert.equal(document.skins[0].joints.length, 17);
  assert.deepEqual(document.animations.map(clip => clip.name).sort(), ['Attack', 'Guard', 'Idle', 'Reaction', 'Walk']);
  assert.equal(document.images.length, 4);
  for (const clip of document.animations) {
    assert.ok(clip.channels.some(channel => channel.target.path === 'rotation'));
    assert.ok(clip.samplers.some(sampler => document.accessors[sampler.output].count > 3));
  }
  for (const mesh of document.meshes) for (const primitive of mesh.primitives) {
    assert.notEqual(primitive.attributes.JOINTS_0, undefined);
    assert.notEqual(primitive.attributes.WEIGHTS_0, undefined);
  }
});

test('both bishops are identified as derived unrigged proposals', () => {
  for (const color of ['blancas', 'negras']) {
    const name = 'alfil_' + color;
    const document = readGlb('bishop-proposal-02/' + name + '.glb');
    const report = JSON.parse(readFileSync(new URL('../public/models/bishop-proposal-02/' + name + '.json', import.meta.url), 'utf8'));
    assert.equal(report.rigged, false);
    assert.match(report.origin, /derived/);
    assert.equal(report.revision, 2);
    assert.ok(report.removed_original_parts.some(part => part.part === 'helmet' && part.vertices >= 600));
    assert.ok(report.removed_original_parts.filter(part => part.part === 'weapon').length >= 5);
    assert.ok(document.meshes.length >= 10);
    assert.ok(document.images.length >= 4);
    assert.equal(document.skins?.length || 0, 0);
  }
});

test('both supplied dragons retain geometry textures and truthful rig status', () => {
  for (const variant of ['red', 'black']) {
    const document = readGlb('real-dragon-01/dragon_' + variant + '.glb');
    const report = JSON.parse(readFileSync(new URL('../public/models/real-dragon-01/dragon_' + variant + '.json', import.meta.url), 'utf8'));
    const triangles = document.meshes.flatMap(mesh => mesh.primitives)
      .reduce((total, primitive) => total + document.accessors[primitive.indices].count / 3, 0);
    assert.equal(triangles, 21013);
    assert.equal(document.images.length, 2);
    assert.equal(document.materials.length, 2);
    assert.equal(report.rigged, false);
    assert.equal(report.geometry_origin, 'User supplied Red Dragon GLB');
    assert.ok(report.width_m > 1);
    assert.ok(report.textures.every(image => image.packed && image.size[0] === 2048));
    assert.equal(document.skins?.length || 0, 0);
  }
});

test('dragon movement samples have skin clips but are not board-ready', () => {
  for (const variant of ['red', 'black']) {
    const document = readGlb('real-dragon-rig-01/dragon_' + variant + '.glb');
    const report = JSON.parse(readFileSync(new URL('../public/models/real-dragon-rig-01/dragon_' + variant + '.json', import.meta.url), 'utf8'));
    assert.equal(document.skins.length, 1);
    assert.equal(document.skins[0].joints.length, 22);
    assert.deepEqual(document.animations.map(clip => clip.name).sort(), ['Attack', 'Guard', 'Idle', 'Reaction', 'Walk']);
    assert.equal(document.images.length, 2);
    assert.equal(report.faces, 21013);
    assert.equal(report.weight_sums_valid, true);
    assert.equal(report.board_ready, false);
    assert.match(report.status, /awaiting approval/);
    for (const mesh of document.meshes) for (const primitive of mesh.primitives) {
      assert.notEqual(primitive.attributes.JOINTS_0, undefined);
      assert.notEqual(primitive.attributes.WEIGHTS_0, undefined);
    }
  }
});