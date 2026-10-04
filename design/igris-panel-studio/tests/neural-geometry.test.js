import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { luminousCloud, filamentPath, orbitalTopology, groupedNeuralLayers } from '../src/neural-geometry.js';

test('blue grouped scene has bounded layers and real paths for moving signals', () => {
  const grouped = groupedNeuralLayers(24);
  assert.equal(grouped.layerNames.length, 6);
  assert.equal(grouped.segments.length, 96);
  assert.equal(grouped.radials.length, 90);
  assert.equal(grouped.cortex.length, 48);
  assert.ok(grouped.signalPaths.length > 20);
  for (const path of [...grouped.cortex, ...grouped.segments, ...grouped.radials, ...grouped.signalPaths]) {
    assert.ok(path.length >= 2);
    assert.ok(path.every(point => point.toArray().every(Number.isFinite) && point.length() <= 1.4));
  }
  assert.deepEqual(groupedNeuralLayers(24).segments[0][0].toArray(), grouped.segments[0][0].toArray());
});

test('original orbital planes remain fixed while verified complexity adds branches', () => {
  const initial = orbitalTopology(24);
  const evolved = orbitalTopology(120);
  assert.equal(initial.rings.length, 15);
  assert.equal(initial.nodes.length, 24);
  assert.equal(evolved.nodes.length, 120);
  assert.ok(evolved.branches.length > initial.branches.length * 3);
  assert.deepEqual(initial.rings.map(ring => ring.points[20].toArray()),
    evolved.rings.map(ring => ring.points[20].toArray()));
  assert.ok(evolved.branches.every(branch => branch.every(point => point.length() <= 1.2)));
});

test('the glow has volumetric layers and bounded reproducible particles', () => {
  const first = luminousCloud(24);
  const second = luminousCloud(24);
  assert.ok(first.length >= 2000 && first.length < 4401);
  assert.ok(first.some(point => point.position.length() < 0.5));
  assert.ok(first.some(point => point.position.length() > 1.1));
  assert.ok(first.every(point => point.position.length() < 1.4));
  assert.deepEqual(first[0].position.toArray(), second[0].position.toArray());
});

test('filaments are curved strands rather than straight polygon edges', () => {
  const start = new THREE.Vector3(1, 0, 0);
  const end = new THREE.Vector3(0, 1, 0);
  const path = filamentPath(start, end, 2);
  assert.equal(path.length, 15);
  const midpoint = path[7];
  assert.ok(midpoint.distanceTo(start.clone().lerp(end, 0.5)) > 0.1);
  assert.ok(path.every(point => point.toArray().every(Number.isFinite)));
});