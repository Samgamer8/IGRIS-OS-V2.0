import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneCharacter } from 'three/addons/utils/SkeletonUtils.js';
import { createIcons, RotateCcw, Play, Pause, Camera, Swords, Shield, Footprints, Crown } from 'lucide';
import '@fontsource/manrope/latin-400.css';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/barlow-condensed/latin-600.css';
import { createFantasyPiece, poseFantasyPiece } from './pieces.js';
import { applyStudioLook } from './studio-look.js';
import { combatFrame } from './combat.js';
import './studio.css';

const labels = { p: 'Peon dragon', n: 'Caballero', b: 'Alfil', r: 'Torre guerrera', q: 'Dama', k: 'Rey' };
document.querySelector('#studio').innerHTML = `
  <header><div class="studio-brand"><i data-lucide="crown"></i><div><h1>ESTUDIO DE PIEZAS</h1><span>IGRIS · AJEDREZ COMBAT</span></div></div><span class="review-state">EN REVISION</span></header>
  <main><section class="sample-stage"><div id="sample-viewport"></div><div class="sample-title"><span id="faction-label">ORDEN DE PLATA</span><h2 id="piece-title">Torre guerrera</h2></div><div class="stage-tools"><button id="home-view" title="Restablecer camara" aria-label="Restablecer camara"><i data-lucide="rotate-ccw"></i></button><button id="front-view" title="Vista frontal" aria-label="Vista frontal"><i data-lucide="camera"></i></button></div></section>
  <aside><h3>Figura</h3><div class="piece-picker">${Object.entries(labels).map(([key, label]) => `<button data-piece="${key}" class="${key === 'r' ? 'selected' : ''}">${label}</button>`).join('')}</div>
  <h3>Bando</h3><div class="segmented"><button data-color="w" class="selected">Blancas</button><button data-color="b">Negras</button></div>
  <h3>Muestra de movimiento</h3><div class="motion-picker"><button data-motion="idle" class="selected"><i data-lucide="pause"></i>Reposo</button><button data-motion="walk"><i data-lucide="footprints"></i>Marcha</button><button data-motion="action"><i data-lucide="swords"></i>Accion</button><button data-motion="guard"><i data-lucide="shield"></i>Defensa</button><button data-motion="reaction"><i data-lucide="rotate-ccw"></i>Reaccion</button></div>
  <div class="playback"><button id="play-toggle" title="Pausar muestra" aria-label="Pausar muestra"><i data-lucide="pause"></i></button><label>Velocidad<input id="speed" type="range" min="0.25" max="1.5" step="0.25" value="1"></label><output id="speed-value">1x</output></div>
  <h3>Iluminacion</h3><div class="segmented"><button data-light="studio" class="selected">Estudio</button><button data-light="arena">Arena</button></div>
  <div class="sample-details"><div><span>MODELO</span><strong id="model-label">Torre original</strong></div><div><span>VERSION</span><strong id="version-label">Modelo SKP · Sin rig validado</strong></div></div>
  </aside></main>`;
const icons = { RotateCcw, Play, Pause, Camera, Swords, Shield, Footprints, Crown };
const $ = selector => document.querySelector(selector);
createIcons({ icons });

const viewport = $('#sample-viewport');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x171a1b);
scene.fog = new THREE.Fog(0x171a1b, 9, 22);
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 40);
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.domElement.setAttribute('aria-label', 'Muestra 3D de figura');
viewport.append(renderer.domElement);
const generator = new THREE.PMREMGenerator(renderer);
const environment = generator.fromScene(new RoomEnvironment(), 0.05);
scene.environment = environment.texture;
scene.environmentIntensity = 0.85;
generator.dispose();
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.82, 0);
controls.enableDamping = true;
controls.enablePan = false;
controls.minDistance = 2.4;
controls.maxDistance = 8;
controls.minPolarAngle = 0.25;
controls.maxPolarAngle = Math.PI / 2;
camera.position.set(2.65, 1.9, 3.75);
controls.update();
const floor = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.MeshStandardMaterial({ color: 0x242729, roughness: 0.95 }));
floor.rotation.x = -Math.PI / 2;
floor.position.y = 0.07;
floor.receiveShadow = true;
scene.add(floor);
scene.add(new THREE.HemisphereLight(0xe6e9ef, 0x272322, 1.4));
const key = new THREE.DirectionalLight(0xffe4c9, 3.5);
key.position.set(-3, 5, 4);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
Object.assign(key.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 0.1, far: 20 });
key.shadow.normalBias = 0.022;
scene.add(key);
const rim = new THREE.DirectionalLight(0xbad4e3, 2.1);
rim.position.set(3, 3, -4);
scene.add(rim);
let piece;
let type = 'r';
let color = 'w';
let motion = 'idle';
let playing = true;
let clock = 0;
let previous = performance.now();
let loadRevision = 0;
const importedModels = new Map();
let mixer;
let clipActions = new Map();
const motionClips = { idle: 'Idle', walk: 'Walk', action: 'Attack', guard: 'Guard', reaction: 'Reaction' };
const loader = new GLTFLoader();

async function choosePiece() {
  const current = ++loadRevision;
  if (piece) {
    mixer?.stopAllAction();
    mixer?.uncacheRoot(piece);
    mixer = null;
    clipActions.clear();
    scene.remove(piece);
    const materials = new Set();
    piece.traverse(object => { if (object.isMesh) materials.add(object.material); });
    for (const surface of materials) surface.dispose();
    piece = null;
  }
  const original = type === 'r';
  const bishop = type === 'b';
  const dragon = type === 'p';
  const imported = original || bishop || dragon;
  const dragonVariant = color === 'w' ? 'red' : 'black';
  const assetKey = original ? 'tower' : dragon ? `dragon-${dragonVariant}` : `bishop-${color}`;
  const assetPath = original ? './models/real-tower-rig-01/torre_articulada.glb'
    : dragon ? `./models/real-dragon-rig-01/dragon_${dragonVariant}.glb`
      : `./models/bishop-proposal-02/alfil_${color === 'w' ? 'blancas' : 'negras'}.glb`;
  $('#piece-title').textContent = imported ? 'Cargando modelo Blender' : labels[type];
  try {
    if (imported) {
      if (!importedModels.has(assetKey)) importedModels.set(assetKey,
        loader.loadAsync(new URL(assetPath, document.baseURI).href));
      const model = await importedModels.get(assetKey);
      if (current !== loadRevision) return;
      piece = cloneCharacter(model.scene);
      const materials = new Map();
      piece.traverse(object => {
        if (!object.isMesh) return;
        object.castShadow = object.receiveShadow = true;
        if (!materials.has(object.material.uuid)) materials.set(object.material.uuid, object.material.clone());
        object.material = materials.get(object.material.uuid);
      });
      piece.userData.design = original ? 'original-heavy-knight' : dragon ? `original-dragon-${dragonVariant}` : `bishop-proposal-${color}`;
      piece.userData.source = original ? 'Malla y texturas originales importadas desde SKP con Blender'
        : dragon ? 'Malla y texturas del GLB Red Dragon aportado por el usuario'
          : 'Propuesta derivada con tunica capucha y baculo nuevos en Blender';
      piece.userData.rigged = model.animations.length > 0;
      piece.userData.motionStatus = 'Pendiente de aprobacion visual';
      piece.position.y = 0.09;
      mixer = piece.userData.rigged ? new THREE.AnimationMixer(piece) : null;
      clipActions = new Map(model.animations.map(clip => [clip.name, mixer.clipAction(clip)]));
      motion = 'idle';
      clipActions.get('Idle')?.play();
      selectButtons('data-motion', motion);
    } else {
      piece = applyStudioLook(createFantasyPiece(type, color), color);
    }
  } catch (error) {
    importedModels.delete(assetKey);
    $('#piece-title').textContent = 'Error al cargar el modelo';
    $('#version-label').textContent = error.message;
    return;
  }
  piece.rotation.y = 0;
  scene.add(piece);
  clock = 0;
  $('#piece-title').textContent = original ? 'Torre original · Heavy Knight' : dragon
    ? `Dragon ${dragonVariant === 'red' ? 'rojo' : 'negro'} · Modelo real` : bishop ? 'Alfil · Propuesta Blender' : labels[type];
  $('#model-label').textContent = original ? 'Geometria y texturas del SKP' : bishop
    ? `Alfil ${color === 'w' ? 'blanco' : 'negro'} · Diseno derivado` : dragon
      ? 'Geometria y texturas del GLB aportado' : `${color === 'w' ? 'Blancas' : 'Negras'} · ${labels[type]}`;
  $('#version-label').textContent = original ? 'Rig de muestra · Movimientos por aprobar'
    : dragon ? 'Rig experimental · Movimientos por aprobar · Pose amplia'
      : bishop ? 'Revision 02 · Aspecto por aprobar · Sin rig' : 'Reconstruccion provisional · No aprobada';
  $('#faction-label').textContent = original ? 'MODELO IMPORTADO CON BLENDER' : bishop ? 'PROPUESTA EN BLENDER'
    : dragon ? 'RED DRAGON · RECURSO APORTADO' : color === 'w' ? 'ORDEN DE PLATA' : 'LEGION DE ZAFIRO';
  for (const button of document.querySelectorAll('[data-motion]')) button.disabled = imported
    && button.dataset.motion !== 'idle' && !clipActions.has(motionClips[button.dataset.motion]);
  for (const button of document.querySelectorAll('[data-color]')) button.disabled = original;
  fitSampleCamera();
}

function fitSampleCamera() {
  if (!piece) return;
  piece.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(piece);
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const direction = camera.position.clone().sub(controls.target).normalize();
  controls.target.copy(center);
  controls.maxDistance = Math.max(8, size.length() * 5);
  let distance = Math.max(controls.minDistance, size.y * 1.8);
  for (let attempt = 0; attempt < 40; attempt++) {
    camera.position.copy(center).addScaledVector(direction, distance);
    camera.lookAt(center);
    camera.updateMatrixWorld();
    const fits = [bounds.min.x, bounds.max.x].every(x =>
      [bounds.min.y, bounds.max.y].every(y => [bounds.min.z, bounds.max.z].every(z => {
        const point = new THREE.Vector3(x, y, z).project(camera);
        return Math.abs(point.x) < 0.8 && Math.abs(point.y) < 0.77;
      })));
    if (fits) break;
    distance *= 1.08;
  }
  controls.update();
}

function selectButtons(attribute, value) {
  for (const button of document.querySelectorAll(`[${attribute}]`)) button.classList.toggle('selected', button.getAttribute(attribute) === value);
}
for (const button of document.querySelectorAll('[data-piece]')) button.onclick = () => { type = button.dataset.piece; selectButtons('data-piece', type); choosePiece(); };
for (const button of document.querySelectorAll('[data-color]')) button.onclick = () => { color = button.dataset.color; selectButtons('data-color', color); choosePiece(); };
for (const button of document.querySelectorAll('[data-motion]')) button.onclick = () => {
  motion = button.dataset.motion;
  clock = 0;
  if (mixer) {
    mixer.stopAllAction();
    clipActions.get(motionClips[motion])?.reset().play();
  }
  selectButtons('data-motion', motion);
};
for (const button of document.querySelectorAll('[data-light]')) button.onclick = () => {
  const arena = button.dataset.light === 'arena';
  selectButtons('data-light', button.dataset.light);
  key.intensity = arena ? 1.9 : 3.5;
  rim.intensity = arena ? 2.8 : 2.1;
  scene.environmentIntensity = arena ? 0.45 : 0.85;
};
$('#play-toggle').onclick = () => {
  playing = !playing;
  $('#play-toggle').innerHTML = `<i data-lucide="${playing ? 'pause' : 'play'}"></i>`;
  $('#play-toggle').setAttribute('aria-label', playing ? 'Pausar muestra' : 'Reproducir muestra');
  createIcons({ icons });
};
$('#speed').oninput = event => { $('#speed-value').textContent = event.target.value + 'x'; };
$('#home-view').onclick = () => { camera.position.set(2.65, 1.9, 3.75); controls.target.set(0, 0.82, 0); fitSampleCamera(); };
$('#front-view').onclick = () => { camera.position.set(0, 1.2, 4.5); controls.target.set(0, 0.82, 0); fitSampleCamera(); };
const resize = () => {
  camera.aspect = viewport.clientWidth / Math.max(1, viewport.clientHeight);
  camera.updateProjectionMatrix();
  renderer.setSize(viewport.clientWidth, viewport.clientHeight);
  fitSampleCamera();
};
new ResizeObserver(resize).observe(viewport);
choosePiece(); resize();
renderer.setAnimationLoop(now => {
  const elapsed = Math.min(0.1, (now - previous) / 1000);
  previous = now;
  if (!piece) { controls.update(); renderer.render(scene, camera); return; }
  if (playing) clock += elapsed * Number($('#speed').value);
  if (mixer) {
    if (playing) mixer.update(elapsed * Number($('#speed').value));
    controls.update();
    renderer.render(scene, camera);
    return;
  }
  const cycle = clock % 2.6 / 2.6;
  const frame = combatFrame(cycle);
  piece.position.set(0, 0.09, 0);
  piece.rotation.set(0, 0, 0);
  poseFantasyPiece(piece);
  if (motion === 'walk') {
    poseFantasyPiece(piece, { walk: Math.sin(clock * 5) * 0.28, wings: Math.sin(clock * 5) * 0.2 });
    piece.position.y += Math.abs(Math.sin(clock * 5)) * 0.012;
  } else if (motion === 'action') {
    poseFantasyPiece(piece, { attack: frame.actorArm, guard: -frame.preparation * (1 - frame.reaction), wings: Math.sin(clock * 7) * 0.3 });
    piece.rotation.x = frame.action * 0.12;
  } else if (motion === 'guard') {
    poseFantasyPiece(piece, { guard: -0.8, attack: -0.18, wings: 0.2 });
  } else if (motion === 'reaction') {
    poseFantasyPiece(piece, { guard: -0.3, attack: 0.2 });
    piece.rotation.x = -frame.reaction * 0.38 * (1 - frame.finish);
  }
  controls.update();
  renderer.render(scene, camera);
});
window.__studio = { get piece() { return piece; }, scene, camera, renderer, get motion() { return motion; },
  get clock() { return clock; }, get clips() { return [...clipActions.keys()]; }, get mixer() { return mixer; } };