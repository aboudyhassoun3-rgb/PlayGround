/* ===== Extra systems: مطاردة + 30ث + مخبرون + قضية5د + مواسم + رتب + صحافة + تنوع + خيوط كاذبة ===== */
(function(){
"use strict";
/* --- ضمان حقول جديدة للحفظ القديم --- */
function ensureExtra(){
  const S=window.S; if(!S) return;
  if(!Array.isArray(S.informants)) S.informants=[];
  if(!S.season) S.season={no:1,startDay:S.day||1,theme:0,solvedAtStart:(S.stats?.solved||0)};
  if(!S.prank) S.prank={xp:0};
  if(!S.novel) S.novel={};
  if(!S.chase) S.chase=null;
  if(!S.quick) S.quick=null;
  if(!S.flash) S.flash=null;
  if(!S.pressCd) S.pressCd=0;
  if(!S.informSeq) S.informSeq=1;
}
window.ensureExtra=ensureExtra;

/* ===== #10 محرك منع التكرار ===== */
const SEASON_THEMES=[
  {name:"انتخابات ملوثة", desc:"مرشحون يشترون الأصوات — الرشاوى والضغوط تتضاعف.", fx:"فساد +"},
  {name:"حرب العصابات", desc:"عصابتان تتصارعان على الأحياء — إطلاق نار أسبوعي.", fx:"عنف +"},
  {name:"أزمة اقتصادية", desc:"إفلاس شركات — السرقات والاحتيال تقفز.", fx:"سرقات +"},
  {name:"تطهير داخلي", desc:"تفتيش مفاجئ على المركز — الفاسدون متوترون.", fx:"تسريبات +"},
];
window.SEASON_THEMES=SEASON_THEMES;
function novelPick(arr,cat){
  try{
    const S=window.S; ensureExtra();
    S.novel[cat]=S.novel[cat]||[];
    const fresh=arr.filter(x=>!S.novel[cat].includes(typeof x==="string"?x:(x.id||x.type||x.kind||JSON.stringify(x))));
    const choice=(fresh.length?fresh:arr)[Math.floor(Math.random()*(fresh.length?fresh.length:arr.length))];
    const key=typeof choice==="string"?choice:(choice.id||choice.type||choice.kind||"x");
    S.novel[cat].push(key); if(S.novel[cat].length>10)S.novel[cat].shift();
    return choice;
  }catch(e){ return arr[Math.floor(Math.random()*arr.length)]; }
}
window.novelPick=novelPick;

/* ===== #7 خيوط حمراء كاذبة: دليل مفبرك لشخص بريء ===== */
function plantRedHerring(c){
  try{
    if(!c||Math.random()>0.38)return;
    const innocents=c.suspects.filter(s=>!c.truth.actors.some(a=>a.who===s.id));
    if(!innocents.length||c.evidence.length>6)return;
    const target=innocents[Math.floor(Math.random()*innocents.length)];
    const kinds=["بصمة مجهولة المصدر","تسجيل كاميرا مشوش","شهادة مدفوعة","هاتف مستعار"];
    const k=kinds[Math.floor(Math.random()*kinds.length)];
    c.evidence.splice(1,0,{id:c.id+"-ER"+Date.now()%1000,kind:k,
      desc:`⚠️ خيط مريب: ${k} تشير بقوة إلى ${target.name} — لكن المصدر غامض وقد يكون مفبركاً لإبعادك عن الحقيقة.`,
      pointsTo:target.name,reliable:false,found:true,analyzed:false,unlocks:false,red:true});
    c.log.push(`⚠️ تنبيه المحققين: خيط جديد ضد ${target.name} — المصدر غير موثوق، احتمال تلفيق!`);
  }catch(e){}
}
/* ربط التلفيق بالتحليل: المختبر قد يكشف الزرع */
function hookAnalysis(){
  try{
    if(typeof analyzeEvidence==="function"&&!analyzeEvidence._hooked){
      const orig=analyzeEvidence;
      window.analyzeEvidence=function(c,idx){
        const e=c&&c.evidence&&c.evidence[idx];
        orig(c,idx);
        try{
          if(e&&e.red&&!e._flagged){
            e._flagged=true;
            if(Math.random()<0.65){
              e.desc+=` — 🔬 المختبر: البصمة/التسجيل لا يتطابق زمنياً. الأرجح أنها زُرعت لتضليلك! تجاهلها.`;
              c.log.push(`🔬 كشف التلفيق في ${c.id}: الدليل ضد ${e.pointsTo} مفبرك!`);
              try{inboxAdd("int",`🔬 المختبر: الدليل ضد ${e.pointsTo} في ${c.id} مفبرك — لا تعتقل بناءً عليه.`,"lab:"+c.id+":"+e.id);}catch(_){}
              try{addXP(15);}catch(_){}
            } else {
              c.log.push(`المختبر لم يحسم: الدليل ضد ${e.pointsTo} ما زال غامضاً.`);
            }
          }
        }catch(_){}
      };
      window.analyzeEvidence._hooked=true;
    }
  }catch(e){}
}

/* ===== الرتب #5 ===== */
const JRANKS=["محقق مساعد","قائد تحقيق","قاضٍ","رئيس محكمة","وزير العدل"];
const JXP=[0,100,250,500,900];
window.JRANKS=JRANKS;
function prankLvl(){ try{ensureExtra();const xp=window.S.prank.xp||0;let l=0;for(let i=0;i<JXP.length;i++)if(xp>=JXP[i])l=i;return l;}catch(e){return 0;} }
function addXP(n){ try{ensureExtra();window.S.prank.xp=(window.S.prank.xp||0)+n;}catch(e){} }
window.addXP=addXP; window.prankLvl=prankLvl;
function hookRewards(){
  try{
    if(typeof issueVerdict==="function"&&!issueVerdict._h){
      const o=issueVerdict; window.issueVerdict=function(c,y,f,a){ const r=o(c,y,f,a); try{addXP(a?5:30);}catch(_){} return r; }; window.issueVerdict._h=true;
    }
    if(typeof arrestSuspect==="function"&&!arrestSuspect._h){
      const o2=arrestSuspect; window.arrestSuspect=function(c,id){ const r=o2(c,id); try{addXP(10);}catch(_){} return r; }; window.arrestSuspect._h=true;
    }
    if(typeof decideIncident==="function"&&!decideIncident._h){
      const o3=decideIncident; window.decideIncident=function(id,ch){ const r=o3(id,ch); try{addXP(12);}catch(_){} return r; }; window.decideIncident._h=true;
    }
  }catch(e){}
}
function freezeFunds(){
  const S=window.S; if(prankLvl()<2){toast("تحتاج رتبة قاضٍ (المستوى 3)");return;}
  if(S.money<4000){toast("التجميد يكلف $4000");return;}
  S.money-=4000; S.econ.corrup=Math.max(5,S.econ.corrup-4); rep("crim",-3); rep("cit",2);
  addNews("تجميد أموال مشبوهة","بأمر قضائي: تجميد حسابات مرتبطة بالعصابات.", "good"); addXP(10); save(); renderAll();
}
function raidWarrant(){
  const S=window.S; if(prankLvl()<3){toast("تحتاج رتبة رئيس محكمة");return;}
  const c=S.cases.find(x=>x.status==="مفتوحة"&&x.evidence.some(e=>e.found&&!e.analyzed));
  if(!c){toast("لا دليل بانتظار التحليل");return;}
  const e=c.evidence.find(x=>x.found&&!x.analyzed);
  analyzeEvidence(c,c.evidence.indexOf(e)); S.money=Math.max(0,S.money-1500);
  toast("⚖️ أمر تفتيش: حُلل "+e.kind); addXP(8); save(); renderAll();
}

/* ===== #3 المخبرون ===== */
const INFORM_COVERS=["سائق تاكسي","صاحب مقهى","عامل مستودع","بائع سوق","حارس ليلي","ساعي بريد"];
function recruitInformant(){
  const S=window.S; ensureExtra();
  if(S.informants.filter(i=>i.alive).length>=5){toast("شبكتك ممتلئة (5)");return;}
  if(S.money<3000){toast("التجنيد يكلف $3000");return;}
  S.money-=3000;
  const inf={id:"INF"+(S.informSeq++),name:arabName(),cover:INFORM_COVERS[Math.floor(Math.random()*INFORM_COVERS.length)],trust:rnd(30,80),alive:true,paid:0};
  S.informants.push(inf);
  addFile("مخبرون",`تجنيد ${inf.name}`,`الغطاء: ${inf.cover} — الثقة ${inf.trust}`);
  toast("🤝 انضم مخبرك: "+inf.name); save(); renderAll();
}
function informantTick(){
  try{
    const S=window.S; ensureExtra();
    for(const inf of S.informants.filter(i=>i.alive)){
      const r=Math.random();
      if(r<0.10){ inf.alive=false; addNews("⚠️ مخبر يُكشف!",`${inf.name} (${inf.cover}) كُشف — نجا بصعوبة وانقطع الاتصال.`,"bad"); try{inboxAdd("int",`⚠️ مخبرك ${inf.name} انكشف! غيّر طرق التواصل.`,"inf-die:"+inf.id);}catch(_){} rep("crim",2); }
      else if(r<0.45){
        const c=S.cases.filter(x=>x.status==="مفتوحة");
        const tip=c.length?`حركة حول ${c[0].type} في ${c[0].distName} — ${pick(["سيارة تتردد فجراً","اجتماع بقهوة معروفة","هاتف جديد بأيدي مشتبه"])} (ثقة ~${inf.trust}%)`:`${pick(["شاحنة تفرغ ليلاً بالمستودعات","وجوه جديدة بأسلحة بالحي الفقير","مرابٍ يعرض قروضاً مشبوهة"])} (ثقة ~${inf.trust}%)`;
        const lie=Math.random()*100>inf.trust;
        try{inboxAdd("off",`🤫 مخبرك ${inf.name}: ${lie?"معلومة مضللة على الأرجح — تحقق قبل التحرك! ":""}${tip}`,"inf:"+inf.id+":"+tip.slice(0,30));}catch(_){}
        if(!lie&&Math.random()<0.4){S.plot.notes.push(`مخبر: ${tip.slice(0,80)}`);}
      }
    }
  }catch(e){}
}

/* ===== #2 قضية الـ5 دقائق ===== */
function startQuickCase(){
  const S=window.S; ensureExtra();
  if(S.quick&&!S.quick.done){toast("لديك قضية سريعة جارية!");return;}
  const c=genCase();
  c.suspects=c.suspects.slice(0,4); c.evidence=c.evidence.slice(0,2);
  c.deadline=S.day+1; c.priority="عاجلة"; c.quick=true;
  c.log.push("⚡ قضية سريعة: 5 دقائق حقيقية للحسم — حلل + اعتقل قبل انتهاء الوقت!");
  S.quick={caseId:c.id,endsAt:Date.now()+5*60*1000,done:false};
  toast("⚡ بدأت القضية السريعة "+c.id+" — 5 دقائق!");
  save(); renderAll(); switchTab("cases");
}
function quickTick(){
  try{
    const S=window.S; if(!S||!S.quick||S.quick.done)return;
    const c=caseById(S.quick.caseId);
    const solved=c&&(c.arrests.length>0||(c.court&&c.court.verdict));
    if(solved){ S.quick.done=true; S.money+=5000; addXP(40); rep("cit",4); rep("media",3);
      addNews("⚡ حسم خاطف!",`القائد حسم ${c.id} خلال دقائق — الشارع مبهور.`,"good"); toast("⚡ حسمت القضية السريعة! +$5000"); save(); try{renderAll();}catch(_){} return; }
    if(Date.now()>S.quick.endsAt||!c||c.status==="متعثرة"){ S.quick.done=true; rep("cit",-3); rep("media",-2);
      addNews("⏰ فشل الحسم السريع",`القضية ${S.quick.caseId} تجاوزت الدقائق الخمس.`,"bad"); toast("⏰ انتهى وقت القضية السريعة"); save(); try{renderAll();}catch(_){} }
  }catch(e){}
}

/* ===== #1 المطاردة الحية ===== */
function startChase(name,dist){
  const S=window.S; ensureExtra();
  if(S.chase&&S.chase.on)return;
  S.chase={on:true,suspect:name||"مشتبه هارب",dist:dist||"الحي الفقير",d:60,rounds:0,max:6};
  try{S.emergencies.unshift({id:"CH"+Date.now()%9999,text:"🚓 مطاردة حية: "+S.chase.suspect,day:S.day,done:false,dist:S.chase.dist});}catch(_){}
  toast("🚓 مطاردة بدأت: "+S.chase.suspect); save(); paintChase();
}
function chaseAction(kind){
  const S=window.S; if(!S.chase||!S.chase.on)return;
  const ch=S.chase; ch.rounds++;
  let cut={block:14,close:10,pit:22}[kind]||10;
  cut+=rnd(-6,8)+Math.floor((S.econ.policeFund||50)/20);
  ch.d=Math.max(0,ch.d-cut);
  if(ch.d<=0){ ch.on=false; addXP(35); S.money+=4000; rep("pol",3); rep("cit",3);
    addNews("🚓 قبضنا عليه!",`مطاردة ناجحة: ${ch.suspect} خلف القضبان.`,"good");
    toast("✅ أمسكته! +$4000"); document.getElementById("modal").classList.add("hidden"); save(); renderAll(); return; }
  if(ch.rounds>=ch.max){ ch.on=false; rep("cit",-4); rep("media",-3);
    addNews("🏃 أفلت المشتبه!",`${ch.suspect} أفلت من الطوق في ${ch.dist}.`,"bad");
    toast("❌ أفلت!"); document.getElementById("modal").classList.add("hidden"); save(); renderAll(); return; }
  if(Math.random()<0.3){ch.d=Math.min(90,ch.d+10); toast("⚠️ التف على الحاجز!");}
  save(); paintChase();
}
function paintChase(){
  const S=window.S; if(!S||!S.chase||!S.chase.on)return;
  const ch=S.chase; const pct=Math.round((1-ch.d/90)*100);
  document.getElementById("modal").classList.remove("hidden");
  document.getElementById("modal-card").innerHTML=`
   <div class="alert-flash">🚓 مطاردة حية — ${escHtml(ch.suspect)}</div>
   <div class="mut small">${escHtml(ch.dist)} • الجولة ${ch.rounds+1}/${ch.max} • تابع الوميض على الخريطة 3D</div>
   <div style="font-size:22px;letter-spacing:2px;margin:8px 0" dir="ltr">🚓${"—".repeat(Math.max(1,Math.round(ch.d/10)))}🏃</div>
   <div class="bar"><i style="width:${pct}%"></i></div>
   <div class="small mut">الاقتراب ${pct}%</div>
   <div style="display:grid;gap:8px;margin-top:8px">
    <button type="button" class="btn primary" onclick="chaseAction('block')">🚧 حاجز أمامي (−14)</button>
    <button type="button" class="btn primary" onclick="chaseAction('close')">🚓 تضييق الطوق (−10 آمن)</button>
    <button type="button" class="btn primary" onclick="chaseAction('pit')">💥 صدم تكتيكي (−22 خطير)</button>
    <button type="button" class="btn" onclick="document.getElementById('modal').classList.add('hidden')">⏸️ متابعة لاحقاً من القيادة</button>
   </div>`;
}
window.chaseAction=chaseAction; window.startChase=startChase; window.paintChase=paintChase;

/* ===== #4 قرارات الـ30 ثانية ===== */
let flashTimer=null;
function startFlashCall(){
  const S=window.S; ensureExtra();
  if(S.flash&&S.flash.on)return;
  if(!document.getElementById("modal").classList.contains("hidden"))return;
  const avail=(S.officers||[]).filter(x=>x.status!=="مفصول");
  const o=avail.length?avail[Math.floor(Math.random()*avail.length)]:{name:"المناوب"};
  const open=S.cases.filter(c=>c.status==="مفتوحة");
  const c=open.length?open[Math.floor(Math.random()*open.length)]:null;
  const opts=[
    {id:"go",label:"✅ اقتحم الآن",good:`اقتحام موفق: قبضنا على ${c?c.suspects[0].name:"مشتبه"}!`,bad:"اقتحام متسرع: بريء أصيب والهدف هرب!"},
    {id:"hold",label:"⏳ اثبت مكانك",good:"الثبات كشف تحركاتهم — معلومات ذهبية.",bad:"التأخير ضيع الفرصة — تبخر الهدف."},
  ];
  S.flash={on:true,from:o.name||o,caseId:c?c.id:null,opts,left:30};
  paintFlash(); save();
}
function paintFlash(){
  const S=window.S; const f=S.flash; if(!f||!f.on)return;
  document.getElementById("modal").classList.remove("hidden");
  document.getElementById("modal-card").innerHTML=`
   <div class="alert-flash">📞 اتصال ميداني — <span id="flash-timer">${f.left}</span> ثانية!</div>
   <div class="msg"><span class="who">👮 ${escHtml(f.from)}:</span> سيدي أنا أمام الهدف الآن (${f.caseId||"موقع مشبوه"})! اقتحم أم أثبت؟ قرر بسرعة!</div>
   <div class="row">${f.opts.map(o=>`<button type="button" class="btn primary" onclick="flashDecide('${o.id}')">${escHtml(o.label)}</button>`).join("")}</div>
   <div class="mut small">إن انتهى الوقت يتصرف الضابط من نفسه (قد يخطئ)!</div>`;
  if(flashTimer)clearInterval(flashTimer);
  flashTimer=setInterval(()=>{
    try{
      const S2=window.S; if(!S2.flash||!S2.flash.on){clearInterval(flashTimer);return;}
      S2.flash.left--;
      const t=document.getElementById("flash-timer"); if(t)t.textContent=S2.flash.left;
      if(S2.flash.left<=0){clearInterval(flashTimer);flashDecide(null);}
    }catch(e){clearInterval(flashTimer);}
  },1000);
}
function flashDecide(id){
  try{
    if(flashTimer)clearInterval(flashTimer);
    const S=window.S; const f=S.flash; if(!f||!f.on)return;
    f.on=false;
    const auto=!id;
    const ch=f.opts.find(o=>o.id===id)||f.opts[Math.floor(Math.random()*f.opts.length)];
    const win=!auto?Math.random()<0.7:Math.random()<0.45;
    const txt=(auto?"(انتهى الوقت — تصرف الضابط وحده) ":"")+ (win?ch.good:ch.bad);
    try{inboxAdd(auto?"media":"pol",`${win?"✅":"❌"} اتصال ميداني (${f.from}): ${txt}`,"flash:"+Date.now());}catch(_){}
    addNews(win?"✅ تدخل ميداني ناجح":"❌ تدخل ميداني فاشل",txt,win?"good":"bad");
    if(win){addXP(15);rep("pol",2);}else{rep("cit",-2);S.internal.heat+=2;}
    document.getElementById("modal").classList.add("hidden");
    save(); renderAll();
  }catch(e){}
}
window.flashDecide=flashDecide; window.startFlashCall=startFlashCall;

/* ===== #6 الرد على الصحافة ===== */
function pressReply(kind){
  const S=window.S; ensureExtra();
  const n=S.news[0]; if(!n){toast("لا أخبار للرد عليها");return;}
  if(S.pressCd>Date.now()){toast("فريقك الإعلامي مشغول… انتظر قليلاً");return;}
  S.pressCd=Date.now()+60000;
  if(kind==="deny"){ rep("media",-2); rep("cit",1); addNews("📢 بيان نفي رسمي",`القيادة تنفي: "${n.title}" — وتتوعد بمقاضاة المروجين.`,"info"); }
  if(kind==="conf"){ S.money=Math.max(0,S.money-2000); rep("media",5); rep("cit",3); addNews("🎤 مؤتمر صحفي للقاضي","أجبت على الأسئلة بشفافية وكسبت الإعلام.","good"); }
  if(kind==="leak"){ rep("media",3); rep("polit",-3); S.internal.heat+=3; addNews("🕵️ تسريب مضاد","مصدر مجهول سرب ما يقلب الرواية لصالحك… لكن السياسيين غاضبون.","alert"); }
  addFile("صحافة","رد رسمي ("+kind+")",n.title); addXP(5); save(); renderAll();
}
window.pressReply=pressReply;

/* ===== #8 المواسم ===== */
function seasonTick(){
  try{
    const S=window.S; ensureExtra();
    if((S.day-S.season.startDay)>=14){
      const gained=(S.stats.solved||0)-S.season.solvedAtStart;
      const th=SEASON_THEMES[S.season.theme%SEASON_THEMES.length];
      if(gained>=3){S.money+=15000;rep("cit",5);addNews(`🏆 نهاية موسم "${th.name}"`,"أداء بطولي — مكافأة دولة $15,000.","good");}
      else{rep("cit",-4);rep("polit",-3);addNews(`🌧️ نهاية موسم "${th.name}"`,"موسم مخيب — الشارع يطالب بالمزيد.","bad");}
      S.season={no:S.season.no+1,startDay:S.day,theme:(S.season.theme+1)%SEASON_THEMES.length,solvedAtStart:S.stats.solved||0};
      const nt=SEASON_THEMES[S.season.theme];
      addNews(`📺 موسم جديد: "${nt.name}"`,nt.desc,"alert");
      try{inboxAdd("media",`📺 بدأ الموسم ${S.season.no}: ${nt.name} — ${nt.desc}`,"season:"+S.season.no);}catch(_){}
    }
  }catch(e){}
}

/* ===== ربط التوليد الجديد بالتنوع ===== */
function hookGen(){
  try{
    if(typeof genCase==="function"&&!genCase._nov){
      const orig=genCase;
      window.genCase=function(force){
        ensureExtra();
        if(force) {const c=orig(force); plantRedHerring(c); novelTrack("ctype",c.type); return c;}
        let c=orig();
        novelTrack("ctype",c.type);
        const last=window.S.novel.ctype||[];
        if(last.length>=2&&last[last.length-1]===c.type&&last[last.length-2]===c.type){
          const alts=(window.CASE_TYPES||[]).map(t=>t.type).filter(t=>t!==c.type);
          if(alts.length){ const alt=novelPick(alts,"ctype-alt"); try{window.S.cases.shift();}catch(_){}
            c=orig(alt); plantRedHerring(c); return c; }
        }
        plantRedHerring(c); return c;
      };
      window.genCase._nov=true;
    }
    if(typeof buildCustomCase==="function"&&!buildCustomCase._nov){
      const o2=buildCustomCase;
      window.buildCustomCase=function(s,i){ const c=o2(s,i); plantRedHerring(c); return c; };
      window.buildCustomCase._nov=true;
    }
    if(typeof startIncident==="function"&&!startIncident._nov){
      const o3=startIncident;
      window.startIncident=function(force){
        if(force)return o3(force);
        const kinds=Object.keys(window.INCIDENT_DEFS||{});
        if(!kinds.length)return o3(force);
        const k=novelPick(kinds,"incident");
        return o3(k);
      };
      window.startIncident._nov=true;
    }
  }catch(e){}
}
function novelTrack(cat,val){ try{ensureExtra();window.S.novel[cat]=window.S.novel[cat]||[];window.S.novel[cat].push(val);if(window.S.novel[cat].length>10)window.S.novel[cat].shift();}catch(e){} }

/* ===== التكامل مع الحلقة + الرسم ===== */
function extraTick(){
  ensureExtra(); hookAnalysis(); hookRewards(); hookGen();
  quickTick(); seasonTick();
  try{informantTickDaily();}catch(e){}
  const S=window.S;
  // مطاردة تلقائية عند هروب
  try{
    if((!S.chase||!S.chase.on)&&Math.random()<0.04){
      const esc=[]; for(const c of (S.cases||[]))for(const s of (c.suspects||[]))if(s.status==="هارب")esc.push({s,c});
      if(esc.length){const t=esc[Math.floor(Math.random()*esc.length)];startChase(t.s.name,t.c.distName);}
    }
  }catch(e){}
  // مكالمة 30 ثانية نادرة
  try{ if(Math.random()<0.03) startFlashCall(); }catch(e){}
}
let _lastInfDay=0;
function informantTickDaily(){ const S=window.S; if(S.day!==_lastInfDay){_lastInfDay=S.day;informantTick();} }

function paintExtraDash(){
  try{
    const S=window.S; if(!S)return; ensureExtra();
    const host=document.getElementById("tab-dash"); if(!host)return;
    if(document.getElementById("x-extra"))document.getElementById("x-extra").remove();
    const lvl=prankLvl(); const xp=S.prank.xp||0; const need=JXP[Math.min(lvl+1,JXP.length-1)];
    const th=SEASON_THEMES[S.season.theme%SEASON_THEMES.length];
    const seasonLeft=Math.max(0,14-(S.day-S.season.startDay));
    const quick=S.quick&&!S.quick.done?(()=>{const s=Math.max(0,Math.round((S.quick.endsAt-Date.now())/1000));return `<div class="kv"><span>⚡ القضية السريعة ${S.quick.caseId}</span><b>${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}</b></div>`;})():"";
    const chase=S.chase&&S.chase.on?`<div class="kv"><span>🚓 مطاردة: ${escHtml(S.chase.suspect)}</span><button type="button" class="btn primary" onclick="paintChase()">فتح المطاردة</button></div>`:"";
    const div=document.createElement("div"); div.id="x-extra";
    div.innerHTML=`
    <div class="card"><h3>🎖️ مسيرتك — ${JRANKS[lvl]} <span class="mut">(${xp} XP${lvl<4?" / التالية "+need:" MAX"})</span></h3>
     <div class="bar"><i style="width:${lvl>=4?100:Math.min(100,Math.round(xp/need*100))}%"></i></div>
     <div class="mut small">الرتب تفتح: تجميد أموال (قاضٍ) • أمر تفتيش (رئيس محكمة)</div>
     <div class="row"><button type="button" class="btn" onclick="freezeFunds()">💰 تجميد أموال ${lvl<2?"🔒":""}</button><button type="button" class="btn" onclick="raidWarrant()">⚖️ أمر تفتيش ${lvl<3?"🔒":""}</button><button type="button" class="btn primary" onclick="startQuickCase()">⚡ قضية 5 دقائق</button></div>
     ${quick}${chase}</div>
    <div class="card"><h3>📺 الموسم ${S.season.no}: ${th.name} <span class="mut">— ينتهي بعد ${seasonLeft} أيام</span></h3><div class="mut small">${th.desc}</div></div>
    <div class="card"><h3>🤫 شبكة المخبرين (${S.informants.filter(i=>i.alive).length}/5)</h3>
     ${S.informants.slice(-5).map(i=>`<div class="kv"><span>${i.alive?"🟢":"⚫"} ${escHtml(i.name)} <span class="mut">(${escHtml(i.cover)} • ثقة ${i.trust})</span></span></div>`).join("")||"<span class='mut'>لا مخبرين — جنّد عيوناً في الشارع.</span>"}
     <div class="row"><button type="button" class="btn primary" onclick="recruitInformant()">+ تجنيد مخبر ($3000)</button><button type="button" class="btn" onclick="startFlashCall()">📞 محاكاة اتصال ميداني</button></div></div>
    <div class="card"><h3>📰 الرد على الصحافة</h3><div class="mut small">الأحدث: ${S.news[0]?escHtml(S.news[0].title.slice(0,80)):"—"}</div>
     <div class="row"><button type="button" class="btn" onclick="pressReply('deny')">📢 نفي</button><button type="button" class="btn primary" onclick="pressReply('conf')">🎤 مؤتمر ($2000)</button><button type="button" class="btn" onclick="pressReply('leak')">🕵️ تسريب مضاد</button></div></div>`;
    host.prepend(div);
  }catch(e){}
}
window.paintExtraDash=paintExtraDash; window.extraTick=extraTick;
window.freezeFunds=freezeFunds; window.raidWarrant=raidWarrant;
window.recruitInformant=recruitInformant; window.startQuickCase=startQuickCase;

/* تثبيت الخطافات + حقن الرسم بعد كل renderAll */
try{
  hookAnalysis(); hookRewards(); hookGen();
  if(typeof renderAll==="function"&&!renderAll._x){
    const origR=renderAll;
    window.renderAll=function(){ origR(); try{paintExtraDash();}catch(e){} };
    window.renderAll._x=true;
  }
  if(typeof tick==="function"&&!tick._x){
    const origT=tick;
    window.tick=function(){ origT(); try{extraTick();}catch(e){} };
    window.tick._x=true;
  }
}catch(e){}
})();
