import { test, expect } from '@playwright/test';
import { mkdirSync, existsSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const settings = fileURLToPath(new URL('../../../runtime/settings.json', import.meta.url));
const checksum = () => existsSync(settings) ? createHash('sha256').update(readFileSync(settings)).digest('hex') : null;

test('portrait preserves its frame and communication settings use a cog', async ({ page }) => {
  await page.goto('http://127.0.0.1:5185/prototype.html');
  const portrait = page.locator('.legacy-portrait img');
  await portrait.evaluate(image => image.decode());
  for (const viewport of [{ width: 1440, height: 960 }, { width: 1024, height: 900 }]) {
    await page.setViewportSize(viewport);
    const result = await portrait.evaluate(image => {
      const frame = image.getBoundingClientRect();
      const parent = image.closest('aside').getBoundingClientRect();
      return { ratio: frame.width / frame.height, width: image.naturalWidth,
        height: image.naturalHeight, inside: frame.left >= parent.left && frame.right <= parent.right };
    });
    expect(result.ratio).toBeCloseTo(194 / 269, 3);
    expect(result.width).toBe(194);
    expect(result.height).toBe(269);
    expect(result.inside).toBe(true);
  }
  await expect(page.locator('#conversation-settings svg')).toHaveAttribute('data-lucide', 'settings');
  await page.locator('#conversation-settings').click();
  await expect(page.locator('#proto-dialog')).toBeVisible();
});

test('conversation wraps long text supports attachments editing and explicit agent power', async ({ page }) => {
  const before = checksum();
  await page.goto('http://127.0.0.1:5185/prototype.html');
  await page.waitForFunction(() => window.__igrisPrototype?.network.nodeCount === 24);
  await page.locator('#agent-choice').selectOption('programmer');
  await page.locator('#power-choice').selectOption('balanced');
  const message = 'Primera linea\nSegunda linea\n' + 'texto'.repeat(160);
  await page.locator('#message-input').fill(message);
  expect(await page.locator('#message-input').inputValue()).toBe(message);
  expect(await page.locator('#message-input').evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
  await page.locator('#attachment-file').setInputFiles({ name: 'referencia.txt', mimeType: 'text/plain', buffer: Buffer.from('Referencia local') });
  await expect(page.locator('#attachments')).toContainText('referencia.txt');
  await page.locator('#send-message').click();
  await expect(page.locator('.chat-message.assistant')).toHaveCount(1);
  const recorded = await page.evaluate(() => window.__igrisPrototype.state.messages[0]);
  expect(recorded.text).toBe(message);
  expect(recorded.agent).toBe('programmer');
  expect(recorded.power).toBe('balanced');
  expect(recorded.attachments[0].name).toBe('referencia.txt');
  await page.getByRole('button', { name: 'Editar y reenviar' }).click();
  await page.locator('#message-input').fill('Mensaje corregido');
  await page.locator('#send-message').click();
  await expect(page.locator('.chat-message.assistant')).toHaveCount(1);
  await expect(page.locator('.chat-message.user .message-body')).toHaveText('Mensaje corregido');
  expect(await page.evaluate(() => window.__igrisPrototype.state.verifiedCapabilities)).toBe(24);
  await page.locator('#agent-choice').selectOption('auto');
  await page.locator('#message-input').fill('Revisa la seguridad de este codigo');
  await page.locator('#send-message').click();
  await page.locator('#stop-response').click();
  await expect(page.locator('#response-state')).toBeHidden();
  await page.waitForFunction(() => window.__igrisPrototype.state.messages.length === 3 && !window.__igrisPrototype.state.pending);
  expect(await page.evaluate(() => window.__igrisPrototype.state.messages.at(-1).agent)).toBe('reviewer');
  expect(checksum()).toBe(before);
  mkdirSync('evidence', { recursive: true });
  await page.screenshot({ path: 'evidence/prototype-conversation.png', fullPage: true });
});

test('image layers visibly move even with all signal points hidden', async ({ page }) => {
  await page.goto('http://127.0.0.1:5185/prototype.html');
  await page.waitForFunction(() => window.__igrisPrototype?.network.referenceLayers.length === 6);
  const motion = await page.evaluate(() => {
    const network = window.__igrisPrototype.network;
    network.renderer.setAnimationLoop(null);
    network.group.visible = false;
    network.referenceEpoch = 0;
    const gl = network.renderer.getContext();
    const capture = time => {
      network.update(time);
      network.renderer.render(network.scene, network.camera);
      const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
      gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      return { pixels, poses: network.referenceLayers.map(mesh => ({
        rotation: mesh.rotation.z, depth: mesh.position.z, scale: mesh.scale.x })) };
    };
    const first = capture(0);
    const next = capture(3);
    let changed = 0;
    for (let offset = 0; offset < first.pixels.length; offset += 4) {
      if (Math.abs(first.pixels[offset + 1] - next.pixels[offset + 1]) > 8 ||
          Math.abs(first.pixels[offset + 2] - next.pixels[offset + 2]) > 8) changed++;
    }
    return { changed, fraction: changed / (first.pixels.length / 4),
      movedLayers: next.poses.filter((pose, index) => Math.abs(pose.rotation - first.poses[index].rotation) > 0.05).length,
      depthChanged: next.poses.some((pose, index) => Math.abs(pose.depth - first.poses[index].depth) > 0.03),
      coreScaleChanged: Math.abs(next.poses[3].scale - first.poses[3].scale) };
  });
  expect(motion.movedLayers).toBe(6);
  expect(motion.depthChanged).toBe(true);
  expect(motion.coreScaleChanged).toBeGreaterThan(0.025);
  expect(motion.fraction).toBeGreaterThan(0.01);
  mkdirSync('evidence', { recursive: true });
  await page.locator('#neural-view canvas').screenshot({ path: 'evidence/layers-moving-without-points.png' });
});

test('reference panels are six transparent independently animated selectable layers', async ({ page }) => {
  await page.goto('http://127.0.0.1:5185/prototype.html');
  await page.waitForFunction(() => window.__igrisPrototype?.network.referenceLayers.length === 6);
  const initial = await page.evaluate(() => window.__igrisPrototype.network.referenceLayers.map(mesh =>
    [mesh.rotation.z, mesh.material.opacity]));
  await page.waitForFunction(values => window.__igrisPrototype.network.referenceLayers.some((mesh, index) =>
    Math.abs(mesh.rotation.z - values[index][0]) > 0.0002), initial);
  const textures = await page.evaluate(() => window.__igrisPrototype.network.referenceLayers.map(mesh => {
    const canvas = mesh.material.map.image;
    const pixels = canvas.getContext('2d').getImageData(0, 0, 512, 512).data;
    let transparent = 0;
    let visible = 0;
    for (let offset = 3; offset < pixels.length; offset += 4) {
      transparent += pixels[offset] === 0;
      visible += pixels[offset] > 40;
    }
    return { name: mesh.name, transparent, visible, size: canvas.width, depth: mesh.position.z };
  }));
  expect(textures.every(texture => texture.transparent > 1000 && texture.visible > 1000 && texture.size === 512)).toBe(true);
  expect(new Set(textures.map(texture => texture.depth)).size).toBe(6);
  await page.locator('#network-settings').click();
  await page.getByLabel('Capa visible').selectOption('5');
  expect(await page.evaluate(() => window.__igrisPrototype.network.referenceLayers.map(mesh => mesh.visible)))
    .toEqual([false, false, false, false, false, true]);
  await page.locator('#close-dialog').click();
  mkdirSync('evidence', { recursive: true });
  await page.locator('#neural-view canvas').screenshot({ path: 'evidence/reference-layer-segments.png' });
  await page.locator('#network-settings').click();
  await page.getByLabel('Capa visible').selectOption('all');
  await page.locator('#close-dialog').click();
  await page.locator('#neural-view canvas').screenshot({ path: 'evidence/reference-layers-combined.png' });
});

test('blue grouped layers animate real signals and remain visible on desktop and mobile', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:5185/prototype.html');
  await page.waitForFunction(() => window.__igrisPrototype?.network.flowGeometry);
  await page.waitForFunction(() => window.__igrisPrototype.network.referenceLayers.length === 6);
  const first = await page.evaluate(() => Array.from(window.__igrisPrototype.network.flowGeometry.attributes.position.array));
  await page.waitForFunction(values => window.__igrisPrototype.network.flowGeometry.attributes.position.array
    .some((value, index) => Math.abs(value - values[index]) > 0.015), first);
  expect(await page.evaluate(() => window.__igrisPrototype.network.layerNames.length)).toBe(6);
  mkdirSync('evidence', { recursive: true });
  for (const viewport of [{ width: 1440, height: 960 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.waitForFunction(() => {
      const network = window.__igrisPrototype.network;
      return Math.abs(network.renderer.domElement.getBoundingClientRect().width - network.container.clientWidth) < 1;
    });
    const result = await page.evaluate(() => {
      const network = window.__igrisPrototype.network;
      network.renderer.render(network.scene, network.camera);
      let framed = true;
      for (const geometry of [network.positions, network.edges, network.orbitGeometry,
        network.channelGeometry, network.flowGeometry, network.coreGeometry]) {
        const positions = geometry.attributes.position;
        for (let index = 0; index < positions.count; index++) {
          const point = network.camera.position.clone().set(positions.getX(index), positions.getY(index), positions.getZ(index)).project(network.camera);
          if (!Number.isFinite(point.x) || !Number.isFinite(point.y) || Math.abs(point.x) > 0.95 || Math.abs(point.y) > 0.95) framed = false;
        }
      }
      network.scene.updateMatrixWorld(true);
      for (const mesh of network.referenceLayers) {
        const positions = mesh.geometry.attributes.position;
        for (let index = 0; index < positions.count; index++) {
          const point = network.camera.position.clone().set(positions.getX(index), positions.getY(index), positions.getZ(index))
            .applyMatrix4(mesh.matrixWorld).project(network.camera);
          if (Math.abs(point.x) > 0.95 || Math.abs(point.y) > 0.95) framed = false;
        }
      }
      const gl = network.renderer.getContext();
      const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
      gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      let cyan = 0;
      for (let index = 0; index < pixels.length; index += 4) {
        if (pixels[index + 2] > 30 && pixels[index + 1] > pixels[index] * 1.25 && pixels[index + 2] > pixels[index] * 1.25) cyan++;
      }
      return { framed, cyan, overflow: document.documentElement.scrollWidth > innerWidth };
    });
    expect(result.framed).toBe(true);
    expect(result.cyan).toBeGreaterThan(100);
    expect(result.overflow).toBe(false);
    await page.screenshot({ path: `evidence/blue-grouped-${viewport.width}.png`, fullPage: true });
    await page.locator('#neural-view canvas').screenshot({ path: `evidence/blue-scene-${viewport.width}.png` });
  }
  expect(errors).toEqual([]);
});

test('network pulses without rotating and complexity is an explicit sample control', async ({ page }) => {
  await page.goto('http://127.0.0.1:5185/prototype.html');
  await page.waitForFunction(() => window.__igrisPrototype?.network.nodeCount === 24);
  const first = await page.evaluate(() => Array.from(window.__igrisPrototype.network.positions.attributes.position.array));
  const initialBranches = await page.evaluate(() => window.__igrisPrototype.network.branchCount);
  await page.locator('#message-input').fill('Estoy escribiendo un mensaje');
  await page.waitForFunction(values => window.__igrisPrototype.network.positions.attributes.position.array
    .some((value, index) => Math.abs(value - values[index]) > 0.002), first);
  expect(await page.evaluate(() => window.__igrisPrototype.network.group.rotation.toArray().slice(0, 3))).toEqual([0, 0, 0]);
  await page.locator('#network-settings').click();
  await page.locator('#dialog-body input[type="range"]').focus();
  await page.locator('#dialog-body input[type="range"]').press('End');
  expect(await page.evaluate(() => window.__igrisPrototype.network.nodeCount)).toBe(120);
  expect(await page.evaluate(() => window.__igrisPrototype.network.branchCount)).toBeGreaterThan(initialBranches * 3);
  expect(await page.evaluate(() => window.__igrisPrototype.state.verifiedCapabilities)).toBe(120);
  await page.locator('#close-dialog').click();
  mkdirSync('evidence', { recursive: true });
  for (const viewport of [{ width: 1440, height: 960 }, { width: 1024, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.waitForFunction(() => {
      const network = window.__igrisPrototype.network;
      return Math.abs(network.renderer.domElement.getBoundingClientRect().width - network.container.clientWidth) < 1;
    });
    const result = await page.evaluate(() => {
      const network = window.__igrisPrototype.network;
      network.renderer.render(network.scene, network.camera);
      let framed = true;
      const positions = network.positions.attributes.position;
      for (let index = 0; index < positions.count; index++) {
        const point = network.camera.position.clone().set(positions.getX(index), positions.getY(index), positions.getZ(index)).project(network.camera);
        if (Math.abs(point.x) > 0.95 || Math.abs(point.y) > 0.95) framed = false;
      }
      const gl = network.renderer.getContext();
      const pixels = new Uint8Array(64 * 64 * 4);
      gl.readPixels(Math.floor(gl.drawingBufferWidth / 2) - 32,
        Math.floor(gl.drawingBufferHeight / 2) - 32, 64, 64, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      const colors = new Set();
      for (let index = 0; index < pixels.length; index += 4) colors.add(`${pixels[index]},${pixels[index + 1]},${pixels[index + 2]}`);
      return { colors: colors.size, framed, overflow: document.documentElement.scrollWidth > innerWidth };
    });
    expect(result.colors).toBeGreaterThan(10);
    expect(result.framed).toBe(true);
    expect(result.overflow).toBe(false);
    await page.screenshot({ path: `evidence/prototype-${viewport.width}.png`, fullPage: true });
  }
});