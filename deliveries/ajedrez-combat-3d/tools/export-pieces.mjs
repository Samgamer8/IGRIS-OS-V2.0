import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { createFantasyPiece } from '../src/pieces.js';

globalThis.FileReader = class {
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then(result => { this.result = result; this.onloadend?.(); });
  }
  readAsDataURL(blob) {
    blob.arrayBuffer().then(result => {
      this.result = `data:${blob.type};base64,${Buffer.from(result).toString('base64')}`;
      this.onloadend?.();
    });
  }
};

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'public/models');
await mkdir(output, { recursive: true });
const exporter = new GLTFExporter();
const names = { p: 'peon_dragon', n: 'caballero', b: 'alfil', r: 'torre_guerrera', q: 'dama', k: 'rey' };
const manifest = [];
for (const color of ['w', 'b']) for (const type of ['p', 'n', 'b', 'r', 'q', 'k']) {
  const object = createFantasyPiece(type, color);
  object.position.y = 0;
  object.rotation.y = 0;
  object.name = `${color}_${names[type]}`;
  const data = await exporter.parseAsync(object, { binary: true, onlyVisible: true });
  const binary = Buffer.from(data);
  if (binary.toString('ascii', 0, 4) !== 'glTF') throw new Error('Exportacion GLB invalida');
  const filename = `${color === 'w' ? 'blancas' : 'negras'}_${names[type]}.glb`;
  await writeFile(path.join(output, filename), binary);
  manifest.push({ color, type, filename, bytes: binary.length,
    origin: 'Reconstruccion desde referencias visuales de PIEZAS_AJEDREZ_SHAPR3D; no malla original recuperada' });
}
await writeFile(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`Exportados ${manifest.length} modelos GLB en ${output}`);