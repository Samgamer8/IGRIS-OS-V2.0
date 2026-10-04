import './editor.css';
import '@fontsource/manrope/latin-400.css';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/barlow-condensed/latin-600.css';
import { createIcons, Download, RotateCcw, Save, Upload, Image, SlidersHorizontal, Check, Focus } from 'lucide';
import { DEFAULT_DESIGN, WIDTH, HEIGHT, panelLayout, validateDesign } from './layout.js';
import { loadPreviewAssets, renderPanel } from './render.js';

const icons = { Download, RotateCcw, Save, Upload, Image, SlidersHorizontal, Check, Focus };
const storageKey = 'igris-panel-design-draft-v1';
let design = { ...DEFAULT_DESIGN };
let mode = 'original';
let assets;
let selected = null;
const ranges = [
  ['sidebar', 'Navegacion', 208, 310, 1, 'px'], ['chat', 'Comunicacion', 360, 560, 1, 'px'],
  ['gap', 'Separacion', 12, 44, 1, 'px'], ['metrics', 'Altura de indicadores', 100, 160, 1, 'px'],
  ['sceneScale', 'Escena central', 0.65, 1.05, 0.01, '%'], ['radius', 'Esquinas', 0, 20, 1, 'px'],
  ['contrast', 'Oscurecer fondo', 0.25, 0.95, 0.01, '%'],
];

document.querySelector('#app').innerHTML = `
  <header class="editor-header"><div class="editor-brand"><i data-lucide="sliders-horizontal"></i><div><h1>IGRIS · ESTUDIO DEL PANEL</h1><span>BORRADOR VISUAL</span></div></div><div class="header-actions"><span id="draft-state">Referencia original</span><button id="export-image" class="primary" disabled><i data-lucide="download"></i><span>Exportar PNG</span></button></div></header>
  <main class="editor-layout"><section class="workspace"><div class="preview-toolbar"><div class="segmented"><button data-view="original" class="active">Original</button><button data-view="proposal">Propuesta</button></div><div class="format-label">1440 × 810</div><button id="clear-selection" class="icon-button" title="Quitar seleccion" aria-label="Quitar seleccion"><i data-lucide="focus"></i></button></div>
    <div class="canvas-area"><div class="canvas-frame"><canvas id="panel-preview" width="1440" height="810" aria-label="Vista renderizada del panel IGRIS"></canvas></div></div><footer class="preview-footer"><span id="selection-name">Panel completo</span><span id="load-status">Cargando referencia</span></footer></section>
    <aside class="controls"><div class="controls-heading"><h2>Composicion</h2><button id="reset" class="icon-button" title="Restablecer propuesta" aria-label="Restablecer propuesta"><i data-lucide="rotate-ccw"></i></button></div>
    ${ranges.map(([key, label, min, max, step]) => `<label class="range-control"><span>${label}<output id="value-${key}"></output></span><input data-setting="${key}" type="range" min="${min}" max="${max}" step="${step}"></label>`).join('')}
    <div class="control-section"><h3>Acento</h3><div class="swatches"><button data-color="#c21632" style="--swatch:#c21632" title="Rojo IGRIS" aria-label="Rojo IGRIS"></button><button data-color="#ab2639" style="--swatch:#ab2639" title="Rojo apagado" aria-label="Rojo apagado"></button><button data-color="#db4250" style="--swatch:#db4250" title="Rojo claro" aria-label="Rojo claro"></button><label class="custom-color" title="Color personalizado"><input id="accent-color" type="color" aria-label="Color personalizado"></label></div></div>
    <div class="control-section toggles"><label><span>Arte de fondo</span><input data-setting="background" type="checkbox"></label><label><span>Indicadores</span><input data-setting="showMetrics" type="checkbox"></label></div>
    <div class="draft-actions"><button id="save-draft" class="secondary"><i data-lucide="save"></i>Guardar borrador</button><button id="export-draft" class="secondary"><i data-lucide="download"></i>Exportar ajustes</button><button id="import-draft" class="secondary"><i data-lucide="upload"></i>Importar ajustes</button></div><div id="notice" role="status" aria-live="polite"></div></aside></main><input id="draft-file" type="file" accept="application/json,.json" hidden>`;
createIcons({ icons });
const $ = selector => document.querySelector(selector);
const canvas = $('#panel-preview');

function values() {
  for (const [key, label, min, max, step, unit] of ranges) {
    $(`[data-setting="${key}"]`).value = design[key];
    $(`#value-${key}`).textContent = unit === '%' ? Math.round(design[key] * 100) + '%' : design[key] + ' px';
  }
  for (const key of ['background', 'showMetrics']) $(`[data-setting="${key}"]`).checked = design[key];
  $('#accent-color').value = design.accent;
  for (const button of document.querySelectorAll('[data-color]')) button.classList.toggle('selected', button.dataset.color === design.accent);
}

function draw() {
  for (const button of document.querySelectorAll('[data-view]')) button.classList.toggle('active', button.dataset.view === mode);
  $('#draft-state').textContent = mode === 'original' ? 'Referencia original' : 'Propuesta sin aplicar';
  if (assets) renderPanel(canvas, assets, design, mode, selected);
}

function change(key, value) { design = validateDesign({ ...design, [key]: value }); mode = 'proposal'; values(); draw(); }
function notice(message) { $('#notice').textContent = message; }
for (const input of document.querySelectorAll('[data-setting]')) input.oninput = () =>
  change(input.dataset.setting, input.type === 'checkbox' ? input.checked : Number(input.value));
for (const button of document.querySelectorAll('[data-view]')) button.onclick = () => { mode = button.dataset.view; selected = null; draw(); };
for (const button of document.querySelectorAll('[data-color]')) button.onclick = () => change('accent', button.dataset.color);
$('#accent-color').oninput = event => change('accent', event.target.value);
$('#reset').onclick = () => { design = { ...DEFAULT_DESIGN }; mode = 'proposal'; selected = null; values(); draw(); notice('Propuesta restablecida'); };
$('#clear-selection').onclick = () => { selected = null; $('#selection-name').textContent = 'Panel completo'; draw(); };
canvas.onclick = event => {
  if (mode !== 'proposal') return;
  const bounds = canvas.getBoundingClientRect();
  const point = { x: (event.clientX - bounds.left) / bounds.width * WIDTH, y: (event.clientY - bounds.top) / bounds.height * HEIGHT };
  selected = Object.entries(panelLayout(design)).find(([key, rect]) => point.x >= rect.x && point.x <= rect.x + rect.w && point.y >= rect.y && point.y <= rect.y + rect.h)?.[0] || null;
  $('#selection-name').textContent = { sidebar: 'Navegacion', chat: 'Comunicacion', scene: 'Escena central', metrics: 'Indicadores' }[selected] || 'Panel completo';
  draw();
};

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('#export-image').onclick = () => {
  const previous = selected; selected = null; draw();
  canvas.toBlob(blob => { if (blob) download(blob, `igris-panel-${mode}.png`); selected = previous; draw(); }, 'image/png');
};
function draft() { return { version: 1, scope: 'visual-only', design }; }
$('#save-draft').onclick = () => {
  try { localStorage.setItem(storageKey, JSON.stringify(draft())); notice('Borrador guardado en el estudio'); }
  catch { notice('No se pudo guardar el borrador'); }
};
$('#export-draft').onclick = () => download(new Blob([JSON.stringify(draft(), null, 2)], { type: 'application/json' }), 'igris-panel-diseno.json');
$('#import-draft').onclick = () => $('#draft-file').click();
$('#draft-file').onchange = async event => {
  try {
    const file = event.target.files[0]; if (!file) return;
    if (file.size > 100000) throw new Error('El archivo supera el limite');
    const data = JSON.parse(await file.text());
    if (data.version !== 1 || data.scope !== 'visual-only') throw new Error('No es un borrador del estudio');
    design = validateDesign(data.design); mode = 'proposal'; selected = null; values(); draw(); notice('Borrador importado');
  } catch (error) { notice('No se pudo importar: ' + error.message); }
  event.target.value = '';
};
try {
  const stored = JSON.parse(localStorage.getItem(storageKey) || 'null');
  if (stored?.version === 1 && stored.scope === 'visual-only') design = validateDesign(stored.design);
} catch {}
values(); draw();
await Promise.all([document.fonts.load('600 14px Manrope'), document.fonts.load('600 16px "Barlow Condensed"')]);
await document.fonts.ready;
try {
  assets = await loadPreviewAssets(); draw(); $('#export-image').disabled = false;
  $('#load-status').textContent = 'Render disponible';
} catch (error) { $('#load-status').textContent = error.message; }
window.__panelStudio = { get design() { return { ...design }; }, get mode() { return mode; }, get ready() { return !!assets; }, canvas };