import test from 'node:test';
import assert from 'node:assert/strict';
import { GameState, squarePosition } from '../src/game.js';

test('initial position and illegal movement', () => {
  const game = new GameState();
  assert.equal(game.chess.moves().length, 20);
  assert.throws(() => game.move('e2', 'e5'));
  assert.equal(game.history.length, 0);
  assert.deepEqual(squarePosition('a1'), { x: -3.5, z: 3.5 });
});

test('castling and en passant use library rules', () => {
  const game = new GameState();
  game.chess.load('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1');
  assert.equal(game.move('e1', 'g1').san, 'O-O');
  assert.equal(game.chess.get('f1').type, 'r');
  game.reset();
  for (const [from, to] of [['e2', 'e4'], ['a7', 'a6'], ['e4', 'e5'], ['d7', 'd5']]) game.move(from, to);
  assert.ok(game.move('e5', 'd6').flags.includes('e'));
  assert.equal(game.chess.get('d5'), undefined);
});

test('promotion and mate', () => {
  const game = new GameState();
  game.chess.load('7k/P7/8/8/8/8/8/7K w - - 0 1');
  game.move('a7', 'a8', 'n');
  assert.equal(game.chess.get('a8').type, 'n');
  game.reset();
  for (const [from, to] of [['f2', 'f3'], ['e7', 'e5'], ['g2', 'g4'], ['d8', 'h4']]) game.move(from, to);
  assert.equal(game.result.title, 'Jaque mate');
  assert.equal(game.result.winner, 'b');
  assert.throws(() => game.move('a2', 'a3'));
});

test('stalemate and repeated position', () => {
  const game = new GameState();
  game.chess.load('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1');
  assert.equal(game.result.title, 'Tablas por ahogado');
  game.reset();
  for (let cycle = 0; cycle < 2; cycle++) {
    for (const [from, to] of [['g1', 'f3'], ['g8', 'f6'], ['f3', 'g1'], ['f6', 'g8']]) game.move(from, to);
  }
  assert.equal(game.result.title, 'Triple repeticion');
});

test('save restore undo and clocks', () => {
  const game = new GameState({ clock: '5+3' });
  game.move('e2', 'e4');
  game.tick(2);
  assert.equal(game.clocks.b, 298);
  const copy = new GameState();
  copy.restore(JSON.parse(JSON.stringify(game.snapshot())));
  assert.equal(copy.chess.fen(), game.chess.fen());
  assert.equal(copy.clocks.b, 298);
  copy.undo();
  assert.equal(copy.history.length, 0);
  assert.equal(copy.clocks.w, 300);
});

test('invalid save is not partially applied', () => {
  const game = new GameState();
  const original = game.chess.fen();
  assert.throws(() => game.restore({ version: 1, pgn: 'not chess', fen: 'bad' }));
  assert.equal(game.chess.fen(), original);
});