/* ===== Cases: generation, linked evidence, case-in-case ===== */
function genCase(forceType){
  const S=window.S;
  const t = forceType ? window.CASE_TYPES.find(c=>c.type===forceType) : pick(window.CASE_TYPES);
  const dist = pick(t.dist);
  const dInfo = window.DISTRICTS.find(d=>d.id===dist);
  const nSus = rnd(6,12);
  const id = "Q-"+String(S.seq.case++).padStart(3,"0");
  const suspects=[];
  for(let i=0;i<nSus;i++){
    const gang = Math.random()<0.35 ? pick(S.gangs).name : "—";
    suspects.push({id:id+"-S"+(i+1), name:arabName(), age:rnd(19,58), job:pick(["سائق","تاجر","موظف بنك","عامل مصنع","مبرمج","عاطل","حارس","سمسار","طالب","ميكانيكي"]), gang, rel:pick(["لا صلة","صديق مشتبه آخر","قريب مشتبه آخر","جار","شريك عمل سابق","خصم قديم"]), status:"مشتبه", suspicion:rnd(5,60), questioned:0, lawyer:arabName()+" (محامٍ)", statement:"", lies:Math.random()<0.3});
  }
  // الأدوار الحقيقية المخفية: قد يكون الفاعل خارج القائمة
  const outside = Math.random()<0.35;
  const nActors = rnd(1,4);
  const roles = ["خطط","نفّذ","ساعد","غطّى","علم وسكت"];
  const truth = {outside, actors:[], gangLink: Math.random()<0.5?pick(S.gangs).name:null, note:""};
  const pool = [...suspects];
  for(let i=0;i<nActors;i++){
    if(outside && i===0){ truth.actors.push({who:"__OUTSIDE__", role:roles[i]}); }
    else { const s=pool.splice(Math.floor(Math.random()*pool.length),1)[0]; if(s) truth.actors.push({who:s.id, role:roles[i]}); }
  }
  if(outside){ truth.outsider={id:id+"-X", name:arabName(), job:"غير مسجل", gang:truth.gangLink||pick(S.gangs).name, hint:"يظهر فقط عبر اعتراف أو دليل متسلسل"}; }
  // سلسلة أدلة مترابطة: كل دليل يفتح التالي، وبعضها مضلل
  const chainKinds=["بصمة","سيارة مشبوهة","رقم هاتف","تحويل مالي","تسجيل كاميرا","شهادة شاهد","عينة DNA","بقايا سلاح","سجل دخول","رسالة مشفرة"];
  const evCount = rnd(3,5);
  const evidence=[];
  for(let i=0;i<evCount;i++){
    const target = Math.random()<0.75 && truth.actors.length ? pick(truth.actors) : null;
    let pointsTo = target ? (target.who==="__OUTSIDE__" ? "شخص مجهول (خيط خارج القائمة)" : (suspects.find(s=>s.id===target.who)?.name||"مجهول")) : pick(suspects).name;
    const reliable = Math.random()<0.7;
    evidence.push({id:id+"-E"+(i+1), kind:chainKinds[i%chainKinds.length], desc:"", pointsTo, reliable, found:i===0, analyzed:false, unlocks: i+1<evCount});
  }
  evidence[0].desc=`بلاغ أولي: ${t.type} في ${dInfo.name}. عُثر على ${evidence[0].kind} أولية تشير ظاهرياً إلى ${evidence[0].pointsTo}. (الدليل الظرفي وحده لا يدين)`;
  for(let i=1;i<evCount;i++) evidence[i].desc=`دليل متسلسل مقفل: يظهر بعد تحليل "${evidence[i-1].kind}". خيط يقود إلى ${evidence[i].pointsTo}. يحتاج مختبر/استخبارات.`;
  const c = {
    id, type:t.type, law:t.law, dist, distName:dInfo.name, sev:t.sev,
    day:S.day, status:"مفتوحة", deadline:S.day+rnd(5,14),
    suspects, evidence, truth, witnesses: genWitnesses(id, suspects),
    log:[`يوم ${S.day}: فُتحت القضية ${id} (${t.type}) في ${dInfo.name}.`],
    arrests:[], court:null, escalated:null, assigned:[], priority:t.sev>=5?"عاجلة":"عادية",
    hiddenPlot: Math.random()<0.3
  };
  S.cases.unshift(c);
  addNews(`بلاغ جديد: ${t.type} في ${dInfo.name}`,`فتحت قيادة التحقيق القضية ${id}. المشتبه بهم ${nSus}. التحقيق جارٍ وسط تكتم.`, "info");
  addFile("قضية",`${id} — ${t.type}`,`فتحت يوم ${S.day}. المنطقة: ${dInfo.name}.`);
  return c;
}
function genWitnesses(caseId, suspects){
  const n=rnd(2,5); const w=[];
  for(let i=0;i<n;i++){
    const motive=pick(["صادق","خائف","يحمي قريباً","مدفوع من عصابة","خصومة مع المتهم","متعاون سري"]);
    w.push({id:caseId+"-W"+(i+1), name:arabName(), motive, trust: motive==="صادق"?75: motive==="خائف"?45: 30, says:""});
  }
  return w;
}
function caseById(id){ return window.S.cases.find(c=>c.id===id); }
/* ===== إنشاء قضية من فكرة اللاعب عبر AI ===== */
async function aiCreateCase(idea){
  idea=(idea||"").trim();
  if(!idea) throw new Error("اكتب فكرة القضية أولاً");
  let spec=null;
  try{
    const laws=window.LAWS.map(l=>l.id+":"+l.name).join("، ");
    const dists=window.DISTRICTS.map(d=>d.id+":"+d.name).join("، ");
    const r=await window.AI.chat({system:`أنت مولد قضايا للعبة تحقيق. أجب بـ JSON فقط بهذا الشكل (بدون أي شرح خارج JSON): {"type":"اسم قصير","law":"معرف من القائمة","district":"معرف حي","severity":3,"suspects":["اسم1","اسم2","اسم3","اسم4","اسم5"],"clues":["دليل1","دليل2","دليل3"],"summary":"سطر واحد"}. القوانين: ${laws}. الأحياء: ${dists}. المشتبهون 5-8 أسماء عربية. الأدلة 3-4 من: بصمة، سيارة مشبوهة، رقم هاتف، تحويل مالي، تسجيل كاميرا، شهادة شاهد، عينة DNA، رسالة مشفرة.`,user:`فكرة اللاعب: ${idea}`,context:"",maxTokens:500});
    const m=r.text.match(/\{[\s\S]*\}/);
    if(m) spec=JSON.parse(m[0]);
  }catch(e){ spec=null; }
  if(!spec || !spec.type){ spec=localSpecFromIdea(idea); }
  return buildCustomCase(spec, idea);
}
function localSpecFromIdea(idea){
  const t = /قتل/.test(idea)?{type:"قتل",law:"murder"} : /مخدر/.test(idea)?{type:"تجارة مخدرات",law:"drugs"} : /سلاح|أسلحة/.test(idea)?{type:"تهريب أسلحة",law:"weapons"} : /سرق/.test(idea)?{type:"سرقة منظمة",law:"theft"} : /خطف|اختطاف/.test(idea)?{type:"اختطاف",law:"kidnap"} : /فساد|رشو/.test(idea)?{type:"فساد",law:"corrupt"} : /ابتزاز/.test(idea)?{type:"ابتزاز",law:"extort"} : /إلكترون|اختراق/.test(idea)?{type:"جرائم إلكترونية",law:"cyber"} : {type:"قضية غامضة",law:"theft"};
  const names=[]; const n=rnd(5,8); for(let i=0;i<n;i++)names.push(arabName());
  return {type:t.type, law:t.law, district:pick(window.DISTRICTS).id, severity:3, suspects:names, clues:["بصمة","رقم هاتف","تحويل مالي"], summary:idea.slice(0,80)};
}
function buildCustomCase(spec, idea){
  const S=window.S;
  const lawOk=window.LAWS.some(l=>l.id===spec.law)?spec.law:"theft";
  const distOk=window.DISTRICTS.some(d=>d.id===spec.district)?spec.district:pick(window.DISTRICTS).id;
  const dInfo=window.DISTRICTS.find(d=>d.id===distOk);
  const id="Q-"+String(S.seq.case++).padStart(3,"0");
  const names=(Array.isArray(spec.suspects)&&spec.suspects.length>=3?spec.suspects.slice(0,10):Array.from({length:6},()=>arabName()));
  const suspects=names.map((nm,i)=>({id:id+"-S"+(i+1),name:String(nm).slice(0,30),age:rnd(19,58),job:pick(["سائق","تاجر","موظف بنك","عامل مصنع","مبرمج","عاطل","حارس","سمسار","طالب","ميكانيكي"]),gang:Math.random()<0.35?pick(S.gangs).name:"—",rel:"لا صلة",status:"مشتبه",suspicion:rnd(5,60),questioned:0,lawyer:arabName()+" (محامٍ)",statement:"",lies:Math.random()<0.3,chat:[]}));
  const outside=Math.random()<0.35;
  const truth={outside,actors:[],gangLink:Math.random()<0.5?pick(S.gangs).name:null,note:"قضية من فكرة اللاعب"};
  const pool=[...suspects]; const roles=["خطط","نفّذ","ساعد","غطّى","علم وسكت"]; const nA=rnd(1,3);
  for(let i=0;i<nA;i++){ if(outside&&i===0)truth.actors.push({who:"__OUTSIDE__",role:roles[i]}); else{const s=pool.splice(Math.floor(Math.random()*pool.length),1)[0]; if(s)truth.actors.push({who:s.id,role:roles[i]});} }
  if(outside)truth.outsider={id:id+"-X",name:arabName(),job:"غير مسجل",gang:truth.gangLink||pick(S.gangs).name,hint:"يظهر عبر اعتراف أو دليل"};
  const kinds=Array.isArray(spec.clues)&&spec.clues.length?spec.clues.slice(0,5):["بصمة","رقم هاتف","تحويل مالي"];
  const evidence=kinds.map((k,i)=>{
    const target=Math.random()<0.7&&truth.actors.length?pick(truth.actors):null;
    const pts=target?(target.who==="__OUTSIDE__"?"شخص مجهول (خيط خارج القائمة)":(suspects.find(s=>s.id===target.who)?.name||"مجهول")):pick(suspects).name;
    return {id:id+"-E"+(i+1),kind:String(k).slice(0,24),desc:i===0?`بلاغ: ${spec.summary||spec.type} في ${dInfo.name}. ${k} أولية تشير ظاهرياً إلى ${pts}.`:`دليل متسلسل مقفل يظهر بعد تحليل السابق. خيط نحو ${pts}.`,pointsTo:pts,reliable:Math.random()<0.7,found:i===0,analyzed:false,unlocks:i+1<kinds.length};
  });
  const c={id,type:String(spec.type).slice(0,30),law:lawOk,dist:distOk,distName:dInfo.name,sev:Math.max(1,Math.min(5,+spec.severity||3)),day:S.day,status:"مفتوحة",deadline:S.day+rnd(5,14),suspects,evidence,truth,witnesses:genWitnesses(id,suspects),log:[`يوم ${S.day}: قضية بفكرة القائد — "${spec.summary||spec.type}" (${id}). الفكرة الأصلية: ${idea.slice(0,100)}`],arrests:[],court:null,escalated:null,assigned:[],priority:(+spec.severity>=4)?"عاجلة":"عادية",hiddenPlot:Math.random()<0.3,custom:true};
  S.cases.unshift(c);
  addNews(`قضية جديدة بطلب القيادة: ${c.type}`,`القضية ${id} في ${dInfo.name} — ${c.suspects.length} مشتبهين.`,"info");
  addFile("قضية",`${id} — ${c.type} (فكرة اللاعب)`,idea);
  save(); return c;
}
async function aiCreateCaseBtn(){
  const inp=document.getElementById("newcase-idea"); const idea=(inp?.value||"").trim();
  if(!idea){toast("اكتب فكرة القضية أولاً");return;}
  inp.disabled=true; toast("الـAI يكتب قضيتك…");
  try{ const c=await aiCreateCase(idea); toast("وُلدت القضية "+c.id); }
  catch(e){ toast(e.message); }
  inp.disabled=false; save(); renderAll(); switchTab("cases");
}
function analyzeEvidence(c, idx){
  const e=c.evidence[idx];
  if(!e||!e.found||e.analyzed) return;
  e.analyzed=true;
  // فتح التالي
  const nxt=c.evidence[idx+1];
  if(nxt){ nxt.found=true; c.log.push(`يوم ${window.S.day}: تحليل ${e.kind} كشف خيطاً جديداً: ${nxt.kind} → ${nxt.pointsTo}.`); }
  // احتمال قضية داخل قضية
  if(c.hiddenPlot && idx>=1 && !c.escalated && Math.random()<0.5){
    c.escalated={to:pick(["عصابة","تهريب أسلحة","جهة داخل الحكومة","شبكة غسيل أموال"]), day:window.S.day};
    c.log.push(`⚠️ تطور خطير يوم ${window.S.day}: القضية مرتبطة بـ ${c.escalated.to}! قضية داخل قضية.`);
    addNews(`القضية ${c.id} تتوسع: ارتباط بـ ${c.escalated.to}`,`مصادر: التحقيق كشف أن ${c.type} البسيطة ظاهرياً مرتبطة بشبكة أكبر.`, "alert");
    rep("media",3);
  }
  // احتمال اعتراف يكشف الخارجي
  if(c.truth.outside && Math.random()<0.4){
    const s=pick(c.suspects);
    c.log.push(`اعتراف جزئي: ${s.name} لمّح لوجود شخص خارج القائمة يقف خلف العملية. (تابع التحقيق)`);
    s.suspicion=Math.max(5,s.suspicion-10);
  }
}
function arrestSuspect(c, suspectId){
  const s=c.suspects.find(x=>x.id===suspectId); if(!s||s.status==="موقوف")return;
  s.status="موقوف"; c.arrests.push(suspectId);
  c.log.push(`يوم ${window.S.day}: توقيف ${s.name} بقرار من القيادة.`);
  window.S.stats.arrests++;
  // انتقام محتمل لاحق
  if(s.gang!=="—"){ window.S.pendingEvents.push({day:window.S.day+rnd(3,10), kind:"revenge", text:`جماعة ${s.gang} تتوعد بالانتقام لتوقيف ${s.name} (${c.id})`, caseId:c.id}); }
  // خطأ قضائي محتمل: التوقيف المبكر بدون أدلة محللة كافية
  const analyzed=c.evidence.filter(e=>e.analyzed).length;
  if(analyzed<2 && Math.random()<0.35){ s.wronglyHeld=true; }
}
