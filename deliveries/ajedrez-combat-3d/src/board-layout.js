import * as THREE from 'three';
import { squarePosition } from './game.js';
import { refreshSkinnedBounds } from './board-pose.js';

export const CELL_SIZE = 1.8;
export const BOARD_HALF_EXTENT = 4.65 * CELL_SIZE;
export const PIECE_HEIGHT = { p: 0.95, n: 1.43, b: 1.7, r: 1.65, q: 1.62, k: 1.8 };
export const CELL_FOOTPRINT_LIMIT = CELL_SIZE * 0.86;

export function boardPosition(square) {
  const position = squarePosition(square);
  return { x: position.x * CELL_SIZE, z: position.z * CELL_SIZE };
}

export function fitPieceToCell(model, type, color) {
  if (!Object.hasOwn(PIECE_HEIGHT, type) || !['w', 'b'].includes(color)) throw new Error('Figura no valida');
  refreshSkinnedBounds(model);
  const bounds = new THREE.Box3().setFromObject(model);
  const size = bounds.getSize(new THREE.Vector3());
  if (!(size.y > 0) || !Number.isFinite(size.y)) throw new Error('Modelo sin dimensiones validas');
  if (![size.x, size.y, size.z].every(value => value > 0 && Number.isFinite(value))) throw new Error('Geometria no valida');
  const scale = Math.min(PIECE_HEIGHT[type] / size.y, CELL_FOOTPRINT_LIMIT / Math.max(size.x, size.z));
  const center = bounds.getCenter(new THREE.Vector3());
  model.position.sub(new THREE.Vector3(center.x, bounds.min.y, center.z));
  const root = new THREE.Group();
  root.name = `${color}_${type}_board`;
  const scaled = new THREE.Group();
  scaled.scale.setScalar(scale);
  scaled.add(model);
  root.add(scaled);
  root.rotation.y = type === 'p' ? (color === 'w' ? -Math.PI / 2 : Math.PI / 2)
    : type === 'r' ? (color === 'w' ? Math.PI : 0) : 0;
  root.userData.approvedAsset = true;
  root.userData.pieceType = type;
  root.userData.color = color;
  root.userData.fitScale = scale;
  root.userData.targetHeight = PIECE_HEIGHT[type];
  root.userData.boardPose = model.userData.boardPose || 'original';
  root.updateMatrixWorld(true);
  const fitted = new THREE.Box3().setFromObject(root);
  const actual = fitted.getSize(new THREE.Vector3());
  if (actual.x > CELL_FOOTPRINT_LIMIT + 0.001 || actual.z > CELL_FOOTPRINT_LIMIT + 0.001
      || Math.abs(fitted.min.y) > 0.001) throw new Error('La figura no encaja con apoyo correcto');
  return root;
}