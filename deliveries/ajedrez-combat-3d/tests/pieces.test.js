import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createFantasyPiece } from '../src/pieces.js';
import { fitBoardCamera } from '../src/scene.js';
import { BOARD_HALF_EXTENT } from '../src/board-layout.js';

test('the board is framed on desktop and portrait screens', () => {
  for (const aspect of [1118 / 818, 390 / 520]) {
    const camera = new THREE.PerspectiveCamera(41, aspect, 0.1, 80);
    camera.position.set(7.2, 10.7, 10.2);
    const controls = { target: new THREE.Vector3(0, 0.1, 0) };
    fitBoardCamera(camera, controls);
    for (const x of [-BOARD_HALF_EXTENT, BOARD_HALF_EXTENT]) for (const z of [-BOARD_HALF_EXTENT, BOARD_HALF_EXTENT]) {
      const projected = new THREE.Vector3(x, 1.9, z).project(camera);
      assert.ok(Math.abs(projected.x) <= 0.92 && Math.abs(projected.y) <= 0.82);
    }
  }
});

test('all twelve reference designs produce bounded real meshes', () => {
  const designs = new Set();
  for (const color of ['w', 'b']) for (const type of ['p', 'n', 'b', 'r', 'q', 'k']) {
    const piece = createFantasyPiece(type, color);
    assert.equal(piece.userData.hasPedestal, false);
    piece.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(piece);
    const dimensions = bounds.getSize(new THREE.Vector3());
    let count = 0;
    piece.traverse(object => { if (object.isMesh) {
      count++;
      assert.ok(object.geometry.attributes.position.count > 0);
      const parameters = object.geometry.parameters;
      assert.ok(!(parameters.radiusTop === 0.3 && parameters.radiusBottom === 0.34), 'Pedestal must not be present');
    } });
    assert.ok(count > 25, `${color}-${type} lacks character detail`);
    assert.ok(dimensions.x < 1.05 && dimensions.z < 1.05, `${color}-${type} exceeds square`);
    assert.ok(dimensions.y > 1 && dimensions.y < 2, `${color}-${type} has invalid height`);
    designs.add(piece.userData.design);
  }
  assert.equal(designs.size, 12);
});

test('the two factions have different knight silhouettes', () => {
  const counts = ['w', 'b'].map(color => {
    let count = 0;
    createFantasyPiece('n', color).traverse(object => { if (object.isMesh) count++; });
    return count;
  });
  assert.notEqual(counts[0], counts[1]);
  assert.throws(() => createFantasyPiece('unknown', 'w'));
});