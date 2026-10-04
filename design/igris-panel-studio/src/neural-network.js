import * as THREE from 'three';
import { groupedNeuralLayers } from './neural-geometry.js';

const levels = { idle: 0.04, typing: 0.18, planning: 0.55, writing: 0.8, verifying: 0.4, error: 0.65 };

function glowTexture() {
  const size = 32;
  const data = new Uint8Array(size * size * 4);
  for (let row = 0; row < size; row++) for (let column = 0; column < size; column++) {
    const radius = ((column + 0.5) / size * 2 - 1) ** 2 + ((row + 0.5) / size * 2 - 1) ** 2;
    const offset = (row * size + column) * 4;
    data[offset] = data[offset + 1] = data[offset + 2] = 255;
    data[offset + 3] = radius > 1 ? 0 : Math.round(Math.exp(-radius * 6) * 255);
  }
  const texture = new THREE.DataTexture(data, size, size);
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return texture;
}

export class NeuralNetwork {
  constructor(container, count = 24) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 30);
    this.camera.position.set(0, 0.08, 4.7);
    this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.domElement.setAttribute('aria-label', 'Red 3D de actividad representada');
    container.append(this.renderer.domElement);
    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.referenceGroup = new THREE.Group();
    this.scene.add(this.referenceGroup);
    this.referenceLayers = [];
    this.referenceLabels = ['Membrana', 'Red irregular', 'Orbitas', 'Nucleo', 'Haces radiales', 'Contorno segmentado'];
    this.referenceMode = 'all';
    this.destroyed = false;
    this.activity = 'idle';
    this.level = 0.04;
    this.glowTexture = glowTexture();
    this.pointsMaterial = new THREE.PointsMaterial({ color: 0x6ddbe8, size: 0.045, map: this.glowTexture,
      transparent: true, opacity: 0.82, depthWrite: false, blending: THREE.AdditiveBlending });
    this.coreMaterial = new THREE.PointsMaterial({ color: 0xb3f6ff, size: 0.12, map: this.glowTexture,
      transparent: true, opacity: 0.9, depthWrite: false, blending: THREE.AdditiveBlending });
    this.orbitMaterial = new THREE.LineBasicMaterial({ vertexColors: true,
      transparent: true, opacity: 0.85, depthWrite: false, blending: THREE.AdditiveBlending });
    this.linesMaterial = new THREE.LineBasicMaterial({ vertexColors: true,
      transparent: true, opacity: 0.45, depthWrite: false, blending: THREE.AdditiveBlending });
    this.channelMaterial = new THREE.LineBasicMaterial({ vertexColors: true,
      transparent: true, opacity: 0.76, depthWrite: false, blending: THREE.AdditiveBlending });
    this.flowMaterial = new THREE.PointsMaterial({ color: 0xb2fbff, size: 0.055, map: this.glowTexture,
      transparent: true, opacity: 0.95, depthWrite: false, blending: THREE.AdditiveBlending });
    this.movingPoint = new THREE.Vector3();
    this.setComplexity(count);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(container);
    this.resize();
    this.lastFrame = 0;
    this.renderer.setAnimationLoop(now => {
      if (now - this.lastFrame < 32) return;
      this.lastFrame = now;
      this.update(now / 1000);
      this.renderer.render(this.scene, this.camera);
    });
    this.loadReferenceLayers();
  }
  loadReferenceLayers() {
    const image = new Image();
    image.onload = () => {
      if (this.destroyed) return;
      const scales = [2.58, 2.54, 2.35, 1.45, 2.62, 2.7];
      const opacities = [0.62, 0.44, 0.28, 0.72, 0.33, 0.82];
      const speeds = [0.035, -0.07, 0.11, -0.025, 0.06, -0.085];
      for (let index = 0; index < 6; index++) {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 512;
        const context = canvas.getContext('2d');
        const width = image.naturalWidth / 2;
        const height = image.naturalHeight / 3;
        context.drawImage(image, index % 2 * width + 4, Math.floor(index / 2) * height + 4,
          width - 8, height - 8, 0, 0, 512, 512);
        const pixels = context.getImageData(0, 0, 512, 512);
        for (let offset = 0; offset < pixels.data.length; offset += 4) {
          const strength = Math.max(pixels.data[offset], pixels.data[offset + 1], pixels.data[offset + 2]) / 255;
          pixels.data[offset] = 22 + strength * 25;
          pixels.data[offset + 1] = 168 + strength * 52;
          pixels.data[offset + 2] = 215 + strength * 40;
          pixels.data[offset + 3] = strength <= 0.06 ? 0 : Math.pow((strength - 0.06) / 0.94, 0.8) * 245;
        }
        context.putImageData(pixels, 0, 0);
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true,
          opacity: opacities[index], depthWrite: false, blending: THREE.AdditiveBlending,
          side: THREE.DoubleSide, toneMapped: false });
        const mesh = new THREE.Mesh(new THREE.CircleGeometry(scales[index] / 2, 96), material);
        mesh.name = this.referenceLabels[index];
        mesh.position.z = (index - 2.5) * 0.055;
        mesh.renderOrder = index;
        mesh.userData.baseOpacity = opacities[index];
        mesh.userData.baseDepth = mesh.position.z;
        mesh.userData.spinSpeed = speeds[index];
        this.referenceGroup.add(mesh);
        this.referenceLayers.push(mesh);
      }
      this.setReferenceMode(this.referenceMode);
      this.group.children.forEach(mesh => { mesh.visible = mesh.geometry === this.flowGeometry; });
    };
    image.onerror = () => { this.referenceError = 'No se pudo cargar la referencia de las seis capas'; };
    image.src = `${import.meta.env.BASE_URL}reference/neural-layers.jpg`;
  }
  setReferenceMode(mode) {
    if (mode !== 'all' && !/^[0-5]$/.test(String(mode))) return;
    this.referenceMode = String(mode);
    this.referenceLayers.forEach((mesh, index) => { mesh.visible = mode === 'all' || String(index) === String(mode); });
  }
  setComplexity(count) {
    count = Math.min(160, Math.max(8, Math.round(count)));
    this.group.clear();
    this.positions?.dispose(); this.edges?.dispose();
    this.channelGeometry?.dispose(); this.flowGeometry?.dispose();
    this.orbitGeometry?.dispose(); this.coreGeometry?.dispose();
    this.topology = groupedNeuralLayers(count);
    this.layerNames = this.topology.layerNames;
    this.segmentAxes = this.topology.rings.slice(0, 6).map(ring => ring.first.clone().cross(ring.second).normalize());
    this.base = this.topology.nodes;
    this.positions = new THREE.BufferGeometry();
    this.positions.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    this.orbitSegments = [];
    this.topology.rings.forEach((ring, ringIndex) => {
      for (let index = 0; index < ring.points.length - 1; index++) this.orbitSegments.push({
        start: ring.points[index], end: ring.points[index + 1], phase: ring.phase, ring: ringIndex });
    });
    this.filaments = [];
    [...this.topology.branches, ...this.topology.cortex].forEach((curve, branch) => {
      for (let index = 0; index < curve.length - 1; index++) this.filaments.push({
        start: curve[index], end: curve[index + 1], phase: branch * 0.37, branch });
    });
    this.channels = [];
    this.topology.segments.forEach((path, pathIndex) => {
      for (let index = 0; index < path.length - 1; index++) this.channels.push({
        start: path[index], end: path[index + 1], ring: Math.floor(pathIndex / 16), phase: pathIndex * 0.19 });
    });
    this.topology.radials.forEach((path, index) => this.channels.push({
      start: path[0], end: path[1], ring: -1, phase: index * 0.31 }));
    this.channelGeometry = new THREE.BufferGeometry();
    this.channelGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(this.channels.length * 6), 3));
    this.channelGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(this.channels.length * 6), 3));
    this.flowGeometry = new THREE.BufferGeometry();
    this.flowGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(this.topology.signalPaths.length * 3), 3));
    this.edges = new THREE.BufferGeometry();
    this.edges.setAttribute('position', new THREE.BufferAttribute(new Float32Array(this.filaments.length * 6), 3));
    this.edges.setAttribute('color', new THREE.BufferAttribute(new Float32Array(this.filaments.length * 6), 3));
    this.orbitGeometry = new THREE.BufferGeometry();
    this.orbitGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(this.orbitSegments.length * 6), 3));
    this.orbitGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(this.orbitSegments.length * 6), 3));
    const core = [];
    for (let index = 0; index < 220; index++) {
      const vertical = 1 - 2 * (index + 0.5) / 220;
      const horizontal = Math.sqrt(1 - vertical * vertical);
      const radius = 0.045 + (index % 13) / 13 * 0.13;
      const angle = index * 2.399963;
      core.push(Math.cos(angle) * horizontal * radius, vertical * radius, Math.sin(angle) * horizontal * radius);
    }
    this.coreGeometry = new THREE.BufferGeometry();
    this.coreGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(core), 3));
    this.group.add(new THREE.LineSegments(this.orbitGeometry, this.orbitMaterial),
      new THREE.LineSegments(this.edges, this.linesMaterial),
      new THREE.Points(this.positions, this.pointsMaterial), new THREE.Points(this.coreGeometry, this.coreMaterial),
      new THREE.LineSegments(this.channelGeometry, this.channelMaterial), new THREE.Points(this.flowGeometry, this.flowMaterial));
    this.nodeCount = count;
    this.branchCount = this.topology.branches.length + this.topology.cortex.length;
    if (this.referenceLayers.length) this.group.children.forEach(mesh => { mesh.visible = mesh.geometry === this.flowGeometry; });
  }
  setActivity(activity) { this.activity = Object.hasOwn(levels, activity) ? activity : 'idle'; }
  update(time) {
    this.level += (levels[this.activity] - this.level) * 0.16;
    this.referenceEpoch ??= time;
    const layerTime = time - this.referenceEpoch;
    this.referenceLayers.forEach((mesh, index) => {
      mesh.rotation.z = (layerTime * mesh.userData.spinSpeed + index * 0.035) % (Math.PI * 2);
      mesh.rotation.x = Math.sin(layerTime * 0.28 + index * 0.7) * (index === 3 ? 0.08 : 0.14);
      mesh.rotation.y = Math.cos(layerTime * 0.23 + index * 0.8) * 0.12;
      mesh.position.z = mesh.userData.baseDepth + Math.sin(layerTime * 0.6 + index) * 0.045;
      const amplitude = index === 3 ? 0.055 : index === 5 ? 0.016 : 0.025;
      const breath = 1 + Math.sin(layerTime * 1.25 + index * 0.6) * (amplitude + this.level * 0.012);
      mesh.scale.setScalar(breath);
      mesh.material.opacity = mesh.userData.baseOpacity * (0.91 + Math.sin(layerTime * 1.25 - index * 0.5) * (0.08 + this.level * 0.1));
    });
    const positions = this.positions.attributes.position;
    for (let index = 0; index < this.base.length; index++) {
      const point = this.base[index];
      const breath = 1 + Math.sin(time * 1.15 + index * 0.17) * (0.003 + this.level * 0.022);
      positions.setXYZ(index, point.x * breath, point.y * breath, point.z * breath);
    }
    positions.needsUpdate = true;
    const lines = this.edges.attributes.position;
    const colors = this.edges.attributes.color;
    const light = this.activity === 'error' ? new THREE.Color(0xf14d61) : this.activity === 'verifying'
      ? new THREE.Color(0x9be5cf) : new THREE.Color(0x38bdde);
    for (let index = 0; index < this.filaments.length; index++) {
      const filament = this.filaments[index];
      const pulse = 0.22 + this.level * (0.45 + 0.38 * Math.sin(time * (1.5 + this.level * 2) - filament.phase));
      const breath = 1 + Math.sin(time * 1.15 + filament.phase) * (0.003 + this.level * 0.018);
      for (let endpoint = 0; endpoint < 2; endpoint++) {
        const point = endpoint ? filament.end : filament.start;
        lines.setXYZ(index * 2 + endpoint, point.x * breath, point.y * breath, point.z * breath);
        colors.setXYZ(index * 2 + endpoint, light.r * pulse, light.g * pulse, light.b * pulse);
      }
    }
    const orbitPositions = this.orbitGeometry.attributes.position;
    const orbitColors = this.orbitGeometry.attributes.color;
    for (let index = 0; index < this.orbitSegments.length; index++) {
      const segment = this.orbitSegments[index];
      const breath = 1 + Math.sin(time * 1.05 + segment.phase) * (0.0015 + this.level * 0.012);
      const color = segment.ring < 9 ? new THREE.Color(0x319fbd) : new THREE.Color(0x81e4ee);
      const brightness = 0.56 + this.level * 0.22 + Math.sin(time * 1.2 + segment.phase) * this.level * 0.05;
      for (let endpoint = 0; endpoint < 2; endpoint++) {
        const point = endpoint ? segment.end : segment.start;
        orbitPositions.setXYZ(index * 2 + endpoint, point.x * breath, point.y * breath, point.z * breath);
        orbitColors.setXYZ(index * 2 + endpoint, color.r * brightness, color.g * brightness, color.b * brightness);
      }
    }
    orbitPositions.needsUpdate = orbitColors.needsUpdate = true;
    lines.needsUpdate = colors.needsUpdate = true;
    const rotations = this.segmentAxes.map((axis, index) => new THREE.Quaternion()
      .setFromAxisAngle(axis, Math.sin(time * 0.22 + index) * 0.2));
    const channelPositions = this.channelGeometry.attributes.position;
    const channelColors = this.channelGeometry.attributes.color;
    for (let index = 0; index < this.channels.length; index++) {
      const channel = this.channels[index];
      const strength = channel.ring < 0 ? 0.16 + this.level * 0.42 : 0.48 + this.level * 0.25;
      const wave = strength + (0.06 + this.level * 0.2) * Math.sin(time * 2.1 - channel.phase);
      for (let endpoint = 0; endpoint < 2; endpoint++) {
        this.movingPoint.copy(endpoint ? channel.end : channel.start);
        if (channel.ring >= 0) this.movingPoint.applyQuaternion(rotations[channel.ring]);
        else this.movingPoint.multiplyScalar(1 + Math.sin(time + channel.phase) * 0.012);
        channelPositions.setXYZ(index * 2 + endpoint, this.movingPoint.x, this.movingPoint.y, this.movingPoint.z);
        channelColors.setXYZ(index * 2 + endpoint, light.r * wave, light.g * wave, light.b * wave);
      }
    }
    const flowPositions = this.flowGeometry.attributes.position;
    this.topology.signalPaths.forEach((path, index) => {
      const progress = ((time * (0.065 + this.level * 0.2) + index * 0.137) % 1) * (path.length - 1);
      const sample = Math.floor(progress);
      this.movingPoint.copy(path[sample]).lerp(path[Math.min(sample + 1, path.length - 1)], progress - sample);
      flowPositions.setXYZ(index, this.movingPoint.x, this.movingPoint.y, this.movingPoint.z);
    });
    channelPositions.needsUpdate = channelColors.needsUpdate = flowPositions.needsUpdate = true;
    this.pointsMaterial.size = 0.045 + this.level * 0.018;
    this.coreMaterial.size = 0.1 + this.level * 0.035 + Math.sin(time * 1.4) * 0.008;
    this.linesMaterial.opacity = 0.35 + this.level * 0.4;
  }
  resize() {
    const width = Math.max(1, this.container.clientWidth);
    const height = Math.max(1, this.container.clientHeight);
    this.camera.aspect = width / height;
    this.camera.position.z = Math.max(5, 1.7 / (Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)) * Math.min(1, this.camera.aspect)));
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }
  destroy() {
    this.destroyed = true;
    this.referenceLayers.forEach(mesh => { mesh.geometry.dispose(); mesh.material.map.dispose(); mesh.material.dispose(); });
    this.renderer.setAnimationLoop(null); this.observer.disconnect();
    this.positions.dispose(); this.edges.dispose(); this.pointsMaterial.dispose(); this.linesMaterial.dispose();
    this.channelGeometry.dispose(); this.flowGeometry.dispose(); this.channelMaterial.dispose(); this.flowMaterial.dispose();
    this.orbitGeometry.dispose(); this.orbitMaterial.dispose(); this.coreGeometry.dispose(); this.coreMaterial.dispose(); this.glowTexture.dispose();
    this.renderer.dispose();
  }
}