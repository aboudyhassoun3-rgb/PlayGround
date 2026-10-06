/* ===== Court: interactive session with AI lawyer/witnesses ===== */
async function openCourt(caseId, suspectId){
  const c=caseById(caseId); if(!c)return;
  const s=c.suspects.find(x=>x.id===suspectId); if(!s)return;
  c.court={suspect:suspectId, stage:"جلسة", transcript:[], verdict:null};
  c.log.push(`يوم ${window.S.day}: أُحيل ${s.name} للمحكمة — جلسة تفاعلية.`);
  save(); renderAll(); switchTab("court");
  await courtSay(c, "القاضي (أنت)", "افتُتحت الجلسة. التهمة حسب قانون: "+lawName(c.law)+". للمتهم محامٍ، وللشهود كلمتهم. الأدلة وحدها تحكم — لا كلام شخص واحد.");
}
function lawName(id){ const l=window.LAWS.find(x=>x.id===id); return l?l.name:id; }
function courtVerdictRange(c){ const l=window.LAWS.find(x=>x.id===c.law); return l||{min:1,max:10,maxFine:20000}; }
async function courtSay(c, who, text, cls=""){
  c.court.transcript.push({who,text,day:window.S.day});
  addFile("محكمة",`${c.id} — ${who}`,text);
  save(); renderCourt();
  // رد المحامي AI تلقائياً عند الحاجة
}
async function courtAskLawyer(c){
  const s=c.suspects.find(x=>x.id===c.court.suspect);
  const ev=c.evidence.filter(e=>e.found).map(e=>`${e.kind}: ${e.desc} (موثوق:${e.reliable?"نعم":"مشكوك"})`).join("\n");
  const ctx=`القضية ${c.id} (${c.type}) — المتهم ${s.name} — الأدلة:\n${ev}\nالشهود: ${c.witnesses.map(w=>w.name+" ("+w.motive+")").join("، ")}`;
  const r=await window.AI.chat({system:"أنت محامي دفاع ذكي شرس. اكتشف أخطاء التحقيق (دليل ظرفي واحد، شاهد متحيز، تأخير، نقص موارد). اطلب تخفيف الحكم أو الإفراج. لا تعترف بذنب موكلك. بالعربية وباختصار.",user:"قدّم مرافعة دفاع عن "+s.name+".",context:ctx});
  await courtSay(c,"المحامي ("+s.lawyer+")",r.text+(r.via==="local"?" <span class='tag ai'>AI محلي</span>":" <span class='tag ai'>AI</span>"));
}
async function courtAskWitness(c, wid){
  const w=c.witnesses.find(x=>x.id===wid); if(!w)return;
  const ctx=`الشاهد ${w.name} — دافعه الخفي: ${w.motive} (لا تكشفه مباشرة، بل لمّح بالسلوك). القضية ${c.id}.`;
  const r=await window.AI.chat({system:`أنت شاهد في محكمة. دافعك: ${w.motive}. إن كنت كاذباً/خائفاً/مدفوعاً فراوغ وتناقض قليلاً. لا تقل الحقيقة كاملة. بالعربية العامية البسيطة.`,user:"ماذا رأيت ليلة الحادثة؟",context:ctx});
  w.says=r.text; await courtSay(c,"الشاهد "+w.name,r.text);
  addMemory(w.id,`شهد في ${c.id} بدافع ${w.motive}.`);
}
function issueVerdict(c, years, fine, acquit=false){
  const S=window.S; const range=courtVerdictRange(c);
  const s=c.suspects.find(x=>x.id===c.court.suspect);
  if(!acquit){ years=Math.max(range.min,Math.min(range.max,years)); fine=Math.max(0,Math.min(range.maxFine,fine)); }
  const isTrueActor=c.truth.actors.some(a=>a.who===s.id);
  c.court.verdict={years:acquit?0:years,fine:acquit?0:fine,acquit,day:S.day};
  S.files.unshift({day:S.day,kind:"حكم",title:`${c.id} — ${s.name}: ${acquit?"براءة":years+" سنوات + غرامة "+fmt(fine)}`,body:`القانون: ${lawName(c.law)} (الحد ${range.min}-${range.max}). الأدلة المحللة: ${c.evidence.filter(e=>e.analyzed).length}.`});
  if(acquit){
    s.status="بريء";
    if(isTrueActor){ // أفلت مجرم!
      rep("crim",5); rep("cit",-6); S.pendingEvents.push({day:S.day+5,kind:"revenge",text:`المجرم ${s.name} الذي برّأته عاد للجريمة — ضغط إعلامي عليك!`});
      addNews(`فضيحة: متهم خطر حصل على البراءة!`,`القضية ${c.id}: مصادر تقول الأدلة كانت أقوى مما عُرض.`,"bad");
    } else { rep("cit",3); rep("jud",2); S.money+=0; }
  } else {
    s.status="مسجون"; s.sentence=years;
    S.prisoners.unshift({name:s.name,caseId:c.id,years,day:S.day,behavior:rnd(30,90),gang:s.gang});
    S.money+=Math.round(fine*0.2); // 20% للميزانية
    rep("cit",2); rep("crim",-3);
    if(!isTrueActor){ // خطأ قضائي!
      s.wrongful=true; S.stats.errors++;
      S.pendingEvents.push({day:S.day+rnd(4,9),kind:"leak",text:`أدلة جديدة في ${c.id}: المحكوم ${s.name} قد يكون بريئاً! عائلته تطالب بإعادة المحاكمة والصحافة تهاجمك.`});
      rep("media",-5); S.internal.heat+=12;
      addNews(`شبهة خطأ قضائي في ${c.id}`,`الحكم على ${s.name} (${years} سنوات) يواجه تشكيكاً. تحقيق داخلي محتمل.`,"bad");
    } else {
      S.stats.solved++;
      addNews(`عدالة: ${years} سنوات في ${c.id}`,`القاضي أصدر حكمه على ${s.name} وفق ${lawName(c.law)}.`,"good");
      if(s.gang!=="—") S.pendingEvents.push({day:S.day+rnd(5,12),kind:"revenge",text:`عصابة ${s.gang} تخطط للانتقام لحبس ${s.name}.`});
    }
    // استئناف للمحكمة العليا
    if(years>=10 && Math.random()<0.6){ S.appeals.push({caseId:c.id,name:s.name,day:S.day,status:"منظور أمام العليا"}); }
  }
  // إغلاق القضية إذا كل الموقوفين حُكموا أو برئوا
  if(c.suspects.every(x=>["بريء","مسجون","مشتبه","هارب"].includes(x.status)) && c.court.verdict){ c.status="مغلقة"; }
  save(); renderAll();
}
