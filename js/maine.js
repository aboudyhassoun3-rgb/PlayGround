import * as THREE from 'three';

/* =====================================================================
   🏰 Maine Crafts للبنات — عالم ماريا 💖 — نسخة ماين كرافت الأصلية ⛏️
   تكسير + تعمير (Voxel) + دخول البيوت من الباب + شخصية جميلة + حيوانات
   جوال/تابلت/كمبيوتر • أونلاين • حفظ تلقائي
   ===================================================================== */

const $ = (id) => document.getElementById(id);
const SAVE_KEY = 'maineCraftsMaria_v2';

// ---------------- STATE ----------------
let playerName = localStorage.getItem('maineName') || 'Maria';
$('player-name').value = playerName;
$('player-name').addEventListener('input', e => { $('start-name-preview').textContent = e.target.value.trim() || 'Maria'; });
$('start-name-preview').textContent = playerName;

const S = {
  name: playerName, coins: 120, hearts: 10, sweets: 1, xp: 0, level: 1, day: 1, dayTime: 0.35,
  inv: { strawberry: 3, blueberry: 2, milk: 2, choco: 1, sugar: 2, wheat: 2, carrot: 2, apple: 1 },
  blocks: { grass: 64, dirt: 32, stone: 16, wood: 16, leaves: 16, planks: 32, pink: 64, glass: 16, brick: 16, sand: 16, white: 32, gold: 8 },
  dress: { dress: 0, hair: 3, hairColor: '#6b3a1f', accessory: 'crown' },
  pets: [], voxels: [], dug: [], brokenSys: [], furniture: [],
  tool: 'build', selBlock: 'pink', selFurn: 'bed', delMode: false,
  music: true, night: false, view: 'third',
};
try { const raw = localStorage.getItem(SAVE_KEY); if (raw) Object.assign(S, JSON.parse(raw)); } catch {}
S.tool = 'build'; S.delMode = false; S.view = 'third';
function save() {
  S.name = playerName;
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify({
      name: S.name, coins: S.coins, hearts: S.hearts, sweets: S.sweets, xp: S.xp, level: S.level,
      day: S.day, inv: S.inv, blocks: S.blocks, dress: S.dress, pets: S.pets,
      voxels: S.voxels.slice(-300), dug: S.dug, brokenSys: S.brokenSys, furniture: S.furniture,
    }));
    localStorage.setItem('maineName', playerName);
  } catch {}
}
setInterval(save, 8000);

// ---------------- AUDIO ----------------
let AC = null;
function beep(freq = 600, dur = 0.15, type = 'sine', vol = 0.15) {
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    if (AC.state === 'suspended') AC.resume();
    const o = AC.createOscillator(), g = AC.createGain();
    o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(vol, AC.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, AC.currentTime + dur);
    o.connect(g); g.connect(AC.destination); o.start(); o.stop(AC.currentTime + dur);
  } catch {}
}
const sndPlace = () => beep(520, .12, 'square', .08);
const sndBreak = () => { beep(180, .12, 'sawtooth', .1); setTimeout(() => beep(120, .15, 'sawtooth', .08), 90); };
const sndYum = () => { beep(700, .12); setTimeout(() => beep(900, .15), 110); setTimeout(() => beep(1200, .2), 230); };
const sndCoin = () => { beep(1200, .08, 'square', .07); setTimeout(() => beep(1600, .12, 'square', .07), 80); };
const sndPop = () => beep(400, .1, 'sine', .12);
const sndDoor = () => { beep(300, .1, 'triangle', .1); setTimeout(() => beep(500, .12, 'triangle', .08), 100); };
const sndMoo = () => { beep(140, .35, 'sawtooth', .09); setTimeout(() => beep(110, .4, 'sawtooth', .08), 200); };
let musicTimer = null;
function musicLoop() {
  if (musicTimer) clearInterval(musicTimer);
  if (!S.music) return;
  const notes = [523, 587, 659, 784, 880, 784, 659, 587];
  let i = 0;
  musicTimer = setInterval(() => { if (S.music) beep(notes[i++ % notes.length], .3, 'triangle', .03); }, 480);
}
musicLoop();

// ---------------- UI ----------------
function toast(msg) {
  const d = document.createElement('div'); d.className = 'toast'; d.textContent = msg;
  $('toast-wrap').appendChild(d); setTimeout(() => d.remove(), 2600);
}
function flyHearts(n = 6) {
  for (let i = 0; i < n; i++) {
    const s = document.createElement('div'); s.className = 'fly';
    s.textContent = ['💖', '✨', '🌸', '💕', '⭐'][Math.floor(Math.random() * 5)];
    s.style.left = (30 + Math.random() * 40) + 'vw'; s.style.top = (40 + Math.random() * 20) + 'vh';
    $('hearts-fly').appendChild(s); setTimeout(() => s.remove(), 1500);
  }
}
function updateHUD() {
  $('hud-name').textContent = (S.name || 'Maria') + ' 💖';
  $('hud-level').textContent = `Lv ${S.level} • ⭐ ${S.xp}`;
  $('coins').textContent = S.coins; $('hearts').textContent = S.hearts; $('sweets').textContent = S.sweets;
  $('clock').textContent = (S.night ? '🌙 ليل ' : '☀️ يوم ') + S.day;
  $('btn-music').classList.toggle('off', !S.music);
}

// ---------------- THREE ----------------
const container = $('game3d');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9adcff);
scene.fog = new THREE.Fog(0x9adcff, 34, 95);
const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.1, 300);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);
renderer.domElement.addEventListener('contextmenu', e => e.preventDefault());

const hemi = new THREE.HemisphereLight(0xffffff, 0xff9ec7, 0.95); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xffffff, 1.35);
sun.position.set(18, 30, 12); sun.castShadow = true;
sun.shadow.camera.left = -32; sun.shadow.camera.right = 32; sun.shadow.camera.top = 32; sun.shadow.camera.bottom = -32;
sun.shadow.mapSize.set(1024, 1024);
scene.add(sun);
const moonL = new THREE.DirectionalLight(0x99aaff, 0); moonL.position.set(-14, 22, -10); scene.add(moonL);

const clouds = [];
function makeCloud(x, y, z) {
  const g = new THREE.Group();
  const m = new THREE.MeshLambertMaterial({ color: 0xffffff });
  for (let i = 0; i < 4; i++) { const s = new THREE.Mesh(new THREE.SphereGeometry(1 + Math.random(), 10, 10), m); s.position.set(i * 1.5 - 2, Math.random() * .5, Math.random()); g.add(s); }
  g.position.set(x, y, z); scene.add(g); clouds.push(g);
}
for (let i = 0; i < 6; i++) makeCloud(-30 + Math.random() * 60, 15 + Math.random() * 6, -30 + Math.random() * 50);

// ---------------- BLOCK TEXTURES (canvas, Minecraft-like) ----------------
function ctex(draw) {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  draw(c.getContext('2d'));
  const t = new THREE.CanvasTexture(c);
  t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
function noise(g, base, vars, n = 260) {
  g.fillStyle = base; g.fillRect(0, 0, 64, 64);
  for (let i = 0; i < n; i++) { g.fillStyle = vars[i % vars.length]; g.fillRect((i * 37) % 64, (i * 53) % 64, 3, 3); }
}
const TEX = {
  grassTop: ctex(g => { noise(g, '#6abe4e', ['#5aa843', '#79cf5c', '#4f9c3a']); }),
  grassSide: ctex(g => { noise(g, '#8a5a2a', ['#7a4e24', '#9c6a34']); g.fillStyle = '#6abe4e'; g.fillRect(0, 0, 64, 16); g.fillStyle = '#4f9c3a'; for (let x = 0; x < 64; x += 6) g.fillRect(x, 14, 3, 8); }),
  dirt: ctex(g => noise(g, '#8a5a2a', ['#7a4e24', '#9c6a34', '#6b4420'])),
  stone: ctex(g => noise(g, '#8d8d8d', ['#7d7d7d', '#9d9d9d', '#6d6d6d'])),
  woodSide: ctex(g => { g.fillStyle = '#6b4420'; g.fillRect(0, 0, 64, 64); g.fillStyle = '#5a3818'; for (let x = 4; x < 64; x += 12) g.fillRect(x, 0, 4, 64); }),
  woodTop: ctex(g => { g.fillStyle = '#c98a5a'; g.fillRect(0, 0, 64, 64); g.strokeStyle = '#8a5a2a'; g.lineWidth = 3; for (let r = 6; r < 44; r += 8) { g.beginPath(); g.arc(32, 32, r, 0, 7); g.stroke(); } }),
  leaves: ctex(g => { noise(g, '#3f9c3f', ['#2f8c2f', '#4fac4f', '#1f6c1f', '#5fbf5f']); }),
  planks: ctex(g => { g.fillStyle = '#c98a5a'; g.fillRect(0, 0, 64, 64); g.fillStyle = '#a86e42'; for (let y = 0; y < 64; y += 16) g.fillRect(0, y, 64, 3); }),
  pink: ctex(g => { noise(g, '#ff9ec7', ['#ff8fbe', '#ffafd6', '#f27fb0']); g.fillStyle = '#ffffff88'; g.fillRect(6, 6, 20, 20); }),
  glass: ctex(g => { g.fillStyle = '#bfe9ffcc'; g.fillRect(0, 0, 64, 64); g.strokeStyle = '#ffffff'; g.lineWidth = 6; g.strokeRect(2, 2, 60, 60); g.beginPath(); g.moveTo(10, 50); g.lineTo(30, 14); g.stroke(); }),
  brick: ctex(g => { g.fillStyle = '#d45a5a'; g.fillRect(0, 0, 64, 64); g.fillStyle = '#f2e8e0'; for (let y = 0; y < 64; y += 16) { g.fillRect(0, y, 64, 3); for (let x = (y % 32 ? 0 : 16); x < 64; x += 32) g.fillRect(x, y, 3, 16); } }),
  sand: ctex(g => noise(g, '#e8d8a3', ['#dcc88f', '#f2e2b3'])),
  white: ctex(g => noise(g, '#f5f5f5', ['#e8e8e8', '#ffffff'])),
  gold: ctex(g => { noise(g, '#ffcf40', ['#e8b830', '#ffe070']); g.fillStyle = '#fff3a3'; g.fillRect(8, 8, 18, 18); }),
  crystal: ctex(g => { noise(g, '#ff7ebb', ['#ff4f9a', '#ffc0dd', '#b388ff']); }),
};
function matFor(type) {
  const L = (t) => new THREE.MeshLambertMaterial({ map: TEX[t] });
  switch (type) {
    case 'grass': return [L('grassSide'), L('grassSide'), L('grassTop'), L('dirt'), L('grassSide'), L('grassSide')];
    case 'dirt': return L('dirt');
    case 'stone': return L('stone');
    case 'wood': return [L('woodSide'), L('woodSide'), L('woodTop'), L('woodTop'), L('woodSide'), L('woodSide')];
    case 'leaves': return L('leaves');
    case 'planks': return L('planks');
    case 'pink': return L('pink');
    case 'glass': return new THREE.MeshLambertMaterial({ map: TEX.glass, transparent: true, opacity: 0.85 });
    case 'brick': return L('brick');
    case 'sand': return L('sand');
    case 'white': return L('white');
    case 'gold': return L('gold');
    case 'crystal': return new THREE.MeshLambertMaterial({ map: TEX.crystal, emissive: 0xff4f9a, emissiveIntensity: 0.35 });
    default: return L('pink');
  }
}
const MATS = {};
Object.keys({ grass: 1, dirt: 1, stone: 1, wood: 1, leaves: 1, planks: 1, pink: 1, glass: 1, brick: 1, sand: 1, white: 1, gold: 1, crystal: 1 }).forEach(t => MATS[t] = matFor(t));
const BOXGEO = new THREE.BoxGeometry(1, 1, 1);
const BLOCK_INFO = {
  grass: { e: '🌱', n: 'عشب', hard: 0.45 }, dirt: { e: '🟫', n: 'تراب', hard: 0.4 },
  stone: { e: '🪨', n: 'حجر', hard: 1.1 }, wood: { e: '🪵', n: 'خشب', hard: 0.8 },
  leaves: { e: '🍃', n: 'ورق شجر', hard: 0.25 }, planks: { e: '🟧', n: 'ألواح', hard: 0.7 },
  pink: { e: '🩷', n: 'وردي', hard: 0.5 }, glass: { e: '🪟', n: 'زجاج', hard: 0.4 },
  brick: { e: '🧱', n: 'طوب', hard: 1.0 }, sand: { e: '⏳', n: 'رمل', hard: 0.4 },
  white: { e: '⬜', n: 'أبيض', hard: 0.5 }, gold: { e: '🌟', n: 'ذهب', hard: 0.9 },
  crystal: { e: '💎', n: 'كريستال', hard: 1.0 },
};
const vkey = (x, y, z) => x + ',' + y + ',' + z;

// ---------------- GROUND (InstancedMesh = fast + diggable) ----------------
const R = 20, GSIZE = R * 2 + 1;
const groundMesh = new THREE.InstancedMesh(BOXGEO, MATS.grass, GSIZE * GSIZE);
groundMesh.castShadow = true; groundMesh.receiveShadow = true;
scene.add(groundMesh);
const groundId = new Map(); // instanceId -> "x,z"
{
  const m = new THREE.Matrix4(); let id = 0;
  for (let x = -R; x <= R; x++) for (let z = -R; z <= R; z++) {
    m.makeTranslation(x, -0.5, z); groundMesh.setMatrixAt(id, m);
    groundId.set(id, x + ',' + z); id++;
  }
}
groundMesh.instanceMatrix.needsUpdate = true;
const dugSet = new Set(S.dug || []);
function hideDug() {
  const m = new THREE.Matrix4(), zero = new THREE.Matrix4(); zero.makeScale(0, 0, 0);
  groundId.forEach((k, id) => {
    if (dugSet.has(k)) { groundMesh.setMatrixAt(id, zero); }
    else { const [x, z] = k.split(',').map(Number); m.makeTranslation(x, -0.5, z); groundMesh.setMatrixAt(id, m); }
  });
  groundMesh.instanceMatrix.needsUpdate = true;
}
hideDug();
// sea + beach
{
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(300, 300), new THREE.MeshLambertMaterial({ color: 0x5ab8ff }));
  sea.rotation.x = -Math.PI / 2; sea.position.y = -1.2; scene.add(sea);
  const sand = new THREE.Mesh(new THREE.RingGeometry(R + 0.4, R + 3.4, 48), new THREE.MeshLambertMaterial({ color: 0xf2e2b3 }));
  sand.rotation.x = -Math.PI / 2; sand.position.y = -0.55; scene.add(sand);
}
function groundSolid(x, z) {
  if (Math.abs(x) > R || Math.abs(z) > R) return false;
  return !dugSet.has(x + ',' + z);
}

// ---------------- VOXELS (trees, houses, builds) ----------------
const voxels = new Map(); // key -> {mesh,type,sys}
const sysKeys = new Set();
function addVoxel(x, y, z, type, sys = false, saveIt = true) {
  x = Math.round(x); y = Math.round(y); z = Math.round(z);
  const k = vkey(x, y, z);
  if (voxels.has(k)) removeVoxelMesh(k);
  const mesh = new THREE.Mesh(BOXGEO, MATS[type] || MATS.pink);
  mesh.position.set(x, y + 0.5, z);
  mesh.castShadow = true; mesh.receiveShadow = true;
  mesh.userData = { vx: x, vy: y, vz: z, vtype: type };
  scene.add(mesh);
  voxels.set(k, { mesh, type, sys });
  if (sys) sysKeys.add(k);
  if (saveIt && !sys) { S.voxels = S.voxels.filter(v => !(v.x === x && v.y === y && v.z === z)); S.voxels.push({ x, y, z, t: type }); }
  return mesh;
}
function removeVoxelMesh(k) {
  const v = voxels.get(k); if (!v) return;
  scene.remove(v.mesh); voxels.delete(k);
}
function breakVoxelAt(x, y, z) {
  const k = vkey(x, y, z);
  const v = voxels.get(k); if (!v) return null;
  removeVoxelMesh(k);
  if (v.sys) { if (!S.brokenSys.includes(k)) S.brokenSys.push(k); }
  else S.voxels = S.voxels.filter(o => vkey(o.x, o.y, o.z) !== k);
  return v.type;
}
function solidAt(x, y, z) {
  x = Math.round(x); y = Math.round(y); z = Math.round(z);
  for (const d of doors) {
    if (d.x === x && d.z === z && (y === 0 || y === 1)) return !d.open; // closed door blocks, open lets you in 🚪
  }
  return voxels.has(vkey(x, y, z));
}
function topAt(px, pz) {
  // highest support top under feet
  let top = groundSolid(Math.round(px), Math.round(pz)) ? 0 : -1.2;
  for (let y = 6; y >= 0; y--) {
    if (solidAt(px, y, pz)) { top = Math.max(top, y + 1); break; }
  }
  return top;
}

// ---------------- DOORS ----------------
const doors = []; // {x,y,z,group,leaf,open}
function addDoor(x, z, color = 0xff4f9a) {
  const g = new THREE.Group(); g.position.set(x - 0.5, 0, z);
  const frame = new THREE.Mesh(new THREE.BoxGeometry(1.2, 2.4, 0.25), new THREE.MeshLambertMaterial({ color: 0xffffff }));
  frame.position.set(0.5, 1.2, 0); frame.castShadow = true; g.add(frame);
  const leaf = new THREE.Group(); leaf.position.set(0.05, 0, 0);
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.95, 2.1, 0.12), new THREE.MeshLambertMaterial({ color }));
  panel.position.set(0.48, 1.1, 0); panel.castShadow = true; leaf.add(panel);
  const knob = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 8), new THREE.MeshLambertMaterial({ color: 0xffd633 }));
  knob.position.set(0.8, 1.1, 0.1); leaf.add(knob);
  g.add(leaf); scene.add(g);
  const d = { x, z, group: g, leaf, open: false };
  doors.push(d); return d;
}
function doorFree(x, y, z) {
  for (const d of doors) {
    if ((d.x === x && d.z === z && (y === 0 || y === 1))) return d.open;
  }
  return false;
}
function toggleDoor(d) { d.open = !d.open; sndDoor(); }
setInterval(() => { // auto open near player
  for (const d of doors) {
    const dist = Math.hypot(d.x - player.position.x, d.z - player.position.z);
    const want = dist < 2.6;
    if (want !== d.open) { d.open = want; sndDoor(); }
  }
}, 400);

// ---------------- WORLD GEN: enterable houses / trees / decor ----------------
const simpleColliders = []; // {x,z,r} for lamps/pond decor
function label(text, x, y, z, size = 1) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 96;
  const g = c.getContext('2d');
  g.fillStyle = '#ffffffee'; g.beginPath(); g.roundRect(4, 8, 248, 80, 24); g.fill();
  g.strokeStyle = '#ff4f9a'; g.lineWidth = 6; g.stroke();
  g.fillStyle = '#c2185b'; g.font = 'bold 32px Arial'; g.textAlign = 'center'; g.fillText(text, 128, 60);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(3.6 * size, 1.35 * size), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, side: THREE.DoubleSide }));
  m.position.set(x, y, z); scene.add(m);
}
function buildEnterableHouse(cx, cz, wall, roofT, name, emoji, doorColor) {
  const W = 7, D = 6, H = 3;
  const x0 = cx - Math.floor(W / 2), z0 = cz - Math.floor(D / 2);
  const doorLX = cx; // door on front (z = z0+D-1 side... use south side z0+D-1? front faces center)
  const frontZ = z0 + D - 1;
  // decide front = side facing world center
  const fz = (cz > 0) ? z0 : z0 + D - 1;
  for (let x = x0; x < x0 + W; x++) for (let z = z0; z < z0 + D; z++) {
    const edge = (x === x0 || x === x0 + W - 1 || z === z0 || z === z0 + D - 1);
    if (!edge) continue;
    for (let y = 0; y < H; y++) {
      if (z === fz && x === cx && (y === 0 || y === 1)) continue; // door gap
      let t = wall;
      if (y === 2 && (x + z) % 3 === 0) t = 'glass'; // windows
      if ((x === x0 || x === x0 + W - 1) && y === 1 && z !== fz && (z - z0) % 2 === 0) t = 'glass';
      addVoxel(x, y, z, t, true, false);
    }
  }
  // roof slabs
  for (let x = x0 - 1; x <= x0 + W; x++) for (let z = z0 - 1; z <= z0 + D; z++) addVoxel(x, H, z, roofT, true, false);
  for (let x = x0; x < x0 + W - 2; x++) for (let z = z0; z < z0 + D - 2; z++) addVoxel(x, H + 1, z, roofT, true, false);
  // floor carpet (flat visual rug so you can walk inside)
  const rug = new THREE.Mesh(new THREE.PlaneGeometry(W - 2, D - 2), new THREE.MeshLambertMaterial({ color: 0xffc0dd }));
  rug.rotation.x = -Math.PI / 2; rug.position.set(cx, 0.03, cz); rug.receiveShadow = true; scene.add(rug);
  addDoor(cx, fz, doorColor);
  label(`${emoji} ${name}`, cx, H + 3, cz, 1);
  return { x0, z0, W, D, fz };
}
function tree(x, z) {
  const h = 3 + Math.floor(Math.random() * 2);
  for (let y = 0; y < h; y++) addVoxel(x, y, z, 'wood', true, false);
  for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let dy = 0; dy <= 1; dy++) {
    if (Math.abs(dx) + Math.abs(dz) + dy > 4) continue;
    if (dx === 0 && dz === 0 && dy === 0) continue;
    const k = vkey(x + dx, h + dy - 1, z + dz);
    if (!voxels.has(k) && Math.random() > 0.25) addVoxel(x + dx, h + dy - 1, z + dz, 'leaves', true, false);
  }
}
const H1 = buildEnterableHouse(0, -13, 'pink', 'white', 'قصر ماريا', '🏰', 0xff4f9a);
const H2 = buildEnterableHouse(12, 7, 'white', 'brick', 'كافيه التذوق', '🍰', 0xff9d00);
const H3 = buildEnterableHouse(-12, 7, 'planks', 'pink', 'بيت النوم', '🛏️', 0xb388ff);
const H4 = buildEnterableHouse(-12, -8, 'brick', 'glass', 'البوتيك', '👗', 0xff7ebb);
// trees + crystals + pond + lamps + paths
[[-4, -2], [5, 12], [-5, 13], [15, 1], [-16, 0], [7, -4], [-6, -13], [16, -3], [-2, 11], [3, 13], [9, 12], [-9, 1]].forEach(([x, z]) => { if (Math.abs(x) < R && Math.abs(z) < R) tree(x, z); });
[[6, -8, 'crystal'], [-7, 3, 'crystal'], [14, 10, 'gold'], [-15, 12, 'gold'], [2, -6, 'stone']].forEach(([x, z, t]) => addVoxel(x, 0, z, t, true, false));
{
  const pond = new THREE.Mesh(new THREE.CircleGeometry(2.6, 24), new THREE.MeshLambertMaterial({ color: 0x5ab8ff }));
  pond.rotation.x = -Math.PI / 2; pond.position.set(5, 0.02, -3); scene.add(pond);
  simpleColliders.push({ x: 5, z: -3, r: 2.2 });
  const mkPath = (x, z, w, l, c = 0xffc0dd) => {
    const p = new THREE.Mesh(new THREE.PlaneGeometry(w, l), new THREE.MeshLambertMaterial({ color: c }));
    p.rotation.x = -Math.PI / 2; p.position.set(x, 0.02, z); p.receiveShadow = true; scene.add(p);
  };
  mkPath(0, 0, 2.4, 34); mkPath(0, 0, 34, 2.4); mkPath(12, 0, 2, 20, 0xfff0c8); mkPath(-12, 0, 2, 20, 0xfff0c8);
  const lampM = new THREE.MeshLambertMaterial({ color: 0x5b2144 });
  [[2, 4], [-2, -6], [8, 4], [-8, 4], [8, -4], [-8, -4]].forEach(([x, z]) => {
    const p = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.12, 3, 8), lampM);
    p.position.set(x, 1.5, z); p.castShadow = true; scene.add(p);
    const b = new THREE.Mesh(new THREE.SphereGeometry(0.32, 10, 10), new THREE.MeshBasicMaterial({ color: 0xfff3a3 }));
    b.position.set(x, 3.1, z); scene.add(b);
    simpleColliders.push({ x, z, r: 0.4 });
  });
}
// flowers + fruit bushes + wheat (visual, pickable)
const pickups = [];
function bush(x, z, type, emoji, color) {
  const g = new THREE.Group(); g.position.set(x, 0, z); scene.add(g);
  const b = new THREE.Mesh(new THREE.SphereGeometry(0.8, 10, 10), new THREE.MeshLambertMaterial({ color: 0x3fa34d }));
  b.position.y = 0.7; b.castShadow = true; g.add(b);
  const f = new THREE.Mesh(new THREE.SphereGeometry(0.26, 8, 8), new THREE.MeshLambertMaterial({ color }));
  f.position.y = 1.25; g.add(f);
  const it = { type, g, fruit: f, x, z, alive: true, emoji, kind: 'bush' };
  pickups.push(it); return it;
}
bush(13, -4, 'strawberry', '🍓', 0xff2244); bush(14, -5.5, 'strawberry', '🍓', 0xff2244);
bush(9, -9, 'blueberry', '🫐', 0x4455ff); bush(12.5, -9, 'blueberry', '🫐', 0x4455ff);
bush(-13, -4, 'milk', '🥛', 0xffffff); bush(-9, -10, 'sugar', '🍬', 0xffd6e8);
bush(13.5, 3, 'choco', '🍫', 0x6b3a1f); bush(-13, 3, 'sugar', '🍬', 0xffd6e8);
bush(10, -5, 'wheat', '🌾', 0xe8c84a); bush(11, -3.5, 'carrot', '🥕', 0xff7f2a);
bush(-10, -4, 'apple', '🍎', 0xff3333);
label('🍓 اقطفي الفواكه!', 12, 3, -7, 0.85);
for (let i = 0; i < 36; i++) {
  const st = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.5, 6), new THREE.MeshLambertMaterial({ color: 0x33aa55 }));
  const fx = -19 + Math.random() * 38, fz = -19 + Math.random() * 38;
  st.position.set(fx, 0.25, fz); scene.add(st);
  const f = new THREE.Mesh(new THREE.SphereGeometry(0.18, 8, 8), new THREE.MeshLambertMaterial({ color: [0xff4f9a, 0xffd633, 0xb388ff, 0xffffff][i % 4] }));
  f.position.set(fx, 0.55, fz); scene.add(f);
}
// re-apply saved player voxels + broken sys
(S.voxels || []).forEach(v => { if (MATS[v.t]) addVoxel(v.x, v.y, v.z, v.t, false, false); });
(S.brokenSys || []).forEach(k => removeVoxelMesh(k));

// ---------------- FURNITURE (inside houses + placeable) ----------------
function box(w, h, d, color, x, y, z, parent = scene) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshLambertMaterial({ color }));
  m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m;
}
const FURN = {
  bed: { e: '🛏️', n: 'سرير الأميرة' }, wardrobe: { e: '🚪', n: 'خزانة' }, vanity: { e: '💄', n: 'تسريحة' },
  sofa: { e: '🛋️', n: 'كنبة' }, chair: { e: '🪑', n: 'كرسي' }, table: { e: '🍽️', n: 'طاولة' },
  lamp: { e: '💡', n: 'مصباح' }, shelf: { e: '📚', n: 'مكتبة' }, tv: { e: '📺', n: 'تلفاز' },
  rug: { e: '🧶', n: 'سجادة' }, kitchen: { e: '🍳', n: 'مطبخ' }, fridge: { e: '🧊', n: 'ثلاجة' },
  tub: { e: '🛁', n: 'بانيو' }, piano: { e: '🎹', n: 'بيانو' }, plant: { e: '🪴', n: 'نبتة' },
  bunk: { e: '🏠', n: 'بيت الدمى' }, fountain: { e: '⛲', n: 'نافورة' }, tent: { e: '⛺', n: 'خيمة' },
};
function makeFurniture(type) {
  const g = new THREE.Group();
  const W = (w, h, d, c, x = 0, y = 0, z = 0) => box(w, h, d, c, x, y, z, g);
  if (type === 'bed') { W(2.2, 0.5, 3.2, 0xff4f9a, 0, 0.4, 0); W(2.2, 1.2, 0.3, 0xffffff, 0, 0.9, -1.6); W(1.9, 0.3, 2.8, 0xffffff, 0, 0.75, 0); W(1.5, 0.25, 1, 0xffc0dd, 0, 0.9, -0.8); }
  else if (type === 'wardrobe') { W(2, 2.6, 1, 0xb388ff, 0, 1.3, 0); W(0.9, 2.2, 0.1, 0xffffff, -0.48, 1.2, 0.55); W(0.9, 2.2, 0.1, 0xffffff, 0.48, 1.2, 0.55); }
  else if (type === 'vanity') { W(1.8, 0.15, 0.8, 0xffffff, 0, 1, 0); W(0.15, 1, 0.8, 0xff9ec7, -0.8, 0.5, 0); W(0.15, 1, 0.8, 0xff9ec7, 0.8, 0.5, 0); W(1.2, 1, 0.1, 0xbfe9ff, 0, 1.9, -0.3); }
  else if (type === 'sofa') { W(2.4, 0.6, 1, 0xff9ec7, 0, 0.5, 0); W(2.4, 0.9, 0.3, 0xff4f9a, 0, 0.9, -0.45); W(0.3, 0.6, 1, 0xff4f9a, -1.1, 0.8, 0); W(0.3, 0.6, 1, 0xff4f9a, 1.1, 0.8, 0); }
  else if (type === 'chair') { W(0.9, 0.15, 0.9, 0xffd633, 0, 0.6, 0); W(0.9, 0.9, 0.15, 0xffd633, 0, 1.1, -0.4); [[-0.35, -0.35], [0.35, -0.35], [-0.35, 0.35], [0.35, 0.35]].forEach(([x, z]) => W(0.12, 0.6, 0.12, 0x8a5a2a, x, 0.3, z)); }
  else if (type === 'table') { W(1.8, 0.15, 1.8, 0xffffff, 0, 0.9, 0); [[-0.7, -0.7], [0.7, -0.7], [-0.7, 0.7], [0.7, 0.7]].forEach(([x, z]) => W(0.15, 0.9, 0.15, 0xff9ec7, x, 0.45, z)); const c = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.2, 0.25, 10), new THREE.MeshLambertMaterial({ color: 0xff4f9a })); c.position.y = 1.1; g.add(c); }
  else if (type === 'lamp') { W(0.4, 0.15, 0.4, 0x5b2144, 0, 0.07, 0); const p = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 1.6, 8), new THREE.MeshLambertMaterial({ color: 0x5b2144 })); p.position.y = 0.9; g.add(p); const s = new THREE.Mesh(new THREE.ConeGeometry(0.5, 0.6, 10), new THREE.MeshLambertMaterial({ color: 0xffe97e, emissive: 0xffd633, emissiveIntensity: 0.5 })); s.position.y = 1.9; g.add(s); }
  else if (type === 'shelf') { W(2, 2.2, 0.5, 0x8a5a2a, 0, 1.1, 0); [0.5, 1.1, 1.7].forEach(y => W(1.8, 0.08, 0.45, 0xffffff, 0, y, 0)); [0xff4f9a, 0x7ecfff, 0xffd633].forEach((c, i) => W(0.25, 0.4, 0.3, c, -0.5 + i * 0.5, 1.35, 0)); }
  else if (type === 'tv') { W(1.8, 1, 0.2, 0x222233, 0, 1.4, 0); W(0.6, 0.4, 0.4, 0x5b2144, 0, 0.4, 0); const s = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 0.75), new THREE.MeshBasicMaterial({ color: 0xff9ec7 })); s.position.set(0, 1.4, 0.12); g.add(s); }
  else if (type === 'rug') { const r = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.4, 0.06, 20), new THREE.MeshLambertMaterial({ color: 0xffc0dd })); r.position.y = 0.05; g.add(r); }
  else if (type === 'kitchen') { W(2.4, 1, 0.9, 0xffffff, 0, 0.5, 0); W(2.4, 0.1, 0.95, 0xff9ec7, 0, 1.05, 0); W(0.8, 0.15, 0.6, 0x333333, -0.5, 1.15, 0); }
  else if (type === 'fridge') { W(1.2, 2.2, 1, 0xffffff, 0, 1.1, 0); W(1.0, 0.9, 0.08, 0xffc0dd, 0, 1.5, 0.52); }
  else if (type === 'tub') { W(1.4, 0.8, 2.4, 0xffffff, 0, 0.5, 0); W(1.1, 0.5, 2.1, 0x7ecfff, 0, 0.75, 0); }
  else if (type === 'piano') { W(1.8, 0.7, 1, 0x222233, 0, 0.5, 0); for (let i = 0; i < 7; i++) W(0.18, 0.05, 0.4, i % 2 ? 0x222233 : 0xffffff, -0.6 + i * 0.2, 0.9, 0.3); }
  else if (type === 'plant') { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.28, 0.5, 10), new THREE.MeshLambertMaterial({ color: 0xff4f9a })); p.position.y = 0.25; g.add(p); const l = new THREE.Mesh(new THREE.SphereGeometry(0.6, 10, 10), new THREE.MeshLambertMaterial({ color: 0x33aa55 })); l.position.y = 1; g.add(l); }
  else if (type === 'bunk') { W(1.6, 0.4, 1.6, 0xb388ff, 0, 0.4, 0); W(1.6, 1.8, 0.15, 0xb388ff, 0, 1.2, -0.75); W(1.2, 0.8, 1, 0xfff5f9, 0, 1.3, 0.1); const r = new THREE.Mesh(new THREE.ConeGeometry(1.2, 0.8, 4), new THREE.MeshLambertMaterial({ color: 0xff4f9a })); r.position.y = 2.2; r.rotation.y = Math.PI / 4; g.add(r); }
  else if (type === 'tent') { const t = new THREE.Mesh(new THREE.ConeGeometry(1.5, 2.2, 6), new THREE.MeshLambertMaterial({ color: 0xff9ec7 })); t.position.y = 1.1; t.castShadow = true; g.add(t); }
  else { const b = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.4, 0.6, 14), new THREE.MeshLambertMaterial({ color: 0xffffff })); b.position.y = 0.3; g.add(b); const w = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 0.2, 14), new THREE.MeshLambertMaterial({ color: 0x7ecfff })); w.position.y = 0.6; g.add(w); }
  g.traverse(o => { if (o.isMesh) o.castShadow = true; });
  return g;
}
const furnMeshes = [];
function addFurniture(type, x, z, rot = 0, saveIt = true, y0 = 0) {
  const g = makeFurniture(type); g.position.set(x, y0, z); g.rotation.y = rot;
  g.userData = { furn: true, type };
  scene.add(g); furnMeshes.push(g);
  if (saveIt) { S.furniture.push({ t: type, x: +x.toFixed(1), z: +z.toFixed(1), r: rot }); if (S.furniture.length > 80) { const o = furnMeshes.shift(); scene.remove(o); S.furniture.shift(); } }
  return g;
}
// default interiors (only first run)
if (!localStorage.getItem(SAVE_KEY)) {
  addFurniture('bed', -1.5, -13.5, 0); addFurniture('vanity', 1.8, -14.5, Math.PI); addFurniture('rug', 0, -12.5, 0);
  addFurniture('table', 12, 7, 0); addFurniture('chair', 12, 8.6, Math.PI); addFurniture('kitchen', 13.5, 5.5, -Math.PI / 2); addFurniture('fridge', 10.5, 5.5, 0);
  addFurniture('bed', -13, 7.5, 0); addFurniture('sofa', -11, 6, Math.PI); addFurniture('lamp', -10.5, 8.5, 0);
  addFurniture('shelf', -12, -9.5, 0); addFurniture('table', -11, -7.5, 0);
}
(S.furniture || []).forEach(f => addFurniture(f.t, f.x, f.z, f.r || 0, false));

// ---------------- BEAUTIFUL MARIA ----------------
const player = new THREE.Group(); scene.add(player);
const P = { parts: {}, blink: 0 };
function faceTexture() {
  const c = document.createElement('canvas'); c.width = 128; c.height = 128;
  const g = c.getContext('2d');
  g.fillStyle = '#ffd9b3'; g.fillRect(0, 0, 128, 128);
  // eyes with lashes
  g.fillStyle = '#fff'; g.beginPath(); g.ellipse(38, 62, 14, 11, 0, 0, 7); g.fill(); g.beginPath(); g.ellipse(90, 62, 14, 11, 0, 0, 7); g.fill();
  g.fillStyle = '#4a2b6b'; g.beginPath(); g.arc(40, 64, 7, 0, 7); g.fill(); g.beginPath(); g.arc(88, 64, 7, 0, 7); g.fill();
  g.fillStyle = '#000'; g.beginPath(); g.arc(40, 64, 3.5, 0, 7); g.fill(); g.beginPath(); g.arc(88, 64, 3.5, 0, 7); g.fill();
  g.fillStyle = '#fff'; g.beginPath(); g.arc(42, 62, 2, 0, 7); g.fill(); g.beginPath(); g.arc(90, 62, 2, 0, 7); g.fill();
  g.strokeStyle = '#333'; g.lineWidth = 3;
  g.beginPath(); g.moveTo(22, 52); g.lineTo(14, 48); g.stroke(); g.beginPath(); g.moveTo(106, 52); g.lineTo(114, 48); g.stroke();
  // blush + smile
  g.fillStyle = '#ff8fbecc'; g.beginPath(); g.arc(24, 84, 9, 0, 7); g.fill(); g.beginPath(); g.arc(104, 84, 9, 0, 7); g.fill();
  g.strokeStyle = '#c2185b'; g.lineWidth = 4; g.beginPath(); g.arc(64, 88, 14, 0.3, Math.PI - 0.3); g.stroke();
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
let faceTex = faceTexture();
function buildGirl() {
  while (player.children.length) player.remove(player.children[0]);
  const dressColors = [0xff4f9a, 0xb388ff, 0x7ecfff, 0xff9d00, 0x66ddaa, 0xff5555, 0xffffff, 0x333355, 0xffd633, 0x99ffcc, 0xff9ec7, 0xcc99ff];
  const dc = dressColors[S.dress.dress % dressColors.length];
  const skin = new THREE.MeshLambertMaterial({ color: 0xffd9b3 });
  const dmat = new THREE.MeshLambertMaterial({ color: dc });
  // shoes + socks + legs
  const shoeM = new THREE.MeshLambertMaterial({ color: 0xc2185b });
  const sockM = new THREE.MeshLambertMaterial({ color: 0xffffff });
  const legL = new THREE.Group(), legR = new THREE.Group();
  [[legL, -0.18], [legR, 0.18]].forEach(([leg, x]) => {
    const th = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.11, 0.5, 8), skin); th.position.y = 0.55; leg.add(th);
    const so = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.25, 8), sockM); so.position.y = 0.2; leg.add(so);
    const sh = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.14, 0.34), shoeM); sh.position.set(0, 0.07, 0.05); leg.add(sh);
    leg.position.set(x, 0, 0); player.add(leg);
  });
  // layered skirt
  const skirt = new THREE.Mesh(new THREE.ConeGeometry(0.72, 1.1, 14), dmat); skirt.position.y = 1.25; player.add(skirt);
  const over = new THREE.Mesh(new THREE.ConeGeometry(0.5, 0.7, 14, 1, true), new THREE.MeshLambertMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, side: THREE.DoubleSide }));
  over.position.y = 1.15; player.add(over);
  const waist = new THREE.Mesh(new THREE.TorusGeometry(0.34, 0.07, 8, 16), new THREE.MeshLambertMaterial({ color: 0xffd633 })); waist.position.y = 1.78; waist.rotation.x = Math.PI / 2; player.add(waist);
  const top = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.36, 0.5, 12), dmat); top.position.y = 2.0; player.add(top);
  // arms with hands
  const armL = new THREE.Group(), armR = new THREE.Group();
  [[armL, -0.46], [armR, 0.46]].forEach(([arm, x]) => {
    const a = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.09, 0.55, 8), skin); a.position.y = -0.28; arm.add(a);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.11, 8, 8), skin); hand.position.y = -0.6; arm.add(hand);
    const sl = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.15, 0.2, 8), dmat); sl.position.y = -0.02; arm.add(sl);
    arm.position.set(x, 2.2, 0); player.add(arm);
  });
  // head with face
  const headG = new THREE.Group(); headG.position.y = 2.62;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.42, 18, 18), new THREE.MeshLambertMaterial({ map: faceTex }));
  headG.add(head);
  player.add(headG);
  // hair
  const hc = new THREE.Color(S.dress.hairColor);
  const hm = new THREE.MeshLambertMaterial({ color: hc });
  const hairG = new THREE.Group(); hairG.position.y = 2.62; player.add(hairG);
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.46, 14, 14, 0, Math.PI * 2, 0, Math.PI / 2.2), hm); cap.position.y = 0.1; hairG.add(cap);
  const style = S.dress.hair % 8;
  const locks = [];
  const lock = (x, len = 1.0) => { const l = new THREE.Mesh(new THREE.BoxGeometry(0.2, len, 0.16), hm); l.position.set(x, -0.35, -0.05); hairG.add(l); locks.push(l); };
  lock(-0.44); lock(0.44);
  if (style === 1) { const b = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.9, 0.25), hm); b.position.set(0, -0.45, -0.3); hairG.add(b); }
  if (style === 2) { [-0.52, 0.52].forEach(x => { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.08, 0.85, 8), hm); p.position.set(x, -0.55, 0); hairG.add(p); locks.push(p); const bow = new THREE.Mesh(new THREE.SphereGeometry(0.14, 8, 8), new THREE.MeshLambertMaterial({ color: 0xff4f9a })); bow.position.set(x, -0.2, 0.05); hairG.add(bow); }); }
  if (style === 3) { const b = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 10), hm); b.position.set(0, 0.55, 0); hairG.add(b); }
  if (style === 5 || style === 6) { const b = new THREE.Mesh(new THREE.TorusGeometry(0.32, 0.08, 8, 18), new THREE.MeshLambertMaterial({ color: 0xffd633 })); b.position.set(0, 0.55, 0); b.rotation.x = Math.PI / 2; hairG.add(b); }
  if (style === 7) { const u = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.5, 10), new THREE.MeshLambertMaterial({ color: 0xff9ec7 })); u.position.set(0, 0.65, 0); hairG.add(u); }
  // ponytail (sways)
  const pony = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.07, 0.9, 8), hm); pony.position.set(0, -0.2, -0.5); pony.rotation.x = 0.35; hairG.add(pony);
  const tie = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.045, 8, 12), new THREE.MeshLambertMaterial({ color: 0xff4f9a })); tie.position.set(0, 0.2, -0.42); hairG.add(tie);
  // accessory
  const acc = S.dress.accessory;
  if (acc === 'crown') { const cr = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.29, 0.24, 8), new THREE.MeshLambertMaterial({ color: 0xffd633, emissive: 0xaa7700, emissiveIntensity: 0.3 })); cr.position.y = 3.18; player.add(cr); }
  if (acc === 'bow') { const b1 = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.22, 0.08), new THREE.MeshLambertMaterial({ color: 0xff2244 })); b1.position.set(0.32, 3.1, 0); b1.rotation.z = 0.6; player.add(b1); const b2 = b1.clone(); b2.position.x = 0.52; b2.rotation.z = -0.6; player.add(b2); }
  if (acc === 'wings') { const wM = new THREE.MeshLambertMaterial({ color: 0xffffff, transparent: true, opacity: 0.85 }); const w1 = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.95, 0.08), wM); w1.position.set(-0.62, 2.0, -0.35); w1.rotation.z = 0.4; player.add(w1); const w2 = w1.clone(); w2.position.x = 0.62; w2.rotation.z = -0.4; player.add(w2); }
  if (acc === 'halo') { const h = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.05, 8, 20), new THREE.MeshLambertMaterial({ color: 0xffe97e, emissive: 0xffd633, emissiveIntensity: 0.6 })); h.position.y = 3.32; h.rotation.x = Math.PI / 2; player.add(h); }
  if (acc === 'cap') { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.36, 0.16, 10), new THREE.MeshLambertMaterial({ color: 0xff4f9a })); c.position.y = 3.12; player.add(c); }
  player.traverse(o => { if (o.isMesh) o.castShadow = true; });
  P.parts = { legL, legR, armL, armR, headG, skirt, pony, locks };
}
buildGirl();
player.position.set(0, 0, 8);
let py = 0, vy = 0, yaw = Math.PI, camPitch = 0.35, camDist = 7.5;

// ---------------- REALISTIC ANIMALS ----------------
function cowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, 64, 64);
  g.fillStyle = '#222222';
  [[8, 10, 14], [38, 6, 12], [20, 36, 16], [46, 40, 10], [8, 50, 8]].forEach(([x, y, r]) => { g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); });
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const animals = [];
function makeAnimal(type) {
  const g = new THREE.Group();
  const legs = [];
  const legM = (c) => new THREE.MeshLambertMaterial({ color: c });
  const addLeg = (x, z, h, w, c) => {
    const l = new THREE.Group(); l.position.set(x, h, z);
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, w), legM(c)); m.position.y = -h / 2; l.add(m);
    g.add(l); legs.push(l); return l;
  };
  let head, tail = null;
  if (type === 'cow') {
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.8, 1.5), new THREE.MeshLambertMaterial({ map: cowTexture() }));
    body.position.y = 1.0; g.add(body);
    head = new THREE.Group(); head.position.set(0, 1.35, 0.85);
    const skull = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.55, 0.5), new THREE.MeshLambertMaterial({ color: 0xffffff })); head.add(skull);
    const snout = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.3, 0.25), new THREE.MeshLambertMaterial({ color: 0xffc0c0 })); snout.position.set(0, -0.15, 0.32); head.add(snout);
    [-0.32, 0.32].forEach(x => { const horn = new THREE.Mesh(new THREE.ConeGeometry(0.08, 0.25, 6), new THREE.MeshLambertMaterial({ color: 0xe8d8b0 })); horn.position.set(x, 0.35, 0); head.add(horn); });
    [-0.3, 0.3].forEach(x => { const ear = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.08, 0.12), new THREE.MeshLambertMaterial({ color: 0xffffff })); ear.position.set(x, 0.15, -0.05); head.add(ear); });
    g.add(head);
    tail = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.7, 0.08), legM(0xffffff)); tail.position.set(0, 1.1, -0.8); g.add(tail);
    const c = 0xeeeeee;
    addLeg(-0.32, 0.55, 0.65, 0.22, c); addLeg(0.32, 0.55, 0.65, 0.22, c); addLeg(-0.32, -0.55, 0.65, 0.22, c); addLeg(0.32, -0.55, 0.65, 0.22, c);
  } else if (type === 'sheep') {
    const woolM = new THREE.MeshLambertMaterial({ color: 0xf2f2f2 });
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.75, 12, 12), woolM); body.position.y = 1.0; body.scale.set(0.9, 0.85, 1.25); g.add(body);
    for (let i = 0; i < 8; i++) { const p = new THREE.Mesh(new THREE.SphereGeometry(0.28, 8, 8), woolM); const a = i / 8 * Math.PI * 2; p.position.set(Math.cos(a) * 0.55, 1.35 + Math.sin(i * 3) * 0.15, Math.sin(a) * 0.8); g.add(p); }
    head = new THREE.Group(); head.position.set(0, 1.15, 0.95);
    const skull = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.45, 0.45), new THREE.MeshLambertMaterial({ color: 0x4a3525 })); head.add(skull);
    g.add(head);
    const c = 0x4a3525;
    addLeg(-0.3, 0.5, 0.6, 0.18, c); addLeg(0.3, 0.5, 0.6, 0.18, c); addLeg(-0.3, -0.5, 0.6, 0.18, c); addLeg(0.3, -0.5, 0.6, 0.18, c);
  } else if (type === 'pig') {
    const pm = new THREE.MeshLambertMaterial({ color: 0xffb0c0 });
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.65, 1.3), pm); body.position.y = 0.75; g.add(body);
    head = new THREE.Group(); head.position.set(0, 0.85, 0.7);
    const skull = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.4), pm); head.add(skull);
    const sn = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.15, 10), new THREE.MeshLambertMaterial({ color: 0xff8fa3 })); sn.rotation.x = Math.PI / 2; sn.position.set(0, -0.05, 0.28); head.add(sn);
    [-0.2, 0.2].forEach(x => { const ear = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.2, 4), pm); ear.position.set(x, 0.3, 0); head.add(ear); });
    g.add(head);
    tail = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.03, 6, 10), pm); tail.position.set(0, 0.85, -0.7); g.add(tail);
    addLeg(-0.28, 0.45, 0.45, 0.2, 0xffb0c0); addLeg(0.28, 0.45, 0.45, 0.2, 0xffb0c0); addLeg(-0.28, -0.45, 0.45, 0.2, 0xffb0c0); addLeg(0.28, -0.45, 0.45, 0.2, 0xffb0c0);
  } else if (type === 'chicken') {
    const wm = new THREE.MeshLambertMaterial({ color: 0xffffff });
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.35, 12, 12), wm); body.position.y = 0.5; body.scale.set(1, 1.1, 1.2); g.add(body);
    head = new THREE.Group(); head.position.set(0, 0.9, 0.25);
    const skull = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 10), wm); head.add(skull);
    const beak = new THREE.Mesh(new THREE.ConeGeometry(0.08, 0.2, 8), new THREE.MeshLambertMaterial({ color: 0xff9d00 })); beak.rotation.x = Math.PI / 2; beak.position.set(0, 0, 0.25); head.add(beak);
    const comb = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.15, 0.2), new THREE.MeshLambertMaterial({ color: 0xff3333 })); comb.position.set(0, 0.2, 0); head.add(comb);
    g.add(head);
    tail = new THREE.Mesh(new THREE.ConeGeometry(0.15, 0.4, 6), new THREE.MeshLambertMaterial({ color: 0xff9d9d })); tail.position.set(0, 0.6, -0.4); tail.rotation.x = -0.8; g.add(tail);
    addLeg(-0.12, 0, 0.3, 0.08, 0xff9d00); addLeg(0.12, 0, 0.3, 0.08, 0xff9d00);
  } else { // horse
    const hm2 = new THREE.MeshLambertMaterial({ color: 0x8a5a2a });
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 1.6), hm2); body.position.y = 1.15; g.add(body);
    const neck = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.8, 0.4), hm2); neck.position.set(0, 1.6, 0.75); neck.rotation.x = -0.3; g.add(neck);
    head = new THREE.Group(); head.position.set(0, 2.0, 0.95);
    const skull = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.35, 0.6), hm2); head.add(skull);
    [-0.12, 0.12].forEach(x => { const ear = new THREE.Mesh(new THREE.ConeGeometry(0.08, 0.22, 4), hm2); ear.position.set(x, 0.28, -0.15); head.add(ear); });
    const mane = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.7, 0.3), new THREE.MeshLambertMaterial({ color: 0x3a2410 })); mane.position.set(0, 1.75, 0.6); g.add(mane);
    g.add(head);
    tail = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.8, 0.12), new THREE.MeshLambertMaterial({ color: 0x3a2410 })); tail.position.set(0, 1.2, -0.85); g.add(tail);
    addLeg(-0.25, 0.6, 0.85, 0.18, 0x8a5a2a); addLeg(0.25, 0.6, 0.85, 0.18, 0x8a5a2a); addLeg(-0.25, -0.6, 0.85, 0.18, 0x8a5a2a); addLeg(0.25, -0.6, 0.85, 0.18, 0x8a5a2a);
  }
  g.traverse(o => { if (o.isMesh) { o.castShadow = true; } });
  return { g, legs, head, tail };
}
const ANIMAL_DEFS = [
  { t: 'cow', e: '🐄', n: 'بقرة', food: 'wheat' }, { t: 'cow', e: '🐄', n: 'بقرة', food: 'wheat' },
  { t: 'sheep', e: '🐑', n: 'خروف', food: 'wheat' }, { t: 'sheep', e: '🐑', n: 'خروف', food: 'wheat' },
  { t: 'pig', e: '🐷', n: 'خنزير', food: 'carrot' }, { t: 'chicken', e: '🐔', n: 'دجاجة', food: 'wheat' },
  { t: 'chicken', e: '🐔', n: 'دجاجة', food: 'wheat' }, { t: 'horse', e: '🐴', n: 'حصان', food: 'apple' },
];
ANIMAL_DEFS.forEach((d, i) => {
  const m = makeAnimal(d.t);
  const hx = 6 + (i % 4) * 2.5, hz = -6 + Math.floor(i / 4) * 3;
  m.g.position.set(hx, 0, hz);
  scene.add(m.g);
  animals.push({ ...d, ...m, tx: hx, tz: hz, timer: 2 + Math.random() * 5, walk: 0, love: 0, followT: 0 });
});
function feedAnimal(a) {
  const need = a.food;
  if ((S.inv[need] || 0) <= 0) { toast(`أطعميها ${need === 'wheat' ? '🌾 قمحاً' : need === 'carrot' ? '🥕 جزراً' : '🍎 تفاحاً'} أولاً! اقطفي من الحديقة 🌸`); return; }
  S.inv[need]--; a.love++; a.followT = 60; sndYum(); flyHearts(4);
  S.hearts += 2; S.xp += 3; checkLevel(); updateHUD();
  toast(`${a.e} تحبك الآن! ستتبعك 💖`);
  if (questStep === 5) updateQuest(6);
  if (S.tool === 'pets') renderPanel();
  save();
}
// adoptable pets (follow forever)
const petGroup = new THREE.Group(); scene.add(petGroup);
let petMeshes = [];
function spawnPets() {
  petMeshes.forEach(p => petGroup.remove(p.g)); petMeshes = [];
  S.pets.forEach((t, i) => {
    const g = new THREE.Group(); let body;
    if (t === 'cat') { body = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.35, 0.65), new THREE.MeshLambertMaterial({ color: 0xffb366 })); const h = new THREE.Mesh(new THREE.SphereGeometry(0.26, 10, 10), new THREE.MeshLambertMaterial({ color: 0xffb366 })); h.position.set(0, 0.3, 0.35); g.add(h); }
    else if (t === 'bunny') { body = new THREE.Mesh(new THREE.SphereGeometry(0.32, 10, 10), new THREE.MeshLambertMaterial({ color: 0xffffff })); [-0.12, 0.12].forEach(x => { const e = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.45, 6), new THREE.MeshLambertMaterial({ color: 0xffc0dd })); e.position.set(x, 0.55, 0); g.add(e); }); }
    else if (t === 'puppy') { body = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.35, 0.7), new THREE.MeshLambertMaterial({ color: 0x9a6b4f })); const h = new THREE.Mesh(new THREE.SphereGeometry(0.27, 10, 10), new THREE.MeshLambertMaterial({ color: 0x9a6b4f })); h.position.set(0, 0.3, 0.4); g.add(h); }
    else { body = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.55, 0.8), new THREE.MeshLambertMaterial({ color: 0xffffff })); const h2 = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.45, 8), new THREE.MeshLambertMaterial({ color: 0xffd633 })); h2.position.set(0, 0.55, 0.45); h2.rotation.x = Math.PI / 2; g.add(h2); }
    body.position.y = 0.3; body.castShadow = true; g.add(body);
    g.position.set(player.position.x + 1 + i, 0, player.position.z + 1);
    petGroup.add(g); petMeshes.push({ g, t, off: i });
  });
}
spawnPets();

// ---------------- FOOD ----------------
const RECIPES = [
  { id: 'cupcake', e: '🧁', n: 'كب كيك وردي', need: { strawberry: 2, sugar: 1 } },
  { id: 'cake', e: '🍰', n: 'كيكة الفراولة', need: { strawberry: 3, milk: 1, sugar: 1 } },
  { id: 'muffin', e: '🧁', n: 'مافن التوت', need: { blueberry: 2, milk: 1, sugar: 1 } },
  { id: 'tea', e: '🧋', n: 'شاي الفقاعات', need: { milk: 1, sugar: 1, strawberry: 1 } },
  { id: 'ice', e: '🍨', n: 'آيس كريم', need: { choco: 1, milk: 1, sugar: 1 } },
  { id: 'lolli', e: '🍭', n: 'مصاصة', need: { sugar: 2, apple: 1 } },
];
function canCook(r) { return Object.entries(r.need).every(([k, v]) => (S.inv[k] || 0) >= v); }
function cook(r) {
  if (!canCook(r)) { toast(`تحتاجين ${Object.entries(r.need).map(([k, v]) => v + ' ' + k).join(' + ')} 😢 اقطفي من الحديقة!`); return; }
  Object.entries(r.need).forEach(([k, v]) => S.inv[k] -= v);
  S.sweets++; S.xp += 5; checkLevel();
  sndYum(); flyHearts(5); toast(`${r.e} طبختي ${r.n}! 😋`);
  updateHUD(); renderPanel(); save(); updateQuest();
}
function taste() {
  if (S.sweets <= 0) { toast('لا حلويات! اطبخي أولاً 🍰'); beep(200, .2); return; }
  S.sweets--; S.hearts += 2; S.coins += 5; S.xp += 3; checkLevel();
  sndYum(); flyHearts(8); toast(`😋 لذيذ! +2💖 +5💰 — ${S.name} تحب التذوق!`);
  updateHUD(); if (S.tool === 'food') renderPanel(); save(); updateQuest();
}
function checkLevel() {
  const nl = 1 + Math.floor(S.xp / 20);
  if (nl > S.level) { S.level = nl; S.coins += 20; toast(`🎉 مستوى جديد Lv ${nl}! +20💰`); sndCoin(); }
}
function collect(p) {
  p.alive = false; p.fruit.visible = false;
  S.inv[p.type] = (S.inv[p.type] || 0) + 1; S.coins += 2; S.xp += 2; checkLevel(); sndCoin();
  flyHearts(2); toast(`${p.emoji} +1 ${p.type}! 😋`);
  updateHUD(); if (S.tool === 'food' || S.tool === 'pets') renderPanel(); save(); updateQuest();
  setTimeout(() => { p.alive = true; p.fruit.visible = true; }, 15000);
}

// ---------------- QUESTS ----------------
let questStep = +(localStorage.getItem('maineQuest2') || 0);
const QUESTS = [
  '🚪 ادخلي قصر ماريا من الباب الوردي (يمشي الباب ويفتح وحده)!',
  '⛏️ وجّهي ＋ نحو شجرة واضغطي ⛏️ مطوّلاً لتكسير خشبة!',
  '🧱 اختاري مكعباً واضغطي 🧱 لبناء مكعب جديد!',
  '🧁 اطبخي وتذوّقي كب كيك من تبويب 🍰!',
  '👗 غيّري فستانك من تبويب 👗!',
  '🐄 أطعمي بقرة 🌾 قمحاً في الحديقة!',
  '💖 مذهلة يا {N}! أنت ملكة الكرافت 👑 ابني وتذوّقي كما تشائين!',
];
function updateQuest(force) {
  if (typeof force === 'number') questStep = Math.max(questStep, force);
  localStorage.setItem('maineQuest2', questStep);
  const last = questStep >= QUESTS.length - 1;
  $('quest').innerHTML = `🌸 ${QUESTS[Math.min(questStep, QUESTS.length - 1)].replace('{N}', `<b>${S.name || 'Maria'}</b>`)} ${last ? '' : '<button id="quest-go">روحي ➜</button>'}`;
  const b = $('quest-go'); if (b) b.onclick = () => { openPanel(S.tool); };
}
updateQuest();
// track entering house
let enteredHouse = false;
function checkHouseEnter() {
  const p = player.position;
  const inside = (h) => p.x > h.x0 && p.x < h.x0 + h.W && p.z > h.z0 && p.z < h.z0 + h.D;
  if (!enteredHouse && (inside(H1) || inside(H2) || inside(H3) || inside(H4))) {
    enteredHouse = true; updateQuest(1);
    toast('🏠 دخلتِ البيت! جميل من الداخل أليس كذلك؟ 💖'); sndCoin(); S.xp += 5; checkLevel(); updateHUD();
  }
}

// ---------------- TARGETING (crosshair raycast) ----------------
const ray = new THREE.Raycaster(); ray.far = 9;
const centerV = new THREE.Vector2(0, 0);
const hlBox = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.BoxGeometry(1.02, 1.02, 1.02)),
  new THREE.LineBasicMaterial({ color: 0x5b2144 })
);
hlBox.visible = false; scene.add(hlBox);
let target = null; // {kind,x,y,z,type,nx,ny,nz}
let lastTargetT = 0;
function updateTargetThrottled() {
  const n = performance.now();
  if (n - lastTargetT < 120) return; // raycast vs 1600+ instances every frame is heavy on phones
  lastTargetT = n;
  updateTarget();
}
function voxelTargets() { return [...voxels.values()].map(v => v.mesh); }
function updateTarget() {
  ray.setFromCamera(centerV, camera);
  const hits = ray.intersectObjects([groundMesh, ...voxelTargets()], false);
  hlBox.visible = false; target = null;
  if (!hits.length) { $('target-info').textContent = '🎯 —'; return; }
  const h = hits[0];
  if (h.object === groundMesh) {
    const k = groundId.get(h.instanceId);
    if (!k || dugSet.has(k)) { $('target-info').textContent = '🎯 —'; return; }
    const [x, z] = k.split(',').map(Number);
    const n = h.face ? h.face.normal.clone().transformDirection(h.object.matrixWorld) : new THREE.Vector3(0, 1, 0);
    target = { kind: 'ground', x, z, type: 'grass', nx: Math.round(n.x), ny: Math.round(n.y), nz: Math.round(n.z) };
    hlBox.position.set(x, 0.01, z); hlBox.scale.set(1, 0.1, 1); hlBox.visible = true;
    $('target-info').textContent = `🌱 عشب — ⛏️ كسّري • 🧱 ابنِ فوقه`;
  } else {
    const u = h.object.userData;
    const n = h.face ? h.face.normal.clone().transformDirection(h.object.matrixWorld) : new THREE.Vector3(0, 1, 0);
    target = { kind: 'voxel', x: u.vx, y: u.vy, z: u.vz, type: u.vtype, nx: Math.round(n.x), ny: Math.round(n.y), nz: Math.round(n.z) };
    hlBox.position.set(u.vx, u.vy + 0.5, u.vz); hlBox.scale.set(1, 1, 1); hlBox.visible = true;
    const bi = BLOCK_INFO[u.vtype] || BLOCK_INFO.pink;
    $('target-info').textContent = `${bi.e} ${bi.n} — ⛏️ تكسير • 🧱 بناء بجانبه`;
  }
}
// break particles
function burst(x, y, z, color = 0xff9ec7) {
  for (let i = 0; i < 8; i++) {
    const m = new THREE.Mesh(BOXGEO, new THREE.MeshBasicMaterial({ color }));
    m.scale.setScalar(0.15); m.position.set(x, y, z);
    scene.add(m);
    const vx = (Math.random() - .5) * 4, vy = Math.random() * 4, vz = (Math.random() - .5) * 4;
    const t0 = performance.now();
    const step = () => {
      const t = (performance.now() - t0) / 500;
      if (t > 1) { scene.remove(m); return; }
      m.position.x += vx * 0.03; m.position.y += vy * 0.03 - t * 0.15; m.position.z += vz * 0.03;
      requestAnimationFrame(step);
    };
    step();
  }
}
function doBreak() {
  if (!target) { toast('وجّهي ＋ نحو مكعب أولاً 🎯'); return; }
  if (target.kind === 'ground') {
    const k = target.x + ',' + target.z;
    // don't dig under houses/doors
    for (const d of doors) if (Math.abs(d.x - target.x) < 1.5 && Math.abs(d.z - target.z) < 1.5) { toast('لا تحفري عند الباب! 🚪'); return; }
    dugSet.add(k); S.dug.push(k); hideDug();
    S.blocks.grass = (S.blocks.grass || 0) + 1; S.xp += 1;
    burst(target.x, 0.3, target.z, 0x6abe4e); sndBreak(); checkLevel(); updateHUD(); save(); updateQuest();
  } else {
    const t = breakVoxelAt(target.x, target.y, target.z);
    if (!t) return;
    if (t === 'crystal') { S.coins += 10; S.hearts += 2; sndCoin(); flyHearts(3); toast('💎 كريستال! +10💰 +2💖'); }
    else if (t === 'gold') { S.coins += 5; sndCoin(); toast('🌟 ذهب! +5💰'); }
    else { S.blocks[t] = (S.blocks[t] || 0) + 1; if (t === 'leaves' && Math.random() > 0.5) { S.inv.apple++; toast('🍎 تفاحة من الشجرة!'); } }
    S.xp += 2;
    burst(target.x, target.y + 0.5, target.z); sndBreak(); checkLevel(); updateHUD(); save();
    if (t === 'wood' && questStep === 1) updateQuest(2);
  }
  if (S.tool === 'build') renderPanel();
}
function doPlace() {
  let px, py2, pz;
  if (target) {
    if (target.kind === 'ground') { px = target.x; py2 = 0; pz = target.z; if (groundSolid(px, pz)) py2 = 0; }
    else { px = target.x + target.nx; py2 = target.y + target.ny; pz = target.z + target.nz; }
  } else {
    px = Math.round(player.position.x - Math.sin(yaw) * 2); pz = Math.round(player.position.z - Math.cos(yaw) * 2); py2 = 0;
  }
  if (Math.abs(px) > R || Math.abs(pz) > R || py2 < 0 || py2 > 6) { toast('خارج العالم! 🌊'); return; }
  // refill dug ground
  if (py2 === 0 && !groundSolid(px, pz) && !solidAt(px, 0, pz)) {
    // fill hole back (free)
    dugSet.delete(px + ',' + pz); S.dug = S.dug.filter(k => k !== px + ',' + pz); hideDug(); sndPlace(); save(); return;
  }
  if (solidAt(px, py2, pz)) { toast('مشغول هنا! 🧱'); return; }
  // don't suffocate player
  const pCell = { x: Math.round(player.position.x), z: Math.round(player.position.z), y0: Math.floor(py + 0.3), y1: Math.floor(py + 1.4) };
  if (px === pCell.x && pz === pCell.z && (py2 === pCell.y0 || py2 === pCell.y1)) { toast('لا تبني داخلك! 😅'); return; }
  const t = S.selBlock;
  if ((S.blocks[t] || 0) <= 0) { toast('نفدت المكعبات! كسّري لتجمعي ⛏️'); return; }
  S.blocks[t]--; addVoxel(px, py2, pz, t, false, true);
  sndPlace(); S.xp += 1; checkLevel(); updateHUD(); save();
  if (questStep === 2) updateQuest(3);
  if (S.tool === 'build') renderPanel();
}
// hold-to-break
let breakHold = null, breakProg = 0, breakNeed = 0.5;
function breakTick() {
  if (!target) { stopBreak(); return; }
  const hard = target.kind === 'ground' ? 0.45 : ((BLOCK_INFO[target.type] || {}).hard || 0.6);
  breakNeed = hard * 1000;
  breakProg += 90;
  const bar = $('break-bar'); bar.style.display = 'block';
  bar.firstElementChild.style.width = Math.min(100, breakProg / breakNeed * 100) + '%';
  beep(150 + breakProg / 8, .05, 'sawtooth', .04);
  if (breakProg >= breakNeed) { stopBreak(); doBreak(); }
}
function startBreak() { stopBreak(); breakProg = 0; breakHold = setInterval(breakTick, 90); }
function stopBreak() { if (breakHold) clearInterval(breakHold); breakHold = null; breakProg = 0; $('break-bar').style.display = 'none'; $('break-bar').firstElementChild.style.width = '0'; }

// ---------------- CONTROLS ----------------
const keys = {};
addEventListener('keydown', e => {
  keys[e.code] = true;
  if (e.code === 'Space') { doJump(); e.preventDefault(); }
  if (e.code === 'KeyE') doPlace();
});
addEventListener('keyup', e => keys[e.code] = false);
renderer.domElement.addEventListener('pointerdown', e => {
  if (e.pointerType !== 'mouse') return; // touch uses ⛏️🧱 buttons (no accidental breaks)
  if (e.button === 0) startBreak();
  if (e.button === 2) doPlace();
});
addEventListener('pointerup', e => { if (e.pointerType !== 'mouse') return; if (e.button === 0) stopBreak(); });

let joy = { x: 0, y: 0 };
const joyEl = $('joystick'), stickEl = $('stick');
let joyId = null;
function joyPos(e) {
  const r = joyEl.getBoundingClientRect(); const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  let dx = (e.clientX - cx) / (r.width / 2), dy = (e.clientY - cy) / (r.height / 2);
  const m = Math.hypot(dx, dy); if (m > 1) { dx /= m; dy /= m; }
  joy = { x: dx, y: dy };
  stickEl.style.transform = `translate(calc(-50% + ${dx * 32}px), calc(-50% + ${dy * 32}px))`;
}
joyEl.addEventListener('pointerdown', e => { joyId = e.pointerId; joyEl.setPointerCapture(e.pointerId); joyPos(e); });
joyEl.addEventListener('pointermove', e => { if (e.pointerId === joyId) joyPos(e); });
const joyEnd = e => { if (e.pointerId === joyId) { joyId = null; joy = { x: 0, y: 0 }; stickEl.style.transform = 'translate(-50%,-50%)'; } };
joyEl.addEventListener('pointerup', joyEnd); joyEl.addEventListener('pointercancel', joyEnd);

$('t-jump').addEventListener('click', () => doJump());
$('t-taste').addEventListener('click', () => taste());
const tb = $('t-break'), tp = $('t-place');
tb.addEventListener('pointerdown', e => { e.preventDefault(); startBreak(); });
tb.addEventListener('pointerup', () => stopBreak());
tb.addEventListener('pointerleave', () => stopBreak());
tp.addEventListener('click', () => doPlace());
function doJump() { if (py <= topAt(player.position.x, player.position.z) + 0.05) { vy = 7; beep(500, .1); } }

let dragging = false, lastX = 0, lastY = 0, moved = 0, downT = 0;
renderer.domElement.addEventListener('pointerdown', e => { dragging = true; moved = 0; lastX = e.clientX; lastY = e.clientY; downT = performance.now(); });
addEventListener('pointermove', e => {
  if (!dragging) return;
  const dx = e.clientX - lastX, dy = e.clientY - lastY; moved += Math.abs(dx) + Math.abs(dy);
  if (breakHold && moved > 18) stopBreak(); // dragging = looking around, not breaking
  yaw -= dx * 0.006; camPitch = Math.min(1.2, Math.max(-0.4, camPitch + dy * 0.004));
  lastX = e.clientX; lastY = e.clientY;
});
addEventListener('pointerup', e => { if (dragging && moved < 12 && performance.now() - downT < 400 && e.target === renderer.domElement) tapHandle(e); dragging = false; });
const tapRay = new THREE.Raycaster();
function tapHandle(e) {
  const nx = (e.clientX / innerWidth) * 2 - 1, ny = -(e.clientY / innerHeight) * 2 + 1;
  tapRay.setFromCamera(new THREE.Vector2(nx, ny), camera);
  // animals first
  const ah = tapRay.intersectObjects(animals.map(a => a.g), true);
  if (ah.length) {
    let o = ah[0].object; while (o && !animals.find(a => a.g === o)) o = o.parent;
    const a = animals.find(a => a.g === o);
    if (a) {
      if ((S.inv[a.food] || 0) > 0) feedAnimal(a);
      else { sndMoo(); flyHearts(2); toast(`${a.e} ${a.n} تقول مرحباً! أطعميها ${a.food === 'wheat' ? '🌾' : a.food === 'carrot' ? '🥕' : '🍎'} لتتبعك`); if (questStep === 5 && a.t === 'cow') updateQuest(5); }
      return;
    }
  }
  // doors
  const dh = tapRay.intersectObjects(doors.map(d => d.group), true);
  if (dh.length) { let o = dh[0].object; while (o && !doors.find(d => d.group === o)) o = o.parent; const d = doors.find(d => d.group === o); if (d) { toggleDoor(d); toast(d.open ? '🚪 أهلاً بك في البيت! 💖' : '🚪 أُغلق الباب'); } return; }
  // bushes
  let best = null, bd = 3.2;
  pickups.forEach(p => { if (!p.alive) return; const d = Math.hypot(p.x - player.position.x, p.z - player.position.z); if (d < bd) { bd = d; best = p; } });
  if (best) { collect(best); return; }
  // furniture rotate/delete
  const fh = tapRay.intersectObjects(furnMeshes, true);
  if (fh.length) {
    let o = fh[0].object; while (o && !(o.userData && o.userData.furn)) o = o.parent;
    if (o) {
      if (S.delMode) { scene.remove(o); furnMeshes.splice(furnMeshes.indexOf(o), 1); S.furniture.splice(S.furniture.findIndex(f => Math.abs(f.x - o.position.x) < 0.3 && Math.abs(f.z - o.position.z) < 0.3), 1); sndPop(); toast('أُزيل الأثاث 🧹'); save(); }
      else { o.rotation.y += Math.PI / 4; sndPop(); }
      return;
    }
  }
}
function placeAtFront() { doPlace(); }

// ---------------- PANELS ----------------
const panel = $('panel'), pbody = $('panel-body'), ptitle = $('panel-title');
document.querySelectorAll('#toolbar button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#toolbar button').forEach(x => x.classList.remove('on')); b.classList.add('on');
  openPanel(b.dataset.panel);
});
$('panel-close').onclick = () => { panel.classList.add('hidden'); document.querySelectorAll('#toolbar button').forEach(x => x.classList.remove('on')); };
function openPanel(name) { S.tool = name; panel.classList.remove('hidden'); renderPanel(); }
function invHTML() {
  return `<div class="inv">🎒 <b>${S.name}</b>: 🍓${S.inv.strawberry || 0} 🫐${S.inv.blueberry || 0} 🥛${S.inv.milk || 0} 🍫${S.inv.choco || 0} 🍬${S.inv.sugar || 0} 🌾${S.inv.wheat || 0} 🥕${S.inv.carrot || 0} 🍎${S.inv.apple || 0} • 🧁${S.sweets} 💰${S.coins} 💖${S.hearts}</div>`;
}
function renderPanel() {
  const t = S.tool;
  if (t === 'build') {
    ptitle.textContent = '🧱 بناء مثل ماين كرافت';
    pbody.innerHTML = invHTML() + `<div class="grid">` + Object.entries(BLOCK_INFO).map(([k, v]) =>
      `<div class="item ${S.selBlock === k ? 'sel' : ''}" data-b="${k}"><span class="em">${v.e}</span>${v.n}<div class="cost">عندي: ${S.blocks[k] || 0}</div></div>`).join('') + `</div>
      <div class="row-btns"><button id="b-place" class="primary">🧱 ابنِ هنا</button><button id="b-break">⛏️ اكسر ＋</button></div>
      <div class="row-btns"><button id="b-del" class="${S.delMode ? 'primary' : ''}">${S.delMode ? '🧹 حذف الأثاث ON' : '🧹 حذف الأثاث'}</button><button id="b-clear">🗑️ مسح بنائي</button></div>
      <p style="font-size:12px">⛏️ اضغطي مطوّلاً للتكسير (الأرض والجدران والأشجار كلها تتكسر!) • 🧱 للبناء بجانب المكعب • ادخلي البيوت من الباب 🚪</p>`;
    pbody.querySelectorAll('[data-b]').forEach(d => d.onclick = () => { S.selBlock = d.dataset.b; S.delMode = false; sndPop(); renderPanel(); });
    $('b-place').onclick = () => doPlace();
    $('b-break').onclick = () => { startBreak(); setTimeout(stopBreak, 1500); };
    $('b-del').onclick = () => { S.delMode = !S.delMode; sndPop(); renderPanel(); };
    $('b-clear').onclick = () => {
      [...voxels.entries()].filter(([k, v]) => !v.sys).forEach(([k]) => removeVoxelMesh(k));
      S.voxels = []; save(); toast('مسحتِ بنائك 🧹 البيوت الأصلية باقية 🏠');
    };
  }
  else if (t === 'furniture') {
    ptitle.textContent = '🛏️ أثاث كامل للبنات';
    pbody.innerHTML = invHTML() + `<div class="grid">` + Object.entries(FURN).map(([k, v]) =>
      `<div class="item ${S.selFurn === k ? 'sel' : ''}" data-f="${k}"><span class="em">${v.e}</span>${v.n}<div class="cost">2💰</div></div>`).join('') + `</div>
      <div class="row-btns"><button id="f-place" class="primary">✨ ضعي الأثاث هنا</button><button id="b-del" class="${S.delMode ? 'primary' : ''}">🧹 حذف/تدوير</button></div>
      <p style="font-size:12px">اختاري ثم اضغطي ✨ — يوضع أمامك. اضغطي على الأثاث لتدويره • وضع 🧹 + ضغط لحذفه.</p>`;
    pbody.querySelectorAll('[data-f]').forEach(d => d.onclick = () => { S.selFurn = d.dataset.f; S.delMode = false; sndPop(); renderPanel(); toast(`${FURN[d.dataset.f].e} اخترتِ ${FURN[d.dataset.f].n}! اضغطي ✨`); });
    $('f-place').onclick = () => {
      const fx = Math.round(player.position.x - Math.sin(yaw) * 2.2), fz = Math.round(player.position.z - Math.cos(yaw) * 2.2);
      if (Math.abs(fx) > R || Math.abs(fz) > R || solidAt(fx, 0, fz) || solidAt(fx, 1, fz)) { toast('مكان مشغول! 🧱'); return; }
      addFurniture(S.selFurn, fx, fz, 0); sndPlace(); S.coins = Math.max(0, S.coins - 2); S.xp += 2; checkLevel(); updateHUD(); save();
    };
    $('b-del').onclick = () => { S.delMode = !S.delMode; sndPop(); renderPanel(); };
  }
  else if (t === 'food') {
    ptitle.textContent = '🍰 اطبخي وتذوّقي!';
    pbody.innerHTML = invHTML() + `<div class="taste-big">🧁😋🍰</div>` +
      RECIPES.map(r => `<div class="item" style="display:flex;align-items:center;gap:8px;margin-bottom:6px;text-align:right" data-r="${r.id}">
        <span class="em" style="font-size:34px">${r.e}</span>
        <span style="flex:1"><b>${r.n}</b><br><small>${Object.entries(r.need).map(([k, v]) => v + ' ' + k).join(' + ')} ${canCook(r) ? '✅' : '🔒'}</small></span>
        <span>👩‍🍳</span></div>`).join('') +
      `<button class="yum-btn" id="taste-btn">😋 تذوّقي! (${S.sweets} حلويات) +💖</button>
       <p style="font-size:12px">اقطفي 🍓🫐🥛🍫🍬 من الحديقة، اطبخي، ثم تذوّقي للقلوب والعملات! 💖</p>`;
    pbody.querySelectorAll('[data-r]').forEach(d => d.onclick = () => cook(RECIPES.find(r => r.id === d.dataset.r)));
    $('taste-btn').onclick = () => taste();
  }
  else if (t === 'dress') {
    const dresses = ['الأميرة الوردية', 'ملكة البنفسج', 'جنية الثلج', 'نجمة العسل', 'ملاك النعناع', 'قلب الياقوت', 'عروس الثلج', 'نجمة الليل', 'فتاة الشمس', 'البرسيم', 'الخدود', 'الليلك'];
    const hairs = ['طويل', 'قصير', 'ضفيرتان', 'كعكة', 'منسدل', 'شعر التاج', 'أميرة', 'يونيكورن'];
    const accs = [['crown', '👑 تاج'], ['bow', '🎀 فيونكة'], ['wings', '🧚 أجنحة'], ['halo', '😇 هالة'], ['cap', '🧢 قبعة'], ['none', '— بدون']];
    ptitle.textContent = '👗 غرفة ملابس ماريا';
    pbody.innerHTML = `<div style="text-align:center;font-size:54px">👧💖</div>` +
      `<b>👗 الفستان (${dresses[S.dress.dress % dresses.length]})</b><div class="grid">` + dresses.map((d, i) => `<div class="item ${S.dress.dress === i ? 'sel' : ''}" data-d="${i}">${['💖', '💜', '🩵', '🧡', '💚', '❤️', '🤍', '🖤', '💛', '💚', '🩷', '💜'][i]}<br>${d}</div>`).join('') + `</div>` +
      `<b>💇‍♀️ الشعر</b><div class="grid">` + hairs.map((h, i) => `<div class="item ${S.dress.hair === i ? 'sel' : ''}" data-h="${i}">💇‍♀️<br>${h}</div>`).join('') + `</div>` +
      `<b>🎀 لون الشعر</b><div class="grid">` + ['#6b3a1f', '#111111', '#ffdd55', '#ff7ebb', '#b388ff', '#ffffff', '#ff5522'].map(c => `<div class="item ${S.dress.hairColor === c ? 'sel' : ''}" data-c="${c}"><span class="em">🎨</span><span style="color:${c}">●●●</span></div>`).join('') + `</div>` +
      `<b>✨ إكسسوار</b><div class="grid">` + accs.map(([k, n]) => `<div class="item ${S.dress.accessory === k ? 'sel' : ''}" data-a="${k}">${n}</div>`).join('') + `</div>`;
    pbody.querySelectorAll('[data-d]').forEach(d => d.onclick = () => { S.dress.dress = +d.dataset.d; buildGirl(); sndPop(); renderPanel(); save(); if (questStep === 4) updateQuest(5); });
    pbody.querySelectorAll('[data-h]').forEach(d => d.onclick = () => { S.dress.hair = +d.dataset.h; buildGirl(); sndPop(); renderPanel(); save(); });
    pbody.querySelectorAll('[data-c]').forEach(d => d.onclick = () => { S.dress.hairColor = d.dataset.c; buildGirl(); sndPop(); renderPanel(); save(); });
    pbody.querySelectorAll('[data-a]').forEach(d => d.onclick = () => { S.dress.accessory = d.dataset.a; buildGirl(); sndPop(); renderPanel(); save(); });
  }
  else if (t === 'pets') {
    ptitle.textContent = '🐄 الحيوانات';
    const PETS = [['cat', '🐱', 'قطة', 30], ['bunny', '🐰', 'أرنب', 30], ['puppy', '🐶', 'جرو', 40], ['unicorn', '🦄', 'يونيكورن', 80]];
    pbody.innerHTML = invHTML() + `<div class="inv">🐄 حيوانات المزرعة: بقرة 🐄 خروف 🐑 خنزير 🐷 دجاجة 🐔 حصان 🐴<br>اضغطي على أي حيوان في العالم لإطعامه (🌾🥕🍎) فيتبعك ويحبك! 💖</div><div class="grid">` + PETS.map(([k, e, n, c]) => {
      const owned = S.pets.includes(k);
      return `<div class="item ${owned ? 'sel' : ''}" data-p="${k}"><span class="em">${e}</span>${n}<div class="cost">${owned ? '💖 معك!' : c + '💰'}</div></div>`; }).join('') + `</div>
      <p style="font-size:12px">الحيوانات الأليفة تتبعك في كل مكان! 🐾</p>`;
    pbody.querySelectorAll('[data-p]').forEach(d => d.onclick = () => {
      const k = d.dataset.p;
      if (S.pets.includes(k)) { S.pets = S.pets.filter(p => p !== k); toast('الحيوان عاد للبيت 🏠'); }
      else {
        const cost = { cat: 30, bunny: 30, puppy: 40, unicorn: 80 }[k];
        if (S.coins < cost) { toast(`تحتاجين ${cost}💰! تذوّقي الحلويات لتربحي! 😋`); return; }
        S.coins -= cost; S.pets.push(k); sndCoin(); flyHearts(6); toast('صديق جديد يتبعك! 💖');
      }
      spawnPets(); updateHUD(); renderPanel(); save();
    });
  }
  else {
    ptitle.textContent = '🌸 عالمي';
    pbody.innerHTML = `<div class="inv">👧 <b>عالم ${S.name}</b> • يوم ${S.day} • 🧱${S.voxels.length} مكعباً 🛏️${S.furniture.length} أثاث 🐾${S.pets.length}</div>
      <div class="grid">
        <div class="item" data-w="castle">🏰<br>القصر</div>
        <div class="item" data-w="cafe">🍰<br>الكافيه</div>
        <div class="item" data-w="home">🛏️<br>البيت</div>
        <div class="item" data-w="garden">🌸<br>الحديقة</div>
        <div class="item" data-w="day">☀️<br>نهار</div>
        <div class="item" data-w="night">🌙<br>ليل</div>
      </div>
      <div class="row-btns"><button id="w-view" class="primary">📷 كاميرا: ${S.view === 'third' ? 'خلفية' : 'أولى'}</button><button id="w-music">${S.music ? '🔇 إيقاف الموسيقى' : '🎵 تشغيل الموسيقى'}</button></div>
      <div class="row-btns"><button id="w-save">💾 حفظ</button><button id="w-name">✏️ الاسم</button></div>
      <div class="row-btns"><button id="w-photo">📸 صورة</button><button id="w-help">❓ مساعدة</button></div>`;
    pbody.querySelectorAll('[data-w]').forEach(d => d.onclick = () => {
      const w = d.dataset.w; sndPop();
      if (w === 'castle') player.position.set(0, 0, -6);
      if (w === 'cafe') player.position.set(12, 0, 2);
      if (w === 'home') player.position.set(-12, 0, 2);
      if (w === 'garden') player.position.set(11, 0, -3);
      if (w === 'day') S.night = false; if (w === 'night') S.night = true;
    });
    $('w-view').onclick = () => { toggleView(); renderPanel(); };
    $('w-music').onclick = () => { S.music = !S.music; musicLoop(); updateHUD(); renderPanel(); };
    $('w-photo').onclick = () => photo();
    $('w-help').onclick = () => $('modal').classList.remove('hidden');
    $('w-save').onclick = () => { save(); toast('حُفظ! 💾 العبي أونلاين من أي مكان! 🌐'); sndCoin(); };
    $('w-name').onclick = () => { const n = prompt('اسمك:', S.name); if (n && n.trim()) { playerName = n.trim().slice(0, 16); S.name = playerName; $('player-name').value = playerName; updateHUD(); save(); toast(`أهلاً ${playerName}! 💖`); } };
  }
}
function toggleView() { S.view = S.view === 'third' ? 'first' : 'third'; player.visible = S.view === 'third'; toast(S.view === 'third' ? '📷 كاميرا خلفية (ترين ماريا الجميلة 💖)' : '📷 منظور أول (مثل ماين كرافت!)'); }

// ---------------- TOP BUTTONS ----------------
$('btn-view').onclick = () => toggleView();
$('btn-music').onclick = () => { S.music = !S.music; musicLoop(); updateHUD(); if (S.tool === 'world') renderPanel(); };
function photo() {
  renderer.render(scene, camera);
  const a = document.createElement('a'); a.download = `maria-crafts-${Date.now()}.png`; a.href = renderer.domElement.toDataURL('image/png'); a.click();
  toast('📸 صورة جميلة! أريها صديقاتك! 💖'); sndCoin();
}
$('btn-help').onclick = () => $('modal').classList.remove('hidden');
$('modal-ok').onclick = () => $('modal').classList.add('hidden');
$('modal').addEventListener('click', e => { if (e.target.id === 'modal') $('modal').classList.add('hidden'); });
$('btn-save').onclick = () => { save(); toast('حُفظ! 💾'); sndCoin(); };

// ---------------- START ----------------
$('btn-start').onclick = () => {
  playerName = ($('player-name').value.trim() || 'Maria').slice(0, 16);
  S.name = playerName; save(); updateHUD(); updateQuest();
  $('boot').classList.add('gone');
  beep(800, .15); setTimeout(() => beep(1000, .2), 150);
  toast(`أهلاً بك في عالمك يا ${playerName}! 💖🏰 ادخلي القصر من الباب 🚪`);
  openPanel('build');
};

// ---------------- COLLISION + MOVE ----------------
function collide(px, pz, feetY) {
  // voxel walls at feet & head
  const y0 = Math.floor(feetY + 0.35), y1 = Math.floor(feetY + 1.5);
  for (const [ox, oz] of [[0, 0], [0.32, 0], [-0.32, 0], [0, 0.32], [0, -0.32]]) {
    if (solidAt(px + ox, y0, pz + oz) || solidAt(px + ox, y1, pz + oz)) return true;
  }
  for (const c of simpleColliders) if (Math.hypot(px - c.x, pz - c.z) < c.r) return true;
  return false;
}

// ---------------- MAIN LOOP ----------------
const clock = new THREE.Clock();
let walk = 0, blinkT = 0;
function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);
  const now = performance.now();
  // day cycle
  if (!S.night) { S.dayTime += dt * 0.004; if (S.dayTime > 1) { S.dayTime = 0; S.day++; updateHUD(); toast(`☀️ صباح الخير! اليوم ${S.day} 💖`); } }
  const t = S.night ? 0 : S.dayTime;
  sun.intensity = S.night ? 0.08 : 0.5 + 1.0 * Math.sin(t * Math.PI);
  moonL.intensity = S.night ? 0.5 : 0;
  scene.background.set(S.night ? 0x1a1440 : 0x9adcff); scene.fog.color.set(S.night ? 0x1a1440 : 0x9adcff);
  hemi.intensity = S.night ? 0.3 : 0.95;
  clouds.forEach((c, i) => { c.position.x += dt * (0.4 + i * 0.1); if (c.position.x > 42) c.position.x = -42; });
  pickups.forEach((p, i) => { if (p.alive) { p.fruit.position.y = 1.25 + Math.sin(now * 0.003 + i) * 0.12; p.fruit.rotation.y += dt; } });
  doors.forEach(d => { d.leaf.rotation.y += ((d.open ? -1.9 : 0) - d.leaf.rotation.y) * Math.min(1, dt * 6); });

  // movement input
  let mx = 0, mz = 0;
  if (keys.KeyW || keys.ArrowUp) mz -= 1; if (keys.KeyS || keys.ArrowDown) mz += 1;
  if (keys.KeyA || keys.ArrowLeft) mx -= 1; if (keys.KeyD || keys.ArrowRight) mx += 1;
  mx += joy.x; mz += joy.y;
  const len = Math.hypot(mx, mz);
  let moving = false;
  if (len > 0.15) {
    moving = true;
    const sp = 6.5;
    const fx = -Math.sin(yaw), fz = -Math.cos(yaw);
    const rx = Math.cos(yaw), rz = -Math.sin(yaw);
    let dx = (fx * -mz + rx * mx), dz = (fz * -mz + rz * mx);
    const dl = Math.hypot(dx, dz) || 1; dx /= dl; dz /= dl;
    let nx = player.position.x + dx * sp * dt;
    let nz = player.position.z + dz * sp * dt;
    const rr = Math.hypot(nx, nz); if (rr > R + 0.5) { nx *= (R + 0.5) / rr; nz *= (R + 0.5) / rr; }
    if (!collide(nx, player.position.z, py)) player.position.x = nx;
    if (!collide(player.position.x, nz, py)) player.position.z = nz;
    player.rotation.y = Math.atan2(dx, dz);
    walk += dt * 11;
    const s = Math.sin(walk);
    if (P.parts.legL) {
      P.parts.legL.rotation.x = s * 0.7; P.parts.legR.rotation.x = -s * 0.7;
      P.parts.armL.rotation.x = -s * 0.6; P.parts.armR.rotation.x = s * 0.6;
      P.parts.skirt.rotation.y = s * 0.06; P.parts.pony.rotation.x = 0.35 + Math.abs(s) * 0.25;
    }
  } else if (P.parts.legL) {
    P.parts.legL.rotation.x *= 0.85; P.parts.legR.rotation.x *= 0.85;
    P.parts.armL.rotation.x = Math.sin(now * 0.002) * 0.06; P.parts.armR.rotation.x = -Math.sin(now * 0.002) * 0.06;
  }
  // gravity + support (stand on voxels)
  const sup = topAt(player.position.x, player.position.z);
  vy -= 22 * dt; py += vy * dt;
  if (py <= sup) { py = sup; vy = 0; }
  if (py < -1.2) { py = 0; player.position.set(0, 0, 8); toast('عدتِ للبيت! 🏠'); }
  player.position.y = py;
  // blink
  blinkT += dt;
  if (blinkT > 3.5) { blinkT = 0; player.scale.y = 0.97; setTimeout(() => player.scale.y = 1, 130); }
  checkHouseEnter();

  // animals AI (wander / graze / follow loved player)
  animals.forEach((a, i) => {
    a.timer -= dt;
    const px = player.position.x, pz = player.position.z;
    const dp = Math.hypot(a.g.position.x - px, a.g.position.z - pz);
    let speed = 0;
    if (a.followT > 0) {
      a.followT -= dt;
      if (dp > 2.2) { a.tx = px; a.tz = pz; speed = 2.6; }
      else { a.tx = a.g.position.x; a.tz = a.g.position.z; speed = 0; if (Math.random() < dt * 0.5) flyHeartsOnce(a); }
    } else if (a.timer <= 0) {
      a.timer = 3 + Math.random() * 6;
      if (Math.random() < 0.65) { a.tx = a.g.position.x + (Math.random() - .5) * 10; a.tz = a.g.position.z + (Math.random() - .5) * 10; }
      else { a.tx = a.g.position.x; a.tz = a.g.position.z; }
      a.grazing = Math.random() < 0.4;
    }
    const dx = a.tx - a.g.position.x, dz = a.tz - a.g.position.z;
    const dd = Math.hypot(dx, dz);
    if (dd > 0.4 && !(a.followT > 0 && dp <= 2.2)) {
      let nx = a.g.position.x + dx / dd * 1.4 * dt * (a.followT > 0 ? 1.8 : 1);
      let nz = a.g.position.z + dz / dd * 1.4 * dt * (a.followT > 0 ? 1.8 : 1);
      if (Math.hypot(nx, nz) < R - 1 && !solidAt(nx, 0, nz) && !solidAt(nx, 1, nz)) { a.g.position.x = nx; a.g.position.z = nz; }
      a.g.rotation.y = Math.atan2(dx, dz);
      a.walk = (a.walk || 0) + dt * 8; speed = 1;
    }
    const s2 = Math.sin(a.walk || 0);
    a.legs.forEach((l, li) => l.rotation.x = (li % 2 ? s2 : -s2) * (speed ? 0.6 : 0));
    if (a.head) a.head.rotation.x = a.grazing && !speed ? 0.55 : Math.sin(now * 0.001 + i) * 0.08;
    if (a.tail) a.tail.rotation.z = Math.sin(now * 0.004 + i * 2) * 0.4;
  });
  // pets follow
  petMeshes.forEach((p, i) => {
    const tx = player.position.x - Math.sin(player.rotation.y) * (1.6 + i * 0.8);
    const tz = player.position.z - Math.cos(player.rotation.y) * (1.6 + i * 0.8);
    p.g.position.x += (tx - p.g.position.x) * Math.min(1, dt * 3);
    p.g.position.z += (tz - p.g.position.z) * Math.min(1, dt * 3);
    p.g.position.y = py + Math.abs(Math.sin(now * 0.005 + i)) * 0.15;
    p.g.rotation.y = Math.atan2(player.position.x - p.g.position.x, player.position.z - p.g.position.z);
  });

  updateTargetThrottled();
  // camera
  if (S.view === 'first') {
    const hx = player.position.x - Math.sin(yaw) * 0.2, hz = player.position.z - Math.cos(yaw) * 0.2;
    camera.position.set(hx, py + 2.7, hz);
    camera.lookAt(hx - Math.sin(yaw) * 5, py + 2.4 - camPitch * 4, hz - Math.cos(yaw) * 5);
  } else {
    const cx = player.position.x + Math.sin(yaw) * camDist * Math.cos(camPitch);
    const cz = player.position.z + Math.cos(yaw) * camDist * Math.cos(camPitch);
    const cy = py + 2 + Math.sin(camPitch) * camDist;
    camera.position.lerp(new THREE.Vector3(cx, Math.max(1.2, cy), cz), 0.14);
    camera.lookAt(player.position.x, py + 1.8, player.position.z);
  }
  renderer.render(scene, camera);
}
let heartOnce = 0;
function flyHeartsOnce(a) {
  if (now2() - heartOnce < 3000) return; heartOnce = now2();
  flyHearts(1);
}
function now2() { return performance.now(); }
animate();

addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
updateHUD(); renderPanel(); panel.classList.add('hidden');
document.addEventListener('gesturestart', e => e.preventDefault());
