/* ===== World sim: clock, economy, emergencies, revenge, internal affairs ===== */
function tick(){
  const S=window.S;
  S.min+=window.GAME_CONFIG.MIN_PER_TICK;
  while(S.min>=60){S.min-=60;S.hour++;}
  if(S.hour>=24){S.hour-=24;S.day++; newDay();}
  else { maybeHourly(); }
  // العالم المستقل: تحركات حتى بدون تدخل + الحوادث الحية
  autonomous();
  try{ incidentTick(); }catch(e){}
  save(); renderHUD();
}
function newDay(){
  const S=window.S;
  // قضايا جديدة تلقائية
  if(S.cases.filter(c=>c.status==="مفتوحة").length<4 && Math.random()<0.8) genCase();
  // تطور قضايا قديمة ذاتياً: محققون يعملون، شهود يختفون، أدلة تتلف
  for(const c of S.cases.filter(c=>c.status==="مفتوحة")){
    if(Math.random()<0.35){ const e=c.evidence.find(e=>e.found&&!e.analyzed); if(e){analyzeEvidence(c,c.evidence.indexOf(e)); c.log.push(`(تلقائي) المحققون حللوا ${e.kind} في ${c.id}.`);} }
    if(Math.random()<0.12 && c.witnesses.length){ const w=c.witnesses.splice(Math.floor(Math.random()*c.witnesses.length),1)[0]; c.log.push(`⚠️ الشاهد ${w.name} اختفى/تراجع عن الشهادة.`); }
    if(Math.random()<0.1){ c.log.push(`دليل تعرض للتلف بسبب التأخير في ${c.id}.`); const e=c.evidence.find(e=>e.found&&!e.analyzed); if(e)e.reliable=false; }
    if(S.day>c.deadline && c.status==="مفتوحة"){ c.status="متعثرة"; rep("cit",-4); rep("media",-3); addNews(`تعثر القضية ${c.id}`,`تجاوزت المهلة (${c.deadline}). الشارع يغلي والصحافة تسأل: أين القاضي؟`,"bad"); }
    // هروب مشتبه
    if(Math.random()<0.08){ const s=pick(c.suspects.filter(s=>s.status!=="موقوف")); if(s){s.status="هارب"; c.log.push(`🚨 المشتبه ${s.name} هرب! صدرت مذكرة مطاردة.`);} }
  }
  // طوارئ
  if(Math.random()<0.5){
    const e={id:"EM"+S.day+"-"+Math.floor(Math.random()*999), text:pick(window.EMERGENCIES), day:S.day, hour:pick([9,12,14,17,21]), done:false, dist:pick(window.DISTRICTS).name};
    S.emergencies.unshift(e); addNews(`طوارئ: ${e.text}`,`بلاغ عاجل في ${e.dist}. القيادة مطالبة بتحديد الأولويات والتحرك.`, "alert");
  }
  // أحداث معلقة (انتقام/تسريب/مؤامرة)
  const due=S.pendingEvents.filter(e=>e.day<=S.day); S.pendingEvents=S.pendingEvents.filter(e=>e.day>S.day);
  for(const e of due){
    if(e.kind==="revenge"){ S.emergencies.unshift({id:"RV"+S.day, text:"انتقام: "+e.text, day:S.day, done:false, dist:"—"}); addNews("انتقام إجرامي",e.text,"bad"); rep("pol",-3); }
    if(e.kind==="leak"){ addNews("تسريب من المركز!",e.text,"bad"); S.internal.heat+=8; rep("media",-4); }
    if(e.kind==="plot"){ S.plot.notes.push(e.text); addNews("خيط مؤامرة",e.text,"alert"); }
  }
  // اقتصاد
  const un=S.econ.unemp;
  S.econ.corrup=Math.max(5,Math.min(90,S.econ.corrup+(Math.random()*2-1)+(S.rep.polit<40?1:0)));
  S.econ.unemp=Math.max(4,Math.min(45,un+(Math.random()*2-1)-(S.econ.growth/4)));
  // رواتب يومية مبسطة: كل 7 أيام
  if(S.day-S.lastSalaryDay>=7){
    S.lastSalaryDay=S.day;
    const cost=officerPayroll()+expertCost();
    S.money-=cost;
    if(S.money<0){ addNews("أزمة رواتب!",`عجز ${fmt(-S.money)}. معنويات الضباط تنهار وخطر الفساد يرتفع.`,"bad"); rep("pol",-8); S.econ.corrup+=4; S.money=0; }
    else { const fund=stateFunding(); S.money+=fund; addNews("دعم الدولة الشهري",`وصل دعم بقيمة ${fmt(fund)} حسب الأداء والسمعة.`,"info"); }
  }
  // تحقيق داخلي ضد اللاعب
  if(S.internal.heat>=50 && !S.internal.open){ S.internal.open=true; addNews("تحقيق داخلي ضد القاضي!",`محقق مستقل يراجع قراراتك وملفاتك. دافع عن نفسك بالأدلة والسجلات.`,"bad"); }
  // مؤامرة كبرى: بعد ~10 قضايا
  if(S.stats.solved>=6 && S.plot.stage===0){ S.plot.stage=1; S.pendingEvents.push({day:S.day+2,kind:"plot",text:"نمط غريب: 3 قضايا تبدو منفصلة تستخدم نفس الوسيط المالي. هل هي صدفة؟"}); }
  if(S.stats.solved>=12 && S.plot.stage===1){ S.plot.stage=2; S.pendingEvents.push({day:S.day+2,kind:"plot",text:"تسريب داخلي: اسم ضابط من مركزك ورد في سجل اتصالات عصابة اليد الخفية!"}); }
  renderAll();
}
function maybeHourly(){ if(Math.random()<0.06){ const S=window.S; S.intelReports++; } }
function autonomous(){
  const S=window.S;
  // العصابات تتوسع/تتحارب
  for(const g of S.gangs){
    if(Math.random()<0.02){ g.power=Math.max(20,Math.min(100,g.power+rnd(-4,5))); g.mood=pick(["هادئة","تتوسع","بحرب مع عصابة","مختفية"]); }
  }
  // الصحافة تعلق دورياً
  if(Math.random()<0.008) pressComment();
}
function pressComment(){
  const S=window.S; const ex=Math.random()<0.5;
  addNews(ex?`الصحيفة: "${pick(["أكبر عملية اعتقال تهز المدينة","القاضي يضرب بيد من حديد","ثقة متزايدة بالقيادة الجديدة"])}"`:`الصحيفة تهاجم: "${pick(["أين العدالة؟ أبرياء خلف القضبان؟","الصحيفة تبالغ: انفلات أمني شامل؟","مصادر: أخطاء تحقيق بالجملة"])}"`, `تقييم الصحافة لأدائك — سمعة إعلامية ${S.rep.media}. قد تكون مبالغة أو غير دقيقة.`, ex?"good":"bad");
}
function officerPayroll(){ return window.S.officers.reduce((a,o)=>a+(o.salary||800),0); }
function expertCost(){ return (window.S.experts||[]).length*1500; }
function stateFunding(){
  const S=window.S; const base=25000;
  const perf=(S.rep.cit+S.rep.pol+S.rep.polit)/3;
  return Math.round(base*(0.6+perf/100));
}
