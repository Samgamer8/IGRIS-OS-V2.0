import test from 'node:test';
import assert from 'node:assert/strict';
import { createFantasyPiece } from '../src/pieces.js';
import { applyStudioLook } from '../src/studio-look.js';

test('the studio changes cloned materials without altering the game', () => {
  const gamePiece = createFantasyPiece('r', 'w');
  const originalColors = [];
  gamePiece.traverse(object => { if (object.isMesh) originalColors.push(object.material.color.getHex()); });
  const sample = applyStudioLook(createFantasyPiece('r', 'w'), 'w');
  const after = [];
  gamePiece.traverse(object => { if (object.isMesh) after.push(object.material.color.getHex()); });
  assert.deepEqual(after, originalColors);
  assert.equal(sample.userData.studioOnly, true);
  let textured = 0;
  sample.traverse(object => { if (object.isMesh && object.material.bumpMap) textured++; });
  assert.ok(textured > 15);
});