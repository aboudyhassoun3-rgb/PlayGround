/* ===== 3D city map: أحياء + معالم مسماة + أوكار عصابات ===== */
let THREE_MOD=null, scene3=null, camera3=null, renderer3=null, raf3=null, markers3=[], patrols3=[];
function poiList(){
  const S=window.S;
  const gangs=(S?.gangs||window.GANG_DEFS||[]).slice(0,3);
  return [
    {name:"🏦 البنك المركزي", x:-28, z:-26, color:0xffd166, h:14, info:"قلب الحي التجاري — جرائم مالية واحتيال"},
    {name:"🚔 مركز الشرطة الرئيسي", x:24, z:12, color:0x38bdf8, h:12, info:"قيادتك — تنطلق منه الدوريات والمداهمات"},
    {name:"🔒 السجن المركزي", x:44, z:34, color:0x64748b, h:8, info:"نزلاؤك هنا — رعاية واستجواب قانوني"},
    {name:"🏥 المستشفى العام", x:-2, z:-30, color:0xf472b6, h:10, info:"يستقبل ضحايا الجرائم والطوارئ"},
    {name:"🏭 ميناء المستودعات", x:-24, z:32, color:0x8a8f98, h:9, info:"تهريب ومخازن مشبوهة"},
    {name:"🔪 وكر "+(gangs[0]?.name||"العصابة 1"), x:32, z:-16, color:0xe11d48, h:7, info:"نشاط: "+(gangs[0]?.spec||"مخدرات")+" — قوة "+(gangs[0]?.power||"?")},
    {name:"🔪 وكر "+(gangs[1]?.name||"العصابة 2"), x:-14, z:26, color:0xf59e0b, h:7, info:"نشاط: "+(gangs[1]?.spec||"تهريب")+" — قوة "+(gangs[1]?.power||"?")},
    {name:"🔪 وكر "+(gangs[2]?.name||"العصابة 3"), x:6, z:6, color:0x8b5cf6, h:6, info:"نشاط: "+(gangs[2]?.spec||"ابتزاز")+" — قوة "+(gangs[2]?.power||"?")},
  ];
}
function makeLabel(text){
  const cv=document.createElement("canvas"); cv.width=512; cv.height=128;
  const g=cv.getContext("2d");
  g.fillStyle="rgba(5,10,24,0.85)"; g.beginPath(); g.roundRect(6,18,500,92,24); g.fill();
  g.strokeStyle="#f2b705"; g.lineWidth=4; g.stroke();
  g.fillStyle="#fff"; g.font="bold 44px Tahoma, Arial"; g.textAlign="center"; g.textBaseline="middle";
  g.fillText(text.slice(0,26), 256, 66);
  const tx=new THREE_MOD.CanvasTexture(cv); tx.anisotropy=4;
  const sp=new THREE_MOD.Sprite(new THREE_MOD.SpriteMaterial({map:tx,transparent:true,depthTest:false}));
  sp.scale.set(16,4,1); return sp;
}
async function initMap(){
  try{ THREE_MOD = await import("three"); }catch(e){ document.getElementById("map-legend").innerHTML="<span class='tag hot'>تعذر تحميل 3D — تحقق من الإنترنت</span>"; return; }
  const el=document.getElementById("map3d");
  el.innerHTML="";
  scene3=new THREE_MOD.Scene(); scene3.background=new THREE_MOD.Color(0x050a18);
  scene3.fog=new THREE_MOD.Fog(0x050a18, 120, 260);
  camera3=new THREE_MOD.PerspectiveCamera(55, el.clientWidth/Math.max(1,el.clientHeight), .1, 1000);
  camera3.position.set(0,72,74); camera3.lookAt(0,0,6);
  renderer3=new THREE_MOD.WebGLRenderer({antialias:true});
  renderer3.setSize(el.clientWidth, el.clientHeight);
  el.appendChild(renderer3.domElement);
  scene3.add(new THREE_MOD.AmbientLight(0xffffff,.75));
  const sun=new THREE_MOD.DirectionalLight(0xffe9a3,1.1); sun.position.set(40,60,20); scene3.add(sun);
  const night=new THREE_MOD.PointLight(0x38bdf8,.6,200); night.position.set(0,30,0); scene3.add(night);
  const ground=new THREE_MOD.Mesh(new THREE_MOD.PlaneGeometry(150,120), new THREE_MOD.MeshStandardMaterial({color:0x0d1730}));
  ground.rotation.x=-Math.PI/2; scene3.add(ground);
  // طرق مضيئة
  const roadMat=new THREE_MOD.MeshStandardMaterial({color:0x1e293b,emissive:0x0ea5e9,emissiveIntensity:.12});
  [[0,0,150,4],[0,0,4,120]].forEach(([x,z,w,d])=>{
    const r=new THREE_MOD.Mesh(new THREE_MOD.BoxGeometry(w,.3,d),roadMat); r.position.set(x,.15,z); scene3.add(r);
  });
  // الأحياء
  window.DISTRICTS.forEach(d=>{
    const g=new THREE_MOD.Group();
    const base=new THREE_MOD.Mesh(new THREE_MOD.BoxGeometry(30,1,24), new THREE_MOD.MeshStandardMaterial({color:d.color,transparent:true,opacity:.32}));
    base.position.set(d.x,0.5,d.z); g.add(base);
    for(let i=0;i<12;i++){
      const h=2+Math.random()*8;
      const b=new THREE_MOD.Mesh(new THREE_MOD.BoxGeometry(2.4,h,2.4), new THREE_MOD.MeshStandardMaterial({color:d.color}));
      b.position.set(d.x-12+Math.random()*24, h/2+1, d.z-9+Math.random()*18);
      g.add(b);
    }
    const lb=makeLabel(d.name); lb.position.set(d.x,13,d.z); g.add(lb);
    scene3.add(g);
  });
  // المعالم
  poiList().forEach(p=>{
    const grp=new THREE_MOD.Group();
    const tower=new THREE_MOD.Mesh(new THREE_MOD.CylinderGeometry(2.2,2.8,p.h,8), new THREE_MOD.MeshStandardMaterial({color:p.color,emissive:p.color,emissiveIntensity:.25}));
    tower.position.set(p.x,p.h/2+1,p.z); grp.add(tower);
    const ring=new THREE_MOD.Mesh(new THREE_MOD.TorusGeometry(3.4,.25,8,32), new THREE_MOD.MeshBasicMaterial({color:p.color}));
    ring.rotation.x=Math.PI/2; ring.position.set(p.x,1.4,p.z); grp.add(ring);
    const lb=makeLabel(p.name); lb.position.set(p.x,p.h+6,p.z); grp.add(lb);
    grp.userData.poi=p; scene3.add(grp);
  });
  // دوريات متحركة
  patrols3=[];
  for(let i=0;i<8;i++){
    const car=new THREE_MOD.Mesh(new THREE_MOD.BoxGeometry(1.4,.8,2.4), new THREE_MOD.MeshStandardMaterial({color:i%3?0x38bdf8:0xef4444,emissive:0x222222,emissiveIntensity:.4}));
    car.position.set(-60+Math.random()*120,1,-40+Math.random()*80);
    car.userData={vx:(Math.random()-.5)*8,vz:(Math.random()-.5)*8};
    scene3.add(car); patrols3.push(car);
  }
  let dragging=false,px=0,ang=0;
  renderer3.domElement.addEventListener("pointerdown",e=>{dragging=true;px=e.clientX;});
  window.addEventListener("pointerup",()=>dragging=false);
  window.addEventListener("pointermove",e=>{if(dragging){ang+=(e.clientX-px)*0.005;px=e.clientX;}});
  renderer3.domElement.addEventListener("wheel",e=>{camera3.position.y=Math.max(25,Math.min(130,camera3.position.y+e.deltaY*0.05));},{passive:true});
  cancelAnimationFrame(raf3);
  let last=Date.now();
  const loop=()=>{
    raf3=requestAnimationFrame(loop);
    const now=Date.now(), dt=Math.min(.05,(now-last)/1000); last=now;
    scene3.rotation.y=ang+Math.sin(now*0.0002)*0.02;
    markers3.forEach((m,i)=>{m.position.y=8+Math.sin(now*0.003+i)*1.5; m.rotation.y+=dt*2;});
    patrols3.forEach(c=>{ c.position.x+=c.userData.vx*dt; c.position.z+=c.userData.vz*dt;
      if(c.position.x>70||c.position.x<-70)c.userData.vx*=-1; if(c.position.z>50||c.position.z<-50)c.userData.vz*=-1; });
    renderer3.render(scene3,camera3);
  };
  loop();
  refreshMarkers();
}
function refreshMarkers(){
  if(!scene3||!THREE_MOD)return;
  markers3.forEach(m=>scene3.remove(m)); markers3=[];
  const open=window.S?window.S.cases.filter(c=>c.status!=="مغلقة").slice(0,10):[];
  open.forEach((c,i)=>{
    const d=window.DISTRICTS.find(x=>x.id===c.dist)||window.DISTRICTS[4];
    const m=new THREE_MOD.Mesh(new THREE_MOD.OctahedronGeometry(1.7), new THREE_MOD.MeshStandardMaterial({color:c.priority==="عاجلة"?0xef4444:0xf2b705, emissive:c.priority==="عاجلة"?0x550000:0x332200}));
    m.position.set(d.x+(i%4)*3-4, 8, d.z+Math.floor(i/4)*3-3);
    scene3.add(m); markers3.push(m);
  });
  window.S?.emergencies?.filter(e=>!e.done).slice(0,5).forEach((e,i)=>{
    const m=new THREE_MOD.Mesh(new THREE_MOD.SphereGeometry(1.3), new THREE_MOD.MeshStandardMaterial({color:0x38bdf8,emissive:0x003355}));
    m.position.set(-50+i*5, 8, 44); scene3.add(m); markers3.push(m);
  });
}
window.initMap=initMap; window.refreshMarkers=refreshMarkers; window.poiList=poiList;
