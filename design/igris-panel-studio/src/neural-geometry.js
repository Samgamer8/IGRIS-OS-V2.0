import * as THREE from 'three';

export function orbitalTopology(requestedCount) {
  const count = Math.max(8, Math.min(160, Math.round(requestedCount)));
  const specifications = [
    [[1, 0, 0], 1], [[0, 1, 0], 1], [[0, 0, 1], 1],
    [[0.78, 0.52, 0.34], 0.96], [[0.61, -0.74, 0.27], 0.91],
    [[0.3, 0.62, 0.72], 0.86], [[-0.55, 0.3, 0.78], 0.8],
    [[0.18, -0.88, 0.44], 0.75], [[0.82, 0.13, -0.55], 0.7],
    [[0, 1, 0], 0.62], [[0.7, 0.18, 0.69], 0.56],
    [[0.24, 0.93, -0.28], 0.49], [[1, 0, 0], 0.42],
    [[0.55, -0.63, 0.55], 0.34], [[0, 0, 1], 0.25],
  ];
  const rings = specifications.map(([axis, radius], index) => {
    const normal = new THREE.Vector3(...axis).normalize();
    const reference = Math.abs(normal.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    const first = reference.cross(normal).normalize();
    const second = normal.clone().cross(first).normalize();
    const points = [];
    for (let sample = 0; sample <= 100; sample++) {
      const angle = sample / 100 * Math.PI * 2;
      points.push(first.clone().multiplyScalar(Math.cos(angle)).addScaledVector(second, Math.sin(angle)).multiplyScalar(radius * 1.18));
    }
    return { points, first, second, radius: radius * 1.18, phase: index * 0.37 };
  });
  const nodes = [];
  for (let index = 0; index < count; index++) {
    const ring = rings[index % 9];
    const angle = index * 2.399963 + ring.phase;
    nodes.push(ring.first.clone().multiplyScalar(Math.cos(angle))
      .addScaledVector(ring.second, Math.sin(angle)).multiplyScalar(ring.radius));
  }
  const branches = [];
  const used = new Set();
  for (let index = 0; index < nodes.length; index++) {
    const candidates = nodes.map((point, target) => ({ target, distance: point.distanceToSquared(nodes[index]) }))
      .filter(item => item.target !== index).sort((first, second) => first.distance - second.distance).slice(0, 3);
    for (const { target } of candidates) {
      const key = [Math.min(index, target), Math.max(index, target)].join('-');
      if (used.has(key)) continue;
      used.add(key);
      const middle = nodes[index].clone().add(nodes[target]).multiplyScalar(0.34);
      branches.push(new THREE.QuadraticBezierCurve3(nodes[index], middle, nodes[target]).getPoints(14));
    }
    if (index % 4 === 0) branches.push(new THREE.QuadraticBezierCurve3(nodes[index],
      nodes[index].clone().multiplyScalar(0.35).add(new THREE.Vector3(0.08, -0.04, 0.07)),
      nodes[index].clone().multiplyScalar(0.07)).getPoints(14));
  }
  return { rings, nodes, branches };
}

export function groupedNeuralLayers(count) {
  const topology = orbitalTopology(count);
  const cortex = [];
  for (let index = 0; index < topology.nodes.length * 2; index++) {
    const endpoint = topology.nodes[index % topology.nodes.length].clone().multiplyScalar(0.85);
    const side = endpoint.clone().cross(new THREE.Vector3(0.2, 1, 0.1)).normalize();
    const bend = Math.sin(index * 1.7) * 0.13;
    cortex.push(new THREE.CatmullRomCurve3([
      endpoint.clone().multiplyScalar(0.12),
      endpoint.clone().multiplyScalar(0.38).addScaledVector(side, bend),
      endpoint.clone().multiplyScalar(0.69).addScaledVector(side, -bend * 0.7), endpoint,
    ]).getPoints(18));
  }
  const segments = [];
  for (let ringIndex = 0; ringIndex < 6; ringIndex++) {
    const ring = topology.rings[ringIndex];
    for (let section = 0; section < 8; section++) {
      const start = section / 8 * Math.PI * 2 + ring.phase;
      for (let lane = 0; lane < 2; lane++) {
        const points = [];
        for (let sample = 0; sample <= 12; sample++) {
          const angle = start + sample / 12 * Math.PI * 0.14;
          points.push(ring.first.clone().multiplyScalar(Math.cos(angle))
            .addScaledVector(ring.second, Math.sin(angle)).multiplyScalar(ring.radius * (0.98 + lane * 0.025)));
        }
        segments.push(points);
      }
    }
  }
  const radials = [];
  for (let index = 0; index < 30; index++) {
    const vertical = 1 - 2 * (index + 0.5) / 30;
    const angle = index * 2.399963;
    const direction = new THREE.Vector3(Math.cos(angle) * Math.sqrt(1 - vertical * vertical), vertical,
      Math.sin(angle) * Math.sqrt(1 - vertical * vertical));
    const sideways = direction.clone().cross(new THREE.Vector3(0, 1, 0)).normalize();
    for (let lane = 0; lane < 3; lane++) {
      const offset = sideways.clone().multiplyScalar((lane - 1) * 0.015);
      radials.push([direction.clone().multiplyScalar(0.89).add(offset),
        direction.clone().multiplyScalar(1.2 + index % 3 * 0.035).add(offset)]);
    }
  }
  return { ...topology, cortex, segments, radials,
    signalPaths: [...topology.rings.slice(0, 9).map(ring => ring.points), ...cortex.slice(0, 24)],
    layerNames: ['core', 'branches', 'orbits', 'segments', 'radials', 'signals'] };
}

function randomGenerator(seed) {
  let value = seed >>> 0;
  return () => {
    value = Math.imul(value ^ (value >>> 16), 2246822507) >>> 0;
    value = Math.imul(value ^ (value >>> 13), 3266489909) >>> 0;
    return ((value ^= value >>> 16) >>> 0) / 4294967296;
  };
}

export function luminousCloud(count) {
  const random = randomGenerator(igrisSeed(count));
  const points = [];
  const particleCount = Math.min(4400, 1700 + count * 16);
  for (let index = 0; index < particleCount; index++) {
    const vertical = random() * 2 - 1;
    const angle = random() * Math.PI * 2;
    const horizontal = Math.sqrt(1 - vertical * vertical);
    const layer = index % 5;
    const noise = Math.sin(angle * 7 + vertical * 8) * 0.045;
    const radius = layer === 0 ? 0.15 + Math.pow(random(), 0.65) * 0.46
      : layer === 1 ? 0.5 + random() * 0.5 : 1.06 + random() * 0.21 + noise;
    points.push({ position: new THREE.Vector3(Math.cos(angle) * horizontal, vertical,
      Math.sin(angle) * horizontal).multiplyScalar(radius), layer, phase: random() * Math.PI * 2 });
  }
  return points;
}

function igrisSeed(count) { return 20261004 + Math.round(count) * 13; }

export function filamentPath(start, end, lane, segments = 14) {
  const normal = start.clone().cross(end).normalize();
  const points = [];
  for (let index = 0; index <= segments; index++) {
    const progress = index / segments;
    const bend = Math.sin(progress * Math.PI);
    const direction = start.clone().lerp(end, progress).normalize();
    const radius = 0.76 + lane * 0.115 + Math.sin(progress * Math.PI * 3 + lane) * 0.045;
    const point = direction.multiplyScalar(radius)
      .addScaledVector(normal, bend * (lane - 1.5) * 0.06);
    points.push(point);
  }
  return points;
}