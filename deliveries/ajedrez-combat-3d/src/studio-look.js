import * as THREE from 'three';

const textures = new Map();

function surfaceTexture(kind) {
  if (textures.has(kind)) return textures.get(kind);
  const width = 256;
  const pixels = new Uint8Array(width * width * 4);
  for (let row = 0; row < width; row++) for (let column = 0; column < width; column++) {
    const noise = ((column * 73856093) ^ (row * 19349663)) >>> 0;
    const grain = (noise % 31) - 15;
    let value;
    if (kind === 'cloth') value = 185 + grain + ((column % 4 === 0 || row % 4 === 0) ? -45 : 12);
    else if (kind === 'scale') value = 190 + grain - ((row % 16 < 2 || (column + (Math.floor(row / 16) % 2) * 8) % 16 < 2) ? 55 : 0);
    else value = 204 + grain - (row % 53 === 0 && column % 13 < 9 ? 58 : 0);
    const offset = (row * width + column) * 4;
    pixels[offset] = pixels[offset + 1] = pixels[offset + 2] = value;
    pixels[offset + 3] = 255;
  }
  const texture = new THREE.DataTexture(pixels, width, width);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  textures.set(kind, texture);
  return texture;
}

export function applyStudioLook(root, color) {
  const clones = new Map();
  root.traverse(object => {
    if (!object.isMesh) return;
    const original = object.material;
    if (!clones.has(original.uuid)) {
      const surface = original.clone();
      if (surface.metalness > 0.5) {
        surface.color.set(color === 'w' ? 0x8e969d : 0x35434f);
        if (original.color.getHex() === 0xc69b57 || original.color.getHex() === 0x91c3d4) surface.color.set(color === 'w' ? 0x92713e : 0x697f86);
        surface.roughness = 0.43;
        surface.metalness = 0.83;
        surface.bumpMap = surfaceTexture('metal');
        surface.bumpScale = 0.004;
        surface.roughnessMap = surfaceTexture('metal');
      } else if (surface.roughness > 0.7) {
        surface.color.set(color === 'w' ? 0x58332c : 0x1f2d36);
        if (original.color.getHex() === 0xe0d3ba) surface.color.set(0xb3a88c);
        surface.bumpMap = surfaceTexture('cloth');
        surface.bumpScale = 0.008;
        surface.roughness = 0.88;
        surface.metalness = 0;
      } else if ([0x94746d, 0x315c80, 0xd6c0a1, 0x94bdc8].includes(original.color.getHex())) {
        surface.color.set(color === 'w' ? 0x666e50 : 0x304754);
        if ([0xd6c0a1, 0x94bdc8].includes(original.color.getHex())) surface.color.set(color === 'w' ? 0xaba28a : 0x798885);
        surface.bumpMap = surfaceTexture('scale');
        surface.bumpScale = 0.008;
        surface.roughness = 0.57;
        surface.metalness = 0.12;
      }
      if (surface.emissiveIntensity > 0) surface.emissiveIntensity *= 0.35;
      clones.set(original.uuid, surface);
    }
    object.material = clones.get(original.uuid);
  });
  root.userData.studioOnly = true;
  return root;
}