import { createElement, Volume2, Mic, Plus, RotateCcw, Settings2, ArrowRight,
  SlidersHorizontal, FolderKanban, GraduationCap, Activity } from 'lucide';
import { WIDTH, HEIGHT, panelLayout } from './layout.js';

const iconNodes = { volume: Volume2, mic: Mic, plus: Plus, reset: RotateCcw,
  settings: Settings2, send: ArrowRight, properties: SlidersHorizontal,
  projects: FolderKanban, academy: GraduationCap, diagnosis: Activity };

function image(source) {
  return new Promise((resolve, reject) => {
    const asset = new Image();
    asset.onload = () => resolve(asset);
    asset.onerror = () => reject(new Error('No se pudo cargar un recurso visual'));
    asset.src = source;
  });
}

export async function loadPreviewAssets() {
  const [original, art] = await Promise.all([
    image(new URL('./reference/original.png', document.baseURI).href),
    image(new URL('./reference/art.png', document.baseURI).href),
  ]);
  const icons = {};
  await Promise.all(Object.entries(iconNodes).map(async ([name, node]) => {
    const svg = createElement(node, { width: 24, height: 24, stroke: '#e9dbe0', 'stroke-width': 1.7 });
    icons[name] = await image('data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg)));
  }));
  return { original, art, icons };
}

function rounded(context, rect, radius, fill, stroke) {
  context.beginPath();
  context.roundRect(rect.x, rect.y, rect.w, rect.h, radius);
  context.fillStyle = fill;
  context.fill();
  if (stroke) { context.strokeStyle = stroke; context.lineWidth = 1; context.stroke(); }
}

function text(context, value, x, y, size = 14, color = '#ece4e6', condensed = false) {
  context.font = `600 ${size}px ${condensed ? 'Barlow Condensed' : 'Manrope'}`;
  context.fillStyle = color;
  context.textAlign = 'left';
  context.textBaseline = 'middle';
  context.fillText(value, x, y);
}

function contain(context, asset, source, target) {
  const factor = Math.min(target.w / source.w, target.h / source.h);
  const width = source.w * factor;
  const height = source.h * factor;
  context.drawImage(asset, source.x, source.y, source.w, source.h,
    target.x + (target.w - width) / 2, target.y + (target.h - height) / 2, width, height);
}

function drawDials(context, rect, radius, accent) {
  rounded(context, rect, radius, '#07080edb', accent);
  const colors = [accent, '#e1b36b', accent, '#5bba89', '#c2cad8', '#6b768a'];
  const names = ['ACTIVIDAD', 'MEMORIA', 'PROCESADO', 'RAZONAR', 'VOZ', 'COMANDOS'];
  const values = [8, 32, 8, 0, 0, 0];
  const slot = (rect.w - 24) / 6;
  const dialRadius = Math.min(33, slot / 2 - 8);
  for (let index = 0; index < 6; index++) {
    const centerX = rect.x + 12 + slot * (index + 0.5);
    const centerY = rect.y + rect.h / 2 - 10;
    const face = context.createRadialGradient(centerX, centerY - 8, 3, centerX, centerY, dialRadius);
    face.addColorStop(0, '#343943'); face.addColorStop(1, '#080c13');
    context.beginPath(); context.arc(centerX, centerY, dialRadius, 0, Math.PI * 2);
    context.fillStyle = face; context.fill(); context.strokeStyle = '#68717f'; context.lineWidth = 2; context.stroke();
    for (let tick = 0; tick < 36; tick++) {
      const angle = tick / 36 * Math.PI * 2;
      context.beginPath();
      context.moveTo(centerX + Math.sin(angle) * (dialRadius - 8), centerY + Math.cos(angle) * (dialRadius - 8));
      context.lineTo(centerX + Math.sin(angle) * (dialRadius - 13), centerY + Math.cos(angle) * (dialRadius - 13));
      context.strokeStyle = colors[index]; context.globalAlpha = tick / 36 * 100 <= values[index] ? 0.9 : 0.25;
      context.lineWidth = 1; context.stroke();
    }
    context.globalAlpha = 1;
    context.font = '600 20px Manrope'; context.fillStyle = '#f0edf1'; context.textAlign = 'center';
    context.fillText(index === 5 ? String(values[index]) : values[index] + '%', centerX, centerY + 1);
    context.font = '600 10px Manrope'; context.fillStyle = '#b8b9c5';
    context.fillText(names[index], centerX, rect.y + rect.h - 21);
  }
  context.textAlign = 'left';
}

export function renderPanel(canvas, assets, design, mode = 'original', selected = null) {
  const context = canvas.getContext('2d');
  context.clearRect(0, 0, WIDTH, HEIGHT);
  if (mode === 'original') {
    context.drawImage(assets.original, 0, 0, WIDTH, HEIGHT);
    return;
  }
  const layout = panelLayout(design);
  if (design.background) context.drawImage(assets.art, 0, 0, WIDTH, HEIGHT);
  else { context.fillStyle = '#08080c'; context.fillRect(0, 0, WIDTH, HEIGHT); }
  context.fillStyle = `rgba(3,4,8,${design.contrast})`;
  context.fillRect(0, 0, WIDTH, HEIGHT);
  const sidebar = layout.sidebar;
  context.fillStyle = '#06080cf2'; context.fillRect(0, 0, design.sidebar, HEIGHT);
  contain(context, assets.original, { x: 0, y: 0, w: 246, h: 104 },
    { x: sidebar.x, y: 9, w: sidebar.w, h: 90 });
  const navigation = [['properties', 'PROPIEDADES'], ['projects', 'PROYECTOS'], ['academy', 'ACADEMIA'], ['diagnosis', 'DIAGNOSTICO']];
  for (let index = 0; index < navigation.length; index++) {
    const button = { x: sidebar.x + 3, y: 120 + index * 72, w: sidebar.w - 6, h: 58 };
    rounded(context, button, design.radius, '#080a10', design.accent);
    context.drawImage(assets.icons[navigation[index][0]], button.x + 16, button.y + 19, 19, 19);
    text(context, navigation[index][1], button.x + 45, button.y + 29, 16, '#e8e5ee', true);
  }
  contain(context, assets.original, { x: 22, y: 477, w: 195, h: 280 },
    { x: sidebar.x + 14, y: 458, w: sidebar.w - 28, h: 289 });
  text(context, 'IGRIS OS', sidebar.x + 20, 752, 14, '#c9ccd3', true);
  context.fillStyle = '#a57359'; context.beginPath(); context.arc(sidebar.x + 20, 781, 3, 0, Math.PI * 2); context.fill();
  text(context, 'Vista de diseno', sidebar.x + 29, 781, 11, '#b7aaa1');
  const area = layout.scene;
  const scale = design.sceneScale;
  contain(context, assets.original, { x: 250, y: 85, w: 663, h: 518 },
    { x: area.x + area.w * (1 - scale) / 2, y: area.y + area.h * (1 - scale) / 2,
      w: area.w * scale, h: area.h * scale });
  text(context, 'GALAXIA', area.x + area.w - 80, 42, 14, '#e1c37e', true);
  if (design.showMetrics) drawDials(context, layout.metrics, design.radius, design.accent);
  text(context, 'IA: vista de diseno', layout.scene.x, 783, 10, '#cbb18c');
  const chat = layout.chat;
  rounded(context, chat, design.radius, '#06080ef5', design.accent);
  text(context, 'COMUNICACION', chat.x + 22, chat.y + 20, 14, '#e6c378');
  text(context, '10:27:47', chat.x + chat.w - 79, chat.y + 20, 11, '#c5c7cf');
  const toolbar = ['volume', 'mic', 'plus', 'reset', 'settings'];
  for (let index = 0; index < toolbar.length; index++) {
    const button = { x: chat.x + chat.w - 200 + index * 36, y: chat.y + 33, w: 30, h: 30 };
    rounded(context, button, Math.min(design.radius, 6), '#2a0e18', '#692231');
    context.drawImage(assets.icons[toolbar[index]], button.x + 7, button.y + 7, 16, 16);
  }
  const dialogue = { x: chat.x + 26, y: chat.y + 72, w: chat.w - 52, h: chat.h - 206 };
  rounded(context, dialogue, design.radius, '#07090f', '#641329');
  text(context, '[IGRIS] Interfaz abierta.', dialogue.x + 20, dialogue.y + 33, 13, '#d8d8df');
  text(context, 'La disponibilidad de la IA se muestra', dialogue.x + 20, dialogue.y + 57, 12, '#b5b7c2');
  text(context, 'en la barra de estado.', dialogue.x + 20, dialogue.y + 77, 12, '#b5b7c2');
  text(context, '[SISTEMA] Escribe una orden.', dialogue.x + 20, dialogue.y + 118, 13, '#d8d8df');
  const input = { x: chat.x + 20, y: chat.y + chat.h - 95, w: chat.w - 98, h: 63 };
  rounded(context, input, design.radius, '#12141d', design.accent);
  text(context, 'Escribe una orden...', input.x + 20, input.y + 31, 14, '#84838e');
  const send = { x: chat.x + chat.w - 67, y: input.y, w: 43, h: input.h };
  rounded(context, send, Math.min(design.radius, 8), '#650d23', design.accent);
  context.drawImage(assets.icons.send, send.x + 10, send.y + 20, 24, 24);
  if (selected && layout[selected]) {
    const rect = layout[selected];
    context.save(); context.setLineDash([6, 5]); context.strokeStyle = '#f0d397'; context.lineWidth = 2;
    context.strokeRect(rect.x - 3, rect.y - 3, rect.w + 6, rect.h + 6); context.restore();
  }
}