import * as THREE from 'three';
/* =====================================================
   باركور الأبطال — 220 مرحلة + قصر الاحتفال والزفاف
   ===================================================== */
const $ = id => document.getElementById(id);
const TOTAL = 220;
const SAVE_KEY = 'parkour_heroes_v1';
let save = { unlocked: 1, stars: {}, coins: 0, gifts: [], deaths: 0 };
try { const s = JSON.parse(localStorage.getItem(SAVE_KEY)); if (s && s.unlocked) save = Object.assign(save, s); } catch(e){}
function persist(){ try{ localStorage.setItem(SAVE_KEY, JSON.stringify(save)); }catch(e){} }
function toast(t, ms=2200){ const d=document.createElement('div'); d.className='toast'; d.textContent=t; $('toast').appendChild(d); setTimeout(()=>d.remove(), ms); }
function mulberry(seed){ return function(){ seed|=0; seed=seed+0x6D2B79F5|0; let t=Math.imul(seed^seed>>>15,1|seed); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }

/* ---------- الصوت ---------- */
let AC=null, muted=false;
function ac(){ if(!AC){ try{ AC=new (window.AudioContext||window.webkitAudioContext)(); }catch(e){} } if(AC&&AC.state==='suspended') AC.resume(); return AC; }
function beep(f=600,d=0.12,type='sine',v=0.25){ if(muted) return; const c=ac(); if(!c) return;
  const o=c.createOscillator(), g=c.createGain(); o.type=type; o.frequency.value=f; g.gain.value=v;
  g.gain.exponentialRampToValueAtTime(0.001, c.currentTime+d); o.connect(g); g.connect(c.destination); o.start(); o.stop(c.currentTime+d); }
const sJump=()=>beep(500+Math.random()*200,0.12,'square',0.12);
const sCoin=()=>{beep(900,0.09,'sine',0.2); setTimeout(()=>beep(1350,0.12,'sine',0.2),70);};
const sDie=()=>beep(160,0.3,'sawtooth',0.2);
const sWin=()=>{[523,659,784,1046].forEach((f,i)=>setTimeout(()=>beep(f,0.22,'triangle',0.25),i*130));};
const sCheck=()=>{beep(700,0.1,'triangle',0.2); setTimeout(()=>beep(1050,0.15,'triangle',0.2),90);};
function crowdCheer(dur=3){ if(muted) return; const c=ac(); if(!c) return;
  const len=c.sampleRate*dur, buf=c.createBuffer(1,len,c.sampleRate), ch=buf.getChannelData(0);
  for(let i=0;i<len;i++) ch[i]=(Math.random()*2-1)*(1-i/len)*0.5;
  const src=c.createBufferSource(); src.buffer=buf;
  const f=c.createBiquadFilter(); f.type='bandpass'; f.frequency.value=1200;
  const g=c.createGain(); g.gain.value=0.6; src.connect(f); f.connect(g); g.connect(c.destination); src.start();
  [660,880,990,1320].forEach((fr,i)=>setTimeout(()=>beep(fr,0.18,'sawtooth',0.08),i*220));
}
function speakCongrats(text){ try{ if(muted) return; const u=new SpeechSynthesisUtterance(text); u.lang='ar-SA'; u.rate=1; speechSynthesis.cancel(); speechSynthesis.speak(u);}catch(e){} }

/* ---------- القرآن ---------- */
const QURAN_URLS=[
 'https://cdn.islamic.network/quran/audio/128/ar.alafasy/1.mp3',
 'https://cdn.islamic.network/quran/audio/128/ar.alafasy/112.mp3',
 'https://cdn.islamic.network/quran/audio/128/ar.alafasy/113.mp3',
 'https://cdn.islamic.network/quran/audio/128/ar.alafasy/114.mp3'
];
let quranIdx=0, quranOn=false;
function quranPlay(){ const a=$('quran'); if(!a) return; a.src=QURAN_URLS[quranIdx%QURAN_URLS.length];
  a.volume=0.9; a.play().then(()=>{ quranOn=true; updQuran(); toast('📖 يتلى الآن القرآن الكريم — بارك الله فيك 🤲'); }).catch(()=>{ toast('📖 اضغط مرة أخرى لتشغيل القرآن (المتصفح منع التشغيل التلقائي)'); }); }
function quranStop(){ const a=$('quran'); a.pause(); quranOn=false; updQuran(); }
function quranToggle(){ const a=$('quran'); if(a.paused) quranPlay(); else quranStop(); }
function updQuran(){ const t=quranOn?'يعمل 🔊':'متوقف'; $('quran-state').textContent=t; }
$('quran').addEventListener('ended',()=>{ quranIdx++; if(quranOn) quranPlay(); });
$('quran').addEventListener('error',()=>{ quranIdx++; if(quranOn){ const a=$('quran'); a.src=QURAN_URLS[quranIdx%QURAN_URLS.length]; a.play().catch(()=>{}); } });

/* ---------- صعوبة / ثيم ---------- */
function diffOf(lv){ if(lv<=30) return {e:'🟢 سهل',c:'d1'}; if(lv<=80) return {e:'🟡 متوسط',c:'d2'}; if(lv<=140) return {e:'🟠 صعب',c:'d3'}; if(lv<=199) return {e:'🔴 أسطوري',c:'d4'}; return {e:'👑 ملكي 👑',c:'d5'}; }
function themeOf(lv){
  if(lv<=30) return {sky:0x87ceeb,fog:0x87ceeb,ground:0x3fbf5a,plat:0xffffff,neon:false,name:'🌳 حديقة البداية'};
  if(lv<=80) return {sky:0xff9d5c,fog:0xffb37a,ground:0xd9a05b,plat:0xfff2cc,neon:false,name:'🏜️ غروب الصحراء'};
  if(lv<=140) return {sky:0x0b1026,fog:0x141b3d,ground:0x11162e,plat:0x22d3ee,neon:true,name:'🌃 مدينة النيون'};
  if(lv<=180) return {sky:0x2b0a0a,fog:0x431111,ground:0x3d1515,plat:0xff6b35,neon:true,name:'🌋 بركان النار'};
  if(lv<=199) return {sky:0x9fd8ff,fog:0xc4e6ff,ground:0xe8f4ff,plat:0x9fd8ff,neon:false,name:'❄️ عاصفة الثلج'};
  return {sky:0x1a1040,fog:0x2b1a5e,ground:0xd4af37,plat:0xffdf5e,neon:true,name:'👑 الجنة الذهبية'};
}

/* ---------- توليد المرحلة ---------- */
function genLevel(lv){
  const R=mulberry(lv*7919+13);
  const count=Math.min(36, 10+Math.floor(lv*0.11));
  const width=Math.max(1.15, 3.4-lv*0.009);
  const gapBase=Math.min(6.6, 2.1+lv*0.021);
  const moveRatio=Math.min(0.75, lv/260);
  const spinRatio=Math.min(0.6, Math.max(0,(lv-25)/220));
  const vanishRatio=Math.min(0.5, Math.max(0,(lv-50)/260));
  const narrowEvery= lv>60 ? 4 : 99;
  const plats=[]; let x=0,y=0,z=0;
  plats.push({x:0,y:0,z:0,w:6,d:6,type:'start'});
  for(let i=1;i<=count;i++){
    const gap=gapBase*(0.8+R()*0.7);
    const turn=(R()-0.5)*(lv>40?7:3.5);
    x+=turn; z-=gap;
    y+= (R()-0.42)*(lv>20?3.2:1.6);
    y=Math.max(-4,Math.min(10,y));
    let w=width*(0.85+R()*0.5), d=width*(0.9+R()*0.5);
    if(i%narrowEvery===0){ w*=0.55; }
    let type='static';
    const r=R();
    if(i>2 && r<moveRatio) type = R()<0.5?'moveX':'moveZ';
    else if(i>3 && r<moveRatio+spinRatio*0.5) type='spin';
    else if(i>4 && r<moveRatio+spinRatio*0.5+vanishRatio*0.6) type='vanish';
    else if(R()<0.12 && lv>15) type='bounce';
    else if(R()<0.10 && lv>35) type='ice';
    plats.push({x,y,z,w,d,type,
      amp:1.5+Math.min(4,lv*0.015)+R()*2, speed:Math.min(4.2,0.6+lv*0.018)+R(),
      spin: (1.2+Math.min(4,lv*0.02))*(R()<0.5?1:-1),
      phase:R()*Math.PI*2});
    if(i%5===0 || i===Math.floor(count/2)) plats[plats.length-1].checkpoint=true;
  }
  plats.push({x:x+(R()-0.5)*4, y:y, z:z-gapBase, w:7, d:7, type:'finish'});
  const coins=[];
  for(let i=1;i<plats.length-1;i+=2){ const p=plats[i]; coins.push({x:p.x,y:p.y+1.6,z:p.z,taken:false}); }
  return {plats,coins,count};
}

/* =====================================================
   محرك اللعب
===================================================== */
const Game={
  active:false, lv:1, data:null, scene:null, camera:null, renderer:null,
  player:null, bodyMat:[], plats:[], coinsM:[], spinners:[], parts:[], fireworks:[],
  vel:new THREE.Vector3(), grounded:false, spawn:new THREE.Vector3(0,1.5,0),
  checkSpawn:null, yaw:Math.PI, deaths:0, coins:0, time:0, coyote:0, jumpBuf:0,
  keys:{}, joy:{x:0,y:0}, jumpQ:false, camDrag:false, shake:0, combo:0, comboT:0, raf:0, last:0, clock:0, quality:true
};
function initRenderer(canvas, quality){
  const r=new THREE.WebGLRenderer({canvas, antialias:true});
  r.setPixelRatio(Math.min(window.devicePixelRatio||1, quality?2:1.25));
  r.setSize(window.innerWidth, window.innerHeight);
  r.shadowMap.enabled=!!quality;
  r.shadowMap.type=THREE.PCFSoftShadowMap;
  return r;
}
function makePlayer(){
  const g=new THREE.Group();
  const skin=new THREE.MeshStandardMaterial({color:0xff6b35,roughness:.5});
  const shirt=new THREE.MeshStandardMaterial({color:0x2563eb,roughness:.5});
  const legs=new THREE.MeshStandardMaterial({color:0x111827,roughness:.6});
  const head=new THREE.Mesh(new THREE.SphereGeometry(0.32,20,20),skin); head.position.y=1.55; head.castShadow=true;
  const eyeM=new THREE.MeshBasicMaterial({color:0x111111});
  const e1=new THREE.Mesh(new THREE.SphereGeometry(0.05,8,8),eyeM); e1.position.set(-0.11,1.6,-0.27);
  const e2=e1.clone(); e2.position.x=0.11; g.add(e1,e2);
  const body=new THREE.Mesh(new THREE.CylinderGeometry(0.26,0.3,0.7,14),shirt); body.position.y=1.0; body.castShadow=true;
  const l1=new THREE.Mesh(new THREE.CylinderGeometry(0.1,0.1,0.55,8),legs); l1.position.set(-0.13,0.45,0);
  const l2=l1.clone(); l2.position.x=0.13;
  const a1=new THREE.Mesh(new THREE.CylinderGeometry(0.08,0.08,0.5,8),shirt); a1.position.set(-0.36,1.05,0); a1.rotation.z=0.25;
  const a2=a1.clone(); a2.position.x=0.36; a2.rotation.z=-0.25;
  const crown=new THREE.Mesh(new THREE.CylinderGeometry(0.16,0.2,0.16,8),new THREE.MeshStandardMaterial({color:0xf2b705,metalness:.8,roughness:.2}));
  crown.position.y=1.92; crown.visible=false; crown.name='crown';
  g.add(head,body,l1,l2,a1,a2,crown);
  g.userData={l1,l2,a1,a2};
  // هالة + ظل
  const ring=new THREE.Mesh(new THREE.TorusGeometry(0.45,0.05,8,24),new THREE.MeshBasicMaterial({color:0xf2b705,transparent:true,opacity:0.8}));
  ring.rotation.x=Math.PI/2; ring.position.y=0.08; g.add(ring);
  return g;
}
function addClouds(scene,R,n=14){
  const m=new THREE.MeshLambertMaterial({color:0xffffff,transparent:true,opacity:0.85});
  for(let i=0;i<n;i++){ const g=new THREE.Group();
    for(let j=0;j<3;j++){ const s=new THREE.Mesh(new THREE.SphereGeometry(2+R()*3,10,10),m); s.position.set(j*3-3,R()*1.5,0); g.add(s); }
    g.position.set((R()-0.5)*160, 25+R()*25, -R()*220); scene.add(g); Game.parts.push({m:g,cloud:true,speed:0.3+R()}); }
}
function buildLevel(lv){
  // تنظيف (مع الحفاظ على مجسم اللاعب)
  if(Game.player && Game.player.parent) Game.player.parent.remove(Game.player);
  if(Game.scene){ Game.scene.traverse(o=>{ if(o.geometry) o.geometry.dispose(); if(o.material && o.material.map) o.material.map.dispose(); }); }
  Game.scene=new THREE.Scene();
  const th=themeOf(lv);
  Game.scene.background=new THREE.Color(th.sky);
  Game.scene.fog=new THREE.Fog(th.fog, 40, 190);
  Game.camera=new THREE.PerspectiveCamera(62, innerWidth/innerHeight, 0.1, 600);
  const hemi=new THREE.HemisphereLight(0xffffff, 0x334155, th.neon?0.9:1.15); Game.scene.add(hemi);
  const sun=new THREE.DirectionalLight(0xffffff, th.neon?1.1:1.6);
  sun.position.set(20,40,10); if(Game.quality){ sun.castShadow=true; sun.shadow.camera.left=-40; sun.shadow.camera.right=40; sun.shadow.camera.top=40; sun.shadow.camera.bottom=-40; sun.shadow.mapSize.set(1024,1024);} Game.scene.add(sun);
  // أرضية بعيدة + ماء/حمم حية
  const gcol = th.ground;
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(600,600), new THREE.MeshStandardMaterial({color:gcol,roughness:1}));
  floor.rotation.x=-Math.PI/2; floor.position.y=-16; Game.scene.add(floor);
  const R=mulberry(99);
  addClouds(Game.scene,R, lv>100?18:12);
  Game.plats=[]; Game.coinsM=[]; Game.spinners=[]; Game.fireworks=[]; Game.parts=Game.parts.filter(p=>p.cloud);
  const data=genLevel(lv); Game.data=data;
  const platBase=new THREE.BoxGeometry(1,0.6,1);
  data.plats.forEach((p,idx)=>{
    let color=th.plat;
    if(p.type==='start') color=0x22c55e; if(p.type==='finish') color=0xf2b705;
    if(p.type==='bounce') color=0xec4899; if(p.type==='ice') color=0xa5f3fc; if(p.type==='vanish') color=0xa78bfa;
    const mat=new THREE.MeshStandardMaterial({color, roughness:.55, metalness: th.neon?0.35:0.05, emissive: th.neon?color:0x000000, emissiveIntensity: th.neon?0.25:0});
    const m=new THREE.Mesh(platBase, mat);
    m.scale.set(p.w,1,p.d); m.position.set(p.x,p.y,p.z);
    m.castShadow=Game.quality; m.receiveShadow=true;
    Game.scene.add(m);
    // حافة مضيئة
    const edge=new THREE.LineSegments(new THREE.EdgesGeometry(platBase), new THREE.LineBasicMaterial({color: th.neon?0xffffff:0x0b1020, transparent:true, opacity:.6}));
    edge.scale.copy(m.scale); edge.position.copy(m.position); Game.scene.add(edge);
    const rec={def:p, mesh:m, edge, cx:p.x, cy:p.y, cz:p.z, dx:0, vis:true, timer:Math.random()*3};
    Game.plats.push(rec);
    if(p.type==='spin'){
      const bar=new THREE.Mesh(new THREE.BoxGeometry(Math.max(4,p.w+3.5),0.35,0.35), new THREE.MeshStandardMaterial({color:0xef4444,emissive:0xef4444,emissiveIntensity:.6}));
      bar.position.set(p.x,p.y+0.9,p.z); bar.castShadow=true; Game.scene.add(bar);
      Game.spinners.push({mesh:bar, cx:p.x, cy:p.y+0.9, cz:p.z, ang:p.phase, speed:p.spin, len:Math.max(4,p.w+3.5)});
    }
    if(p.checkpoint){
      const pole=new THREE.Mesh(new THREE.CylinderGeometry(0.08,0.08,3,8), new THREE.MeshStandardMaterial({color:0xffffff}));
      pole.position.set(p.x+p.w/2-0.3,p.y+1.8,p.z); Game.scene.add(pole);
      const flag=new THREE.Mesh(new THREE.PlaneGeometry(1.1,0.7), new THREE.MeshBasicMaterial({color:0x22c55e,side:THREE.DoubleSide}));
      flag.position.set(p.x+p.w/2-0.85,p.y+2.9,p.z); Game.scene.add(flag); rec.flag=flag;
    }
    if(p.type==='finish'){
      const gate=new THREE.Mesh(new THREE.TorusGeometry(2.2,0.35,12,32), new THREE.MeshStandardMaterial({color:0xf2b705,emissive:0xf2b705,emissiveIntensity:.9,metalness:.7,roughness:.2}));
      gate.position.set(p.x,p.y+2.6,p.z); Game.scene.add(gate); rec.gate=gate;
      const txt=makeTextSprite('🏁 النهاية 🏁','#f2b705'); txt.position.set(p.x,p.y+5.6,p.z); txt.scale.set(8,2,1); Game.scene.add(txt);
    }
  });
  // عملات
  const coinGeo=new THREE.CylinderGeometry(0.4,0.4,0.12,18);
  data.coins.forEach(c=>{
    const m=new THREE.Mesh(coinGeo, new THREE.MeshStandardMaterial({color:0xffd23f,metalness:.8,roughness:.2,emissive:0xaa7700,emissiveIntensity:.4}));
    m.rotation.x=Math.PI/2; m.position.set(c.x,c.y,c.z); Game.scene.add(m); Game.coinsM.push({def:c,mesh:m});
  });
  // اللاعب
  if(!Game.player){ Game.player=makePlayer(); }
  Game.scene.add(Game.player);
  const s=data.plats[0]; Game.spawn.set(s.x, s.y+1.6, s.z); Game.checkSpawn=null;
  Game.player.position.copy(Game.spawn); Game.vel.set(0,0,0);
  Game.deaths=0; Game.coins=0; Game.time=0; Game.combo=0;
  $('hud-deaths').textContent='0'; $('hud-coins').textContent='0';
  $('hud-level').textContent=`المرحلة ${lv} / ${TOTAL}`;
  $('hud-diff').textContent=`${diffOf(lv).e} • ${th.name}`;
  $('hud-msg').textContent= lv>=200?'👑 المراحل الملكية! النهاية قريبة — أنت بطل!': lv>1?`🏁 اجري نحو البوابة! صعوبة أعلى من المرحلة ${lv-1} 🔥`:'🏁 اجري نحو البوابة الذهبية!';
  if(lv>=200) Game.player.getObjectByName('crown').visible=true;
}
function makeTextSprite(text,color='#fff'){
  const cv=document.createElement('canvas'); cv.width=512; cv.height=128;
  const x=cv.getContext('2d'); x.font='bold 56px Arial'; x.textAlign='center'; x.textBaseline='middle';
  x.shadowColor='#000'; x.shadowBlur=12; x.fillStyle=color; x.fillText(text,256,64);
  const t=new THREE.CanvasTexture(cv); return new THREE.Sprite(new THREE.SpriteMaterial({map:t,transparent:true,depthWrite:false}));
}
// جزيئات الغبار
let dustPool=[];
function puff(pos,color=0xffffff,n=8){
  if(!Game.scene) return;
  for(let i=0;i<n;i++){ const m=new THREE.Mesh(new THREE.SphereGeometry(0.09+Math.random()*0.1,6,6), new THREE.MeshBasicMaterial({color,transparent:true,opacity:0.9}));
    m.position.copy(pos); m.position.y+=0.2;
    Game.scene.add(m);
    Game.parts.push({m, vx:(Math.random()-0.5)*6, vy:Math.random()*5+1, vz:(Math.random()-0.5)*6, life:0.6+Math.random()*0.4, t:0, grav:-6, fade:true});
  }
}
function firework(pos){
  const colors=[0xff5252,0xffd740,0x69f0ae,0x40c4ff,0xe040fb,0xffffff];
  const c=colors[Math.floor(Math.random()*colors.length)];
  for(let i=0;i<26;i++){ const m=new THREE.Mesh(new THREE.SphereGeometry(0.12,6,6), new THREE.MeshBasicMaterial({color:c}));
    m.position.copy(pos); Game.scene.add(m);
    const a=Math.random()*Math.PI*2, b=Math.random()*Math.PI-Math.PI/2, s=8+Math.random()*10;
    Game.parts.push({m, vx:Math.cos(a)*Math.cos(b)*s, vy:Math.abs(Math.sin(b))*s+4, vz:Math.sin(a)*Math.cos(b)*s, life:1.2+Math.random(), t:0, grav:-9, fade:true});
  }
  crowdCheer(1.2);
}
function die(reason){
  sDie(); Game.shake=0.7; Game.deaths++; save.deaths++;
  $('hud-deaths').textContent=Game.deaths;
  puff(Game.player.position,0xef4444,14);
  try{ if($('chk-vib').checked && navigator.vibrate) navigator.vibrate(120); }catch(e){}
  toast(reason||'💥 وقعت! حاول مجدداً يا بطل 💪');
  const s=Game.checkSpawn||Game.spawn;
  Game.player.position.copy(s); Game.vel.set(0,0,0); Game.combo=0; updCombo();
}
function updCombo(){ const el=$('combo'); if(Game.combo>=3){ el.classList.remove('hidden'); el.textContent=`🔥 كومبو ×${Game.combo} !!`; } else el.classList.add('hidden'); }
function cheer(texts){
  const box=$('cheer-bubbles');
  texts.forEach((t,i)=>setTimeout(()=>{
    const d=document.createElement('div'); d.className='bubble'; d.textContent=t;
    d.style.right=(5+Math.random()*85)+'%'; d.style.background=['#fff','#ffdf5e','#b7f5cd','#ffc7de'][Math.floor(Math.random()*4)];
    box.appendChild(d); setTimeout(()=>d.remove(),4100);
  },i*350));
}
function winLevel(){
  sWin(); crowdCheer(3); persist();
  const t=Game.time.toFixed(1);
  let stars=3; if(Game.deaths>6||Game.time>120) stars=1; else if(Game.deaths>2||Game.time>60) stars=2;
  save.stars[Game.lv]=Math.max(save.stars[Game.lv]||0,stars);
  save.coins+=Game.coins;
  if(Game.lv< TOTAL) save.unlocked=Math.max(save.unlocked, Game.lv+1);
  persist(); renderSave();
  for(let i=0;i<5;i++) setTimeout(()=>firework(Game.player.position.clone().add(new THREE.Vector3((Math.random()-0.5)*10,6+Math.random()*5,(Math.random()-0.5)*10))),i*250);
  puff(Game.player.position,0xf2b705,20);
  const msgs=['🎉 مبارك يا بطل!','👏 أحسنت!','🌟 ما شاء الله!','🔥 أسطورة الباركور!','💪 المرحلة اللي بعدها أصعب!'];
  cheer(msgs);
  speakCongrats(`مبارك! أنهيت المرحلة ${Game.lv}. أحسنت يا بطل!`);
  $('win-emoji').textContent = Game.lv>=TOTAL?'👑': Game.lv>=200?'🏰': Game.lv>=140?'🔥':'🏆';
  $('win-title').textContent = Game.lv>=TOTAL?'👑 أسطورة الأساطير! ختمت كل المراحل!':`أنهيت المرحلة ${Game.lv}! 🎉`;
  $('win-sub').textContent = Game.lv>=TOTAL?'🎁 هداياك وقصر الاحتفال والعرس بانتظارك!!':`المرحلة ${Game.lv+1} أصعب 🔥 هل أنت مستعد؟`;
  $('win-time').textContent=t+' ث'; $('win-deaths').textContent=Game.deaths; $('win-coins').textContent=Game.coins;
  $('win-stars').textContent='⭐'.repeat(stars)+'☆'.repeat(3-stars);
  $('btn-goto-party').classList.toggle('hidden', !(Game.lv>=195||Game.lv===TOTAL));
  setTimeout(()=>{ $('win').classList.remove('hidden'); Game.active=false; }, 900);
}

/* ---------- حلقة اللعب ---------- */
function loop(ts){
  if(!Game.renderer) return;
  Game.raf=requestAnimationFrame(loop);
  const dt=Math.min(0.033,(ts-Game.last)/1000||0.016); Game.last=ts;
  const paused = !$('pause').classList.contains('hidden') || !$('win').classList.contains('hidden');
  if(!Game.active || paused) { try{ Game.renderer.render(Game.scene,Game.camera); }catch(e){} Game.last=ts; return; }
  Game.time+=dt; Game.clock+=dt;
  $('hud-time').textContent=Game.time.toFixed(1);
  const P=Game.player.position;
  // إدخال
  let ix=0,iz=0;
  if(Game.keys['arrowup']||Game.keys['w']) iz-=1; if(Game.keys['arrowdown']||Game.keys['s']) iz+=1;
  if(Game.keys['arrowleft']||Game.keys['a']) ix-=1; if(Game.keys['arrowright']||Game.keys['d']) ix+=1;
  ix+=Game.joy.x; iz+=Game.joy.y;
  const l=Math.hypot(ix,iz); if(l>1){ix/=l;iz/=l;}
  // حركة نسبية للكاميرا
  const sin=Math.sin(Game.yaw), cos=Math.cos(Game.yaw);
  const wx=ix*cos - iz*sin, wz=-ix*sin - iz*cos;
  const speed = Game.grounded?11:8.5;
  const ice = Game.onIce?0.06:0.25;
  Game.vel.x += (wx*speed-Game.vel.x)*Math.min(1,ice*60*dt+ (Game.grounded?0.35:0.08));
  Game.vel.z += (wz*speed-Game.vel.z)*Math.min(1,ice*60*dt+(Game.grounded?0.35:0.08));
  // قفز
  Game.coyote-=dt; Game.jumpBuf-=dt;
  if(Game.jumpQ){ Game.jumpBuf=0.15; Game.jumpQ=false; }
  if(Game.jumpBuf>0 && (Game.grounded||Game.coyote>0)){ Game.vel.y=13.2; Game.grounded=false; Game.coyote=0; Game.jumpBuf=0; sJump(); puff(P,0xffffff,6); }
  Game.vel.y-=32*dt; if(Game.vel.y<-30) Game.vel.y=-30;
  // منصات متحركة
  Game.plats.forEach(pl=>{
    const d=pl.def, t=Game.clock*d.speed+pl.def.phase;
    pl.dx=0;
    if(d.type==='moveX'){ const nx=d.x+Math.sin(t)*d.amp; pl.dx=nx-pl.mesh.position.x; pl.mesh.position.x=nx; pl.edge.position.x=nx; }
    if(d.type==='moveZ'){ const nz=d.z+Math.sin(t)*d.amp; pl.dx=0; pl.mesh.position.z=nz; pl.edge.position.z=nz; pl.dz=nz-(pl._pz??nz); pl._pz=nz; }
    if(d.type==='vanish'){ pl.timer-=dt; const cyc=((t%(4))/4); pl.vis = cyc<0.62; pl.mesh.visible=pl.vis; pl.edge.visible=pl.vis; }
  });
  Game.spinners.forEach(s=>{ s.ang+=s.speed*dt; s.mesh.rotation.y=s.ang; });
  // تكامل
  P.x+=Game.vel.x*dt; P.z+=Game.vel.z*dt; P.y+=Game.vel.y*dt;
  // اصطدام علوي
  let wasGround=Game.grounded; Game.grounded=false; Game.onIce=false;
  const pr=0.35, ph=P.y; // قدم اللاعب ≈ P.y
  for(const pl of Game.plats){
    if(!pl.vis) continue;
    const m=pl.mesh, hw=m.scale.x/2+pr, hd=m.scale.z/2+pr, top=m.position.y+0.3;
    const dx=P.x-m.position.x, dz=P.z-m.position.z;
    if(Math.abs(dx)<hw && Math.abs(dz)<hd){
      const feet=P.y, prev=feet-Game.vel.y*dt;
      if(Game.vel.y<=0 && prev>=top-0.5 && feet<=top+0.4){
        P.y=top; Game.vel.y=0; Game.grounded=true; Game.coyote=0.12;
        if(pl.def.type==='bounce'){ Game.vel.y=19; Game.grounded=false; beep(300,0.15,'sine',0.25); puff(P,0xec4899,10); }
        if(pl.def.type==='ice') Game.onIce=true;
        if(pl.def.type==='moveX') P.x+=pl.dx||0;
        if(pl._pz!==undefined && pl.def.type==='moveZ' && pl.dz) P.z+=pl.dz;
        if(pl.def.checkpoint && (!Game.checkSpawn || Game.checkSpawn.y<top-1 || Math.abs(Game.checkSpawn.x-m.position.x)>0.5)){
          Game.checkSpawn=new THREE.Vector3(m.position.x,top+0.6,m.position.z);
          if(pl.flag) pl.flag.material.color.set(0xf2b705);
          sCheck(); toast('🚩 نقطة حفظ!'); puff(P,0x22c55e,10);
        }
        if(pl.def.type==='finish'){ winLevel(); return; }
        if(!wasGround && Game.vel.y===0){ puff(P,0xffffff,4); Game.shake=Math.max(Game.shake,0.12); }
        break;
      }
      // اصطدام جانبي قاتل للمنصات العالية
      if(feet<top-0.9 && Math.abs(dx)>hw-0.5){ /* يمر */ }
    }
  }
  if(P.y<-18){ die('💥 سقطت في الفراغ!'); return; }
  // المراوح القاتلة
  for(const s of Game.spinners){
    const dx=P.x-s.cx, dz=P.z-s.cz, dy=P.y-s.cy;
    if(Math.abs(dy)<1.1){
      const lx=Math.cos(-s.ang)*dx - Math.sin(-s.ang)*dz;
      const lz=Math.sin(-s.ang)*dx + Math.cos(-s.ang)*dz;
      if(Math.abs(lx)<s.len/2 && Math.abs(lz)<0.55){ die('🌀 ضربتك المروحة الدوارة!'); return; }
    }
  }
  // العملات
  Game.coinsM.forEach(c=>{
    if(c.def.taken) return;
    c.mesh.rotation.y+=3*dt;
    const d=c.mesh.position.distanceTo(new THREE.Vector3(P.x,P.y+1,P.z));
    if(d<1.2){ c.def.taken=true; c.mesh.visible=false; Game.coins++; $('hud-coins').textContent=Game.coins; sCoin(); Game.combo++; Game.comboT=3; updCombo(); puff(c.mesh.position,0xffd23f,6); }
  });
  Game.comboT-=dt; if(Game.comboT<0 && Game.combo>0){ Game.combo=0; updCombo(); }
  // أنيميشن الجري
  const u=Game.player.userData, run=Math.hypot(Game.vel.x,Game.vel.z);
  const sw=Math.sin(Game.clock*(6+run))*Math.min(1,run/6);
  if(u.l1){ u.l1.rotation.x=sw*0.9; u.l2.rotation.x=-sw*0.9; u.a1.rotation.x=-sw*0.8; u.a2.rotation.x=sw*0.8; }
  Game.player.rotation.y=Math.atan2(Game.vel.x,Game.vel.z)+Math.PI;
  // كاميرا
  const dist=8.5, h=4.6;
  const cx=P.x+Math.sin(Game.yaw)*dist, cz=P.z+Math.cos(Game.yaw)*dist, cy=P.y+h;
  Game.camera.position.lerp(new THREE.Vector3(cx,cy,cz), 1-Math.pow(0.001,dt));
  const look=P.clone(); look.y+=1.4;
  if(Game.shake>0){ Game.shake-=dt; look.x+=(Math.random()-0.5)*Game.shake; look.y+=(Math.random()-0.5)*Game.shake; }
  Game.camera.lookAt(look);
  // جزيئات
  for(let i=Game.parts.length-1;i>=0;i--){ const p=Game.parts[i]; if(p.cloud){ p.m.position.x+=p.speed*dt; if(p.m.position.x>100)p.m.position.x=-100; continue; }
    p.t+=dt; if(p.t>p.life){ Game.scene.remove(p.m); p.m.geometry.dispose(); Game.parts.splice(i,1); continue; }
    p.vy+=(p.grav||0)*dt; p.m.position.x+=p.vx*dt; p.m.position.y+=p.vy*dt; p.m.position.z+=p.vz*dt;
    if(p.fade) p.m.material.opacity=1-p.t/p.life;
  }
  // تقدم
  const total=Game.data.plats.length;
  let best=0; Game.data.plats.forEach((p,i)=>{ if(Math.abs(P.x-p.x)<4&&Math.abs(P.z-p.z)<4) best=Math.max(best,i); });
  $('hud-progress-fill').style.width=Math.round(best/(total-1)*100)+'%';
  Game.renderer.render(Game.scene,Game.camera);
}

/* ---------- بدء اللعب ---------- */
function startLevel(lv){
  Game.lv=lv; Game.quality=$('chk-quality')?$('chk-quality').checked:true;
  if(!Game.renderer) Game.renderer=initRenderer($('c'), Game.quality);
  else { Game.renderer.shadowMap.enabled=!!Game.quality; Game.renderer.setPixelRatio(Math.min(devicePixelRatio||1, Game.quality?2:1.25)); }
  if(!Game.camera) Game.camera=new THREE.PerspectiveCamera(62,innerWidth/innerHeight,0.1,600);
  Game.parts=[];
  buildLevel(lv);
  Game.yaw=Math.PI; Game.active=true; Game.last=performance.now();
  cancelAnimationFrame(Game.raf);
  $('home').classList.add('hidden'); $('levels-screen').classList.add('hidden'); $('party-ui').classList.add('hidden');
  $('game-ui').classList.remove('hidden'); $('win').classList.add('hidden'); $('pause').classList.add('hidden');
  Game.raf=requestAnimationFrame(loop);
  onResize();
}
function onResize(){ if(Game.renderer){ Game.renderer.setSize(innerWidth,innerHeight); Game.camera.aspect=innerWidth/innerHeight; Game.camera.updateProjectionMatrix(); } if(Party.renderer){ Party.renderer.setSize(innerWidth,innerHeight); Party.camera.aspect=innerWidth/innerHeight; Party.camera.updateProjectionMatrix(); } }

/* =====================================================
   قصر الاحتفال والزفاف 💍🏰
===================================================== */
const Party={ active:false, renderer:null, scene:null, camera:null, crowd:[], gifts:[], raf:0, last:0, clock:0, yaw:0 };
const GIFT_DATA=[
 {e:'🏆',t:'كأس البطل الذهبي',x:'لأنك ختمت 220 مرحلة! أنت أسطورة الباركور الحقيقية 👑'},
 {e:'👑',t:'تاج الملوك',x:'توجناك ملكاً على كل اللاعبين! الجمهور كله يهتف باسمك 📣'},
 {e:'💍',t:'خاتم الزفاف المبارك',x:'بارك الله لكما وبارك عليكما وجمع بينكما في خير 💍🤲 ألف مبارك الزواج!'},
 {e:'🏰',t:'قصر الأحلام',x:'هذا القصر صار ملكك! غرف ذهبية + حدائق + ألعاب نارية كل ليلة 🎆'},
 {e:'🚗',t:'سيارة الأحلام الذهبية',x:'سيارة تطير فوق السحاب! هدية العرس الكبرى 🚗💨'},
 {e:'📖',t:'مصحف مزخرف بالذهب',x:'هدية أغلى من الدنيا: القرآن الكريم نور دربك دائماً 📖✨'},
 {e:'🎮',t:'1000 جوهرة + شخصيات نادرة',x:'فتحت كل الشخصيات: النينجا 🥷 والروبوت 🤖 والتنين 🐉!'},
 {e:'✈️',t:'تذكرة شهر العسل',x:'رحلة حول العالم لك ولعروستك! ✈️❤️ بارك الله زواجكم'},
 {e:'🌟',t:'نجمة في السماء باسمك',x:'سمينا نجمة باسمك تلمع كل ليلة — لأنك نجم حقيقي 🌟'},
 {e:'🎉',t:'تصفيق الجمهور الأبدي',x:'200 مشجع يصفقون لك ويهنئونك كل يوم! مبروووك 🎉👏'},
];
function startParty(){
  Game.active=false; cancelAnimationFrame(Game.raf);
  $('home').classList.add('hidden'); $('levels-screen').classList.add('hidden'); $('game-ui').classList.add('hidden');
  $('party-ui').classList.remove('hidden');
  if(!Party.renderer) Party.renderer=initRenderer($('c2'), true);
  Party.scene=new THREE.Scene();
  Party.scene.background=new THREE.Color(0x1a1040);
  Party.scene.fog=new THREE.Fog(0x2b1a5e,50,260);
  Party.camera=new THREE.PerspectiveCamera(60,innerWidth/innerHeight,0.1,800);
  Party.camera.position.set(0,14,34);
  Party.scene.add(new THREE.HemisphereLight(0xffe9a8,0x332266,1.2));
  const sun=new THREE.DirectionalLight(0xffe9a8,1.4); sun.position.set(30,50,20); Party.scene.add(sun);
  const moon=new THREE.Mesh(new THREE.SphereGeometry(6,20,20), new THREE.MeshBasicMaterial({color:0xfff6c9}));
  moon.position.set(-60,60,-120); Party.scene.add(moon);
  // أرضية ذهبية
  const ground=new THREE.Mesh(new THREE.CylinderGeometry(60,60,2,40), new THREE.MeshStandardMaterial({color:0xd4af37,metalness:.4,roughness:.4}));
  ground.position.y=-1; Party.scene.add(ground);
  const carpet=new THREE.Mesh(new THREE.PlaneGeometry(10,90), new THREE.MeshStandardMaterial({color:0xc2185b,roughness:.8}));
  carpet.rotation.x=-Math.PI/2; carpet.position.set(0,0.05,0); Party.scene.add(carpet);
  // القصر
  const goldM=new THREE.MeshStandardMaterial({color:0xf2c94c,metalness:.6,roughness:.3});
  const whiteM=new THREE.MeshStandardMaterial({color:0xfff8e7,roughness:.6});
  function box(w,h,d,x,y,z,m){ const q=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),m); q.position.set(x,y,z); Party.scene.add(q); return q; }
  box(24,10,6,0,5,-42,whiteM); box(26,2,8,0,11,-42,goldM);
  [[-10],[10]].forEach(([tx])=>{ const t=new THREE.Mesh(new THREE.CylinderGeometry(3,3.4,18,12),whiteM); t.position.set(tx,9,-42); Party.scene.add(t);
    const roof=new THREE.Mesh(new THREE.ConeGeometry(4.4,6,12), new THREE.MeshStandardMaterial({color:0xff5fa2})); roof.position.set(tx,21,-42); Party.scene.add(roof); });
  const dome=new THREE.Mesh(new THREE.SphereGeometry(5,20,14,0,Math.PI*2,0,Math.PI/2), goldM); dome.position.set(0,12,-42); Party.scene.add(dome);
  const gateTxt=makeTextSprite('💍 قصر الزفاف الملكي 💍','#ffdf5e'); gateTxt.position.set(0,18,-38); gateTxt.scale.set(20,5,1); Party.scene.add(gateTxt);
  // العروسان 💒
  function person(color,x,z,ry=0){ const g=new THREE.Group();
    const b=new THREE.Mesh(new THREE.CylinderGeometry(0.5,0.7,1.6,10), new THREE.MeshStandardMaterial({color})); b.position.y=1; g.add(b);
    const h=new THREE.Mesh(new THREE.SphereGeometry(0.42,14,14), new THREE.MeshStandardMaterial({color:0xffd9b3})); h.position.y=2.1; g.add(h);
    g.position.set(x,0,z); g.rotation.y=ry; Party.scene.add(g); return g; }
  const groom=person(0x111827,-1.5,-30,0.3), bride=person(0xffffff,1.5,-30,-0.3);
  const heart=makeTextSprite('❤️',' #ff5fa2'); heart.position.set(0,4,-30); heart.scale.set(4,2,1); Party.scene.add(heart);
  Party.heart=heart;
  // الجمهور 👥 200 مشجع
  Party.crowd=[];
  const R=mulberry(7);
  for(let i=0;i<200;i++){
    const g=new THREE.Group();
    const c=[0xef4444,0x22c55e,0x3b82f6,0xf59e0b,0xa855f7,0xec4899][i%6];
    const b=new THREE.Mesh(new THREE.CylinderGeometry(0.35,0.45,1.1,8), new THREE.MeshStandardMaterial({color:c})); b.position.y=0.7; g.add(b);
    const h=new THREE.Mesh(new THREE.SphereGeometry(0.3,10,10), new THREE.MeshStandardMaterial({color:0xffd9b3})); h.position.y=1.55; g.add(h);
    const ang=(i/200)*Math.PI*2, rad=16+(i%5)*3.4;
    g.position.set(Math.cos(ang)*rad, 0, Math.sin(ang)*rad*0.8 - 8);
    Party.scene.add(g);
    Party.crowd.push({m:g, ph:R()*6, sp:3+R()*3});
  }
  const cheerTxt=makeTextSprite('🎉 مبارك 🎉 ألف مبروك 🎉','#ffffff'); cheerTxt.position.set(0,10,-20); cheerTxt.scale.set(16,4,1); Party.scene.add(cheerTxt);
  // الهدايا 🎁
  Party.gifts=[];
  const giftCols=[0xff5252,0x40c4ff,0x69f0ae,0xe040fb,0xffd740,0xff8a65,0x7c4dff,0x18ffff,0x76ff03,0xff4081];
  for(let i=0;i<10;i++){
    const g=new THREE.Group();
    const bx=new THREE.Mesh(new THREE.BoxGeometry(1.6,1.2,1.6), new THREE.MeshStandardMaterial({color:giftCols[i],roughness:.4}));
    bx.position.y=0.6; g.add(bx);
    const rib=new THREE.Mesh(new THREE.BoxGeometry(1.7,1.3,0.3), new THREE.MeshStandardMaterial({color:0xffffff})); rib.position.y=0.6; g.add(rib);
    const rib2=rib.clone(); rib2.rotation.y=Math.PI/2; g.add(rib2);
    const lid=new THREE.Mesh(new THREE.BoxGeometry(1.8,0.3,1.8), new THREE.MeshStandardMaterial({color:0xffffff,metalness:.3})); lid.position.y=1.3; g.add(lid); g.userData.lid=lid;
    const ang=(i/10)*Math.PI*2;
    g.position.set(Math.cos(ang)*10, 0, Math.sin(ang)*10-14);
    const lbl=makeTextSprite(`🎁 ${i+1}`,'#ffffff'); lbl.position.y=2.8; lbl.scale.set(3,1.2,1); g.add(lbl);
    Party.scene.add(g);
    Party.gifts.push({m:g, idx:i, opened: save.gifts.includes(i)});
    if(save.gifts.includes(i)){ lid.position.y=2.4; lid.rotation.z=0.6; }
  }
  Party.clock=0; Party.active=true; Party.last=performance.now();
  cancelAnimationFrame(Party.raf);
  Party.raf=requestAnimationFrame(partyLoop);
  updGiftBar();
  // قرآن + تهنئة تلقائية
  quranPlay();
  crowdCheer(4);
  speakCongrats('ألف ألف مبارك! وصلت قصر الاحتفال! بارك الله فيك وجمع بين العروسين في خير!');
  partyCheerRain();
  onResize();
}
function updGiftBar(){ const n=save.gifts.length; $('gift-count').textContent=`${n} / 10`; document.querySelector('#gift-progress i').style.width=(n*10)+'%'; }
function openGift(i, silent=false){
  if(save.gifts.includes(i)){ showGift(i); return; }
  save.gifts.push(i); persist(); updGiftBar();
  const g=Party.gifts[i]; if(g){ g.m.userData.lid.position.y=2.6; g.m.userData.lid.rotation.z=0.7; }
  sWin(); crowdCheer(2); puff2(Party.gifts[i]?Party.gifts[i].m.position:new THREE.Vector3());
  if(!silent) showGift(i);
  if(save.gifts.length===10){ setTimeout(()=>{ speakCongrats('ما شاء الله! فتحت كل الهدايا العشر! أنت الملك!'); toast('👑 فتحت كل الهدايا!! أنت الملك! 👑'); },800); }
}
function showGift(i){ const d=GIFT_DATA[i]; $('gift-emoji').textContent=d.e; $('gift-title').textContent=d.t; $('gift-text').textContent=d.x; $('gift-modal').classList.remove('hidden'); speakCongrats(d.t+'. '+d.x); }
function puff2(pos){ for(let k=0;k<3;k++) setTimeout(()=>partyFirework(pos.clone().add(new THREE.Vector3((Math.random()-0.5)*8,8+Math.random()*6,(Math.random()-0.5)*8))),k*200); }
let partyParts=[];
function partyFirework(pos){
  const c=[0xff5252,0xffd740,0x69f0ae,0x40c4ff,0xe040fb,0xffffff][Math.floor(Math.random()*6)];
  for(let i=0;i<20;i++){ const m=new THREE.Mesh(new THREE.SphereGeometry(0.16,6,6), new THREE.MeshBasicMaterial({color:c}));
    m.position.copy(pos); Party.scene.add(m);
    const a=Math.random()*Math.PI*2, s=6+Math.random()*9;
    partyParts.push({m, vx:Math.cos(a)*s, vy:Math.random()*10+2, vz:Math.sin(a)*s, life:1.4, t:0});
  }
  crowdCheer(0.8);
}
function partyCheerRain(){
  const box=$('party-cheer');
  const msgs=['🎉 مبارك!','💍 بالرفاه والبنين!','👏 أحسنت يا بطل!','🌟 ما شاء الله!','❤️ ألف مبروك الزواج!','🎁 هدية لك!','👑 ملك الباركور!','📖 بارك الله فيك!'];
  for(let i=0;i<24;i++) setTimeout(()=>{
    const d=document.createElement('div'); d.className='bubble'; d.textContent=msgs[i%msgs.length];
    d.style.right=(Math.random()*88)+'%'; d.style.bottom='auto'; d.style.top='60px';
    box.appendChild(d); setTimeout(()=>d.remove(),4100);
  },i*400);
}
function partyLoop(ts){
  if(!Party.renderer) return;
  Party.raf=requestAnimationFrame(partyLoop);
  const dt=Math.min(0.05,(ts-Party.last)/1000||0.016); Party.last=ts;
  if(!Party.active){ Party.renderer.render(Party.scene,Party.camera); return; }
  Party.clock+=dt; Party.yaw+=dt*0.12;
  const r=36;
  Party.camera.position.set(Math.sin(Party.yaw)*r, 13+Math.sin(Party.clock*0.4)*2, Math.cos(Party.yaw)*r-10);
  Party.camera.lookAt(0,5,-30);
  Party.crowd.forEach(c=>{ c.m.position.y=Math.abs(Math.sin(Party.clock*c.sp+c.ph))*0.9; c.m.rotation.y+=dt*0.6; });
  Party.gifts.forEach((g,i)=>{ if(!g.opened) g.m.rotation.y+=dt*0.8; g.m.position.y=Math.sin(Party.clock*2+i)*0.15; });
  if(Party.heart) Party.heart.position.y=4+Math.sin(Party.clock*3)*0.3;
  if(Math.random()<dt*2.2) partyFirework(new THREE.Vector3((Math.random()-0.5)*50,18+Math.random()*10,-20-Math.random()*30));
  for(let i=partyParts.length-1;i>=0;i--){ const p=partyParts[i]; p.t+=dt;
    if(p.t>p.life){ Party.scene.remove(p.m); p.m.geometry.dispose(); partyParts.splice(i,1); continue; }
    p.vy-=9*dt; p.m.position.x+=p.vx*dt; p.m.position.y+=p.vy*dt; p.m.position.z+=p.vz*dt; }
  Party.renderer.render(Party.scene,Party.camera);
}

/* =====================================================
   القوائم + الإدخال
===================================================== */
function renderSave(){
  $('save-line').textContent=`🏆 تقدمك: المرحلة ${save.unlocked} / ${TOTAL} • 🪙 ${save.coins} • ⭐ ${Object.keys(save.stars).length}`;
  const gr=$('levels-grid'); gr.innerHTML='';
  for(let i=1;i<=TOTAL;i++){
    const b=document.createElement('button');
    const open=i<=save.unlocked, done=!!save.stars[i];
    b.className=`lv open ${diffOf(i).c} ${done?'done':''} ${!open?'lock':''} ${i===save.unlocked?'cur':''}`;
    b.innerHTML=`${open?(done?'⭐':'')+i:'🔒'}<small>${i>=200?'👑':i>=141?'🔴':i>=81?'🟠':i>=31?'🟡':'🟢'}</small>`;
    if(open) b.onclick=()=>{ sJump(); startLevel(i); };
    else b.onclick=()=>toast('🔒 أنهِ المراحل السابقة لفتحها!');
    gr.appendChild(b);
  }
}
// أزرار
$('btn-play').onclick=()=>{ ac(); sJump(); startLevel(Math.min(save.unlocked,TOTAL)); };
$('btn-levels').onclick=()=>{ sJump(); renderSave(); $('home').classList.add('hidden'); $('levels-screen').classList.remove('hidden'); };
$('btn-back-home').onclick=()=>{ $('levels-screen').classList.add('hidden'); $('home').classList.remove('hidden'); };
$('btn-how').onclick=()=>toast('🏃 حرّك بالعصا أو WASD • ⬆️ قفز • 🚩 احفظ checkpoint • 🏁 ادخل البوابة الذهبية!',3500);
$('btn-quran-home').onclick=()=>{ ac(); quranToggle(); $('btn-quran-home').textContent=quranOn?'⏸️ إيقاف القرآن':'📖 قرآن'; };
$('btn-sound-home').onclick=e=>{ muted=!muted; e.target.textContent=muted?'🔇 الصوت: متوقف':'🔊 الصوت: يعمل'; };
$('btn-party-go').onclick=()=>startParty();
$('btn-menu').onclick=()=>$('pause').classList.toggle('hidden');
$('btn-resume').onclick=()=>$('pause').classList.add('hidden');
$('btn-restart').onclick=()=>startLevel(Game.lv);
$('btn-restart2').onclick=()=>startLevel(Game.lv);
$('btn-quit').onclick=()=>{ Game.active=false; cancelAnimationFrame(Game.raf); $('game-ui').classList.add('hidden'); $('home').classList.remove('hidden'); renderSave(); };
$('btn-next-locked').onclick=()=>{ if(Game.lv<TOTAL) startLevel(Game.lv+1); };
$('btn-next').onclick=()=>{ $('win').classList.add('hidden'); if(Game.lv>=TOTAL) startParty(); else startLevel(Game.lv+1); };
$('btn-replay').onclick=()=>{ $('win').classList.add('hidden'); startLevel(Game.lv); };
$('btn-home2').onclick=()=>{ $('win').classList.add('hidden'); Game.active=false; cancelAnimationFrame(Game.raf); $('game-ui').classList.add('hidden'); $('home').classList.remove('hidden'); renderSave(); };
$('btn-goto-party').onclick=()=>startParty();
$('btn-mute').onclick=e=>{ muted=!muted; e.target.textContent=muted?'🔇':'🔊'; };
$('btn-quran').onclick=()=>{ ac(); quranToggle(); };
$('btn-cheer').onclick=()=>{ crowdCheer(2); cheer(['🎉 مبارك!','👏 واصل!','🔥 أنت الأفضل!']); speakCongrats('واصل يا بطل! الجمهور كله معك!'); };
$('btn-party-back').onclick=()=>{ Party.active=false; cancelAnimationFrame(Party.raf); quranStop(); $('party-ui').classList.add('hidden'); $('home').classList.remove('hidden'); renderSave(); };
$('btn-open-all').onclick=()=>{ for(let i=0;i<10;i++) if(!save.gifts.includes(i)) openGift(i,true); showGift(save.gifts[save.gifts.length-1]??0); partyCheerRain(); };
$('btn-fireworks').onclick=()=>{ for(let i=0;i<6;i++) setTimeout(()=>partyFirework(new THREE.Vector3((Math.random()-0.5)*40,16,-15-Math.random()*20)),i*200); crowdCheer(2); };
$('btn-quran2').onclick=()=>{ ac(); quranToggle(); toast(quranOn?'📖 القرآن يعمل الآن 🤲':'📖 القرآن متوقف'); };
$('btn-congrats').onclick=()=>{ crowdCheer(3); partyCheerRain(); speakCongrats('ألف مبارك! بارك الله فيك! أنت بطل الأبطال وزواج مبارك!'); };
$('gift-close').onclick=()=>$('gift-modal').classList.add('hidden');
// كيبورد
addEventListener('keydown',e=>{ Game.keys[e.key.toLowerCase()]=true; if(e.code==='Space'){ Game.jumpQ=true; e.preventDefault(); } });
addEventListener('keyup',e=>{ Game.keys[e.key.toLowerCase()]=false; });
// عصا اللمس
(function(){
  const joy=$('joy'), knob=$('joy-knob'); let id=null, cx=0, cy=0;
  function setKnob(dx,dy){ knob.style.transform=`translate(calc(50% + ${dx}px), calc(-50% + ${dy}px))`; }
  joy.addEventListener('touchstart',e=>{ const t=e.changedTouches[0]; id=t.identifier; const r=joy.getBoundingClientRect(); cx=r.left+r.width/2; cy=r.top+r.height/2; e.preventDefault(); },{passive:false});
  addEventListener('touchmove',e=>{
    for(const t of e.changedTouches){ if(t.identifier===id){
      let dx=t.clientX-cx, dy=t.clientY-cy; const m=Math.hypot(dx,dy), max=45;
      if(m>max){ dx*=max/m; dy*=max/m; }
      setKnob(dx,dy); Game.joy.x=dx/max; Game.joy.y=dy/max;
    }}
    // تدوير الكاميرا بالسحب على الشاشة
    if(Party.active && e.touches.length===1){ Party.yaw+=0.01; }
  },{passive:true});
  addEventListener('touchend',e=>{ for(const t of e.changedTouches){ if(t.identifier===id){ id=null; Game.joy.x=0; Game.joy.y=0; setKnob(0,0);} } });
  $('btn-jump').addEventListener('touchstart',e=>{ Game.jumpQ=true; e.preventDefault(); },{passive:false});
  $('btn-jump').addEventListener('mousedown',()=>Game.jumpQ=true);
  // كاميرا: سحب أفقي على الزر
  let camX=null;
  $('btn-cam').addEventListener('touchstart',e=>{ camX=e.changedTouches[0].clientX; },{passive:true});
  $('btn-cam').addEventListener('touchmove',e=>{ const x=e.changedTouches[0].clientX; Game.yaw+=(x-camX)*0.01; camX=x; e.preventDefault(); },{passive:false});
})();
// سحب لتدوير الكاميرا (ماوس + لمس على الكانفس)
(function(){
  const cv=$('c'); let drag=false, px=0;
  cv.addEventListener('mousedown',e=>{drag=true;px=e.clientX;});
  addEventListener('mousemove',e=>{ if(drag&&Game.active){ Game.yaw+=(e.clientX-px)*0.006; px=e.clientX; } });
  addEventListener('mouseup',()=>drag=false);
  cv.addEventListener('touchstart',e=>{ if(e.touches.length===1 && e.touches[0].clientX>innerWidth*0.4){ drag=true; px=e.touches[0].clientX; } },{passive:true});
  cv.addEventListener('touchmove',e=>{ if(drag&&Game.active){ const x=e.touches[0].clientX; Game.yaw+=(x-px)*0.008; px=x; } },{passive:true});
  cv.addEventListener('touchend',()=>drag=false);
  // نقر الهدايا في الحفلة (raycast)
  const cv2=$('c2'); const ray=new THREE.Raycaster();
  cv2.addEventListener('click',e=>{
    if(!Party.active) return;
    const m=new THREE.Vector2((e.clientX/innerWidth)*2-1, -(e.clientY/innerHeight)*2+1);
    ray.setFromCamera(m, Party.camera);
    const objs=Party.gifts.map(g=>g.m);
    const hit=ray.intersectObjects(objs,true);
    if(hit.length){ let o=hit[0].object; while(o && !Party.gifts.find(g=>g.m===o)) o=o.parent; const g=Party.gifts.find(g=>g.m===o); if(g) openGift(g.idx); }
  });
})();
addEventListener('resize', onResize);
document.addEventListener('visibilitychange',()=>{ if(document.hidden&&Game.active){ $('pause').classList.remove('hidden'); } });
renderSave();
