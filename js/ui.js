/* ===== UI: render all tabs ===== */
function switchTab(t){ window.S.activeTab=t; document.querySelectorAll("#drawer button").forEach(b=>b.classList.toggle("on",b.dataset.tab===t)); document.querySelectorAll(".tab").forEach(s=>s.classList.remove("active")); document.getElementById("tab-"+t)?.classList.add("active"); if(t==="map")setTimeout(()=>window.initMap&&window.initMap(),50); save(); }
function renderHUD(){
  const S=window.S; if(!S)return;
  document.getElementById("hud-day").textContent="اليوم "+S.day;
  document.getElementById("hud-time").textContent=String(S.hour).padStart(2,"0")+":"+String(S.min).padStart(2,"0");
  document.getElementById("hud-money").textContent=fmt(S.money);
  document.getElementById("badge-cases").textContent=S.cases.filter(c=>c.status==="مفتوحة").length||"";
  document.getElementById("badge-off").textContent=S.officers.length||"";
  const em=S.emergencies.filter(e=>!e.done).length;
  document.getElementById("ticker-inner").textContent=(em?`🚨 ${em} طوارئ نشطة — `:"")+(S.news[0]?`📰 ${S.news[0].title} — `:"")+"المدينة مستمرة سواء تدخلت أم لا • كل قرار له ثمن • AI لا يعطي اليقين أبداً";
  const me=window.Auth?.current();
  document.getElementById("city-name").textContent="• "+S.city+(me?" • 👤 "+me.name.split(" ")[0]:"");
  // زر عائم للحادث المنتظر بدل اقتحام الشاشة
  const fab=document.getElementById("alert-fab");
  if(fab){
    const waiting=(S.alertQueue&&S.alertQueue.length)||0;
    fab.classList.toggle("hidden",!waiting);
    if(waiting)fab.textContent=`🚨 حادث يحتاج قرارك (${waiting})`;
    fab.onclick=()=>showAlertQueue(true);
  }
}
function repBar(k,label){ const v=window.S.rep[k]; return `<div class="small">${label}: ${v}</div><div class="bar ${v<35?"low":""}"><i style="width:${v}%"></i></div>`; }
function renderAll(){ renderHUD(); renderDash(); renderCases(); renderCourt(); renderChat(); renderOfficers(); renderBudget(); renderPrison(); renderNews(); renderFiles(); renderSettings(); renderMapInfo(); if(window.refreshMarkers)window.refreshMarkers(); }
function renderDash(){
  const S=window.S; S.incidents=S.incidents||[]; S.inbox=S.inbox||[];
  const open=S.cases.filter(c=>c.status==="مفتوحة");
  const urg=open.filter(c=>c.status==="مفتوحة"&&S.day>=c.deadline-2);
  const actInc=S.incidents.filter(i=>i.active);
  const salaryIn=Math.max(0,7-(S.day-S.lastSalaryDay));
  const el=document.getElementById("tab-dash");
  el.innerHTML=`
  <div class="card"><h3>🖥️ مكتبك — ${S.city} <span class="mut">اليوم ${S.day} • ${String(S.hour).padStart(2,"0")}:${String(S.min).padStart(2,"0")}</span></h3>
   <div class="mut">أنت جالس في مكتبك… المدينة تعمل، والسالفة قد تفجأك بأي لحظة. القادة يراسلونك هنا، والصحافة تنشر، والقرار قرارك.</div>
   <div class="row" style="margin-top:8px">
    <button type="button" class="btn primary" onclick="genCase();renderAll()">📁 قضية جديدة</button>
    <button type="button" class="btn" onclick="secretOp()">🕵️ عملية سرية</button>
    <button type="button" class="btn" onclick="dailyBrief()">📋 موجز AI لليوم</button>
   </div><div id="brief"></div></div>
  ${actInc.length?`<div class="card"><h3>🚨 حادث جارٍ الآن (${actInc.length}) — يحتاج قرارك</h3>${actInc.slice(0,3).map(i=>{
    const total=INCIDENT_DEFS[i.kind].stages.length;
    return `<div class="person"><b>${i.icon} ${escHtml(i.title)}</b> <span class="mut">${escHtml(i.dist)} • <span class="stage-dots">${"●".repeat(Math.min(i.stage+1,total))+"○".repeat(Math.max(0,total-i.stage-1))}</span> مرحلة ${Math.min(i.stage+1,total)}/${total}${i.ignored?` • <span class="tag hot">تجاهل ×${i.ignored}</span>`:""}</span>
    <div class="small">${escHtml(i.log[i.log.length-1]||"")}</div>
    <div class="row"><button type="button" class="btn primary" onclick="showAlertQueue(true)">⚡ افتح غرفة القرار</button></div></div>`}).join("")}</div>`:""}
  <div class="grid2">
   <div class="card"><h3>📥 بريد المكتب الوارد</h3>
    ${(S.inbox||[]).slice(0,5).map(m=>`<div class="inbox-msg"><span class="who">${m.from==="pol"?"👮 قائد الشرطة":m.from==="int"?"🛰️ الاستخبارات":"📢 النظام"}:</span> ${escHtml(m.text.slice(0,160))}<div class="meta">يوم ${m.day} • ${m.time}</div></div>`).join("")||"<span class='mut'>هادئ… حتى الآن.</span>"}
    <div class="mut small">الرسائل الكاملة في تبويب 💬 القيادات.</div></div>
   <div class="card"><h3>🗓️ جدول اليوم واستمراريتك</h3>
    <div class="kv"><span>📁 قضايا مفتوحة</span><b>${open.length}</b></div>
    <div class="kv"><span>⏰ تقترب من المهلة</span><b>${urg.length?urg.map(c=>c.id).join("، "):"—"}</b></div>
    <div class="kv"><span>💵 الرواتب بعد</span><b>${salaryIn} أيام</b></div>
    <div class="kv"><span>🔥 حرارة التحقيق الداخلي</span><b>${S.internal.heat}${S.internal.open?" (مفتوح ضدك!)":""}</b></div>
    <div class="kv"><span>🕸️ المؤامرة</span><b>${S.plot.stage===0?"لا خيوط":S.plot.stage===1?"خيوط أولى":"اختراق داخلي!"}</b></div>
   </div></div>
  <div class="grid2">
   <div class="card"><h3>⭐ السمعة (7 جهات)</h3>${repBar("cit","👥 المواطنون")}${repBar("pol","👮 الشرطة")}${repBar("polit","🏛️ السياسيون")}${repBar("media","📺 الإعلام")}${repBar("crim","🔪 المجرمون (خوفهم منك)")}${repBar("jud","⚖️ القضاء")}${repBar("bus","💼 رجال الأعمال")}
   ${S.internal.open?`<div class="tag hot">🚨 تحقيق داخلي مفتوح ضدك! حرارة ${S.internal.heat}</div><div class="row"><button type="button" class="btn ok" onclick="defendInternal()">ادفع عن نفسك بالسجلات</button></div>`:`<div class="small mut">حرارة التحقيق الداخلي: ${S.internal.heat}</div>`}</div>
   <div class="card"><h3>📊 اقتصاد المدينة</h3>
    <div class="kv"><span>بطالة</span><b>${S.econ.unemp.toFixed(1)}%</b></div>
    <div class="kv"><span>فساد</span><b>${S.econ.corrup.toFixed(1)}%</b></div>
    <div class="kv"><span>نمو</span><b>${S.econ.growth}%</b></div>
    <div class="kv"><span>حللت قضايا</span><b>${S.stats.solved}</b></div>
    <div class="kv"><span>أخطاء قضائية</span><b>${S.stats.errors}</b></div>
    ${S.plot.notes.map(n=>`<div class="small ev">🕸️ ${n}</div>`).join("")}
   </div></div>
  <div class="card"><h3>🚨 الطوارئ (${S.emergencies.filter(e=>!e.done).length})</h3>
   ${S.emergencies.filter(e=>!e.done).slice(0,6).map(e=>`<div class="person"><b>${e.text}</b> <span class="mut">${e.dist} — يوم ${e.day}</span><div class="row"><button type="button" class="btn primary" onclick="resolveEmergency('${e.id}')">تحرك (يستهلك ضباطاً)</button><button type="button" class="btn" onclick="ignoreEmergency('${e.id}')">تجاهل</button></div></div>`).join("")||"<span class='mut'>لا طوارئ حالياً.</span>"}</div>
  <div class="card"><h3>🏢 العصابات</h3>${S.gangs.map(g=>`<div class="kv"><span>🔪 ${g.name} (${g.spec}) — ${g.mood}</span><b>قوة ${g.power}</b></div>`).join("")}</div>`;
}
function renderMapInfo(){
  const el=document.getElementById("map-legend"); if(!el)return;
  el.innerHTML=window.DISTRICTS.map(d=>`<span class="tag">${d.name}: ${d.crime}</span>`).join("");
  const di=document.getElementById("district-info"); if(!di)return;
  const open=window.S.cases.filter(c=>c.status!=="مغلقة").slice(0,8);
  const pois=(window.poiList?window.poiList():[]);
  di.innerHTML=`<div class="card"><h3>🏙️ معالم المدينة</h3><div class="poi-list">${pois.map(p=>`<div class="poi"><b>${p.name}</b><div class="mut">${p.info}</div></div>`).join("")}</div></div>
  <div class="card"><h3>📍 النشاط الحالي (🔴 عاجلة 🟡 عادية 🔵 طارئ)</h3>${open.map(c=>`<div class="kv"><span>${c.priority==="عاجلة"?"🔴":"🟡"} ${c.id} — ${c.type} @ ${c.distName}</span><button type="button" class="btn" onclick="focusCase('${c.id}')">فتح</button></div>`).join("")||"هادئة نسبياً…"}</div>`;
}
function focusCase(id){ window._openCase=id; renderCases(); switchTab("cases"); setTimeout(()=>{document.getElementById("case-"+id)?.scrollIntoView({behavior:"smooth"});},100); }
/* تحليل الأدلة مع إظهار النتيجة فوراً (لا تنطوي القوائم بوجهك) */
function analyzeEvidenceUI(caseId, idx){
  const c=caseById(caseId); if(!c)return;
  const before=c.evidence.filter(e=>e.found).length;
  analyzeEvidence(c, idx);
  window._openCase=caseId; // تبقى الأدلة مفتوحة حتى بعد أي تحديث
  save(); renderAll(); switchTab("cases");
  const after=c.evidence.filter(e=>e.found).length;
  const nxt=c.evidence[idx+1];
  toast("🧪 تم تحليل " + (c.evidence[idx]?.kind||"الدليل"));
  if(after>before && nxt) setTimeout(()=>toast("🔓 انفتح دليل جديد: "+nxt.kind+" → "+nxt.pointsTo),600);
  if(c.escalated) setTimeout(()=>toast("⚠️ تطور خطير: القضية مرتبطة بـ "+c.escalated.to),1200);
  const card=document.getElementById("case-"+caseId);
  if(card){ const d=card.querySelector("details"); if(d)d.open=true; setTimeout(()=>card.scrollIntoView({behavior:"smooth",block:"start"}),100); }
}
function renderCases(){
  const el=document.getElementById("tab-cases"); const S=window.S;
  el.innerHTML=`<div class="card"><b>📁 القضايا (${S.cases.length})</b><div class="mut small">القضية تستمر أياماً. المشتبه قد يهرب، الشاهد قد يختفي، الدليل قد يتلف.</div>
   <div class="row" style="margin-top:8px"><input id="newcase-idea" placeholder="💡 اكتب فكرة قضية… مثال: اختراق بنك بالتزامن مع اختفاء موظف"><button type="button" class="btn primary" onclick="aiCreateCaseBtn()">✨ توليدها بالـAI</button></div>
   <div class="row"><button type="button" class="btn" onclick="genCase();renderAll()">+ قضية عشوائية سريعة</button></div></div>`+
  S.cases.slice(0,15).map(c=>`
  <div class="card" id="case-${c.id}">
   <h3>${c.priority==="عاجلة"?"🔴":"🟡"} ${c.id} — ${c.type} <span class="mut">@ ${c.distName} — يوم ${c.day} — مهلة يوم ${c.deadline}</span></h3>
   <div><span class="tag ${c.status==="مفتوحة"?"hot":c.status==="مغلقة"?"good":""}">${c.status}</span><span class="tag">قانون: ${lawName(c.law)}</span>${c.escalated?`<span class="tag hot">⚠️ مرتبطة: ${c.escalated.to}</span>`:""}<span class="tag ai">مشبوهون ${c.suspects.length}</span></div>
   <div class="chatbox small">${c.log.slice(-6).map(l=>`<div>• ${l}</div>`).join("")}</div>
   <details${window._openCase===c.id?" open":""}><summary>🔗 الأدلة المترابطة (${c.evidence.filter(e=>e.found).length}/${c.evidence.length})</summary>
    ${c.evidence.map((e,i)=>`<div class="person"><b>${e.found?"🔓":"🔒"} ${e.kind}</b> <span class="mut">${e.reliable?"موثوق":"مشكوك فيه"}</span><div class="small">${e.found?e.desc:"مقفل — حلل الدليل السابق لفتحه."}</div><div class="small mut">يؤشر إلى: ${e.found?e.pointsTo:"؟؟"}</div>${e.found&&!e.analyzed?`<button type="button" class="btn ok" onclick="analyzeEvidenceUI('${c.id}',${i})">🧪 تحليل مخبري/استخباري</button>`:""}${e.analyzed?`<span class="tag good">محلَّل</span>`:""}</div>`).join("")}
    <div class="mut small">القاعدة: دليل واحد لا يدين. اربط بصمة→سيارة→هاتف→تحويل بنفسك.</div></details>
   <details><summary>🧑‍🤝‍🧑 المشتبهون (${c.suspects.length}) — الفاعل قد يكون خارج القائمة!</summary>
    ${c.suspects.map(s=>{s.chat=s.chat||[];return `<div class="person"><span class="nm">${s.name}</span> <span class="mut">${s.age}س — ${s.job} — ${s.gang} — ${s.status}</span><div class="bar ${s.suspicion<35?"low":""}"><i style="width:${s.suspicion}%"></i></div>
     <div class="row"><button type="button" class="btn primary" onclick="openPersonChat('${c.id}','${s.id}','suspect')">💬 شات استجواب AI ${s.chat.length?`(${s.chat.length})`:""}</button><button type="button" class="btn" onclick="arrestSuspect(caseById('${c.id}'),'${s.id}');renderAll()">⛓️ توقيف</button><button type="button" class="btn primary" onclick="openCourt('${c.id}','${s.id}')">⚖️ إحالة للمحكمة</button></div>${s.chat.length?`<div class="small mut">آخر رد: ${escHtml(s.chat[s.chat.length-1].text.slice(0,90))}…</div>`:""}</div>`}).join("")}</details>
   <details><summary>👁️ الشهود (${c.witnesses.length}) — قد يكذبون!</summary>${c.witnesses.map(w=>{w.chat=w.chat||[];return `<div class="person"><b>${w.name}</b> <span class="mut">ثقة ${w.trust}</span><div class="small">${w.says?escHtml(w.says.slice(0,120))+"…":"لم يُستجوب بعد."}</div><button type="button" class="btn primary" onclick="openPersonChat('${c.id}','${w.id}','witness')">💬 شات الشاهد AI ${w.chat.length?`(${w.chat.length})`:""}</button></div>`}).join("")||"لا شهود (اختفوا!)."}</details>
   <div class="row"><button class="btn" onclick="assignOfficers('${c.id}')">👮 إسناد ضباط</button><button class="btn" onclick="intelDeep('${c.id}')">🛰️ بحث استخباري معمق (AI)</button><span class="mut small" id="deep-${c.id}"></span></div>
  </div>`).join("")||"<div class='card'>لا قضايا.</div>";
}
function escHtml(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
/* ===== شات AI مستمر مع مشتبه/شاهد (نافذة لا تُمسح) ===== */
window._activeChat = null;
function openPersonChat(caseId, personId, kind){
  window._activeChat = {caseId, personId, kind};
  paintPersonChat();
}
function closePersonChat(){ window._activeChat = null; document.getElementById("modal").classList.add("hidden"); }
function getChatPerson(){
  const a = window._activeChat; if(!a) return null;
  const c = caseById(a.caseId); if(!c) return null;
  const p = a.kind==="suspect" ? c.suspects.find(x=>x.id===a.personId) : c.witnesses.find(x=>x.id===a.personId);
  return {c, p};
}
function paintPersonChat(typing){
  const gp = getChatPerson(); if(!gp) return;
  const {c, p} = gp; const a = window._activeChat;
  p.chat = p.chat || [];
  const title = a.kind==="suspect" ? `🎤 استجواب: ${p.name}` : `👁️ شاهد: ${p.name}`;
  const sub = a.kind==="suspect"
    ? `${c.id} — ${c.type} @ ${c.distName} • ${p.job} • الحالة: ${p.status}`
    : `${c.id} — ثقة ${p.trust} • قد يكذب أو يخاف`;
  document.getElementById("modal").classList.remove("hidden");
  document.getElementById("modal-card").innerHTML = `
    <div class="row" style="justify-content:space-between"><b>${escHtml(title)}</b><button type="button" class="btn" onclick="closePersonChat()">✕ إغلاق</button></div>
    <div class="mut small">${escHtml(sub)}</div>
    <div class="chatbox" id="pc-log" style="max-height:46vh">${p.chat.map(m=>`<div class="msg ${m.me?"me":""}"><span class="who">${m.me?"أنت (المحقق)":escHtml(p.name)}:</span> ${escHtml(m.text)}</div>`).join("")||"<div class='mut small'>ابدأ الحديث… اسأله: أين كنت ليلة الحادثة؟</div>"}${typing?"<div class='msg'><span class='who'>"+escHtml(p.name)+":</span> … يكتب الآن …</div>":""}</div>
    <div class="row"><input id="pc-input" placeholder="اكتب سؤالك هنا…"><button type="button" class="btn primary" onclick="personChatSend()">إرسال</button></div>
    <div class="row"><button type="button" class="btn" onclick="personChatQuick('أين كنت ليلة الحادثة؟')">أين كنت ليلتها؟</button><button type="button" class="btn" onclick="personChatQuick('من تعرف من المشتبهين الآخرين؟')">علاقتك بالآخرين؟</button><button type="button" class="btn" onclick="personChatQuick('هل تهددك جهة ما؟')">هل أنت مهدد؟</button></div>`;
  const log = document.getElementById("pc-log"); if(log) log.scrollTop = log.scrollHeight;
  const inp = document.getElementById("pc-input");
  if(inp) inp.onkeydown = (e)=>{ if(e.key==="Enter") personChatSend(); };
}
function personChatQuick(q){ const inp=document.getElementById("pc-input"); if(inp){inp.value=q; personChatSend();} }
async function personChatSend(){
  const inp = document.getElementById("pc-input");
  const txt = (inp?.value||"").trim(); if(!txt || window._chatBusy) return;
  const gp = getChatPerson(); if(!gp) return;
  const {c, p} = gp; const a = window._activeChat;
  window._chatBusy = true;
  p.chat.push({me:true, text:txt});
  if(a.kind==="suspect"){ p.questioned=(p.questioned||0)+1; }
  paintPersonChat(true);
  try{
    let r;
    if(a.kind==="suspect"){
      const ctx=`القضية ${c.id} (${c.type}) في ${c.distName}. المشتبه ${p.name} (${p.job}، ${p.age}س). استُجوب ${p.questioned} مرات. سجل الحديث:\n${p.chat.slice(-6).map(m=>(m.me?"المحقق: ":"المشتبه: ")+m.text).join("\n")}\nذاكرته: ${memOf(p.id)}. الأدلة الظاهرة: ${c.evidence.filter(e=>e.found).map(e=>e.kind).join("، ")}.`;
      r = await window.AI.chat({system:"أنت مشتبه به في تحقيق جنائي. شخصيتك واحدة ثابتة (اختر: خائف متلعثم، أو متعاون جزئياً، أو مراوغ ذكي، أو عدواني). أجب باختصار (2-5 أسطر) على آخر سؤال فقط. قد تكذب أو تخفي أو تراوغ حسب شخصيتك. لا تعترف أبداً إلا إذا ذُكر دليلان قويان معاً. لا تكشف أنك AI. بالعربية.", user:txt, context:ctx});
      addMemory(p.id, `استُجوب: ${txt.slice(0,60)}… → ${r.text.slice(0,80)}…`);
      c.log.push(`استجواب ${p.name}: ${txt.slice(0,60)}… → ${r.text.slice(0,100)}…`);
    } else {
      const ctx=`القضية ${c.id} (${c.type}). الشاهد ${p.name}. سجل الحديث:\n${p.chat.slice(-6).map(m=>(m.me?"المحقق: ":"الشاهد: ")+m.text).join("\n")}`;
      r = await window.AI.chat({system:`أنت شاهد في قضية جنائية. دافعك الخفي: ${p.motive}. تصرف وفقه (خائف يتلعثم، يحمي قريباً فيراوغ، مدفوع يكذب بثقة، صادق يتعاون). أجب باختصار (2-4 أسطر) ولا تكشف دافعك مباشرة. بالعربية.`, user:txt, context:ctx});
      p.says = r.text; addMemory(p.id, `شهد: ${r.text.slice(0,80)}…`);
      c.log.push(`شهادة ${p.name}: ${r.text.slice(0,100)}…`);
    }
    p.chat.push({me:false, text:r.text});
  }catch(e){ p.chat.push({me:false, text:"(تعذر الاتصال — أعد المحاولة)"}); }
  window._chatBusy = false;
  save(); paintPersonChat();
  try{ renderCases(); }catch(e){}
}
/* توافق خلفي: الأزرار القديمة تفتح الشات */
async function questionSuspect(caseId,susId){ openPersonChat(caseId, susId, "suspect"); }
async function questionWitness(caseId,wid){ openPersonChat(caseId, wid, "witness"); }
/* ===== شات AI مع الضباط ===== */
window._activeOfficer = null;
function openOfficerChat(oid){
  window._activeOfficer = oid;
  paintOfficerChat();
}
function closeOfficerChat(){ window._activeOfficer=null; document.getElementById("modal").classList.add("hidden"); }
function paintOfficerChat(typing){
  const o = window.S.officers.find(x=>x.id===window._activeOfficer); if(!o) return;
  o.chat = o.chat || [];
  document.getElementById("modal").classList.remove("hidden");
  document.getElementById("modal-card").innerHTML = `
    <div class="row" style="justify-content:space-between"><b>👮 ${escHtml(o.name)} <span class="tag">${escHtml(o.rank)} • ${escHtml(o.spec)}</span></b><button type="button" class="btn" onclick="closeOfficerChat()">✕ إغلاق</button></div>
    <div class="mut small">ولاء ${o.loyalty} • حالة ${escHtml(o.status)} • يتذكر كل قراراتك بحقه</div>
    <div class="chatbox" id="oc-log" style="max-height:46vh">${o.chat.map(m=>`<div class="msg ${m.me?"me":""}"><span class="who">${m.me?"أنت (القائد)":escHtml(o.name)}:</span> ${escHtml(m.text)}</div>`).join("")||"<div class='mut small'>تحدث مع ضابطك… اسأله عن قضية، أو كلفه بمهمة، أو اسأله عن رأيه.</div>"}${typing?"<div class='msg'><span class='who'>"+escHtml(o.name)+":</span> … يكتب …</div>":""}</div>
    <div class="row"><input id="oc-input" placeholder="اكتب رسالتك للضابط…"><button type="button" class="btn primary" onclick="officerChatSend()">إرسال</button></div>
    <div class="row"><button type="button" class="btn" onclick="officerChatQuick('ما وضع قضاياك الحالية؟')">وضع قضاياك؟</button><button type="button" class="btn" onclick="officerChatQuick('أريدك تراقب الحي الفقير وتبلغني بأي حركة')">كلفه بمهمة</button><button type="button" class="btn" onclick="officerChatQuick('هل لاحظت شيئاً مريباً داخل المركز؟')">شيء مريب؟</button></div>`;
  const log=document.getElementById("oc-log"); if(log)log.scrollTop=log.scrollHeight;
  const inp=document.getElementById("oc-input");
  if(inp)inp.onkeydown=(e)=>{if(e.key==="Enter")officerChatSend();};
}
function officerChatQuick(q){ const i=document.getElementById("oc-input"); if(i){i.value=q;officerChatSend();} }
async function officerChatSend(){
  const inp=document.getElementById("oc-input"); const txt=(inp?.value||"").trim();
  if(!txt||window._ochatBusy)return;
  const o=window.S.officers.find(x=>x.id===window._activeOfficer); if(!o)return;
  window._ochatBusy=true; o.chat.push({me:true,text:txt}); paintOfficerChat(true);
  try{
    const ctx=`الضابط ${o.name} (${o.rank}، تخصص ${o.spec}). الولاء ${o.loyalty}، الحالة ${o.status}. سجل الحديث:\n${o.chat.slice(-6).map(m=>(m.me?"القائد: ":"الضابط: ")+m.text).join("\n")}\nذاكرته عنك: ${memOf(o.id)}\nالقضايا المفتوحة: ${window.S.cases.filter(c=>c.status==="مفتوحة").slice(0,3).map(c=>c.id+" "+c.type).join("، ")}`;
    const r=await window.AI.chat({system:`أنت ضابط شرطة (${o.spec}) تتحدث مع قائدك المباشر عبر دردشة خاصة. شخصيتك ثابتة: ${o.loyalty>70?"مخلص ومحترم":o.loyalty>45?"مهني متحفظ":"متذمر وحذر"}. أجب باختصار (2-4 أسطر): تقارير ميدانية، طلب موارد عند الحاجة، أو رأي صادق. إن كنت فاسداً (${o.corrupt?"نعم":"لا"}) لا تكشف ذلك أبداً بل تظاهر بالإخلاص. لا تخترع أدلة قاطعة. بالعربية.`,user:txt,context:ctx});
    o.chat.push({me:false,text:r.text});
    addMemory(o.id,`دردشة: ${txt.slice(0,50)}…`);
  }catch(e){ o.chat.push({me:false,text:"(تعذر الاتصال — أعد المحاولة)"}); }
  window._ochatBusy=false; save(); paintOfficerChat();
}
async function intelDeep(caseId){
  const c=caseById(caseId); const box=document.getElementById("deep-"+caseId); if(box)box.textContent="… الاستخبارات تبحث …";
  const ctx=`القضية ${c.id} (${c.type}) في ${c.distName}. المشتبهون: ${c.suspects.slice(0,6).map(s=>s.name).join("، ")}. الأدلة: ${c.evidence.filter(e=>e.found).map(e=>e.kind).join("، ")}.`;
  const r=await window.AI.chat({system:window.INVESTIGATORS[0].sys,user:"قدّم بحثاً: مراقبة/تتبع/مصادر حول هذه القضية.",context:ctx+(memOf("int")?"\nذاكرة سابقة:\n"+memOf("int"):"")});
  addMemory("int",`بحث في ${c.id}: ${r.text.slice(0,100)}…`);
  c.log.push(`تقرير استخباري: ${r.text.slice(0,150)}…`);
  if(box)box.innerHTML=r.text;
  save(); renderCases();
}
function renderCourt(){
  const el=document.getElementById("tab-court"); const S=window.S;
  const active=S.cases.filter(c=>c.court&&!c.court.verdict);
  const done=S.cases.filter(c=>c.court?.verdict).slice(0,5);
  el.innerHTML=`<div class="card"><h3>⚖️ المحكمة — جلسات تفاعلية</h3><div class="mut">المحامي AI يستغل أي خطأ. الشهود قد يكذبون. الحكم ضمن حدود القانون فقط. الاستئناف وارد للأحكام ≥10 سنوات.</div></div>`+
  (active.map(c=>{
    const s=c.suspects.find(x=>x.id===c.court.suspect); const range=courtVerdictRange(c);
    return `<div class="card"><h3>🔨 ${c.id} — محاكمة ${s.name}</h3>
    <div><span class="tag">${lawName(c.law)}</span><span class="tag">الحد: ${range.min}–${range.max} سنة، غرامة ≤ ${fmt(range.maxFine)}</span></div>
    <div class="chatbox">${c.court.transcript.map(t=>`<div class="msg"><span class="who">${t.who}:</span> ${t.text}</div>`).join("")}</div>
    <div class="row"><button class="btn" onclick='courtAskLawyer(caseById("${c.id}"))'>🎓 مرافعة المحامي (AI)</button>
    ${c.witnesses.map(w=>`<button class="btn" onclick='courtAskWitness(caseById("${c.id}"),"${w.id}")'>👁️ ${w.name}</button>`).join("")}</div>
    <div class="row" style="margin-top:6px"><input id="vy-${c.id}" type="number" value="${range.min}" min="${range.min}" max="${range.max}" style="max-width:110px" placeholder="سنوات"><input id="vf-${c.id}" type="number" value="5000" style="max-width:140px" placeholder="غرامة"><button class="btn primary" onclick="doVerdict('${c.id}')">إصدار الحكم</button><button class="btn ok" onclick="doAcquit('${c.id}')">براءة</button></div>
    <div class="mut small">القوانين الكاملة في تبويب السجلات.</div></div>`;
  }).join("")||"<div class='card mut'>لا جلسات نشطة. أحِل مشتبهاً من تبويب القضايا.</div>")+
  `<div class="card"><h3>📜 أحكام سابقة + استئنافات (${S.appeals.length})</h3>${done.map(c=>`<div class="kv"><span>${c.id} — ${c.court.verdict.acquit?"براءة":"حكم "+c.court.verdict.years+" سنوات"}</span></div>`).join("")}${S.appeals.map(a=>`<div class="kv"><span>⚖️ العليا: ${a.caseId} — ${a.name}</span><button class="btn" onclick="resolveAppeal('${a.caseId}')">بتّ الاستئناف</button></div>`).join("")}</div>`;
}
function doVerdict(caseId){ const c=caseById(caseId); const y=+document.getElementById("vy-"+caseId).value||5; const f=+document.getElementById("vf-"+caseId).value||0; issueVerdict(c,y,f,false); }
function doAcquit(caseId){ issueVerdict(caseById(caseId),0,0,true); }
function renderChat(){
  const el=document.getElementById("tab-chat");
  el.innerHTML=`<div class="card"><h3>💬 القيادات والفرق + غرفة الاجتماعات</h3><div class="mut">كل قائد AI بشخصية مختلفة. المحققون قد يخطئون أو يكتشفون ما فاتك. اطلب، شاور، واجتمع.</div></div>`+
  window.INVESTIGATORS.map(p=>`
   <div class="card"><h3>${p.role} — ${p.name}</h3><div class="mut small">${p.style}</div>
   ${p.id.startsWith("det")?`<div class="mut small">ذاكرة: ${(window.S.memory[p.id]||[]).slice(-2).join(" | ")||"—"}</div>`:""}
   <div class="chatbox" id="chat-${p.id}">${(window.S.chats[p.id]||[]).slice(-8).map(m=>`<div class="msg ${m.me?"me":""}"><span class="who">${m.me?"أنت":p.name}:</span> ${m.text}</div>`).join("")}</div>
   <div class="row"><input id="in-${p.id}" placeholder="اكتب أمرك أو سؤالك…"><button class="btn primary" onclick="sendTo('${p.id}')">إرسال</button></div></div>`).join("")+
  `<div class="card"><h3>🏛️ غرفة الاجتماعات (جماعي)</h3><div class="chatbox">${(window.S.chats.meeting||[]).slice(-10).map(m=>`<div class="msg"><span class="who">${m.who}:</span> ${m.text}</div>`).join("")}</div>
   <div class="row"><input id="in-meeting" placeholder="اطرح قضية للتشاور…"><button class="btn primary" onclick="sendMeeting()">اجتماع</button></div></div>`;
}
async function sendTo(pid){
  const inp=document.getElementById("in-"+pid); const txt=inp.value.trim(); if(!txt)return; inp.value="";
  const p=window.INVESTIGATORS.find(x=>x.id===pid);
  window.S.chats[pid].push({me:true,text:txt});
  const open=window.S.cases.filter(c=>c.status==="مفتوحة").slice(0,3).map(c=>`${c.id}:${c.type}@${c.distName}`).join(" | ");
  const ctx=`المدينة: اليوم ${window.S.day}. قضايا مفتوحة: ${open}. ذاكرتك عن القائد: ${memOf(pid)}.`;
  const r=await window.AI.chat({system:p.sys,user:txt,context:ctx});
  window.S.chats[pid].push({me:false,text:r.text});
  addMemory(pid,`حديث: ${txt.slice(0,60)}… → رددت بملخص ${r.text.slice(0,60)}…`);
  save(); renderChat();
}
async function sendMeeting(){
  const inp=document.getElementById("in-meeting"); const txt=inp.value.trim(); if(!txt)return; inp.value="";
  window.S.chats.meeting.push({who:"القائد (أنت)",text:txt});
  for(const pid of ["det1","det2","det3"]){
    const p=window.INVESTIGATORS.find(x=>x.id===pid);
    const r=await window.AI.chat({system:p.sys+" اجتمع مع القائد ومحققين آخرين. قد تختلف معهم أو تخطئ.",user:txt,context:`آراء سابقة: ${(window.S.chats.meeting||[]).slice(-4).map(m=>m.who+":"+m.text.slice(0,80)).join("\n")}`});
    window.S.chats.meeting.push({who:p.name,text:r.text});
  }
  save(); renderChat();
}
function renderOfficers(){
  const S=window.S; const el=document.getElementById("tab-officers");
  el.innerHTML=`<div class="card row"><b>👮 الضباط (${S.officers.length}) — الرواتب: ${fmt(officerPayroll())}/أسبوع</b>
   <button class="btn primary" onclick="hireOfficer()">+ توظيف ضابط</button>
   <button class="btn" onclick="createSquad(prompt('اسم الفرقة الجديدة:')||'')">+ فرقة</button></div>
  <div class="card"><h3>🎖️ الفرق (${S.squads.length})</h3>${S.squads.map(q=>`<div class="kv"><span>${q.name} — القائد: ${q.leader||"—"} — الأعضاء: ${q.members.length}</span></div>`).join("")||"<span class='mut'>أنشئ: تحقيق، جنائيات، مخدرات، أسلحة، تدخل، استخبارات…</span>"}
   <div class="mut small">الفرق الافتراضية: ${SQUAD_DEFS.join("، ")}</div></div>`+
  S.officers.slice(0,30).map(o=>{o.chat=o.chat||[];return `<div class="person"><span class="nm">${o.name}</span> <span class="tag">${o.rank}</span><span class="tag">${o.spec}</span><span class="tag">${o.status}</span>
   <div class="small mut">ذكاء ${o.intel} • ولاء ${o.loyalty} • شجاعة ${o.brave} • راتب ${o.salary} ${o.corrupt?"• ⚠️ مشبوه (أنت لا تعرف!)":""}</div>
   <div class="small">السجل: ${(o.history||[]).slice(-3).join(" | ")}</div>
   <div class="small mut">الذاكرة: ${(window.S.memory[o.id]||[]).slice(-2).join(" | ")||"—"}</div>
   <div class="row"><button type="button" class="btn primary" onclick="openOfficerChat('${o.id}')">💬 دردشة ${o.chat.length?`(${o.chat.length})`:""}</button><button type="button" class="btn" onclick="officerAction('${o.id}','promote')">⬆️ ترقية</button><button type="button" class="btn ok" onclick="officerAction('${o.id}','reward')">🏅 مكافأة</button><button type="button" class="btn" onclick="officerAction('${o.id}','warn')">⚠️ تحذير</button><button type="button" class="btn" onclick="officerAction('${o.id}','probe')">🔍 تحقيق فساد</button><button type="button" class="btn danger" onclick="officerAction('${o.id}','fire')">❌ فصل</button></div></div>`}).join("")+
  `<div class="card"><h3>🧪 الخبراء (راتب 1500/أسبوع لكل خبير)</h3><div class="row">${window.EXPERTS.map(e=>`<button class="btn ${(S.experts||[]).includes(e)?"ok":""}" onclick="toggleExpert('${e}')">${(S.experts||[]).includes(e)?"✔ ":"+"} ${e}</button>`).join("")}</div></div>`;
}
function renderBudget(){
  const S=window.S;
  document.getElementById("tab-budget").innerHTML=`<div class="card"><h3>💰 الميزانية — رصيدك ${fmt(S.money)} • دعم الدولة ~${fmt(stateFunding())}</h3>
  <div class="kv"><span>رواتب الضباط/أسبوع</span><b>${fmt(officerPayroll())}</b></div>
  <div class="kv"><span>الخبراء/أسبوع</span><b>${fmt(expertCost())}</b></div>
  <div class="mut small">وزّع ميزانية الدولة %: الشرطة/الاستخبارات/العمليات/المحاكم/السجون/المعدات. التمويل يحسّن الاستجابة وجودة المعلومات.</div>
  ${Object.entries({police:"👮 شرطة",intel:"🛰️ استخبارات",ops:"⚔️ عمليات",courts:"⚖️ محاكم",prisons:"🔒 سجون",equip:"🚔 معدات"}).map(([k,l])=>`<div class="kv"><span>${l}</span><span><input type="range" min="0" max="60" value="${S.budget[k]}" onchange="setBudget('${k}',this.value)" style="width:120px"> ${S.budget[k]}%</span></div>`).join("")}
  <div class="row"><button class="btn" onclick="donate()">❤️ تبرع للمدينة (سمعة +)</button><button class="btn" onclick="upgradeUnit('police')">🚔 تطوير الشرطة ($8000)</button><button class="btn" onclick="upgradeUnit('intel')">🛰️ تطوير الاستخبارات ($8000)</button></div></div>`;
}
function prisonGet(p){
  if(p.health==null){p.health=rnd(60,90);p.morale=rnd(30,70);p.coop=rnd(10,50);p.meals=0;p.cell=false;p.visits=0;}
  return p;
}
function renderPrison(){
  const S=window.S;
  document.getElementById("tab-prison").innerHTML=`<div class="card"><h3>🔒 السجن المركزي (${S.prisoners.length})</h3>
  <div class="mut">كل سجين أمامك في زنزانته: أطعمه واسقه وحسّن فراشه ليرتفع تعاونه، ثم استجوبه <b>قانونياً وبحضور محامٍ</b> ليعترف أو يكشف معلومات. ⚠️ التعذيب والإيذاء الجسدي <b>ممنوعان تماماً</b> — أي تجاوز = تحقيق داخلي فوري وانهيار سمعتك.</div></div>`+
  (S.prisoners.slice(0,20).map((raw,i)=>{const p=prisonGet(raw);return `<div class="person">
   <div class="cell-visual">🧍<div class="small" style="font-size:12px">🔒 ${escHtml(p.name)}</div></div>
   <div class="small mut" style="margin-top:6px">${escHtml(p.caseId)} — ${p.years} سنوات ${p.gang&&p.gang!=="—"?"— "+escHtml(p.gang):""} ${p.cell?"• 🛏️ زنزانة محسنة":""}</div>
   <div class="needs">
     <div class="need">❤️ صحة<div class="bar ${p.health<35?"low":""}"><i style="width:${p.health}%"></i></div>${p.health}</div>
     <div class="need">🙂 معنويات<div class="bar ${p.morale<35?"low":""}"><i style="width:${p.morale}%"></i></div>${p.morale}</div>
     <div class="need">🤝 تعاون<div class="bar ${p.coop<35?"low":""}"><i style="width:${p.coop}%"></i></div>${p.coop}</div>
   </div>
   <div class="row">
     <button type="button" class="btn ok" onclick="prisonMeal(${i})">🍲 وجبة ($50)</button>
     <button type="button" class="btn ok" onclick="prisonCare(${i})">💧💊 ماء ورعاية ($80)</button>
     <button type="button" class="btn" onclick="prisonCell(${i})">🛏️ تحسين الزنزانة ($500)</button>
   </div>
   <div class="row">
     <button type="button" class="btn" onclick="prisonVisit(${i})">👨‍👩‍👧 زيارة عائلية</button>
     <button type="button" class="btn primary" onclick="prisonInterrogate(${i})">🎤 استجواب قانوني (محامٍ حاضر)</button>
     <button type="button" class="btn" onclick="prisonDeal(${i})">🤝 صفقة معلومات</button>
   </div>
   <div class="small mut">الرعاية ترفع التعاون والاعتراف — الإهمال يخفض الصحة ويزيد الشغب والشكاوى.</div>
  </div>`}).join("")||"<div class='card mut'>فارغ — أحكامك بالسجن ستظهر هنا.</div>");
}
function prisonMeal(i){ const p=prisonGet(window.S.prisoners[i]); if(!p)return; if(window.S.money<50){toast("لا ميزانية للوجبات");return;} window.S.money-=50; p.health=Math.min(100,p.health+8); p.morale=Math.min(100,p.morale+6); p.coop=Math.min(100,p.coop+5); p.meals++; addMemory(p.name,`قدمت له وجبة ساخنة (${p.meals}×) — امتنان وتعاون أعلى.`); save(); renderPrison(); }
function prisonCare(i){ const p=prisonGet(window.S.prisoners[i]); if(!p)return; if(window.S.money<80){toast("لا ميزانية للرعاية");return;} window.S.money-=80; p.health=Math.min(100,p.health+15); p.morale=Math.min(100,p.morale+5); save(); renderPrison(); }
function prisonCell(i){ const p=prisonGet(window.S.prisoners[i]); if(!p||p.cell)return; if(window.S.money<500){toast("التحسين يكلف $500");return;} window.S.money-=500; p.cell=true; p.morale=Math.min(100,p.morale+15); p.coop=Math.min(100,p.coop+8); addFile("سجون",`تحسين زنزانة ${p.name}`,"سرير وتهوية أفضل."); save(); renderPrison(); }
function prisonVisit(i){ const p=prisonGet(window.S.prisoners[i]); if(!p)return; p.visits++; p.morale=Math.min(100,p.morale+12); p.coop=Math.min(100,p.coop+7); addMemory(p.name,`سمحت بزيارة عائلية (${p.visits}×) — تعاونه ارتفع.`); save(); renderPrison(); }
async function prisonInterrogate(i){
  const p=prisonGet(window.S.prisoners[i]); if(!p||window._pintBusy)return; window._pintBusy=true;
  toast("⚖️ بدأ استجواب قانوني بحضور محامٍ…");
  const evBonus=Math.min(30,(caseById(p.caseId)?.evidence.filter(e=>e.analyzed).length||0)*10);
  const chance=Math.max(5,Math.min(90,p.coop*0.6+p.morale*0.2+evBonus-10));
  const ok=Math.random()*100<chance;
  if(ok){
    p.coop=Math.min(100,p.coop+5);
    const r=await window.AI.chat({system:"أنت سجين يتعاون بعد استجواب قانوني إنساني وبحضور محاميه. اكشف معلومة واحدة مفيدة (اسم وسيط، مخبأ، موعد تسليم) دون اعترافات مبالغ فيها. بالعربية.",user:`السجين ${p.name} (${p.caseId}) وافق على الكلام. ماذا يكشف؟`,context:`معنوياته ${p.morale} وتعاونه ${p.coop}.`});
    window.S.pendingEvents.push({day:window.S.day+1,kind:"plot",text:`اعتراف قانوني من السجين ${p.name}: ${r.text.slice(0,120)}`});
    addNews(`اعتراف قانوني في ${p.caseId}`,`${p.name} كشف معلومات جديدة أثناء استجواب موثق بحضور محاميه.`,"good");
    rep("jud",2); rep("cit",1); toast("✅ اعترف وكشف معلومة! (سجلت في الأحداث)");
  }else{
    p.morale=Math.max(0,p.morale-6);
    if(p.morale<25&&Math.random()<0.4){ window.S.internal.heat+=6; addNews("شكوى من داخل السجن",`السجين ${p.name} اشتكى من سوء المعاملة — الإدارة تحقق. حسّن الرعاية والمعنويات.`,"bad"); }
    else toast(`❌ رفض الكلام (فرصة النجاح ${Math.round(chance)}%). ارفع تعاونه بالرعاية والأدلة.`);
  }
  window._pintBusy=false; save(); renderAll();
}
function renderNews(){
  document.getElementById("tab-news").innerHTML=`<div class="card"><h3>📰 صحيفة المدينة — قد تبالغ أو تخطئ</h3></div>`+window.S.news.slice(0,25).map(n=>`<div class="card ev"><b>[يوم ${n.day}] ${n.title}</b><div class="small">${n.body}</div></div>`).join("");
}
function renderFiles(){
  const S=window.S;
  document.getElementById("tab-files").innerHTML=`<div class="card"><h3>🗂️ السجلات والملفات (${S.files.length})</h3><div class="mut">كل قرار وحكم وعملية محفوظة. معلومة قديمة قد تحل قضية جديدة.</div><input id="fq" placeholder="ابحث في السجلات…" oninput="renderFilesQ(this.value)"><div id="fqres"></div></div>
  <div class="card"><h3>📚 قائمة القوانين (حدود الحكم)</h3>${window.LAWS.map(l=>`<div class="law"><b>${l.name}</b> — ${l.min} إلى ${l.max} سنوات — غرامة ≤ ${fmt(l.maxFine)}<div class="mut">${l.desc}</div></div>`).join("")}</div>
  <div class="card"><h3>🧠 ذاكرة الشخصيات</h3>${Object.entries(S.memory).slice(0,12).map(([k,v])=>`<details><summary>${k}</summary><div class="small">${v.slice(-5).join("<br>")}</div></details>`).join("")||"فارغة."}</div>`;
}
function renderSettings(){
  const me = window.Auth?.current(); const admin = window.Auth?.isAdmin();
  const accCard = `<div class="card"><h3>👤 حسابي</h3>
    <div class="kv"><span>الاسم</span><b>${me?escHtml(me.name):"—"}</b></div>
    <div class="kv"><span>البريد</span><b>${me?escHtml(me.email):"—"} ${admin?"👑 أدمن":""}</b></div>
    <div class="mut small">حفظك منفصل عن باقي الحسابات. تقدمك: يوم ${window.S?.day||1} • ${window.S?.cases?.length||0} قضايا.</div>
    <div class="row"><button type="button" class="btn" onclick="window.Auth.logout()">تسجيل الخروج</button><button type="button" class="btn danger" onclick="if(confirm('مسح مدينتك نهائياً؟')){wipe();location.reload()}">🗑️ مدينة جديدة (مسح حفظي)</button></div></div>`;
  let adminCard = "";
  if(admin){
    const users = window.Auth.list();
    adminCard = `<div class="card"><h3>👑 لوحة الأدمن — تحكم كامل</h3>
    <div class="mut small">مسجّل كـ ${escHtml(window.ADMIN_EMAIL)}. إعدادات الـAI والأحداث واللاعبون.</div>
    <h3 style="margin-top:8px">🔌 إعدادات AI API</h3>
    <label class="small">رابط API</label><input id="s-url" value="${localStorage.getItem("ai_url")||window.GAME_CONFIG.AI_URL}">
    <label class="small">المفتاح</label><input id="s-key" value="${localStorage.getItem("ai_key")||window.GAME_CONFIG.AI_KEY}">
    <label class="small">الموديل (يعمل حالياً: gpt-5-mini)</label><input id="s-model" value="${localStorage.getItem("ai_model")||"gpt-5-mini"}">
    <div class="row" style="margin-top:6px"><button type="button" class="btn primary" onclick="saveAI()">حفظ</button><button type="button" class="btn" onclick="testAI()">اختبار الاتصال</button><span class="mut small" id="ai-test"></span></div>
    <h3 style="margin-top:10px">🎮 التحكم بالمدينة (مدينتك الحالية)</h3>
    <div class="row"><button type="button" class="btn ok" onclick="adminGrant(50000)">+ 50,000 💰</button><button type="button" class="btn" onclick="genCase();renderAll()">+ قضية</button><button type="button" class="btn" onclick="adminEvent()">🚨 حدث طارئ الآن</button><button type="button" class="btn" onclick="adminBoostRep()">⭐ رفع السمعات +10</button></div>
    <div class="row"><input id="adm-news" placeholder="📢 بث خبر عاجل للصحيفة…"><button type="button" class="btn primary" onclick="adminBroadcast()">بث</button></div>
    <h3 style="margin-top:10px">👥 اللاعبون (${users.length})</h3>
    ${users.map(u=>`<div class="kv"><span>${escHtml(u.name)}<br><span class="mut">${escHtml(u.email)}${u.email===window.ADMIN_EMAIL.toLowerCase()?" 👑":""}</span></span><span class="row"><button type="button" class="btn" onclick="adminResetSave('${escHtml(u.email)}')">تصفير حفظه</button>${u.email!==window.ADMIN_EMAIL.toLowerCase()?`<button type="button" class="btn danger" onclick="if(confirm('حذف ${escHtml(u.email)}؟')){window.Auth.remove('${escHtml(u.email)}');renderAll()}">حذف</button>`:""}</span></div>`).join("")}
    </div>`;
  } else {
    adminCard = `<div class="card"><h3>🔌 الذكاء الاصطناعي</h3><div class="mut small">إعدادات الـAPI تُدار من لوحة الأدمن. إن فشل الاتصال يعمل المولد المحلي تلقائياً.</div></div>`;
  }
  document.getElementById("tab-settings").innerHTML = accCard + adminCard;
}
function adminGrant(n){ window.S.money+=n; addNews("دعم استثنائي","الإدارة العليا ضخت تمويلاً إضافياً للقيادة.","good"); save(); renderAll(); }
function adminEvent(){ window.S.emergencies.unshift({id:"EM-ADM"+Date.now()%9999,text:pick(window.EMERGENCIES),day:window.S.day,done:false,dist:pick(window.DISTRICTS).name}); save(); renderAll(); }
function adminBoostRep(){ for(const k of Object.keys(window.S.rep)) rep(k,10); save(); renderAll(); }
function adminBroadcast(){ const i=document.getElementById("adm-news"); if(i&&i.value.trim()){addNews("📢 بيان رسمي",i.value.trim(),"alert"); i.value=""; save(); renderAll();} }
function adminResetSave(email){ localStorage.removeItem(window.GAME_CONFIG.SAVE_KEY+"::"+email.toLowerCase()); toast("صُفّر حفظ "+email); }
/* actions used by inline onclick */
function setBudget(k,v){ window.S.budget[k]=+v; save(); }
function toggleExpert(e){ window.S.experts=window.S.experts||[]; const i=window.S.experts.indexOf(e); if(i>=0)window.S.experts.splice(i,1); else window.S.experts.push(e); save(); renderAll(); }
function donate(){ if(window.S.money>=3000){window.S.money-=3000;rep("cit",4);rep("media",2);addNews("القاضي يتبرع للمدينة","تبرع سخي يعيد رفع السمعة الشعبية.","good");} save();renderAll(); }
function upgradeUnit(u){ if(window.S.money>=8000){window.S.money-=8000; if(u==="police")window.S.econ.policeFund+=10; else window.S.econ.intelFund+=10; toast("تم التطوير");} save();renderAll(); }
function resolveEmergency(id){ const e=window.S.emergencies.find(x=>x.id===id); if(!e)return; const avail=window.S.officers.filter(o=>o.status==="متاح").length; if(avail<2){toast("لا موارد كافية! تحتاج ضابطين على الأقل — الصعوبة مقصودة");return;} e.done=true; rep("cit",3); rep("pol",2); window.S.money+=1500; addNews("احتواء: "+e.text,"تدخلت القيادة بسرعة رغم نقص الموارد.","good"); save();renderAll(); }
function ignoreEmergency(id){ const e=window.S.emergencies.find(x=>x.id===id); if(e){e.done=true;e.ignored=true;rep("cit",-4);rep("media",-3);addNews("إهمال: "+e.text,"تجاهل البلاغ يفاقم الأزمة.","bad");} save();renderAll(); }
function prisonDeal(i){ const p=window.S.prisoners[i]; if(!p)return; p.behavior+=5; addNews("سجين يتعاون",`${p.name} عرض معلومات عن عصابة مقابل تخفيف. خيط جديد!`,"info"); window.S.pendingEvents.push({day:window.S.day+2,kind:"plot",text:`معلومة من السجين ${p.name}: تحركات مشبوهة لعصابة في ${pick(["الحي الفقير","المنطقة الصناعية"])}.`}); save();renderAll(); }
function prisonRiot(i){ const p=window.S.prisoners[i]; if(p){p.behavior-=10;rep("pol",-2);addNews("شغب في السجن","أحداث شغب محدودة. الوضع تحت السيطرة.","bad");} save();renderAll(); }
function resolveAppeal(caseId){ const S=window.S; const a=S.appeals.find(x=>x.caseId===caseId); if(!a)return; a.status="محسوم"; const keep=Math.random()<0.6; addNews("المحكمة العليا تبت",`${caseId}: ${keep?"تأييد الحكم":"تخفيف/إعادة تحقيق"}. طُلب تفسير الأدلة.` ,keep?"info":"alert"); if(!keep){const c=caseById(caseId); if(c){c.status="مفتوحة"; c.court=null;}} S.appeals=S.appeals.filter(x=>x!==a); save();renderAll(); }
async function dailyBrief(){ const box=document.getElementById("brief"); if(box)box.innerHTML="…"; const ctx=`اليوم ${window.S.day}. قضايا: ${window.S.cases.slice(0,4).map(c=>c.id+c.type).join("، ")}. طوارئ: ${window.S.emergencies.filter(e=>!e.done).map(e=>e.text).join("، ")}. سمعة: ${JSON.stringify(window.S.rep)}.`; const r=await window.AI.chat({system:"أنت مستشار القائد. لخص الأولويات (أهم 3) وحذر من إهمال شيء. بالعربية.",user:"ما موجز اليوم وخطة الأولويات؟",context:ctx}); if(box)box.innerHTML=`<div class="msg"><span class="who">موجز AI:</span> ${r.text}</div>`; }
async function secretOp(){ const S=window.S; const n=rnd(2,4); addFile("سرية",`عملية سرية يوم ${S.day}`,`مجموعة محدودة (${n} ضباط). احتمال تسريب!`); if(Math.random()<0.3){S.pendingEvents.push({day:S.day+rnd(2,5),kind:"leak",text:"تسريب عملية سرية! ابحث عن المسرّب بين الضباط والموظفين."});toast("انطلقت العملية… مع خطر تسريب");} else {toast("عملية سرية ناجحة: معلومات مهمة");S.pendingEvents.push({day:S.day+1,kind:"plot",text:"العملية السرية كشفت وسيطاً مالياً يربط قضيتين!"});} save();renderAll(); }
async function askBribe(){ const amt=fmt(rnd(20000,100000)); const ok=confirm(`💸 شخص مجهول يعرض ${amt} لإغلاق قضية/تخفيف حكم.\nموافق = قبول؟ إلغاء = رفض وإبلاغ.`); if(ok){window.S.money+=30000;window.S.internal.heat+=20;window.S.econ.corrup+=5;addFile("فساد",`رشوة مقبولة يوم ${window.S.day}`,"قبلت المال — خطر انكشاف وتحقيق داخلي.");toast("قبلت… قد ينكشف الأمر");} else {rep("jud",3);rep("cit",2);addFile("نزاهة",`رفض رشوة يوم ${window.S.day}`,"رفضت وأبلغت.");toast("رفضت الرشوة — سمعة +");} save();renderAll(); }
function defendInternal(){ const S=window.S; if(S.files.length>10){S.internal.heat=Math.max(0,S.internal.heat-25);if(S.internal.heat<50)S.internal.open=false;toast("دفاعك بالسجلات خفف الشبهة");} else toast("سجلاتك ضعيفة!"); save();renderAll(); }
function assignOfficers(caseId){ const c=caseById(caseId); const free=window.S.officers.filter(o=>o.status==="متاح").slice(0,3); if(!free.length){toast("لا ضباط متاحين — وزّع مواردك!");return;} c.assigned=free.map(o=>o.id); free.forEach(o=>o.status="مشغول"); c.log.push(`أُسند ${free.length} ضباط لـ ${c.id}. (نقص الموارد مقصود)`); save();renderAll(); }
function saveAI(){ localStorage.setItem("ai_url",document.getElementById("s-url").value); localStorage.setItem("ai_key",document.getElementById("s-key").value); localStorage.setItem("ai_model",document.getElementById("s-model").value); toast("حُفظت إعدادات AI"); }
async function testAI(){ const el=document.getElementById("ai-test"); el.textContent="…"; const r=await window.AI.chat({system:"أنت مساعد.",user:"قل: الاتصال يعمل."}); el.textContent=(r.via==="ai"?"✅ AI متصل: ":"⚠️ محلي: ")+r.text.slice(0,80); }
function renderFilesQ(q){ const res=(window.S.files||[]).filter(f=>(f.title+f.body).includes(q)).slice(0,20); document.getElementById("fqres").innerHTML=res.map(f=>`<div class="kv"><span>[${f.kind} يوم ${f.day}] ${f.title}</span></div>`).join(""); }
