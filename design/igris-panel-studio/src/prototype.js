import './prototype.css';
import '@fontsource/manrope/latin-400.css';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/barlow-condensed/latin-600.css';
import { createIcons, SlidersHorizontal, FolderKanban, GraduationCap, Activity, Plus,
  History, Settings, Settings2, Paperclip, Mic, Volume2, ArrowUp, Square, Copy, Pencil, RotateCcw, X, Network, Download } from 'lucide';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { ConversationState, AGENTS, POWER_LEVELS } from './conversation-state.js';
import { NeuralNetwork } from './neural-network.js';

const icons = { SlidersHorizontal, FolderKanban, GraduationCap, Activity, Plus, History,
  Settings, Settings2, Paperclip, Mic, Volume2, ArrowUp, Square, Copy, Pencil, RotateCcw, X, Network, Download };
const $ = selector => document.querySelector(selector);
let state = new ConversationState();
let files = [];
let editingId = null;
let sessionHistory = [];
try { sessionHistory = JSON.parse(localStorage.getItem('igris-prototype-sessions') || '[]').slice(-10); } catch {}

document.querySelector('#prototype').innerHTML = `
  <header class="proto-header"><div class="proto-brand"><img class="brand-emblem" src="./reference/icon.ico" alt=""><h1>IGRIS <span>OS</span></h1><span class="prototype-badge">PROTOTIPO</span></div><div class="proto-header-right"><span class="mode-indicator">VISTA PREVIA LOCAL</span><a href="./">Estudio visual</a></div></header>
  <main class="proto-layout"><aside class="proto-navigation"><nav><button data-panel="properties"><i data-lucide="sliders-horizontal"></i>PROPIEDADES</button><button data-panel="projects"><i data-lucide="folder-kanban"></i>PROYECTOS</button><button data-panel="academy"><i data-lucide="graduation-cap"></i>ACADEMIA</button><button data-panel="diagnosis"><i data-lucide="activity"></i>DIAGNOSTICO</button></nav><figure class="legacy-portrait"><img src="./reference/portrait.png" alt="Retrato original de IGRIS"><figcaption>IGRIS OS</figcaption></figure><div class="proto-side-status"><b></b>Vista previa · Sin IA conectada</div></aside>
  <section class="proto-center"><div class="network-heading"><h2>RED DE ACTIVIDAD</h2><span id="network-state">REPOSO</span></div><div id="neural-view"></div><div class="network-meta"><span id="network-count">24 nodos de muestra</span><button id="network-settings" class="proto-icon" title="Complejidad de muestra" aria-label="Complejidad de muestra"><i data-lucide="settings-2"></i></button></div><div class="proto-metrics">${['ACTIVIDAD', 'MEMORIA', 'PROCESADO', 'RAZONAR', 'VOZ', 'COMANDOS'].map((name, index) => `<div><div class="metric-ring" id="metric-${index}">${index === 5 ? '0' : '—'}</div><span>${name}</span></div>`).join('')}</div><div class="proto-system-label">Señales de interfaz · Modelo sin conectar</div></section>
  <section class="conversation"><div class="conversation-header"><div><h2>COMUNICACION</h2><span id="session-label">Nueva sesion</span></div><div><button id="new-session" class="proto-icon" title="Nueva conversacion" aria-label="Nueva conversacion"><i data-lucide="plus"></i></button><button id="history-session" class="proto-icon" title="Historial local de muestras" aria-label="Historial local de muestras"><i data-lucide="history"></i></button><button id="conversation-settings" class="proto-icon" title="Opciones del prototipo" aria-label="Opciones del prototipo"><i data-lucide="settings"></i></button></div></div>
  <div id="messages" class="messages" aria-live="polite"><div class="empty-chat"><div class="empty-mark">IGRIS</div><strong>Una nueva conversacion</strong><span>Vista previa local</span></div></div>
  <div id="response-state" class="response-state" hidden><b></b><span>Preparando muestra</span><button id="stop-response" title="Detener muestra" aria-label="Detener muestra"><i data-lucide="square"></i></button></div>
  <div class="composer"><div id="editing-banner" hidden><span>Editando mensaje</span><button id="cancel-edit" title="Cancelar edicion" aria-label="Cancelar edicion"><i data-lucide="x"></i></button></div><div id="attachments" class="attachment-list"></div><textarea id="message-input" rows="3" wrap="soft" placeholder="Escribe tu mensaje..." aria-label="Mensaje para IGRIS" spellcheck="true" lang="es"></textarea><div class="composer-toolbar"><div class="composer-left"><button id="attach-file" class="proto-icon" title="Adjuntar archivos a la muestra" aria-label="Adjuntar archivos"><i data-lucide="paperclip"></i></button><button class="proto-icon" disabled title="Dictado de IGRIS pendiente de conectar" aria-label="Dictado no conectado"><i data-lucide="mic"></i></button><button class="proto-icon" disabled title="Voz de IGRIS pendiente de conectar" aria-label="Voz no conectada"><i data-lucide="volume-2"></i></button></div><button id="send-message" class="send-message" title="Enviar mensaje" aria-label="Enviar mensaje"><i data-lucide="arrow-up"></i></button></div><div class="agent-controls"><label>Agente<select id="agent-choice">${Object.entries(AGENTS).map(([key, agent]) => `<option value="${key}">${agent.label}</option>`).join('')}</select></label><label>Recursos<select id="power-choice">${Object.entries(POWER_LEVELS).map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}</select></label></div></div><footer class="conversation-footer"><span id="selected-agent">Auto · Seleccion por tarea</span><span>Modelo: sin conectar</span></footer></section></main>
  <div id="proto-toast" role="status"></div><input id="attachment-file" type="file" multiple hidden><dialog id="proto-dialog"><div class="proto-dialog-header"><h2 id="dialog-title"></h2><button id="close-dialog" class="proto-icon" aria-label="Cerrar"><i data-lucide="x"></i></button></div><div id="dialog-body"></div></dialog>`;
createIcons({ icons });
const network = new NeuralNetwork($('#neural-view'), state.verifiedCapabilities);
let toastTimer;

function toast(text) { $('#proto-toast').textContent = text; $('#proto-toast').classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#proto-toast').classList.remove('visible'), 3000); }
function updateActivity() {
  network.setActivity(state.activity);
  $('#network-state').textContent = { idle: 'REPOSO', typing: 'ESCRITURA', planning: 'PLANIFICACION DEMO', writing: 'REDACCION DEMO', verifying: 'REVISION DEMO' }[state.activity] || 'REPOSO';
  $('#network-count').textContent = state.verifiedCapabilities + ' nodos de muestra';
  $('#metric-0').textContent = state.pending ? 'DEMO' : '—';
  $('#metric-5').textContent = String(state.messages.filter(message => message.role === 'user').length);
  $('#response-state').hidden = !state.pending;
  $('#send-message').disabled = !!state.pending || !$('#message-input').value.trim();
  $('#agent-choice').disabled = $('#power-choice').disabled = !!state.pending;
}

function renderMessages() {
  const container = $('#messages');
  container.replaceChildren();
  if (!state.messages.length) {
    const empty = document.createElement('div'); empty.className = 'empty-chat';
    empty.innerHTML = '<div class="empty-mark">IGRIS</div><strong>Una nueva conversacion</strong><span>Vista previa local</span>';
    container.append(empty);
  }
  for (const message of state.messages) {
    const item = document.createElement('article'); item.className = 'chat-message ' + message.role; item.dataset.id = message.id;
    const header = document.createElement('div'); header.className = 'message-header';
    const author = document.createElement('strong'); author.textContent = message.role === 'user' ? 'TU' : 'IGRIS';
    const meta = document.createElement('span'); meta.textContent = `${AGENTS[message.agent]?.label || 'Auto'} · ${POWER_LEVELS[message.power] || 'Auto'}${message.preview ? ' · VISTA PREVIA' : ''}`;
    header.append(author, meta);
    const body = document.createElement('div'); body.className = 'message-body';
    if (message.role === 'user') body.textContent = message.text;
    else body.innerHTML = DOMPurify.sanitize(marked.parse(message.text), { FORBID_TAGS: ['img', 'iframe', 'style', 'form'], FORBID_ATTR: ['style'] });
    const actions = document.createElement('div'); actions.className = 'message-actions';
    const copy = document.createElement('button'); copy.title = 'Copiar mensaje'; copy.setAttribute('aria-label', 'Copiar mensaje'); copy.innerHTML = '<i data-lucide="copy"></i>';
    copy.onclick = async () => { try { await navigator.clipboard.writeText(message.text); toast('Mensaje copiado'); } catch { toast('No se pudo acceder al portapapeles'); } };
    actions.append(copy);
    if (message.role === 'user') {
      const edit = document.createElement('button'); edit.title = 'Editar y reenviar'; edit.setAttribute('aria-label', 'Editar y reenviar'); edit.innerHTML = '<i data-lucide="pencil"></i>';
      edit.disabled = !!state.pending;
      edit.onclick = () => { editingId = message.id; $('#message-input').value = message.text; $('#editing-banner').hidden = false; resizeInput(); $('#message-input').focus(); updateActivity(); };
      actions.append(edit);
    } else {
      const retry = document.createElement('button'); retry.title = 'Repetir muestra'; retry.setAttribute('aria-label', 'Repetir muestra'); retry.innerHTML = '<i data-lucide="rotate-ccw"></i>'; retry.disabled = !!state.pending;
      retry.onclick = () => {
        const index = state.messages.indexOf(message);
        const user = state.messages.slice(0, index).reverse().find(item => item.role === 'user');
        if (user) { editingId = user.id; $('#message-input').value = user.text; send(); }
      };
      actions.append(retry);
    }
    item.append(header, body);
    if (message.attachments?.length) {
      const attached = document.createElement('div'); attached.className = 'message-files';
      attached.textContent = message.attachments.map(file => file.name).join(' · '); item.append(attached);
    }
    item.append(actions); container.append(item);
  }
  createIcons({ icons });
  container.scrollTop = container.scrollHeight;
  updateActivity();
}

function resizeInput() {
  const input = $('#message-input');
  input.style.height = 'auto'; input.style.height = Math.min(180, Math.max(94, input.scrollHeight)) + 'px';
}
function renderAttachments() {
  $('#attachments').replaceChildren();
  for (const file of files) {
    const chip = document.createElement('div'); chip.className = 'file-chip';
    const text = document.createElement('span'); text.textContent = file.name;
    const remove = document.createElement('button'); remove.title = 'Quitar adjunto'; remove.setAttribute('aria-label', 'Quitar adjunto'); remove.innerHTML = '<i data-lucide="x"></i>';
    remove.onclick = () => { files = files.filter(item => item !== file); renderAttachments(); };
    chip.append(text, remove); $('#attachments').append(chip);
  }
  createIcons({ icons });
}

const responses = {
  director: 'El encargo debe separar **objetivo, restricciones y criterios de entrega**. No he realizado cambios en su equipo.',
  programmer: 'Propondría empezar por una implementación acotada y una prueba verificable. **No he generado ni ejecutado código** en este intercambio.',
  reviewer: 'Conviene comprobar entradas, errores y casos límite antes de dar el resultado por válido. **No he ejecutado pruebas ni cambiado archivos**.',
  researcher: 'Es necesario contrastar las referencias y sus licencias antes de utilizarlas. **No he consultado fuentes externas** en este intercambio.',
};
function respond(token, text) {
  setTimeout(() => {
    if (state.pending?.id !== token.id) return;
    state.activity = 'writing'; updateActivity();
  }, 220);
  setTimeout(() => {
    if (state.pending?.id !== token.id) return;
    state.activity = 'verifying'; updateActivity();
  }, 600);
  setTimeout(() => {
    const response = /^hola\b/i.test(text.trim()) ? 'Buenas. ¿Qué necesita resolver?' : responses[token.agent];
    if (state.finish(token, response)) renderMessages();
  }, 1100);
}
function send() {
  const input = $('#message-input');
  try {
    const text = input.value;
    const token = editingId ? state.editAndRetry(editingId, text) : state.send(text, files);
    editingId = null; files = []; input.value = ''; $('#editing-banner').hidden = true;
    renderAttachments(); resizeInput(); renderMessages(); respond(token, text);
    $('#session-label').textContent = text.trim().slice(0, 38);
  } catch (error) { toast(error.message); }
}
$('#send-message').onclick = send;
$('#message-input').oninput = () => { resizeInput(); if (!state.pending) state.activity = $('#message-input').value ? 'typing' : 'idle'; updateActivity(); };
$('#message-input').onkeydown = event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); }
};
$('#stop-response').onclick = () => { state.stop(); renderMessages(); toast('Muestra detenida'); };
$('#cancel-edit').onclick = () => { editingId = null; $('#editing-banner').hidden = true; $('#message-input').value = ''; resizeInput(); updateActivity(); };
$('#agent-choice').onchange = event => { state.setAgent(event.target.value); $('#selected-agent').textContent = `${AGENTS[state.agent].label} · ${AGENTS[state.agent].role}`; };
$('#power-choice').onchange = event => { state.setPower(event.target.value); };
$('#attach-file').onclick = () => $('#attachment-file').click();
$('#attachment-file').onchange = event => {
  for (const file of event.target.files) {
    if (files.length >= 5 || file.size > 2 * 1024 * 1024) { toast('Maximo cinco adjuntos de hasta 2 MB'); continue; }
    files.push(file);
  }
  event.target.value = ''; renderAttachments();
};

function dialog(title, content) { $('#dialog-title').textContent = title; $('#dialog-body').replaceChildren(content); $('#proto-dialog').showModal(); }
$('#close-dialog').onclick = () => $('#proto-dialog').close();
function networkSettings() {
  const content = document.createElement('div'); content.className = 'network-options';
  const label = document.createElement('label'); label.textContent = 'Complejidad de muestra';
  const input = document.createElement('input'); input.type = 'range'; input.min = '8'; input.max = '120'; input.step = '4'; input.value = state.verifiedCapabilities;
  const count = document.createElement('output'); count.textContent = state.verifiedCapabilities + ' nodos';
  input.oninput = () => { state.setVerifiedCapabilities(Number(input.value)); network.setComplexity(state.verifiedCapabilities); count.textContent = input.value + ' nodos'; updateActivity(); };
  const layerLabel = document.createElement('label'); layerLabel.textContent = 'Capa visible';
  const layers = document.createElement('select'); layers.setAttribute('aria-label', 'Capa visible');
  layers.add(new Option('Conjunto', 'all'));
  network.referenceLabels.forEach((name, index) => layers.add(new Option(name, String(index))));
  layers.value = network.referenceMode;
  layers.onchange = () => network.setReferenceMode(layers.value);
  content.append(layerLabel, layers, label, input, count); dialog('Red · Muestra visual', content);
}
$('#network-settings').onclick = networkSettings;
$('#conversation-settings').onclick = networkSettings;
for (const button of document.querySelectorAll('[data-panel]')) button.onclick = () => {
  if (button.dataset.panel === 'academy' || button.dataset.panel === 'properties') return networkSettings();
  const content = document.createElement('dl');
  for (const [label, value] of button.dataset.panel === 'diagnosis'
    ? [['Conexion', 'Sin backend'], ['Red', state.verifiedCapabilities + ' nodos de muestra'], ['Conversaciones', sessionHistory.length + 1]]
    : [['Proyecto', 'IGRIS OS'], ['Modo', 'Prototipo de interfaz'], ['Cambios reales', 'Ninguno']]) {
    const term = document.createElement('dt'); term.textContent = label; const description = document.createElement('dd'); description.textContent = value; content.append(term, description);
  }
  dialog(button.dataset.panel === 'diagnosis' ? 'Diagnostico del prototipo' : 'Proyecto actual', content);
};
$('#new-session').onclick = () => {
  state.stop();
  if (state.messages.length) {
    sessionHistory.push({ id: crypto.randomUUID(), title: state.messages[0].text.slice(0, 48), messages: state.messages });
    sessionHistory = sessionHistory.slice(-10);
    try { localStorage.setItem('igris-prototype-sessions', JSON.stringify(sessionHistory)); } catch { toast('No se pudo guardar el historial local'); }
  }
  const agent = state.agent, power = state.power, count = state.verifiedCapabilities;
  state = new ConversationState(); state.setAgent(agent); state.setPower(power); state.setVerifiedCapabilities(count);
  files = []; editingId = null; $('#editing-banner').hidden = true; $('#message-input').value = ''; $('#session-label').textContent = 'Nueva sesion';
  renderAttachments(); resizeInput(); renderMessages();
};
$('#history-session').onclick = () => {
  const content = document.createElement('div'); content.className = 'session-history';
  if (!sessionHistory.length) content.textContent = 'Sin conversaciones guardadas';
  for (const session of [...sessionHistory].reverse()) {
    const button = document.createElement('button'); button.textContent = session.title;
    button.onclick = () => { state.stop(); state.messages = structuredClone(session.messages); $('#session-label').textContent = session.title; $('#proto-dialog').close(); renderMessages(); };
    content.append(button);
  }
  dialog('Historial local', content);
};
window.__igrisPrototype = { get state() { return state; }, network };
renderMessages(); resizeInput();
window.addEventListener('beforeunload', () => network.destroy());