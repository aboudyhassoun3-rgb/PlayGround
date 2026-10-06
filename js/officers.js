/* ===== Officers, squads, experts ===== */
const RANKS=["شرطي","عريف","رقيب","ملازم","نقيب","رائد","مقدم","عقيد"];
const SPECS=["تحقيق","مداهمات","تفاوض","استخبارات","قناصة/تدخل","مراقبة","حماية","سيبراني"];
function hireOfficer(){
  const S=window.S;
  const cost=1200;
  if(S.money<cost){toast("لا توجد ميزانية للتوظيف");return;}
  S.money-=cost;
  const id="O"+(S.seq.off++);
  const o={id, name:arabName(), rank:"شرطي", lvl:1, spec:pick(SPECS), intel:rnd(40,95), loyalty:rnd(40,95), brave:rnd(30,95), salary:rnd(700,1400), status:"متاح", squad:null, history:[`يوم ${S.day}: عُيّن براتب ${cost}`], corrupt:Math.random()<0.12, rel:{}, xp:0};
  S.officers.push(o); addMemory(o.id,`انضم للخدمة. ولاء ${o.loyalty}، تخصص ${o.spec}.`);
  addFile("ضباط",`تعيين ${o.name}`,`${o.spec} — راتب ${o.salary}`);
  save(); renderAll();
}
function officerAction(id, act){
  const o=window.S.officers.find(x=>x.id===id); if(!o)return;
  if(act==="promote"){ const i=RANKS.indexOf(o.rank); if(i<RANKS.length-1){o.rank=RANKS[i+1];o.salary+=300;o.history.push(`يوم ${window.S.day}: رُقّي إلى ${o.rank}`);addMemory(o.id,`رقيته إلى ${o.rank} — زادت ثقته بك.`);rep("pol",1);inboxAdd("off",`👮 ${o.name}: شكراً سيدي على الثقة بالترقية إلى ${o.rank} — لن أخذلك في الميدان.`,"offreact:"+o.id+":promote:"+o.rank);} }
  if(act==="warn"){o.history.push(`يوم ${window.S.day}: تحذير رسمي`);addMemory(o.id,`وجهت له تحذيراً — استياء خفيف.`);inboxAdd("off",`👮 ${o.name}: استلمت التحذير سيدي… سأراجع نفسي. أتمنى فرصة لإثبات نفسي.`,"offreact:"+o.id+":warn");}
  if(act==="fire"){o.status="مفصول";o.history.push(`يوم ${window.S.day}: فُصل من الخدمة`);addMemory(o.id,`فصلته — يكنّ لك الكراهية وقد ينتقم.`);rep("pol",-1);window.S.pendingEvents.push({day:window.S.day+6,kind:"leak",text:`الضابط المفصول ${o.name} سرّب معلومات للصحافة عن المركز!`});}
  if(act==="reward"){o.xp+=20;o.loyalty=Math.min(100,o.loyalty+8);o.history.push(`يوم ${window.S.day}: مكافأة وتكريم`);addMemory(o.id,`كافأته — ولاؤه ارتفع.`);window.S.money=Math.max(0,window.S.money-800);rep("pol",2);}
  if(act==="probe"){ if(o.corrupt){o.history.push(`يوم ${window.S.day}: ثبت فساده — فُصل وحُوكم`);o.status="مفصول";addNews(`ضابط فاسد خلف القضبان`,`التحقيق الداخلي كشف تعاون ${o.name} مع عصابة.`,"good");rep("pol",3);rep("cit",2);} else {o.history.push(`يوم ${window.S.day}: تحقيق — بريء`);addMemory(o.id,`حققت معه وظهر بريئاً — ثقته بك اهتزت قليلاً.`);o.loyalty-=5;} }
  save(); renderAll();
}
const SQUAD_DEFS=["تحقيق","جنائيات","مكافحة مخدرات","مكافحة أسلحة","تدخل","استخبارات","مراقبة","حماية"];
function createSquad(name){
  const S=window.S;
  if(!name)return;
  S.squads.push({id:"SQ"+Date.now()%100000,name,leader:null,members:[],chat:[]});
  save(); renderAll();
}
/* ===== مبادرات الضباط: يراسلونك من أنفسهم بتطورات حقيقية ===== */
let _offCd=0;
async function maybeOfficerUpdate(){
  const S=window.S; if(!S||!S.officers||!S.officers.length) return;
  if(Date.now()-_offCd<90000) return;       // رسالة كل 90 ثانية كحد أقصى
  if(Math.random()>0.45) return;
  _offCd=Date.now();
  const avail=S.officers.filter(x=>x.status!=="مفصول");
  if(!avail.length) return;
  const o=pick(avail);
  const open=S.cases.filter(c=>c.status==="مفتوحة");
  const c=open.length?pick(open):null;
  const ctx=`اليوم ${S.day} ${String(S.hour).padStart(2,"0")}:${String(S.min).padStart(2,"0")}. الضابط ${o.name} (${o.rank}، ${o.spec}، ولاء ${o.loyalty}). قضية مرجعية: ${c?c.id+" "+c.type+" في "+c.distName+" (مشتبهون "+c.suspects.length+")":"لا قضايا مفتوحة"}. سمعة الشرطة ${S.rep.pol}. ذاكرته: ${memOf(o.id)}`;
  let text="";
  try{
    const r=await window.AI.chat({system:`أنت الضابط ${o.name} (${o.spec}) ترسل تحديثاً ميدانياً قصيراً لقائدك عبر القناة الداخلية. اكتب رسالة واحدة واقعية (سطران فقط): بلاغ ميداني حقيقي من البيانات (دورية، مشاهدة، معلومة من الشارع، طلب دعم، أو ملاحظة عن زميل)، بلا تحية متكلفة وبلا تكرار. اذكر أسماء وأماكن حقيقية من السياق. بالعربية.`,user:"أرسل تحديثك الميداني الحالي.",context:ctx,maxTokens:140});
    text=r.text;
  }catch(e){ text=""; }
  if(!text) text=pick(officerFallbacks(o,c));
  o.chat=o.chat||[]; o.chat.push({me:false,text});
  inboxAdd("off",`👮 ${o.name}: ${text}`,"off:"+o.id+":"+text.slice(0,40));
  addMemory(o.id,`بادر بتحديث: ${text.slice(0,70)}…`);
  save(); try{renderHUD();}catch(e){}
}
function officerFallbacks(o,c){
  const d=c?c.distName:pick(window.DISTRICTS).name;
  const cid=c?c.id:"الدورية العامة";
  return [
    `أنهيت جولة في ${d} — رصدت ${rnd(1,3)} سيارات بلا لوحات قرب ${pick(["سوق شعبي","مستودع مهجور","مقهى معروف"])}. سجلت الأرقام (${cid}). أحتاج إذن تفتيش؟`,
    `مصدر في ${d} همس لي: ${c?("حركة غير طبيعية حول "+c.type):"شاحنة تفرغ ليلاً"} — المعلومة (ثقة ~50%) وتحتاج تأكيداً قبل التحرك.`,
    `الدورية الليلة ناقصة: زميلي مريض ولا يوجد بديل. أقدر أغطي ${d} وحدي لكن الاستجابة ستتأخر.`,
    `استجوبت شاهداً في ${cid} — خائف ويرفض الكتابة باسمه. أقترح حماية شاهد قبل أن نخسره.`,
    `${c?("بخصوص "+cid+": تتبعت "+pick(["كاميرا محل","سجل اتصالات","تحويلاً مالياً"])+" وأحتاج خبير "+pick(window.EXPERTS)+" لإكمال الصورة."):("راجعت سجلات "+d+" القديمة: نمط يتكرر كل خميس — قد يفيد قضية قادمة.")}`,
    `ملاحظة داخلية (بيننا): ${pick(["ضابط جديد يسأل كثيراً عن العمليات السرية","سمعت تذمراً من تأخر البدلات","أحد المخبرين يطلب مبلغاً أكبر"])} — أردت أن تعرف قبل أن تكبر.`,
  ];
}
