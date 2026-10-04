import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_DESIGN, WIDTH, HEIGHT, panelLayout, validateDesign } from '../src/layout.js';

test('allowed dimensions never overlap or leave the rendered panel', () => {
  for (const sidebar of [208, 248, 310]) for (const chat of [360, 450, 560]) for (const gap of [12, 44]) {
    const layout = panelLayout({ ...DEFAULT_DESIGN, sidebar, chat, gap });
    assert.ok(layout.sidebar.x + layout.sidebar.w < layout.scene.x);
    assert.ok(layout.scene.x + layout.scene.w < layout.chat.x);
    assert.ok(layout.scene.y + layout.scene.h < layout.metrics.y);
    for (const rect of Object.values(layout)) {
      assert.ok(rect.x >= 0 && rect.y >= 0 && rect.x + rect.w <= WIDTH && rect.y + rect.h <= HEIGHT);
      assert.ok(rect.w > 0 && rect.h > 0);
    }
  }
});

test('draft parsing rejects invalid data and preserves defaults', () => {
  assert.throws(() => validateDesign({ chat: 'wide' }));
  assert.throws(() => validateDesign({ accent: 'red' }));
  assert.throws(() => validateDesign({ background: 'yes' }));
  assert.equal(validateDesign({ sidebar: 900 }).sidebar, 310);
  assert.deepEqual(validateDesign({}), DEFAULT_DESIGN);
});