export const AGENTS = Object.freeze({
  auto: { label: 'Auto', role: 'Seleccion por tarea' },
  director: { label: 'Director', role: 'Planificacion y coordinacion' },
  programmer: { label: 'Programador', role: 'Codigo y construccion' },
  reviewer: { label: 'Revisor', role: 'Riesgos y comprobaciones' },
  researcher: { label: 'Investigador', role: 'Analisis de referencias' },
});
export const POWER_LEVELS = Object.freeze({ auto: 'Auto', light: 'Ligero', balanced: 'Equilibrado', advanced: 'Avanzado' });

export function resolveAgent(text, choice = 'auto') {
  if (!Object.hasOwn(AGENTS, choice)) throw new Error('Agente no valido');
  if (choice !== 'auto') return choice;
  const normalized = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  if (/revisa|audita|riesgo|seguridad|comprueba|pruebas/.test(normalized)) return 'reviewer';
  if (/investiga|compara|referencias|documentacion/.test(normalized)) return 'researcher';
  if (/codigo|programa|implementa|funcion|pagina|script|error/.test(normalized)) return 'programmer';
  return 'director';
}

export class ConversationState {
  constructor() {
    this.messages = [];
    this.agent = 'auto';
    this.power = 'auto';
    this.activity = 'idle';
    this.verifiedCapabilities = 24;
    this.pending = null;
  }
  setAgent(agent) { if (!Object.hasOwn(AGENTS, agent)) throw new Error('Agente no valido'); this.agent = agent; }
  setPower(power) { if (!Object.hasOwn(POWER_LEVELS, power)) throw new Error('Potencia no valida'); this.power = power; }
  send(text, attachments = []) {
    if (this.pending) throw new Error('Hay una respuesta en curso');
    if (!text.trim()) throw new Error('Escribe un mensaje');
    const agent = resolveAgent(text, this.agent);
    const message = { id: crypto.randomUUID(), role: 'user', text, agent, power: this.power,
      attachments: attachments.map(file => ({ name: file.name, size: file.size })), time: Date.now() };
    this.messages.push(message);
    this.pending = { id: crypto.randomUUID(), agent, power: this.power, userId: message.id };
    this.activity = 'planning';
    return this.pending;
  }
  finish(token, text) {
    if (!this.pending || this.pending.id !== token.id) return false;
    this.messages.push({ id: crypto.randomUUID(), role: 'assistant', text,
      agent: token.agent, power: token.power, preview: true, time: Date.now() });
    this.pending = null;
    this.activity = 'idle';
    return true;
  }
  stop() { this.pending = null; this.activity = 'idle'; }
  editAndRetry(id, text) {
    if (this.pending) throw new Error('Deten la respuesta antes de editar');
    const index = this.messages.findIndex(message => message.id === id && message.role === 'user');
    if (index < 0) throw new Error('Mensaje no editable');
    const attachments = this.messages[index].attachments;
    this.messages.splice(index);
    return this.send(text, attachments);
  }
  setVerifiedCapabilities(count) {
    if (!Number.isInteger(count) || count < 0 || count > 200) throw new Error('Numero de capacidades no valido');
    this.verifiedCapabilities = count;
  }
}