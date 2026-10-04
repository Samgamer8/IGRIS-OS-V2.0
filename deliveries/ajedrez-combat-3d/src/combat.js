const TYPES = {
  p: { style: 'dragon', duration: 2200 },
  n: { style: 'duel', duration: 1950 },
  b: { style: 'staff', duration: 2300 },
  r: { style: 'shield', duration: 2150 },
  q: { style: 'royal', duration: 2100 },
  k: { style: 'command', duration: 2350 },
};

const clamp = value => Math.min(1, Math.max(0, value));
const smooth = value => value * value * (3 - 2 * value);

export function combatProfile(type) {
  if (!Object.hasOwn(TYPES, type)) throw new Error('Tipo de combate invalido');
  return { ...TYPES[type] };
}

export function combatFrame(progress) {
  progress = clamp(progress);
  const approach = smooth(clamp(progress / 0.3));
  const preparation = smooth(clamp((progress - 0.3) / 0.2));
  const action = Math.sin(clamp((progress - 0.48) / 0.26) * Math.PI);
  const reaction = smooth(clamp((progress - 0.63) / 0.2));
  const finish = smooth(clamp((progress - 0.84) / 0.16));
  const phase = progress < 0.3 ? 'approach' : progress < 0.48 ? 'prepare' : progress < 0.74 ? 'action' : progress < 0.84 ? 'reaction' : 'finish';
  return { phase, approach, preparation, action, reaction, finish,
    actorTravel: 0.73 * approach + 0.27 * finish,
    actorArm: -1.05 * preparation * (1 - reaction) + 1.25 * action,
    victimTilt: reaction * Math.PI * 0.48,
    victimScale: 1 - smooth(clamp((progress - 0.78) / 0.22)),
    effect: action, walk: Math.sin(progress / 0.3 * Math.PI * 4) * (progress < 0.3 ? 0.22 : 0) };
}