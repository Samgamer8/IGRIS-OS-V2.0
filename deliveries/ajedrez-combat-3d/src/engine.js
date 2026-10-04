export class ChessEngine {
  constructor(onEvaluation = () => {}) {
    this.onEvaluation = onEvaluation;
    this.pending = null;
    this.stopping = null;
    this.ready = new Promise((resolve, reject) => { this.resolveReady = resolve; this.rejectReady = reject; });
    this.ready.catch(() => {});
    this.worker = new Worker(new URL('./engine/stockfish-19-lite-single.js', document.baseURI));
    this.worker.onmessage = event => String(event.data).split('\n').forEach(line => this.handle(line.trim()));
    this.worker.onerror = () => { this.rejectReady(new Error('No se pudo iniciar Stockfish')); this.pending?.reject(new Error('Stockfish no disponible')); this.pending = null; };
    this.worker.postMessage('uci');
  }
  handle(line) {
    if (line === 'uciok') {
      this.worker.postMessage('setoption name Hash value 32');
      this.worker.postMessage('setoption name Threads value 1');
      this.worker.postMessage('isready');
    }
    if (line === 'readyok') this.resolveReady();
    const score = line.match(/score (cp|mate) (-?\d+)/);
    if (score && this.pending) this.onEvaluation({ type: score[1], value: Number(score[2]), fen: this.pending.fen });
    if (line.startsWith('bestmove ')) {
      if (this.stopping) { this.stopping.resolve(); this.stopping = null; return; }
      if (this.pending) { this.pending.resolve(line.split(' ')[1]); this.pending = null; }
    }
  }
  async cancel() {
    if (this.stopping) return this.stopping.promise;
    if (!this.pending) return;
    this.pending.reject(new Error('cancelled'));
    this.pending = null;
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    this.stopping = { promise, resolve };
    this.worker.postMessage('stop');
    return promise;
  }
  async search(fen, difficulty) {
    await this.ready;
    await this.cancel();
    const settings = { novice: [0, 250], club: [6, 500], expert: [12, 900], master: [20, 1500] }[difficulty] || [6, 500];
    this.worker.postMessage(`setoption name Skill Level value ${settings[0]}`);
    this.worker.postMessage(`position fen ${fen}`);
    return new Promise((resolve, reject) => {
      this.pending = { resolve, reject, fen };
      this.worker.postMessage(`go movetime ${settings[1]}`);
    });
  }
  destroy() { this.worker.terminate(); }
}