export const WIDTH = 1440;
export const HEIGHT = 810;
export const DEFAULT_DESIGN = Object.freeze({ sidebar: 248, chat: 450, gap: 26,
  metrics: 126, sceneScale: 0.94, radius: 10, accent: '#c21632', contrast: 0.68,
  background: true, showMetrics: true });

const limits = { sidebar: [208, 310], chat: [360, 560], gap: [12, 44], metrics: [100, 160],
  sceneScale: [0.65, 1.05], radius: [0, 20], contrast: [0.25, 0.95] };

export function validateDesign(value) {
  if (!value || typeof value !== 'object') throw new Error('Diseno invalido');
  const result = { ...DEFAULT_DESIGN };
  for (const [key, [minimum, maximum]] of Object.entries(limits)) {
    if (value[key] !== undefined) {
      if (!Number.isFinite(value[key])) throw new Error('Valor no valido: ' + key);
      result[key] = Math.min(maximum, Math.max(minimum, value[key]));
    }
  }
  if (value.accent !== undefined) {
    if (!/^#[0-9a-f]{6}$/i.test(value.accent)) throw new Error('Color invalido');
    result.accent = value.accent;
  }
  for (const key of ['background', 'showMetrics']) if (value[key] !== undefined) {
    if (typeof value[key] !== 'boolean') throw new Error('Opcion invalida: ' + key);
    result[key] = value[key];
  }
  return result;
}

export function panelLayout(design) {
  const settings = validateDesign(design);
  const chat = { x: WIDTH - settings.chat - 22, y: 42, w: settings.chat, h: HEIGHT - 62 };
  const sidebar = { x: 8, y: 10, w: settings.sidebar - 16, h: HEIGHT - 26 };
  const centerX = settings.sidebar + 18;
  const centerWidth = chat.x - settings.gap - centerX;
  const metrics = { x: centerX, y: HEIGHT - settings.metrics - 42, w: centerWidth, h: settings.metrics };
  const scene = { x: centerX, y: 64, w: centerWidth,
    h: (settings.showMetrics ? metrics.y - settings.gap : HEIGHT - 42) - 64 };
  return { sidebar, chat, scene, metrics };
}