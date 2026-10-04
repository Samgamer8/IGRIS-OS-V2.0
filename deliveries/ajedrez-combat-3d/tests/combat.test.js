import test from 'node:test';
import assert from 'node:assert/strict';
import { combatFrame, combatProfile } from '../src/combat.js';
import { createFantasyPiece, poseFantasyPiece } from '../src/pieces.js';

test('characters move limbs and equipment follows the arm', () => {
  const knight = createFantasyPiece('n', 'w');
  const sword = knight.getObjectByName('sword');
  assert.equal(sword.parent, knight.rig.rightArm);
  poseFantasyPiece(knight, { attack: 0.8, walk: 0.2, guard: -0.5 });
  assert.ok(knight.rig.rightArm.rotation.x > 0.6);
  assert.equal(knight.rig.leftLeg.rotation.x, 0.2);
  const dragon = createFantasyPiece('p', 'b');
  poseFantasyPiece(dragon, { wings: 0.5, attack: 1 });
  assert.equal(dragon.rig.leftWing.rotation.x, 0.5);
  assert.ok(dragon.rig.jaw.rotation.x > 0);
});

test('all six piece types have distinct capture styles', () => {
  const profiles = ['p', 'n', 'b', 'r', 'q', 'k'].map(combatProfile);
  assert.equal(new Set(profiles.map(profile => profile.style)).size, 6);
  assert.ok(profiles.every(profile => profile.duration >= 1900));
  assert.throws(() => combatProfile('invalid'));
});

test('capture has preparation action reaction and finish without early removal', () => {
  assert.equal(combatFrame(0).actorTravel, 0);
  assert.equal(combatFrame(0.4).phase, 'prepare');
  assert.ok(combatFrame(0.6).action > 0.9);
  assert.equal(combatFrame(0.6).victimScale, 1);
  assert.ok(combatFrame(0.8).victimTilt > 0);
  assert.equal(combatFrame(1).actorTravel, 1);
  assert.equal(combatFrame(1).victimScale, 0);
});