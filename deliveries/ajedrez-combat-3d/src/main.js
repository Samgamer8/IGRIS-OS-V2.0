import './style.css'
import heroImg from './assets/hero.png'
import javascriptLogo from './assets/javascript.svg'
import viteLogo from './assets/vite.svg'
import { setupCounter } from './counter.js'
import './style.css';
import './game.css';
import '@fontsource/manrope/400.css';
import '@fontsource/manrope/600.css';
import '@fontsource/barlow-condensed/500.css';
import '@fontsource/barlow-condensed/600.css';
import { createIcons, icons } from 'lucide';
import { GameState } from './game.js';
import { BoardScene } from './scene.js';
import { ChessEngine } from './engine.js';

const names = { p: 'Peon', n: 'Caballo', b: 'Alfil', r: 'Torre', q: 'Dama', k: 'Rey' };
const levels = { novice: 'Aprendiz', club: 'Club', expert: 'Experto', master: 'Maestro' };
const store = new GameState();
let selected = null;
let busy = true;
let thinking = false;
let revision = 0;
let lastMove = null;
let engine = null;
let toastTimer;
let audioContext;
let dialogPause = false;

document.querySelector('#app').innerHTML = `
  <header class="topbar">
    <div class="brand"><i data-lucide="crown"></i><div><h1>AJEDREZ COMBAT <span>3D</span></h1><p>IGRIS EDITION</p></div></div>
    <div class="top-actions"><span class="local-badge"><b></b>LOCAL</span><button id="new-game" class="command"><i data-lucide="plus"></i><span>Nueva partida</span></button><button id="settings" class="icon-button" title="Configurar partida" aria-label="Configurar partida"><i data-lucide="settings-2"></i></button></div>
  </header>
  <main class="game-layout">
    <section class="arena" aria-label="Escena de juego">
      <div id="viewport"></div>
      <div class="arena-heading"><span class="section-label">ARENA 01</span><h2>EL TABLERO DE LOS REYES</h2></div>
      <div class="opponent-chip"><span class="faction-dot black"></span><span id="opponent-name">Stockfish 19</span><span id="opponent-level">Club</span></div>
      <div class="selection-label" id="selection-label"></div>
      <nav class="camera-tools" aria-label="Herramientas de camara">
        <button id="flip" class="icon-button" title="Girar tablero" aria-label="Girar tablero"><i data-lucide="rotate-3d"></i></button>
        <button id="camera-home" class="icon-button" title="Restablecer camara" aria-label="Restablecer camara"><i data-lucide="focus"></i></button>
        <button id="fullscreen" class="icon-button" title="Pantalla completa" aria-label="Pantalla completa"><i data-lucide="maximize"></i></button>
      </nav>
      <div class="arena-bottom"><div><span class="faction-dot white"></span><span id="player-side">Tu ejercito</span></div><span id="move-count">MOVIMIENTO 01</span></div>
      <div id="toast" role="status" aria-live="polite"></div>
    </section>
    <aside class="match-panel">
      <div class="panel-heading"><span class="section-label">LA PARTIDA</span><span id="mode-label">CONTRA LA IA</span></div>
      <div class="player-row black-row"><div class="player-emblem"><i data-lucide="cpu"></i></div><div class="player-info"><strong id="black-name">Stockfish 19</strong><span>Negras</span></div><output id="clock-b">--:--</output></div>
      <div class="turn-status"><span id="turn-dot" class="faction-dot white"></span><div><strong id="status-title">Juegan blancas</strong><span id="status-detail">Partida en curso</span></div><span id="thinking" hidden></span></div>
      <div class="player-row white-row"><div class="player-emblem"><i data-lucide="user-round"></i></div><div class="player-info"><strong id="white-name">Tu ejercito</strong><span>Blancas</span></div><output id="clock-w">--:--</output></div>
      <div class="capture-row"><span>CAPTURADAS</span><div id="captured-white">-</div><div id="captured-black">-</div></div>
      <div class="history-heading"><h3>Movimientos</h3><span id="evaluation">POSICION INICIAL</span></div>
      <div id="move-history" aria-label="Historial de movimientos"></div>
      <div class="match-tools"><button id="undo" class="icon-button" title="Deshacer turno" aria-label="Deshacer turno"><i data-lucide="undo-2"></i></button><button id="pause" class="icon-button" title="Pausar partida" aria-label="Pausar partida"><i data-lucide="pause"></i></button><button id="save" class="icon-button" title="Guardar partida" aria-label="Guardar partida"><i data-lucide="save"></i></button><button id="load" class="icon-button" title="Cargar partida guardada" aria-label="Cargar partida guardada"><i data-lucide="folder-open"></i></button><button id="export" class="icon-button" title="Exportar PGN" aria-label="Exportar PGN"><i data-lucide="download"></i></button><button id="import" class="icon-button" title="Importar PGN" aria-label="Importar PGN"><i data-lucide="upload"></i></button></div>
      <button id="resign" class="resign-command"><i data-lucide="flag"></i>Abandonar partida</button>
      <footer class="panel-footer"><span>REGLAS CLASICAS</span><span id="engine-status">STOCKFISH LOCAL</span></footer>
    </aside>
  </main>
  <dialog id="setup-dialog"><form id="setup-form"><div class="dialog-heading"><div><span class="section-label">CONFIGURACION</span><h2>Nueva partida</h2></div><button type="button" class="icon-button close-dialog" aria-label="Cerrar"><i data-lucide="x"></i></button></div>
    <div class="form-grid"><label>Rival<select name="mode"><option value="ai">Stockfish local</option><option value="local">Dos jugadores</option></select></label><label>Tu ejercito<select name="side"><option value="w">Blancas</option><option value="b">Negras</option></select></label><label>Nivel de IA<select name="difficulty"><option value="novice">Aprendiz</option><option value="club" selected>Club</option><option value="expert">Experto</option><option value="master">Maestro</option></select></label><label>Reloj<select name="clock"><option value="none">Sin limite</option><option value="5+3">5 minutos + 3 segundos</option><option value="10+5">10 minutos + 5 segundos</option></select></label><label>Calidad grafica<select name="quality"><option value="balanced">Equilibrada</option><option value="high">Alta</option></select></label><label class="check-label"><input name="animation" type="checkbox" checked>Capturas animadas</label><label class="check-label"><input name="sound" type="checkbox" checked>Sonido</label></div>
    <div class="dialog-actions"><button type="button" class="secondary-command close-dialog">Cancelar</button><button type="submit" class="command">Comenzar partida<i data-lucide="arrow-right"></i></button></div></form></dialog>
  <dialog id="promotion-dialog"><span class="section-label">PROMOCION</span><h2>Elige una pieza</h2><div class="promotion-options">${[['q', 'Dama'], ['r', 'Torre'], ['b', 'Alfil'], ['n', 'Caballo']].map(([piece, name]) => `<button data-promotion="${piece}" class="secondary-command">${name}</button>`).join('')}</div></dialog>
  <dialog id="result-dialog"><span class="section-label">PARTIDA FINALIZADA</span><h2 id="result-title"></h2><p id="result-detail"></p><div class="dialog-actions"><button class="secondary-command" id="result-close">Ver tablero</button><button class="command" id="result-new">Nueva partida<i data-lucide="arrow-right"></i></button></div></dialog>
  <input id="pgn-file" type="file" accept=".pgn,.txt" hidden>
`;

const $ = selector => document.querySelector(selector);
const scene = new BoardScene($('#viewport'), chooseSquare);
scene.sync(store.chess);
scene.ready.then(() => {
  scene.sync(store.chess);
  busy = false;
  render();
  maybeThink();
}).catch(error => {
  toast('No se pudieron cargar las figuras aprobadas: ' + error.message);
  render();
});
createIcons({ icons });

function toast(text) {
  $('#toast').textContent = text;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3400);
}

function sound(capture = false) {
  if (!store.settings.sound) return;
  try {
    audioContext ||= new AudioContext();
    audioContext.resume();
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = capture ? 'triangle' : 'sine';
    oscillator.frequency.setValueAtTime(capture ? 170 : 540, audioContext.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(capture ? 72 : 240, audioContext.currentTime + 0.15);
    gain.gain.setValueAtTime(0.07, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.22);
    oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start(); oscillator.stop(audioContext.currentTime + 0.23);
  } catch {}
}

function render() {
  const result = store.result;
  $('#status-title').textContent = result ? result.title : store.paused ? 'Partida pausada' : thinking ? 'Stockfish piensa' : store.turn === 'w' ? 'Juegan blancas' : 'Juegan negras';
  $('#status-detail').textContent = scene.error ? 'Modelos no disponibles' : scene.loading ? 'Cargando figuras 3D'
    : result ? (result.winner ? `Victoria de ${result.winner === 'w' ? 'blancas' : 'negras'}` : 'Partida empatada') : store.chess.isCheck() ? 'Jaque al rey' : busy ? 'Movimiento en curso' : store.paused ? 'Reloj detenido' : store.humanTurn ? 'Tu turno' : 'Turno del rival';
  $('#turn-dot').className = `faction-dot ${store.turn === 'w' ? 'white' : 'black'}`;
  $('#thinking').hidden = !thinking;
  $('#mode-label').textContent = store.settings.mode === 'local' ? 'DOS JUGADORES' : 'CONTRA LA IA';
  for (const color of ['w', 'b']) {
    const seconds = Math.ceil(store.clocks[color]);
    $(`#clock-${color}`).textContent = store.settings.clock === 'none' ? '--:--' : `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
    $(`.${color === 'w' ? 'white' : 'black'}-row`).classList.toggle('active', store.turn === color && !store.ended);
    $(`#${color === 'w' ? 'white' : 'black'}-name`).textContent = store.settings.mode === 'local' ? (color === 'w' ? 'Ejercito blanco' : 'Ejercito negro') : color === store.settings.side ? 'Tu ejercito' : 'Stockfish 19';
  }
  $('#opponent-name').textContent = store.settings.mode === 'local' ? 'Duelo local' : 'Stockfish 19';
  $('#opponent-level').textContent = store.settings.mode === 'local' ? 'Dos jugadores' : levels[store.settings.difficulty];
  $('#player-side').textContent = store.settings.mode === 'local' ? 'Partida local' : `Tu ejercito: ${store.settings.side === 'w' ? 'blancas' : 'negras'}`;
  $('#move-count').textContent = `MOVIMIENTO ${String(Math.floor(store.history.length / 2) + 1).padStart(2, '0')}`;
  const history = store.history;
  const rows = [];
  for (let index = 0; index < history.length; index += 2) rows.push(`<div class="move-row"><span>${index / 2 + 1}.</span><span>${history[index].san}</span><span>${history[index + 1]?.san || ''}</span></div>`);
  $('#move-history').innerHTML = rows.length ? rows.join('') : '<div class="empty-history">Sin movimientos</div>';
  $('#move-history').scrollTop = $('#move-history').scrollHeight;
  for (const color of ['w', 'b']) {
    const captures = history.filter(move => move.color === color && move.captured).map(move => names[move.captured]);
    $(`#captured-${color === 'w' ? 'white' : 'black'}`).textContent = captures.length ? captures.join(' · ') : '-';
  }
  $('#undo').disabled = busy || !history.length;
  $('#resign').disabled = busy || store.ended;
  $('#selection-label').textContent = selected ? `${names[store.chess.get(selected)?.type] || ''} · ${selected.toUpperCase()}` : '';
  let king = null;
  if (store.chess.isCheck()) for (const row of store.chess.board()) for (const piece of row) if (piece?.type === 'k' && piece.color === store.turn) king = piece.square;
  scene.highlight(selected, selected ? store.legalMoves(selected) : [], lastMove, king);
}

function persist() { try { localStorage.setItem('igris-chess-autosave', JSON.stringify(store.snapshot())); } catch { toast('No se pudo guardar en este dispositivo'); } }

async function chooseSquare(square) {
  if (busy || thinking || store.paused || store.ended || !store.humanTurn) return;
  const piece = store.chess.get(square);
  if (selected) {
    const moves = store.legalMoves(selected).filter(move => move.to === square);
    if (moves.length) {
      const from = selected;
      let promotion = 'q';
      if (moves.some(move => move.promotion)) {
        promotion = await choosePromotion();
        if (!promotion) { selected = null; render(); return; }
      }
      await performMove(from, square, promotion);
      return;
    }
  }
  selected = piece?.color === store.turn ? square : null;
  render();
}

function choosePromotion() {
  const dialog = $('#promotion-dialog');
  store.paused = true;
  dialog.showModal();
  return new Promise(resolve => {
    const finish = value => { store.paused = false; dialog.close(); dialog.oncancel = null; resolve(value); };
    for (const button of dialog.querySelectorAll('button')) button.onclick = () => finish(button.dataset.promotion);
    dialog.oncancel = event => { event.preventDefault(); finish(null); };
  });
}

async function performMove(from, to, promotion = 'q') {
  if (busy) return;
  busy = true;
  try {
    const move = store.move(from, to, promotion);
    selected = null;
    lastMove = move;
    sound(!!move.captured);
    render();
    await scene.animateMove(move, store.chess, store.settings.animation);
    persist();
    if (store.ended) showResult();
  } catch (error) { toast(error.message); }
  finally { busy = false; render(); }
  maybeThink();
}

async function maybeThink() {
  if (store.settings.mode !== 'ai' || store.humanTurn || store.ended || store.paused || thinking || busy) return;
  const current = revision;
  thinking = true;
  render();
  try {
    engine ||= new ChessEngine(score => {
      const whiteScore = score.value * (score.fen.split(' ')[1] === 'w' ? 1 : -1);
      $('#evaluation').textContent = score.type === 'mate' ? `MATE ${Math.abs(whiteScore)}` : `${whiteScore >= 0 ? '+' : ''}${(whiteScore / 100).toFixed(1)}`;
    });
    const move = await engine.search(store.chess.fen(), store.settings.difficulty);
    if (current !== revision || store.ended) return;
    if (!/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(move)) throw new Error('El motor no devolvio un movimiento valido');
    thinking = false;
    await performMove(move.slice(0, 2), move.slice(2, 4), move[4] || 'q');
  } catch (error) {
    if (current === revision && error.message !== 'cancelled') { store.paused = true; toast('Stockfish: ' + error.message); }
  } finally { if (current === revision) { thinking = false; render(); } }
}

async function stopThinking() { revision++; await engine?.cancel(); thinking = false; }

function showResult() {
  const result = store.result;
  $('#result-title').textContent = result.title;
  $('#result-detail').textContent = result.winner ? `Victoria del ejercito ${result.winner === 'w' ? 'blanco' : 'negro'}` : 'La partida termina en tablas';
  if (!$('#result-dialog').open) $('#result-dialog').showModal();
}

async function openSetup() {
  if (busy) return;
  dialogPause = store.paused;
  store.paused = true;
  await stopThinking();
  const form = $('#setup-form');
  for (const key of ['mode', 'side', 'difficulty', 'clock']) form.elements[key].value = store.settings[key];
  form.elements.animation.checked = store.settings.animation;
  form.elements.sound.checked = store.settings.sound;
  $('#setup-dialog').showModal();
  render();
}

function closeSetup() { $('#setup-dialog').close(); store.paused = dialogPause; render(); maybeThink(); }
$('#new-game').onclick = openSetup;
$('#settings').onclick = openSetup;
for (const button of document.querySelectorAll('.close-dialog')) button.onclick = closeSetup;
$('#setup-dialog').oncancel = event => { event.preventDefault(); closeSetup(); };
$('#setup-form').onsubmit = async event => {
  event.preventDefault();
  await stopThinking();
  const form = event.target;
  store.reset({ mode: form.elements.mode.value, side: form.elements.side.value, difficulty: form.elements.difficulty.value,
    clock: form.elements.clock.value, animation: form.elements.animation.checked, sound: form.elements.sound.checked });
  scene.quality(form.elements.quality.value === 'high');
  scene.home(store.settings.side);
  selected = lastMove = null;
  $('#evaluation').textContent = 'POSICION INICIAL';
  scene.sync(store.chess);
  $('#setup-dialog').close();
  persist(); render(); maybeThink();
};
$('#flip').onclick = () => scene.flip();
$('#camera-home').onclick = () => scene.home();
$('#fullscreen').onclick = () => document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
$('#pause').onclick = async () => { if (busy || store.ended) return; store.paused = !store.paused; if (store.paused) await stopThinking(); render(); maybeThink(); };
$('#undo').onclick = async () => {
  if (busy) return;
  await stopThinking();
  store.undo();
  if (store.settings.mode === 'ai' && !store.humanTurn && store.history.length) store.undo();
  selected = null; lastMove = store.history.at(-1) || null;
  scene.sync(store.chess); persist(); render(); maybeThink();
};
$('#save').onclick = () => { try { localStorage.setItem('igris-chess-save', JSON.stringify(store.snapshot())); toast('Partida guardada'); } catch { toast('No se pudo guardar la partida'); } };
$('#load').onclick = async () => {
  if (busy) return;
  try {
    const data = localStorage.getItem('igris-chess-save') || localStorage.getItem('igris-chess-autosave');
    if (!data) return toast('No hay una partida guardada');
    await stopThinking(); store.restore(JSON.parse(data)); selected = null; lastMove = store.history.at(-1) || null;
    scene.sync(store.chess); scene.home(store.settings.side); render(); toast('Partida recuperada'); maybeThink();
  } catch (error) { toast('No se pudo cargar: ' + error.message); }
};
$('#export').onclick = () => {
  const blob = new Blob([store.chess.pgn()], { type: 'application/x-chess-pgn' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = 'ajedrez-combat.pgn'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$('#import').onclick = () => { if (!busy) $('#pgn-file').click(); };
$('#pgn-file').onchange = async event => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 1024 * 1024) throw new Error('El archivo supera 1 MB');
    const text = await file.text(); await stopThinking(); store.importPgn(text); selected = null; lastMove = store.history.at(-1) || null;
    scene.sync(store.chess); render(); persist(); maybeThink();
  } catch (error) { toast('PGN no valido: ' + error.message); }
  event.target.value = '';
};
$('#resign').onclick = async () => { if (confirm('Abandonar la partida actual?')) { await stopThinking(); store.resign(); render(); persist(); showResult(); } };
$('#result-close').onclick = () => $('#result-dialog').close();
$('#result-new').onclick = () => { $('#result-dialog').close(); openSetup(); };
window.addEventListener('keydown', event => { if (event.code === 'Space' && !document.querySelector('dialog[open]') && event.target === document.body) { event.preventDefault(); $('#pause').click(); } });

let previousTick = performance.now();
setInterval(() => {
  const now = performance.now();
  if (!busy) store.tick((now - previousTick) / 1000);
  previousTick = now;
  if (store.ended && thinking) { stopThinking(); showResult(); }
  for (const color of ['w', 'b']) {
    const seconds = Math.ceil(store.clocks[color]);
    $(`#clock-${color}`).textContent = store.settings.clock === 'none' ? '--:--' : `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
  }
}, 200);

window.__game = { store, scene, get busy() { return busy; }, get thinking() { return thinking; },
  square: square => scene.project(square), move: performMove,
  async reset(settings = {}) { await stopThinking(); store.reset(settings); selected = lastMove = null; scene.sync(store.chess); render(); maybeThink(); },
  async loadFen(fen) { await stopThinking(); store.reset({ mode: 'local' }); store.chess.load(fen); selected = lastMove = null; scene.sync(store.chess); render(); } };
render();
