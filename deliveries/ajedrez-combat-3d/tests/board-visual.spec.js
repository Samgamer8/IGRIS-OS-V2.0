import { test, expect } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

test('approved figures have ground contact cell clearance and responsive framing', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:5179/');
  await page.waitForFunction(() => window.__game && !window.__game.scene.loading);
  const loadingError = await page.locator('#toast').textContent();
  expect(loadingError, 'Model loading or posing failed').not.toContain('No se pudieron');
  await page.waitForFunction(() => !window.__game.busy && window.__game.scene.pieces.size === 32);
  const evidence = await page.evaluate(async () => {
    const THREE = await import('/node_modules/three/build/three.module.js');
    const game = window.__game;
    const approved = [];
    for (const [square, piece] of game.scene.pieces) {
      if (!piece.userData.approvedAsset) continue;
      piece.updateMatrixWorld(true);
      const bounds = new THREE.Box3().setFromObject(piece);
      const size = bounds.getSize(new THREE.Vector3());
      approved.push({ square, type: piece.userData.pieceType, pose: piece.userData.boardPose,
        width: size.x, depth: size.z, height: size.y, bottom: bounds.min.y,
        offsetX: Math.abs((bounds.min.x + bounds.max.x) / 2 - piece.position.x),
        offsetZ: Math.abs((bounds.min.z + bounds.max.z) / 2 - piece.position.z) });
    }
    return { approved, count: game.scene.pieces.size };
  });
  expect(evidence.count).toBe(32);
  expect(evidence.approved).toHaveLength(20);
  for (const figure of evidence.approved) {
    expect(figure.width).toBeLessThanOrEqual(1.55);
    expect(figure.depth).toBeLessThanOrEqual(1.55);
    expect(figure.bottom).toBeCloseTo(0.09, 2);
    expect(figure.offsetX).toBeLessThan(0.01);
    expect(figure.offsetZ).toBeLessThan(0.01);
    if (figure.type === 'p') expect(figure.pose).toBe('compact-dragon-v1');
  }
  mkdirSync('evidence', { recursive: true });
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.locator('#camera-home').click();
    const result = await page.evaluate(async () => {
      const THREE = await import('/node_modules/three/build/three.module.js');
      const { camera, controls, renderer, scene } = window.__game.scene;
      camera.updateMatrixWorld();
      let framed = true;
      for (const x of [-8.37, 8.37]) for (const z of [-8.37, 8.37]) {
        const point = new THREE.Vector3(x, 1.9, z).project(camera);
        if (Math.abs(point.x) > 0.92 || Math.abs(point.y) > 0.82) framed = false;
      }
      renderer.render(scene, camera);
      const gl = renderer.getContext();
      const pixels = new Uint8Array(64 * 64 * 4);
      gl.readPixels(Math.floor(gl.drawingBufferWidth / 2) - 32,
        Math.floor(gl.drawingBufferHeight / 2) - 32, 64, 64, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      const colors = new Set();
      for (let index = 0; index < pixels.length; index += 4) colors.add(`${pixels[index]},${pixels[index + 1]},${pixels[index + 2]}`);
      return { framed, colors: colors.size, overflow: document.documentElement.scrollWidth > innerWidth };
    });
    expect(result.framed).toBe(true);
    expect(result.colors).toBeGreaterThan(15);
    expect(result.overflow).toBe(false);
    await page.screenshot({ path: `evidence/board-${viewport.width}.png`, fullPage: true });
  }
  expect(errors).toEqual([]);
  writeFileSync('evidence/board-fit.json', JSON.stringify(evidence, null, 2));
});

test('moving a real pawn keeps ground contact and lands on the legal square', async ({ page }) => {
  await page.goto('http://127.0.0.1:5179/');
  await page.waitForFunction(() => window.__game && !window.__game.busy && !window.__game.scene.loading);
  await page.evaluate(() => window.__game.reset({ mode: 'local', animation: true, sound: false }));
  const source = await page.evaluate(() => window.__game.square('e2'));
  await page.mouse.click(source.x, source.y);
  await expect(page.locator('#selection-label')).toContainText('E2');
  const destination = await page.evaluate(() => window.__game.square('e4'));
  await page.mouse.click(destination.x, destination.y);
  const samples = await page.evaluate(async () => {
    const THREE = await import('/node_modules/three/build/three.module.js');
    return new Promise(resolve => {
      const heights = [];
      function sample() {
        const game = window.__game;
        if (!game.busy) { resolve(heights); return; }
        const actor = game.scene.pieces.get('e2');
        if (actor) {
          actor.updateMatrixWorld(true);
          heights.push(new THREE.Box3().setFromObject(actor).min.y);
        }
        requestAnimationFrame(sample);
      }
      sample();
    });
  });
  expect(samples.length).toBeGreaterThan(0);
  for (const height of samples) expect(height).toBeCloseTo(0.09, 2);
  await page.waitForFunction(() => !window.__game.busy && window.__game.scene.pieces.has('e4'));
  const final = await page.evaluate(() => {
    const game = window.__game;
    const piece = game.scene.pieces.get('e4');
    return { legalSquare: game.store.chess.get('e4')?.type, asset: piece.userData.asset,
      x: piece.position.x, z: piece.position.z, history: game.store.history.map(move => move.san) };
  });
  expect(final.legalSquare).toBe('p');
  expect(final.asset).toBe('Red Dragon red');
  expect(final.x).toBeCloseTo(0.9, 5);
  expect(final.z).toBeCloseTo(0.9, 5);
  expect(final.history).toEqual(['e4']);
  writeFileSync('evidence/pawn-movement.json', JSON.stringify({ samples, final }, null, 2));
});