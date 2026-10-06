/* ===== Main boot with Auth ===== */
let authMode="login";
function boot(){
  window.S = null;
  document.querySelectorAll("#drawer button").forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));
  document.getElementById("menu-btn").onclick=()=>window.scrollTo({top:document.body.scrollHeight,behavior:"smooth"});
  document.getElementById("radio-fab").onclick=()=>{document.getElementById("radio-panel").classList.toggle("hidden");buildRadioTargets();};
  document.getElementById("radio-close").onclick=()=>document.getElementById("radio-panel").classList.add("hidden");
  document.getElementById("radio-send").onclick=sendRadio;
  // تتبع آخر تفاعل حتى لا تقتحم التنبيهات شاشتك وأنت مشغول
  window._lastTap=0;
  window.addEventListener("pointerdown",()=>{window._lastTap=Date.now();},{passive:true});
  // auth tabs
  document.getElementById("tab-login").onclick=()=>setAuthMode("login");
  document.getElementById("tab-signup").onclick=()=>setAuthMode("signup");
  document.getElementById("btn-auth").onclick=doAuth;
  ["auth-name","auth-email","auth-pass"].forEach(id=>{
    document.getElementById(id).addEventListener("keydown",(e)=>{ if(e.key==="Enter") doAuth(); });
  });
  document.getElementById("btn-logout").onclick=()=>window.Auth.logout();
  document.getElementById("btn-new").onclick=()=>{ wipe(); seedWorld(); enterGame(); };
  document.getElementById("btn-continue").onclick=()=>{ if(!window.S)window.S=defaultState(); if(!window.S.cases.length)seedWorld(); enterGame(); };
  const cur=window.Auth.current();
  if(cur){ showCityMenu(cur); }
}
function setAuthMode(m){ authMode=m;
  document.getElementById("tab-login").classList.toggle("on",m==="login");
  document.getElementById("tab-signup").classList.toggle("on",m==="signup");
  document.getElementById("auth-name-row").style.display=m==="signup"?"block":"none";
  document.getElementById("btn-auth").textContent=m==="signup"?"إنشاء الحساب":"دخول";
}
async function doAuth(){
  const err=document.getElementById("auth-err"); err.textContent="… جارٍ التحقق …";
  const btn=document.getElementById("btn-auth"); btn.disabled=true;
  const name=document.getElementById("auth-name").value;
  const email=document.getElementById("auth-email").value;
  const pass=document.getElementById("auth-pass").value;
  try{
    const u = authMode==="signup" ? await window.Auth.signup(name,email,pass) : await window.Auth.login(email,pass);
    showCityMenu(u);
  }catch(e){ err.textContent="⚠️ "+e.message; }
  btn.disabled=false;
}
function showCityMenu(u){
  document.getElementById("auth-box").style.display="none";
  document.getElementById("city-box").style.display="block";
  window.S = load();
  const has = !!(window.S && window.S.cases.length);
  document.getElementById("hello-user").textContent=`أهلاً ${u.name} (${u.email}) ${window.Auth.isAdmin()?"👑 أدمن":""} — ${has?"لديك حفظ: يوم "+window.S.day+" — "+window.S.cases.length+" قضايا":"لا يوجد حفظ بعد — ابدأ مدينة جديدة"}`;
  document.getElementById("btn-continue").disabled=!has;
}
function enterGame(){
  document.getElementById("boot").classList.add("gone");
  startLoop();
  // سالفة افتتاحية تفجأك بمكتبك بعد أن تستقر
  setTimeout(()=>{ try{
    if(window.S && activeIncidents().length===0 && (!window.S.alertQueue||!window.S.alertQueue.length)){
      startIncident(); save(); renderAll(); showAlertQueue();
    }
  }catch(e){} }, 12000);
}
function seedWorld(){
  window.S.city="مدينة العدل";
  // ضباط بداية: 6 فقط (ندرة مقصودة)
  for(let i=0;i<6;i++) hireSilent();
  SQUAD_DEFS.slice(0,4).forEach(n=>window.S.squads.push({id:"SQ"+n,name:"فرقة "+n,leader:null,members:[],chat:[]}));
  genCase(); genCase(); genCase();
  addNews("تنصيب القاضي الجديد","استلم القائد العام مهامه: التحقيق والقضاء والشرطة والميزانية تحت مسؤوليته.","good");
  save();
}
function hireSilent(){
  const S=window.S; const id="O"+(S.seq.off++);
  S.officers.push({id,name:arabName(),rank:"شرطي",lvl:1,spec:pick(SPECS),intel:rnd(40,95),loyalty:rnd(40,95),brave:rnd(30,95),salary:rnd(700,1400),status:"متاح",squad:null,history:[`يوم ${S.day}: تعيين`],corrupt:Math.random()<0.12,rel:{},xp:0});
}
let loopTimer=null;
function startLoop(){
  renderAll(); switchTab(window.S.activeTab||"dash");
  if(loopTimer)clearInterval(loopTimer);
  loopTimer=setInterval(()=>{ tick(); }, window.GAME_CONFIG.TICK_MS);
}
function buildRadioTargets(){
  const sel=document.getElementById("radio-target");
  sel.innerHTML=window.S.officers.slice(0,20).map(o=>`<option value="${o.id}">📡 ${o.name} (${o.spec})</option>`).join("")+`<option value="all">📢 نداء عام</option>`;
  const log=document.getElementById("radio-log");
  log.innerHTML=(window.S.chats.radio||[]).slice(-20).map(m=>`<div class="msg ${m.me?"me":""}"><span class="who">${m.who}:</span> ${m.text}</div>`).join("");
}
async function sendRadio(){
  const inp=document.getElementById("radio-input"); const txt=inp.value.trim(); if(!txt)return; inp.value="";
  const tid=document.getElementById("radio-target").value;
  const target=window.S.officers.find(o=>o.id===tid);
  const who="القائد"; window.S.chats.radio.push({who,me:true,text:(target?"إلى "+target.name+": ":"")+txt});
  buildRadioTargets();
  const ctx=`أنت ${target?target.name+" ("+target.spec+")":"ضابط مناوب"}. القائد يأمرك عبر اللاسلكي. رد عسكرياً مختصراً مع تحديث ميداني. لا ردود محفوظة.`;
  const r=await window.AI.chat({system:ctx,user:txt,context:`اليوم ${window.S.day}. ذاكرتك: ${memOf(tid)}`});
  window.S.chats.radio.push({who:target?target.name:"المناوب",me:false,text:r.text});
  if(target)addMemory(tid,`لاسلكي: ${txt.slice(0,50)}…`);
  save(); buildRadioTargets();
}
window.addEventListener("resize",()=>{});
document.addEventListener("DOMContentLoaded",boot);
