import { copyFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'public/engine');
await mkdir(output, { recursive: true });
for (const name of ['stockfish-19-lite-single.js', 'stockfish-19-lite-single.wasm']) {
  await copyFile(path.join(root, 'node_modules/stockfish/bin', name), path.join(output, name));
}
console.log('Stockfish local preparado.');