import * as THREE from 'three';

export function refreshSkinnedBounds(model) {
  model.updateMatrixWorld(true);
  model.traverse(object => {
    if (!object.isSkinnedMesh) return;
    object.skeleton.update();
    object.computeBoundingBox();
    object.computeBoundingSphere();
  });
}

function rotateWorld(model, name, axis, angle) {
  const bone = model.getObjectByName(name)
    || model.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(name));
  if (!bone?.isBone) throw new Error('El dragon no tiene el hueso necesario: ' + name);
  model.updateMatrixWorld(true);
  const parentRotation = bone.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
  const localAxis = new THREE.Vector3(...axis).applyQuaternion(parentRotation).normalize();
  bone.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(localAxis, angle));
}

export function compactDragonBoardPose(model) {
  if (model.userData.boardPose === 'compact-dragon-v1') return;
  rotateWorld(model, 'tail.1', [0, 1, 0], 0.45);
  rotateWorld(model, 'tail.2', [0, 1, 0], 0.8);
  rotateWorld(model, 'tail.3', [0, 1, 0], 0.95);
  rotateWorld(model, 'wing.L', [1, 0, 0], 0.32);
  rotateWorld(model, 'wing.R', [1, 0, 0], -0.32);
  model.userData.boardPose = 'compact-dragon-v1';
  refreshSkinnedBounds(model);
}