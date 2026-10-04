import { mkdir, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const repository = path.resolve(root, '../..');
const target = path.join(root, 'public/reference');
await mkdir(target, { recursive: true });
await copyFile(path.join(repository, 'runtime/ui-review/panel_actual.png'), path.join(target, 'original.png'));
await copyFile(path.join(repository, 'assets/igris_window_art_only_1600.png'), path.join(target, 'art.png'));
await copyFile(path.join(repository, 'assets/igris_icon_v2.ico'), path.join(target, 'icon.ico'));
await copyFile(path.join(root, 'src/assets/portrait.png'), path.join(target, 'portrait.png'));
await copyFile(path.join(repository, 'deliveries/625859679440576457.jpg'), path.join(target, 'neural-layers.jpg'));
console.log('Referencia y arte originales preparados para el estudio.');