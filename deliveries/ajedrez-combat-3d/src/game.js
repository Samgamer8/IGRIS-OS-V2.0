import { Chess } from 'chess.js';

export const DEFAULT_SETTINGS = { mode: 'ai', side: 'w', difficulty: 'club', clock: 'none', animation: true, sound: true };
const CLOCKS = { none: [0, 0], '5+3': [300, 3], '10+5': [600, 5] };

export function squarePosition(square) {
  if (!/^[a-h][1-8]$/.test(square)) throw new Error('Casilla invalida');
  return { x: square.charCodeAt(0) - 97 - 3.5, z: 3.5 - (Number(square[1]) - 1) };
}

export class GameState {
  constructor(settings = {}) { this.reset(settings); }

  reset(settings = {}) {
    this.settings = { ...DEFAULT_SETTINGS, ...settings };
    if (!['ai', 'local'].includes(this.settings.mode) || !['w', 'b'].includes(this.settings.side)
      || !Object.hasOwn(CLOCKS, this.settings.clock)) throw new Error('Configuracion invalida');
    this.chess = new Chess();
    const [seconds, increment] = CLOCKS[this.settings.clock];
    this.clocks = { w: seconds, b: seconds };
    this.increment = increment;
    this.previousClocks = [];
    this.forcedResult = null;
    this.paused = false;
    this.chess.header('Event', 'Ajedrez Combat 3D', 'White', this.settings.mode === 'ai' && this.settings.side === 'b' ? 'Stockfish' : 'Blancas',
      'Black', this.settings.mode === 'ai' && this.settings.side === 'w' ? 'Stockfish' : 'Negras');
  }

  get ended() { return !!this.forcedResult || this.chess.isGameOver(); }
  get turn() { return this.chess.turn(); }
  get history() { return this.chess.history({ verbose: true }); }
  get humanTurn() { return this.settings.mode === 'local' || this.turn === this.settings.side; }
  get result() {
    if (this.forcedResult) return this.forcedResult;
    if (this.chess.isCheckmate()) return { title: 'Jaque mate', winner: this.turn === 'w' ? 'b' : 'w' };
    if (this.chess.isStalemate()) return { title: 'Tablas por ahogado', winner: null };
    if (this.chess.isInsufficientMaterial()) return { title: 'Material insuficiente', winner: null };
    if (this.chess.isThreefoldRepetition()) return { title: 'Triple repeticion', winner: null };
    if (this.chess.isDrawByFiftyMoves()) return { title: 'Regla de los 50 movimientos', winner: null };
    if (this.chess.isDraw()) return { title: 'Tablas', winner: null };
    return null;
  }

  legalMoves(square) { return this.ended ? [] : this.chess.moves({ square, verbose: true }); }

  move(from, to, promotion = 'q') {
    if (this.ended || this.paused) throw new Error('La partida no admite movimientos');
    const previous = { ...this.clocks };
    const move = this.chess.move({ from, to, promotion });
    this.previousClocks.push(previous);
    if (this.settings.clock !== 'none') this.clocks[move.color] += this.increment;
    return move;
  }

  undo() {
    const move = this.chess.undo();
    if (move) {
      this.clocks = this.previousClocks.pop() || this.clocks;
      this.forcedResult = null;
    }
    return move;
  }

  tick(seconds) {
    if (this.settings.clock === 'none' || this.paused || this.ended || !this.history.length) return;
    this.clocks[this.turn] = Math.max(0, this.clocks[this.turn] - Math.max(0, seconds));
    if (this.clocks[this.turn] === 0) this.forcedResult = { title: 'Tiempo agotado',
      winner: this.chess.isInsufficientMaterial() ? null : (this.turn === 'w' ? 'b' : 'w') };
  }

  resign() { if (!this.ended) this.forcedResult = { title: 'Abandono', winner: this.turn === 'w' ? 'b' : 'w' }; }

  snapshot() {
    return { version: 1, settings: this.settings, pgn: this.chess.pgn(), fen: this.chess.fen(),
      clocks: this.clocks, previousClocks: this.previousClocks, forcedResult: this.forcedResult };
  }

  restore(snapshot) {
    if (snapshot.version !== 1) throw new Error('Formato de partida no compatible');
    const candidate = new GameState(snapshot.settings);
    if (snapshot.pgn) candidate.chess.loadPgn(snapshot.pgn);
    else candidate.chess.load(snapshot.fen);
    if (candidate.chess.fen() !== snapshot.fen) throw new Error('Partida guardada inconsistente');
    for (const color of ['w', 'b']) {
      if (!Number.isFinite(snapshot.clocks?.[color]) || snapshot.clocks[color] < 0) throw new Error('Reloj guardado invalido');
    }
    Object.assign(this, candidate, { clocks: { ...snapshot.clocks }, previousClocks: snapshot.previousClocks || [],
      forcedResult: snapshot.forcedResult || null });
  }

  importPgn(text) {
    const candidate = new Chess();
    candidate.loadPgn(text);
    this.reset(this.settings);
    this.chess = candidate;
  }
}