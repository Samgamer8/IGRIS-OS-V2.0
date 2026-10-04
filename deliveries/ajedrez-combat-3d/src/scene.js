import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneCharacter } from 'three/addons/utils/SkeletonUtils.js';
import { boardPosition as squarePosition, CELL_SIZE, BOARD_HALF_EXTENT, fitPieceToCell } from './board-layout.js';
import { compactDragonBoardPose } from './board-pose.js';
import { createFantasyPiece } from './pieces.js';

const geometries = new Map();
function geometry(key, create) {
  if (!geometries.has(key)) geometries.set(key, create());
  return geometries.get(key);
}
const cylinder = (top, bottom, height) => geometry(`c${top}-${bottom}-${height}`, () => new THREE.CylinderGeometry(top, bottom, height, 24));
const sphere = radius => geometry(`s${radius}`, () => new THREE.SphereGeometry(radius, 20, 12));
const box = (width, height, depth) => geometry(`b${width}-${height}-${depth}`, () => new THREE.BoxGeometry(width, height, depth));
const torus = (radius, tube) => geometry(`t${radius}-${tube}`, () => new THREE.TorusGeometry(radius, tube, 8, 32));

function mesh(parent, shape, material, position, scale) {
  const object = new THREE.Mesh(shape, material);
  if (position) object.position.set(...position);
  if (scale) object.scale.set(...scale);
  object.castShadow = true;
  object.receiveShadow = true;
  parent.add(object);
  return object;
}

export function fitBoardCamera(camera, controls) {
  const direction = camera.position.clone().sub(controls.target).normalize();
  const corners = [];
  for (const x of [-BOARD_HALF_EXTENT, BOARD_HALF_EXTENT]) for (const z of [-BOARD_HALF_EXTENT, BOARD_HALF_EXTENT]) {
    for (const y of [0, 1.9]) corners.push(new THREE.Vector3(x, y, z));
  }
  let distance = 11;
  for (let attempt = 0; attempt < 40; attempt++) {
    camera.position.copy(controls.target).addScaledVector(direction, distance);
    camera.lookAt(controls.target);
    camera.updateMatrixWorld();
    const framed = corners.every(corner => {
      const projected = corner.clone().project(camera);
      return Math.abs(projected.x) <= 0.91 && Math.abs(projected.y) <= 0.81;
    });
    if (framed) return;
    distance *= 1.05;
  }
}

export class BoardScene {
  constructor(container, onSquare) {
    this.container = container;
    this.onSquare = onSquare;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x101315);
    this.scene.fog = new THREE.Fog(0x101315, 55, 120);
    this.camera = new THREE.PerspectiveCamera(41, 1, 0.1, 140);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.autoUpdate = false;
    this.renderer.shadowMap.needsUpdate = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.92;
    const environment = new THREE.PMREMGenerator(this.renderer);
    this.environmentMap = environment.fromScene(new RoomEnvironment(), 0.04);
    this.scene.environment = this.environmentMap.texture;
    this.scene.environmentIntensity = 0.45;
    environment.dispose();
    this.renderer.domElement.setAttribute('aria-label', 'Tablero de ajedrez 3D');
    container.append(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.09;
    this.controls.enablePan = false;
    this.controls.minDistance = 10;
    this.controls.maxDistance = 75;
    this.controls.minPolarAngle = 0.2;
    this.controls.maxPolarAngle = 1.12;
    this.controls.target.set(0, 0.1, 0);
    this.needsRender = true;
    this.controls.addEventListener('change', () => { this.needsRender = true; });
    this.side = 'w';
    this.tiles = new Map();
    this.pieces = new Map();
    this.approvedModels = new Map();
    this.loading = true;
    this.error = null;
    this.pieceRoot = new THREE.Group();
    this.markers = new THREE.Group();
    this.markerMaterials = new Map();
    this.scene.add(this.pieceRoot, this.markers);
    this.materials = {
      light: new THREE.MeshStandardMaterial({ color: 0xc6c3b4, roughness: 0.56, metalness: 0.04 }),
      dark: new THREE.MeshStandardMaterial({ color: 0x354149, roughness: 0.5, metalness: 0.08 }),
      border: new THREE.MeshStandardMaterial({ color: 0x25292b, roughness: 0.31, metalness: 0.65 }),
      trim: new THREE.MeshStandardMaterial({ color: 0xaf885a, roughness: 0.28, metalness: 0.78 }),
      w: new THREE.MeshStandardMaterial({ color: 0xc8d5d4, roughness: 0.24, metalness: 0.78 }),
      b: new THREE.MeshStandardMaterial({ color: 0x35404a, roughness: 0.28, metalness: 0.79 }),
      jewelW: new THREE.MeshStandardMaterial({ color: 0x4ef1bd, emissive: 0x18946c, emissiveIntensity: 0.9, roughness: 0.25, metalness: 0.3 }),
      jewelB: new THREE.MeshStandardMaterial({ color: 0xffad61, emissive: 0xb54c16, emissiveIntensity: 0.65, roughness: 0.25, metalness: 0.3 }),
    };
    this.buildEnvironment();
    this.buildBoard();
    this.home();
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    let down = null;
    this.renderer.domElement.addEventListener('pointerdown', event => { down = { x: event.clientX, y: event.clientY }; });
    this.renderer.domElement.addEventListener('pointerup', event => {
      if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 6) return;
      const square = this.pick(event.clientX, event.clientY);
      if (square) this.onSquare(square);
      down = null;
    });
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.renderer.setAnimationLoop(time => {
      const moved = this.controls.update();
      if (this.animation) { this.advanceAnimation(time); this.needsRender = true; }
      if (moved || this.needsRender) {
        this.renderer.render(this.scene, this.camera);
        this.needsRender = false;
      }
    });
    this.ready = this.loadApprovedModels();
  }

  async loadApprovedModels() {
    const loader = new GLTFLoader();
    const assets = [
      ['w-p', './models/real-dragon-rig-01/dragon_red.glb'],
      ['b-p', './models/real-dragon-rig-01/dragon_black.glb'],
      ['r', './models/real-tower-rig-01/torre_articulada.glb'],
    ];
    try {
      await Promise.all(assets.map(async ([key, path]) => {
        const asset = await loader.loadAsync(new URL(path, document.baseURI).href);
        this.approvedModels.set(key, asset);
      }));
    } catch (error) {
      this.error = error.message;
      throw error;
    } finally { this.loading = false; }
  }

  buildEnvironment() {
    this.scene.add(new THREE.HemisphereLight(0xd9f1e8, 0x292620, 1.5));
    const key = new THREE.DirectionalLight(0xffebcb, 2.1);
    key.position.set(-4 * CELL_SIZE, 11 * CELL_SIZE, 5 * CELL_SIZE);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 0.1, far: 60 });
    key.shadow.bias = -0.00035;
    key.shadow.normalBias = 0.035;
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xb6d0db, 1.6);
    rim.position.set(5 * CELL_SIZE, 5 * CELL_SIZE, -7 * CELL_SIZE);
    this.scene.add(rim);
    const floor = mesh(this.scene, geometry('floor', () => new THREE.PlaneGeometry(70, 70)),
      new THREE.MeshStandardMaterial({ color: 0x171c1b, roughness: 0.88 }), [0, -0.62, 0]);
    floor.rotation.x = -Math.PI / 2;
    floor.castShadow = false;
    for (const side of [-1, 1]) {
      for (const offset of [-1, 1]) {
        const pedestal = new THREE.Group();
        pedestal.position.set(side * 7.1 * CELL_SIZE, -0.5, offset * 5.7 * CELL_SIZE);
        mesh(pedestal, cylinder(0.3, 0.45, 1.7), this.materials.border, [0, 0.55, 0]);
        mesh(pedestal, cylinder(0.45, 0.35, 0.18), this.materials.trim, [0, 1.48, 0]);
        mesh(pedestal, sphere(0.16), side < 0 ? this.materials.jewelW : this.materials.jewelB, [0, 1.65, 0]);
        this.scene.add(pedestal);
      }
    }
  }

  buildBoard() {
    mesh(this.scene, box(9.15 * CELL_SIZE, 0.42, 9.15 * CELL_SIZE), this.materials.border, [0, -0.3, 0]);
    mesh(this.scene, box(9.18 * CELL_SIZE, 0.055, 9.18 * CELL_SIZE), this.materials.trim, [0, -0.08, 0]);
    mesh(this.scene, box(8.64 * CELL_SIZE, 0.08, 8.64 * CELL_SIZE), this.materials.border, [0, -0.025, 0]);
    for (let rank = 1; rank <= 8; rank++) {
      for (let file = 0; file < 8; file++) {
        const square = String.fromCharCode(97 + file) + rank;
        const position = squarePosition(square);
        const tile = mesh(this.scene, box(0.992 * CELL_SIZE, 0.085, 0.992 * CELL_SIZE), (file + rank) % 2 ? this.materials.dark : this.materials.light,
          [position.x, 0.04, position.z]);
        tile.userData.square = square;
        this.tiles.set(square, tile);
      }
    }
    for (let index = 0; index < 8; index++) {
      this.label(String.fromCharCode(65 + index), (index - 3.5) * CELL_SIZE, 4.3 * CELL_SIZE);
      this.label(String(index + 1), -4.3 * CELL_SIZE, (3.5 - index) * CELL_SIZE);
      this.label(String.fromCharCode(65 + index), (index - 3.5) * CELL_SIZE, -4.3 * CELL_SIZE, Math.PI);
      this.label(String(index + 1), 4.3 * CELL_SIZE, (3.5 - index) * CELL_SIZE, Math.PI);
    }
  }

  label(text, x, z, angle = 0) {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 128;
    const context = canvas.getContext('2d');
    context.font = '500 62px sans-serif';
    context.fillStyle = '#bfa67f';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(text, 64, 68);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const label = new THREE.Mesh(new THREE.PlaneGeometry(0.32 * CELL_SIZE, 0.32 * CELL_SIZE), new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false }));
    label.rotation.set(-Math.PI / 2, 0, angle);
    label.position.set(x, 0.045, z);
    this.scene.add(label);
  }

  createPiece(type, color) {
    if (type === 'p' || type === 'r') {
      const asset = this.approvedModels.get(type === 'r' ? 'r' : `${color}-p`);
      if (!asset) {
        const empty = new THREE.Group();
        empty.userData.loading = true;
        return empty;
      }
      const model = cloneCharacter(asset.scene);
      if (type === 'p') compactDragonBoardPose(model);
      const materials = new Map();
      model.traverse(object => {
        if (!object.isMesh) return;
        object.castShadow = object.receiveShadow = true;
        if (!materials.has(object.material.uuid)) {
          const surface = object.material.clone();
          surface.userData.boardInstance = true;
          materials.set(object.material.uuid, surface);
        }
        object.material = materials.get(object.material.uuid);
      });
      const piece = fitPieceToCell(model, type, color);
      piece.userData.asset = type === 'r' ? 'Heavy Knight original' : color === 'w' ? 'Red Dragon red' : 'Red Dragon black';
      return piece;
    }
    return createFantasyPiece(type, color);
  }

  createLegacyPiece(type, color) {
    const root = new THREE.Group();
    const body = this.materials[color];
    const accent = color === 'w' ? this.materials.jewelW : this.materials.jewelB;
    mesh(root, cylinder(0.27, 0.34, 0.13), body, [0, 0.08, 0]);
    const rim = mesh(root, torus(0.29, 0.021), this.materials.trim, [0, 0.145, 0]);
    rim.rotation.x = Math.PI / 2;
    mesh(root, cylinder(0.22, 0.26, 0.11), body, [0, 0.19, 0]);
    const ring = mesh(root, torus(0.225, 0.011), accent, [0, 0.25, 0]);
    ring.rotation.x = Math.PI / 2;
    if (type === 'p') {
      mesh(root, cylinder(0.075, 0.17, 0.34), body, [0, 0.43, 0]);
      mesh(root, sphere(0.12), body, [0, 0.65, -0.04], [0.9, 1.1, 1.55]);
      mesh(root, box(0.09, 0.08, 0.16), body, [0, 0.64, -0.18]);
      for (const side of [-1, 1]) {
        const wingShape = new THREE.Shape();
        wingShape.moveTo(0, 0); wingShape.lineTo(side * 0.23, 0.2); wingShape.lineTo(side * 0.31, -0.08); wingShape.closePath();
        mesh(root, geometry(`wing${side}`, () => new THREE.ExtrudeGeometry(wingShape, { depth: 0.025, bevelEnabled: false })), body, [0, 0.49, 0.015]);
        mesh(root, sphere(0.024), accent, [side * 0.084, 0.67, -0.15]);
        const horn = mesh(root, cylinder(0, 0.025, 0.12), this.materials.trim, [side * 0.07, 0.8, 0]);
        horn.rotation.z = -side * 0.25;
      }
    } else if (type === 'n') {
      mesh(root, cylinder(0.13, 0.21, 0.35), body, [0, 0.43, 0]);
      const shape = new THREE.Shape();
      shape.moveTo(-0.17, 0); shape.lineTo(0.15, 0); shape.lineTo(0.2, 0.34); shape.lineTo(0.02, 0.64);
      shape.lineTo(-0.12, 0.62); shape.lineTo(-0.27, 0.38); shape.lineTo(-0.35, 0.3); shape.lineTo(-0.32, 0.19); shape.lineTo(-0.09, 0.27); shape.closePath();
      const head = mesh(root, geometry('horse', () => new THREE.ExtrudeGeometry(shape, { depth: 0.19, bevelEnabled: true, bevelSize: 0.025, bevelThickness: 0.025, bevelSegments: 2, steps: 1 })), body, [-0.1, 0.48, 0.08]);
      head.rotation.y = Math.PI / 2;
      for (const side of [-1, 1]) {
        mesh(root, cylinder(0, 0.05, 0.18), this.materials.trim, [side * 0.06, 1.13, -0.02]);
        mesh(root, sphere(0.027), accent, [side * 0.13, 0.91, -0.19]);
      }
    } else if (type === 'r') {
      mesh(root, cylinder(0.19, 0.22, 0.55), body, [0, 0.54, 0]);
      mesh(root, cylinder(0.28, 0.21, 0.12), this.materials.trim, [0, 0.86, 0]);
      for (let index = 0; index < 6; index++) {
        const angle = index * Math.PI / 3;
        mesh(root, box(0.13, 0.15, 0.13), body, [Math.sin(angle) * 0.2, 0.99, Math.cos(angle) * 0.2]);
      }
      mesh(root, sphere(0.075), accent, [0, 0.94, 0]);
    } else {
      const height = type === 'k' ? 0.65 : type === 'q' ? 0.6 : 0.52;
      mesh(root, cylinder(0.1, 0.22, height), body, [0, 0.27 + height / 2, 0]);
      mesh(root, cylinder(0.24, 0.1, 0.09), this.materials.trim, [0, height + 0.3, 0]);
      if (type === 'b') {
        mesh(root, sphere(0.14), body, [0, 1, 0], [1, 1.4, 1]);
        const slit = mesh(root, box(0.022, 0.23, 0.3), accent, [0, 1.03, 0]);
        slit.rotation.z = -0.28;
        mesh(root, sphere(0.045), this.materials.trim, [0, 1.21, 0]);
      } else if (type === 'q') {
        mesh(root, cylinder(0.19, 0.13, 0.15), body, [0, 1.03, 0]);
        for (let index = 0; index < 7; index++) {
          const angle = index * Math.PI * 2 / 7;
          mesh(root, cylinder(0.025, 0.055, 0.19), body, [Math.sin(angle) * 0.16, 1.17, Math.cos(angle) * 0.16]);
          mesh(root, sphere(0.035), accent, [Math.sin(angle) * 0.16, 1.28, Math.cos(angle) * 0.16]);
        }
      } else {
        mesh(root, sphere(0.13), body, [0, 1.1, 0]);
        mesh(root, box(0.07, 0.33, 0.07), this.materials.trim, [0, 1.35, 0]);
        mesh(root, box(0.25, 0.07, 0.07), this.materials.trim, [0, 1.4, 0]);
        mesh(root, sphere(0.045), accent, [0, 1.26, -0.08]);
      }
    }
    root.position.y = 0.09;
    root.rotation.y = color === 'w' ? 0 : Math.PI;
    return root;
  }

  sync(chess) {
    const oldMaterials = new Set();
    this.pieceRoot.traverse(object => {
      if (object.isMesh && object.material.userData.boardInstance) oldMaterials.add(object.material);
    });
    for (const surface of oldMaterials) surface.dispose();
    this.pieceRoot.clear();
    this.pieces.clear();
    for (const row of chess.board()) for (const piece of row) if (piece) {
      const group = this.createPiece(piece.type, piece.color);
      const position = squarePosition(piece.square);
      group.position.set(position.x, 0.09, position.z);
      group.userData.square = piece.square;
      this.pieces.set(piece.square, group);
      this.pieceRoot.add(group);
    }
    this.needsRender = true;
    this.renderer.shadowMap.needsUpdate = true;
  }

  highlight(selected, legal, lastMove, kingInCheck) {
    this.markers.clear();
    this.needsRender = true;
    const colors = new Map();
    if (lastMove) { colors.set(lastMove.from, 0xf0b879); colors.set(lastMove.to, 0xf0b879); }
    if (kingInCheck) colors.set(kingInCheck, 0xef6c64);
    if (selected) colors.set(selected, 0x55e9ba);
    for (const [square, color] of colors) this.marker(square, color, 0.44 * CELL_SIZE, 0.4 * CELL_SIZE);
    for (const move of legal || []) this.marker(move.to, 0x6ef0c7, (move.captured ? 0.41 : 0.1) * CELL_SIZE, (move.captured ? 0.036 : 0.1) * CELL_SIZE);
  }

  marker(square, color, radius, inner) {
    const position = squarePosition(square);
    const shape = geometry(`ring${radius}-${inner}`, () => new THREE.RingGeometry(Math.max(0, radius - inner), radius, 40));
    if (!this.markerMaterials.has(color)) this.markerMaterials.set(color,
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.64, depthWrite: false, side: THREE.DoubleSide }));
    const marker = new THREE.Mesh(shape, this.markerMaterials.get(color));
    marker.rotation.x = -Math.PI / 2;
    marker.position.set(position.x, 0.09, position.z);
    this.markers.add(marker);
  }

  animateMove(move, chess, enabled = true) {
    if (!enabled || !this.pieces.has(move.from)) { this.sync(chess); return Promise.resolve(); }
    const actor = this.pieces.get(move.from);
    const target = squarePosition(move.to);
    const victimSquare = move.flags.includes('e') ? move.to[0] + move.from[1] : move.to;
    return new Promise(resolve => {
      this.animation = { actor, victim: this.pieces.get(victimSquare), start: actor.position.clone(),
        target: new THREE.Vector3(target.x, 0.09, target.z), began: performance.now(),
        duration: move.captured ? 820 : 350, jump: move.piece === 'n' ? 2.1 : 0, chess, resolve };
    });
  }

  advanceAnimation(time) {
    this.renderer.shadowMap.needsUpdate = true;
    const animation = this.animation;
    const progress = Math.min(1, Math.max(0, (time - animation.began) / animation.duration));
    const eased = progress * progress * (3 - 2 * progress);
    animation.actor.position.lerpVectors(animation.start, animation.target, eased);
    animation.actor.position.y += Math.sin(progress * Math.PI) * animation.jump;
    if (animation.victim) {
      const fade = Math.max(0, (progress - 0.5) / 0.5);
      animation.victim.scale.setScalar(1 - fade);
      animation.victim.rotation.z = fade * 0.7;
    }
    if (progress === 1) {
      this.animation = null;
      this.sync(animation.chess);
      animation.resolve();
    }
  }

  pick(clientX, clientY) {
    const bounds = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set((clientX - bounds.left) / bounds.width * 2 - 1, -(clientY - bounds.top) / bounds.height * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const intersections = this.raycaster.intersectObjects([...this.tiles.values(), ...this.pieceRoot.children], true);
    for (const hit of intersections) {
      let object = hit.object;
      while (object) {
        if (object.userData.square) return object.userData.square;
        object = object.parent;
      }
    }
    return null;
  }

  project(square) {
    this.camera.updateMatrixWorld();
    const position = squarePosition(square);
    const projected = new THREE.Vector3(position.x, 0.16, position.z).project(this.camera);
    const bounds = this.renderer.domElement.getBoundingClientRect();
    return { x: bounds.left + (projected.x + 1) / 2 * bounds.width, y: bounds.top + (1 - projected.y) / 2 * bounds.height };
  }

  home(side = this.side) {
    this.side = side;
    const direction = side === 'w' ? 1 : -1;
    this.camera.position.set(direction * 7.2, 10.7, direction * 10.2);
    this.controls.target.set(0, 0.1, 0);
    this.resize();
    this.controls.update();
  }

  flip() { this.home(this.side === 'w' ? 'b' : 'w'); }
  resize() {
    const width = Math.max(1, this.container.clientWidth);
    const height = Math.max(1, this.container.clientHeight);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    fitBoardCamera(this.camera, this.controls);
    this.controls.update();
    this.renderer.setSize(width, height);
    this.needsRender = true;
  }
  quality(high) { this.renderer.setPixelRatio(Math.min(devicePixelRatio, high ? 2 : 1)); this.resize(); }
}