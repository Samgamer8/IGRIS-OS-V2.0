import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { boardPosition, CELL_SIZE, CELL_FOOTPRINT_LIMIT, fitPieceToCell } from '../src/board-layout.js';
import { compactDragonBoardPose } from '../src/board-pose.js';
import { squarePosition } from '../src/game.js';

test('visual spacing does not change logical chess coordinates', () => {
  assert.deepEqual(squarePosition('a1'), { x: -3.5, z: 3.5 });
  assert.deepEqual(boardPosition('a1'), { x: -3.5 * CELL_SIZE, z: 3.5 * CELL_SIZE });
  assert.ok(Math.abs(boardPosition('b1').x - boardPosition('a1').x - CELL_SIZE) < 1e-10);
});

test('approved figures fit a cell with uniform non-destructive scale', () => {
  for (const [type, dimensions] of [['p', [2.2869, 1.05, 1.6839]], ['r', [0.9, 1.65, 0.5]]]) {
    const geometry = new THREE.BoxGeometry(...dimensions);
    const model = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial());
    model.position.set(0.4, 0.8, -0.2);
    const original = Array.from(geometry.attributes.position.array);
    const root = fitPieceToCell(model, type, 'w');
    root.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(root);
    const size = bounds.getSize(new THREE.Vector3());
    assert.ok(size.x <= CELL_FOOTPRINT_LIMIT + 0.001);
    assert.ok(size.z <= CELL_FOOTPRINT_LIMIT + 0.001);
    assert.ok(Math.abs(bounds.min.y) < 0.001);
    assert.deepEqual(Array.from(geometry.attributes.position.array), original);
    assert.equal(root.userData.approvedAsset, true);
  }
});

test('compact pose is a bounded skeletal change and not cumulative', () => {
  const model = new THREE.Group();
  for (const name of ['tail.1', 'tail.2', 'tail.3', 'wing.L', 'wing.R']) {
    const bone = new THREE.Bone();
    bone.name = name;
    model.add(bone);
  }
  compactDragonBoardPose(model);
  const first = model.children.map(bone => bone.quaternion.toArray());
  compactDragonBoardPose(model);
  assert.deepEqual(model.children.map(bone => bone.quaternion.toArray()), first);
  assert.equal(model.userData.boardPose, 'compact-dragon-v1');
  assert.throws(() => compactDragonBoardPose(new THREE.Group()), /hueso/);
});

test('compact pose accepts exported bone names sanitized by the GLTF loader', () => {
  const model = new THREE.Group();
  for (const name of ['tail.1', 'tail.2', 'tail.3', 'wing.L', 'wing.R']) {
    const bone = new THREE.Bone();
    bone.name = THREE.PropertyBinding.sanitizeNodeName(name);
    model.add(bone);
  }
  compactDragonBoardPose(model);
  assert.equal(model.userData.boardPose, 'compact-dragon-v1');
});