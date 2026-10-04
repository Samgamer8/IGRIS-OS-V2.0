import test from 'node:test';
import assert from 'node:assert/strict';
import { ConversationState, resolveAgent } from '../src/conversation-state.js';

test('manual and automatic agent choices are explicit', () => {
  assert.equal(resolveAgent('Revisa el codigo y sus riesgos'), 'reviewer');
  assert.equal(resolveAgent('Implementa una funcion'), 'programmer');
  assert.equal(resolveAgent('Compara estas referencias'), 'researcher');
  assert.equal(resolveAgent('Implementa una funcion', 'director'), 'director');
});

test('multiline input is preserved and stopped replies cannot appear later', () => {
  const state = new ConversationState();
  const text = 'Primera linea\nSegunda linea con caracteres largos ' + 'a'.repeat(800);
  const token = state.send(text);
  assert.equal(state.messages[0].text, text);
  assert.throws(() => state.send('Otra orden'));
  state.stop();
  assert.equal(state.finish(token, 'Respuesta antigua'), false);
  assert.equal(state.messages.length, 1);
});

test('editing retries replace the previous branch without increasing capabilities', () => {
  const state = new ConversationState();
  const token = state.send('Mensaje original');
  state.finish(token, 'Respuesta');
  const userId = state.messages[0].id;
  state.editAndRetry(userId, 'Mensaje corregido');
  assert.equal(state.messages.length, 1);
  assert.equal(state.messages[0].text, 'Mensaje corregido');
  assert.equal(state.verifiedCapabilities, 24);
  assert.throws(() => state.setPower('unlimited'));
});