import * as THREE from 'three';

const shapes = new Map();
const palettes = new Map();
const UP = new THREE.Vector3(0, 1, 0);

function cached(key, create) {
  if (!shapes.has(key)) shapes.set(key, create());
  return shapes.get(key);
}

function material(color, roughness = 0.35, metalness = 0.55) {
  return new THREE.MeshStandardMaterial({ color, roughness, metalness });
}

function palette(color) {
  if (!palettes.has(color)) {
    const light = color === 'w';
    palettes.set(color, {
      armor: material(light ? 0xcbd5dc : 0x4f6980, 0.29, 0.76),
      plate: material(light ? 0xe8e0d1 : 0x788da0, 0.32, 0.65),
      trim: material(light ? 0xc69b57 : 0x91c3d4, 0.25, 0.82),
      fabric: material(light ? 0x572d60 : 0x152b69, 0.78, 0.08),
      robe: material(light ? 0xe0d3ba : 0x253750, 0.72, 0.05),
      skin: material(light ? 0xdeb89e : 0x90a4ac, 0.68, 0.02),
      hair: material(light ? 0x683b6b : 0xa0aab1, 0.62, 0.07),
      scale: material(light ? 0x94746d : 0x315c80, 0.43, 0.31),
      belly: material(light ? 0xd6c0a1 : 0x94bdc8, 0.56, 0.13),
      wing: material(light ? 0x55385e : 0x1e3f79, 0.57, 0.18),
      dark: material(0x14212b, 0.55, 0.2),
      eye: new THREE.MeshStandardMaterial({ color: light ? 0xd8b864 : 0x63d5f4,
        emissive: light ? 0x76531a : 0x287c9e, emissiveIntensity: 0.7, roughness: 0.22 }),
    });
  }
  return palettes.get(color);
}

function add(parent, geometry, surface, position = [0, 0, 0], scale = [1, 1, 1]) {
  const object = new THREE.Mesh(geometry, surface);
  object.position.set(...position);
  object.scale.set(...scale);
  object.castShadow = true;
  object.receiveShadow = true;
  parent.add(object);
  return object;
}

function ellipsoid(parent, surface, position, scale) {
  return add(parent, cached('sphere', () => new THREE.SphereGeometry(1, 16, 12)), surface, position, scale);
}

function block(parent, surface, position, scale) {
  return add(parent, cached('box', () => new THREE.BoxGeometry(1, 1, 1)), surface, position, scale);
}

function cone(parent, surface, position, scale) {
  return add(parent, cached('cone', () => new THREE.ConeGeometry(1, 1, 12)), surface, position, scale);
}

function ring(parent, surface, position, radius, tube = 0.018) {
  const geometry = cached(`ring-${radius}-${tube}`, () => new THREE.TorusGeometry(radius, tube, 6, 28));
  return add(parent, geometry, surface, position);
}

function limb(parent, surface, start, end, radius) {
  const direction = new THREE.Vector3(...end).sub(new THREE.Vector3(...start));
  const center = new THREE.Vector3(...start).addScaledVector(direction, 0.5);
  const object = add(parent, cached('limb', () => new THREE.CylinderGeometry(1, 1, 1, 12)),
    surface, center.toArray(), [radius, direction.length(), radius]);
  object.quaternion.setFromUnitVectors(UP, direction.normalize());
  return object;
}

function curved(parent, surface, key, points, radius) {
  const geometry = cached(key, () => new THREE.TubeGeometry(
    new THREE.CatmullRomCurve3(points.map(point => new THREE.Vector3(...point))), 22, radius, 8, false));
  return add(parent, geometry, surface);
}

function part(root, name, pivot, build) {
  const group = new THREE.Group();
  group.name = name;
  build(group);
  for (const child of group.children) child.position.sub(new THREE.Vector3(...pivot));
  group.position.set(...pivot);
  root.add(group);
  root.rig[name] = group;
  return group;
}

function equipment(root, hand, name, build) {
  const group = new THREE.Group();
  group.name = name;
  group.userData.hand = hand;
  build(group);
  root.add(group);
}

function dragon(root, surfaces, color) {
  const light = color === 'w';
  ellipsoid(root, surfaces.scale, [0, 0.52, 0.06], [0.18, 0.29, 0.16]);
  ellipsoid(root, surfaces.belly, [0, 0.48, -0.073], [0.128, 0.24, 0.07]);
  const neckPoints = [[0, 0.61, 0.03], [0, 0.79, 0.025], [0, 0.96, -0.1], [0, 1.13, -0.07], [0, 1.24, -0.16]];
  curved(root, surfaces.scale, 'dragon-neck', neckPoints, 0.084);
  curved(root, surfaces.belly, 'dragon-neck-belly', neckPoints.map(([x, y, z]) => [x, y, z - 0.052]), 0.035);
  ellipsoid(root, surfaces.scale, [0, 1.26, -0.2], [0.115, 0.083, 0.15]);
  ellipsoid(root, surfaces.scale, [0, 1.235, -0.335], [0.085, 0.049, 0.1]);
  root.rig.jaw = ellipsoid(root, surfaces.belly, [0, 1.205, -0.28], [0.085, 0.019, 0.13]);
  for (const side of [-1, 1]) {
    ellipsoid(root, surfaces.eye, [side * 0.095, 1.285, -0.24], [0.018, 0.014, 0.022]);
    const horn = cone(root, surfaces.trim, [side * 0.083, 1.36, -0.095], [0.031, 0.2, 0.031]);
    horn.rotation.x = 0.42;
    horn.rotation.z = -side * 0.24;
    limb(root, surfaces.scale, [side * 0.12, 0.39, 0.04], [side * 0.17, 0.2, -0.04], 0.064);
    ellipsoid(root, surfaces.scale, [side * 0.175, 0.145, -0.085], [0.08, 0.04, 0.13]);
    for (let claw = 0; claw < 3; claw++) {
      const nail = cone(root, surfaces.trim, [side * 0.175 + (claw - 1) * 0.035, 0.14, -0.2], [0.012, 0.066, 0.012]);
      nail.rotation.x = -Math.PI / 2;
    }
    limb(root, surfaces.scale, [side * 0.11, 0.67, -0.02], [side * 0.2, 0.55, -0.2], 0.035);
    ellipsoid(root, surfaces.trim, [side * 0.205, 0.54, -0.205], [0.033, 0.027, 0.046]);
    const wingShape = new THREE.Shape();
    wingShape.moveTo(0, 0);
    wingShape.quadraticCurveTo(side * 0.12, 0.23, side * 0.28, 0.39);
    wingShape.lineTo(side * 0.36, 0.25);
    wingShape.lineTo(side * 0.3, 0.22);
    wingShape.lineTo(side * 0.37, 0.05);
    wingShape.quadraticCurveTo(side * 0.23, 0.11, side * 0.23, -0.035);
    wingShape.quadraticCurveTo(side * 0.15, 0.05, side * 0.15, -0.13);
    wingShape.lineTo(0, -0.04);
    const wing = add(root, cached(`dragon-wing-${side}`, () => new THREE.ExtrudeGeometry(wingShape,
      { depth: 0.015, bevelEnabled: true, bevelSize: 0.004, bevelThickness: 0.003, bevelSegments: 1 })), surfaces.wing, [side * 0.075, 0.64, 0.11]);
    wing.rotation.y = -side * 0.2;
    root.rig[side < 0 ? 'leftWing' : 'rightWing'] = wing;
    limb(root, surfaces.scale, [side * 0.075, 0.64, 0.11], [side * 0.35, 1.03, 0.17], 0.016);
    limb(root, surfaces.scale, [side * 0.075, 0.64, 0.11], [side * 0.4, 0.87, 0.16], 0.012);
    limb(root, surfaces.scale, [side * 0.075, 0.64, 0.11], [side * 0.34, 0.69, 0.16], 0.012);
  }
  curved(root, surfaces.scale, 'dragon-tail', [[0, 0.4, 0.12], [0.18, 0.31, 0.23], [0.26, 0.17, 0.3], [0.1, 0.12, 0.35], [-0.1, 0.16, 0.25]], 0.042);
  for (let index = 0; index < 7; index++) {
    const crest = cone(root, light ? surfaces.hair : surfaces.fabric,
      [0, 0.65 + index * 0.09, 0.1 - index * 0.016], [0.03, 0.105, 0.06]);
    crest.rotation.x = 0.5;
  }
  if (!light) {
    for (const side of [-1, 1]) cone(root, surfaces.trim, [side * 0.14, 0.79, 0.07], [0.024, 0.12, 0.025]);
  }
}

function shield(root, surfaces, position, heavy = false) {
  const group = new THREE.Group();
  group.position.set(...position);
  group.rotation.y = -0.15;
  group.name = 'shield';
  group.userData.hand = 'leftArm';
  const disc = cached('shield', () => new THREE.CylinderGeometry(1, 1, 1, 32));
  const face = add(group, disc, surfaces.fabric, [0, 0, 0], [heavy ? 0.21 : 0.155, 0.035, heavy ? 0.21 : 0.265]);
  face.rotation.x = Math.PI / 2;
  const rim = ring(group, surfaces.trim, [0, 0, -0.026], 0.15, 0.014);
  rim.scale.set(heavy ? 1.4 : 1, heavy ? 1.4 : 1.74, 1);
  ellipsoid(group, surfaces.armor, [0, 0, -0.038], [0.052, 0.052, 0.025]);
  for (let index = 0; index < 6; index++) {
    const angle = index * Math.PI / 3;
    ellipsoid(group, surfaces.trim, [Math.sin(angle) * 0.11, Math.cos(angle) * (heavy ? 0.14 : 0.205), -0.04], [0.012, 0.012, 0.009]);
  }
  root.add(group);
}

function sword(root, surfaces, x, y, z) {
  equipment(root, x < 0 ? 'leftArm' : 'rightArm', 'sword', group => {
    block(group, surfaces.armor, [x, y + 0.2, z], [0.035, 0.52, 0.015]);
    cone(group, surfaces.plate, [x, y + 0.48, z], [0.025, 0.11, 0.012]);
    block(group, surfaces.trim, [x, y - 0.04, z], [0.16, 0.025, 0.025]);
    limb(group, surfaces.dark, [x, y - 0.15, z], [x, y - 0.02, z], 0.02);
    ellipsoid(group, surfaces.eye, [x, y - 0.16, z], [0.029, 0.025, 0.025]);
  });
}

function staff(root, surfaces, x, skull = false) {
  equipment(root, 'leftArm', 'staff', group => {
  limb(group, surfaces.trim, [x, 0.16, -0.05], [x, 1.57, -0.05], 0.023);
  if (skull) {
    ellipsoid(group, surfaces.plate, [x, 1.62, -0.05], [0.087, 0.1, 0.068]);
    for (const side of [-1, 1]) ellipsoid(group, surfaces.dark, [x + side * 0.035, 1.64, -0.11], [0.022, 0.026, 0.012]);
    block(group, surfaces.armor, [x, 1.53, -0.05], [0.11, 0.03, 0.03]);
  } else {
    ring(group, surfaces.trim, [x, 1.65, -0.05], 0.085, 0.017);
    for (const side of [-1, 1]) {
      limb(group, surfaces.trim, [x + side * 0.04, 1.68, -0.05], [x + side * 0.15, 1.79, -0.05], 0.014);
      limb(group, surfaces.trim, [x + side * 0.04, 1.65, -0.05], [x + side * 0.17, 1.72, -0.05], 0.011);
    }
  }
  });
}

function character(root, surfaces, type, color) {
  const light = color === 'w';
  const heavy = type === 'r';
  const robed = type === 'b';
  const royal = type === 'q' || type === 'k';
  const king = type === 'k';
  const height = king ? 1.62 : type === 'q' ? 1.5 : heavy ? 1.36 : 1.43;
  const hip = heavy ? 0.67 : 0.65;
  for (const side of [-1, 1]) {
    const x = side * (heavy ? 0.12 : 0.085);
    part(root, side < 0 ? 'leftLeg' : 'rightLeg', [x, hip, 0], group => {
    ellipsoid(group, surfaces.armor, [x, 0.16, -0.045], [0.07, 0.055, 0.12]);
    limb(group, surfaces.armor, [x, 0.23, 0.025], [x, 0.43, 0], heavy ? 0.08 : 0.052);
    ellipsoid(group, surfaces.trim, [x, 0.45, -0.024], [heavy ? 0.073 : 0.058, 0.057, 0.058]);
    limb(group, surfaces.fabric, [x, 0.47, 0], [x, hip, 0], heavy ? 0.085 : 0.055);
    if (royal || heavy) for (let index = 0; index < 4; index++) {
      block(group, surfaces.armor, [x, 0.24 + index * 0.043, -0.034], [0.1, 0.025, 0.065]);
    }
    });
  }
  ellipsoid(root, surfaces.fabric, [0, hip, 0], [heavy ? 0.21 : 0.135, 0.12, 0.1]);
  ellipsoid(root, surfaces.armor, [0, hip + 0.25, 0], [heavy ? 0.26 : 0.17, heavy ? 0.29 : 0.24, heavy ? 0.18 : 0.095]);
  if (heavy && !light) ellipsoid(root, surfaces.plate, [0, 0.81, -0.115], [0.23, 0.22, 0.12]);
  const belt = add(root, cached('belt', () => new THREE.CylinderGeometry(1, 1, 1, 20)), surfaces.trim,
    [0, hip + 0.045, -0.01], [heavy ? 0.23 : 0.145, 0.039, heavy ? 0.15 : 0.105]);
  belt.userData.detail = 'armored belt';
  ellipsoid(root, surfaces.eye, [0, hip + 0.16, heavy ? -0.21 : -0.101], [0.036, 0.041, 0.017]);
  const shoulderY = hip + 0.42;
  for (const side of [-1, 1]) {
    const shoulderX = side * (heavy ? 0.27 : 0.18);
    part(root, side < 0 ? 'leftArm' : 'rightArm', [shoulderX, shoulderY, 0], group => {
    ellipsoid(group, surfaces.plate, [shoulderX, shoulderY, 0], [heavy ? 0.105 : 0.077, 0.073, 0.095]);
    const elbow = [side * (heavy ? 0.31 : 0.235), shoulderY - 0.19, -0.02];
    const hand = [side * (heavy ? 0.3 : 0.255), shoulderY - (side < 0 && (robed || king) ? 0.05 : 0.31), -0.11];
    limb(group, surfaces.armor, [shoulderX, shoulderY - 0.04, 0], elbow, heavy ? 0.071 : 0.042);
    ellipsoid(group, surfaces.trim, elbow, [0.045, 0.045, 0.045]);
    limb(group, surfaces.armor, elbow, hand, heavy ? 0.06 : 0.04);
    ellipsoid(group, surfaces.plate, hand, [0.044, 0.053, 0.045]);
    if (!light || king) {
      const spike = cone(group, surfaces.trim, [shoulderX + side * 0.035, shoulderY + 0.075, 0], [0.03, royal ? 0.18 : 0.1, 0.027]);
      spike.rotation.z = -side * 0.75;
    }
    });
  }
  const neckY = shoulderY + 0.09;
  limb(root, surfaces.skin, [0, neckY, 0], [0, height - 0.17, 0], 0.042);
  ellipsoid(root, heavy ? surfaces.dark : surfaces.skin, [0, height - 0.11, -0.013], [0.078, 0.106, 0.078]);
  if (type === 'n' || heavy || (king && !light)) {
    ellipsoid(root, surfaces.armor, [0, height - 0.075, 0.005], [0.092, 0.115, 0.09]);
    block(root, surfaces.dark, [0, height - 0.10, -0.086], [0.117, 0.027, 0.01]);
    for (const side of [-1, 1]) ellipsoid(root, surfaces.eye, [side * 0.03, height - 0.1, -0.093], [0.014, 0.009, 0.008]);
    if (type === 'n' || (king && !light)) for (const side of [-1, 1]) {
      curved(root, surfaces.trim, `helmet-horn-${type}-${color}-${side}`, [[side * 0.055, height - 0.02, 0],
        [side * 0.12, height + 0.06, 0.025], [side * 0.15, height + 0.16, 0]], 0.015);
    }
    if (type === 'n' && light) ellipsoid(root, surfaces.hair, [0, height + 0.065, 0.035], [0.045, 0.16, 0.11]);
    if (heavy) for (const side of [-1, 0, 1]) block(root, surfaces.plate, [side * 0.065, height + 0.025, 0], [0.047, 0.08, 0.09]);
  } else {
    ellipsoid(root, surfaces.hair, [0, height - 0.025, 0.025], [0.087, 0.06, 0.087]);
    for (const side of [-1, 1]) {
      ellipsoid(root, surfaces.hair, [side * 0.076, height - 0.17, 0.048], [0.025, royal ? 0.17 : 0.07, 0.055]);
      ellipsoid(root, surfaces.dark, [side * 0.027, height - 0.11, -0.081], [0.012, 0.008, 0.006]);
    }
  }
  if (robed) {
    add(root, cached('robe', () => new THREE.CylinderGeometry(0.13, 0.225, 0.72, 24)), surfaces.robe, [0, 0.61, 0.035]);
    for (const side of [-1, 1]) block(root, surfaces.fabric, [side * 0.07, 0.71, -0.159], [0.033, 0.49, 0.018]);
    if (light) cone(root, surfaces.robe, [0, height + 0.04, 0.01], [0.14, 0.34, 0.12]);
    else ellipsoid(root, surfaces.fabric, [0, height - 0.06, 0.025], [0.106, 0.14, 0.1]);
    staff(root, surfaces, -0.285, !light);
  } else if (type === 'n') {
    if (light) shield(root, surfaces, [-0.28, 0.87, -0.19]);
    else curved(root, surfaces.plate, 'black-knight-blade', [[0.28, 0.79, -0.12], [0.37, 1.07, -0.12], [0.38, 1.34, -0.12]], 0.018);
    sword(root, surfaces, light ? 0.29 : -0.29, 0.81, -0.13);
  } else if (heavy) {
    shield(root, surfaces, [-0.31, 0.79, -0.14], true);
    sword(root, surfaces, 0.32, 0.79, -0.15);
  } else if (royal) {
    const cape = add(root, cached('cape', () => new THREE.CylinderGeometry(0.11, 0.21, 0.89, 20, 1, true, 0, Math.PI)), surfaces.fabric, [0, 0.68, 0.08]);
    cape.rotation.y = -Math.PI / 2;
    const crown = ring(root, surfaces.trim, [0, height - 0.01, 0], 0.093, 0.016);
    crown.rotation.x = Math.PI / 2;
    for (let index = 0; index < (king ? 5 : 7); index++) {
      const angle = index * Math.PI * 2 / (king ? 5 : 7);
      const point = [Math.sin(angle) * 0.086, height + 0.065, Math.cos(angle) * 0.086];
      cone(root, surfaces.trim, point, [0.013, king ? 0.17 : 0.105, 0.013]);
      ellipsoid(root, surfaces.eye, [point[0], point[1] + 0.04, point[2]], [0.017, 0.02, 0.017]);
    }
    if (king) staff(root, surfaces, -0.28, false);
    else {
      sword(root, surfaces, 0.28, 0.78, -0.11);
      ellipsoid(root, surfaces.eye, [-0.27, 1.0, -0.12], [0.065, 0.065, 0.065]);
    }
  }
}

export function createFantasyPiece(type, color) {
  if (!['p', 'n', 'b', 'r', 'q', 'k'].includes(type) || !['w', 'b'].includes(color)) throw new Error('Tipo de pieza invalido');
  const root = new THREE.Group();
  root.rig = {};
  const surfaces = palette(color);
  if (type === 'p') dragon(root, surfaces, color);
  else character(root, surfaces, type, color);
  for (const child of root.children) child.position.y -= 0.105;
  root.position.y = 0.09;
  root.rotation.y = color === 'w' ? 0 : Math.PI;
  root.updateMatrixWorld(true);
  for (const child of [...root.children]) {
    if (child.userData.hand && root.rig[child.userData.hand]) root.rig[child.userData.hand].attach(child);
  }
  root.userData.faction = color === 'w' ? 'Orden de plata' : 'Legion de zafiro';
  root.userData.hasPedestal = false;
  root.userData.articulated = true;
  root.userData.pieceType = type;
  root.userData.design = `${color}-${type}`;
  root.userData.source = 'PIEZAS_AJEDREZ_SHAPR3D - reconstruccion desde referencias';
  return root;
}

export function poseFantasyPiece(root, { walk = 0, attack = 0, guard = 0, wings = 0 } = {}) {
  const rig = root.rig;
  if (!rig) return;
  if (rig.leftLeg) rig.leftLeg.rotation.x = walk;
  if (rig.rightLeg) rig.rightLeg.rotation.x = -walk;
  if (rig.rightArm) rig.rightArm.rotation.x = attack - walk * 0.8;
  if (rig.leftArm) rig.leftArm.rotation.x = guard + walk * 0.8;
  if (rig.leftWing) rig.leftWing.rotation.x = wings;
  if (rig.rightWing) rig.rightWing.rotation.x = -wings;
  if (rig.jaw) rig.jaw.rotation.x = attack * 0.22;
}