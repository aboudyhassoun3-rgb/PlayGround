/* ===== مدير الحوادث الحية: سالفة تفجأك بمكتبك وتتطور بدونك ===== */
const INCIDENT_DEFS = {
  bank:{ icon:"🏦", title:"سطو مسلح على البنك المركزي",
    stages:[
      {police:"سيدي! بلاغ عاجل: 4 مسلحين اقتحموا البنك المركزي واحتجزوا رهائن. الدوريات طوقت المكان. ما أوامرك؟",
       intel:"مصدرنا: سيارة الهروب مستأجرة باسم وهمي، وواحد من المسلحين له سوابق سطو (ثقة 65%). قد يكون تمويهاً لعملية أكبر.",
       press:"عاجل: سطو على البنك المركزي واحتجاز رهائن — أنظار المدينة على القاضي.",
       choices:[{id:"storm",label:"⚔️ اقتحام فوري",hint:"حسم سريع لكن خطر على الرهائن"},{id:"talk",label:"🎙️ تفاوض",hint:"يكسب وقتاً ومعلومات"},{id:"wait",label:"⏳ انتظار ومراقبة",hint:"يراقب لكن يغضب الشارع"}]},
      {police:"المفاوض على الخط: يطالبون بسيارة وممر آمن مقابل 3 رهائن. القناصة جاهزون. القرار لك سيدي.",
       intel:"تحليل جديد: أحدهم يتصل برقم خارجي كل 10 دقائق (ثقة 55%) — ربما عقل مدبر خارج البنك. الاقتحام الآن قد يفجر الوضع.",
       press:"المفاوضات متعثرة… أهالي الرهائن يتجمعون أمام البنك.",
       choices:[{id:"deal",label:"🚗 صفقة تبادل",hint:"رهائن مقابل ممر مراقب"},{id:"snipe",label:"🎯 قنص دقيق",hint:"ينهيها إن نجح"},{id:"letgo",label:"🛣️ اتركهم يخرجون",hint:"تتبعهم بدل المواجهة"}]},
    ]},
  shooting:{ icon:"🔫", title:"إطلاق نار في حي سكني",
    stages:[
      {police:"إطلاق نار كثيف في الحي الفقير! إصابات أولية ودوريتان في الطريق. هل أرسل التدخل وأطوق الحي؟",
       intel:"مصادر متضاربة: شاهد يقول عصابة الأفاعي، وآخر يقول خلاف عائلي (ثقة 40%). لا تتحرك بقوة قبل التأكد.",
       press:"ذعر في الحي الفقير: إطلاق نار وإصابات — أين الشرطة؟",
       choices:[{id:"cordon",label:"🚧 تطويق الحي",hint:"يمنع الامتداد"},{id:"raid",label:"⚔️ مداهمة فورية",hint:"حسم سريع وخطر أخطاء"},{id:"calm",label:"🩺 إسعاف وتحقيق هادئ",hint:"يحمي المدنيين أولاً"}]},
      {police:"المسلحون تحصنوا بسوق شعبي ومعهم مدنيون. القوة غير كافية — أحتاج قرارك: أقتحم أم أفاوض؟",
       intel:"رصدنا دراجتين غادرتا السوق قبل دقائق (ثقة 50%) — القيادة الحقيقية قد تكون هربت أصلاً.",
       press:"المسلحون يتحصنون بالسوق… والناس محاصرة بالداخل!",
       choices:[{id:"storm2",label:"⚔️ اقتحام السوق",hint:"خطر مدنيين"},{id:"talk2",label:"🎙️ تفاوض خروج آمن",hint:"يحفظ الأرواح"},{id:"siege",label:"⏳ حصار وخنق",hint:"بطيء لكن آمن نسبياً"}]},
    ]},
  vip:{ icon:"🕴️", title:"اختفاء شخصية مهمة",
    stages:[
      {police:"بلاغ حساس: عضو مجلس المدينة اختفى بعد اجتماعه المسائي. هاتفه مغلق وسائقه لا يرد. هل أعلن حالة بحث؟",
       intel:"آخر إشارة لهاتفه قرب المنطقة الصناعية (ثقة 60%). سجله: كان يحقق بعقود مشبوهة… الاختفاء قد يكون مدبراً.",
       press:"شائعات عن اختفاء مسؤول… البلدية تلتزم الصمت.",
       choices:[{id:"search",label:"🔍 بحث سري",hint:"بلا ضجة إعلامية"},{id:"public",label:"📢 بحث معلن",hint:"ضغط شعبي وسياسي"},{id:"watch",label:"👁️ مراقبة صامتة",hint:"نراقب من يتحرك"}]},
      {police:"وصلت رسالة فدية! يطالبون بإطلاق موقوف من عصابتهم مقابل حياته. المهلة 48 ساعة. سيدي… القرار؟",
       intel:"الرقم المستخدم مسروق، لكن أسلوب الصياغة يطابق عصابة ظل السوق (ثقة 55%). قد تكون الفدية فخاً لكشف عملائنا.",
       press:"تسريب: فدية مقابل المسؤول المختفي! المدينة تغلي.",
       choices:[{id:"pay",label:"💰 ادفع وراقب",hint:"ينقذه ويكشفهم"},{id:"trap",label:"🪤 كمين التسليم",hint:"مخاطرة محسوبة"},{id:"refuse",label:"✋ ارفض التفاوض",hint:"موقف صلب وعواقب"}]},
    ]},
  fire:{ icon:"🔥", title:"حريق كبير يهدد منطقة",
    stages:[
      {police:"حريق ضخم في مستودعات المنطقة الصناعية! الدخان يغطي المدينة والإطفاء يطلب تطويقاً وإخلاءً. أوامرك؟",
       intel:"المستودع المحترق مؤمن عليه بمبلغ ضخم قبل أسبوع فقط (ثقة 70%) — قد يكون حريقاً مفتعلاً لإخفاء تهريب.",
       press:"حريق هائل… والسنة اللهب تُرى من كل الأحياء!",
       choices:[{id:"evac",label:"🧯 إخلاء وإطفاء شامل",hint:"يحمي الأرواح أولاً"},{id:"save",label:"📦 حماية المستودعات المجاورة",hint:"يمنع الكارثة الأكبر"},{id:"inv",label:"🔍 إطفاء + تحفظ جنائي",hint:"نحفظ الأدلة مع الإطفاء"}]},
      {police:"النار وصلت مخزن وقود! إن انفجر خسرنا المنطقة. هل أسحب الفرق أم أخاطر بإخماد أخير؟",
       intel:"رُصدت شاحنة غادرت الموقع قبل الحريق بدقائق (ثقة 45%). سجلنا لوحتها — قرارك يحسم الليلة.",
       press:"مخزن الوقود مهدد بالانفجار… لحظات حرجة!",
       choices:[{id:"risk",label:"🚒 إخماد أخير جريء",hint:"بطولة أو كارثة"},{id:"pull",label:"↩️ سحب الفرق",hint:"سلامة الرجال أولاً"},{id:"demo",label:"💥 تفجير وقائي مسيطر عليه",hint:"حل هندسي"}]},
    ]},
  hit:{ icon:"🎯", title:"محاولة اغتيال مسؤول",
    stages:[
      {police:"إطلاق نار على موكب مسؤول حكومي! نجا بأعجوبة وحارسه مصاب. المهاجم هرب. هل أعلن الاستنفار؟",
       intel:"الرصاصة من سلاح قنص مسروق من مخزن شرطة قبل شهر (ثقة 75%)… لدينا تسريب داخلي يا سيدي.",
       press:"محاولة اغتيال تهز الحي الحكومي — من التالي؟",
       choices:[{id:"lock",label:"🔒 إغلاق واستنفار",hint:"يطمئن المسؤولين"},{id:"hunt",label:"🕵️ مطاردة صامتة",hint:"لا ننبه الشبكة"},{id:"guard",label:"🛡️ حماية المسؤولين",hint:"دفاعي"}]},
      {police:"اعتقلنا مشتبهاً قرب الموقع ومعه حقيبة! يصرخ أنه بريء وأن الحقيبة ليست له. ماذا نفعل به؟",
       intel:"بصماته غير مسجلة، لكنه اتصل برقم مشبوه 6 مرات اليوم (ثقة 60%). قد يكون كبش فداء… أو القناص نفسه.",
       press:"اعتقال مشتبه باغتيال المسؤول — هل انتهى الخطر؟",
       choices:[{id:"hold",label:"⛓️ توقيف وتحقيق",hint:"قانوني وآمن"},{id:"release",label:"🕊️ إطلاق بمراقبة",hint:"نتبعه للشبكة"},{id:"press2",label:"🎤 استجواب ضاغط",hint:"سريع ومحفوف بالشكاوى"}]},
    ]},
};
function incidentGuards(){ const S=window.S; S.incidents=S.incidents||[]; S.inbox=S.inbox||[]; S.alertQueue=S.alertQueue||[]; }
function activeIncidents(){ incidentGuards(); return window.S.incidents.filter(i=>i.active); }
function startIncident(forceKind){
  incidentGuards(); const S=window.S;
  if(activeIncidents().length>=3) return null;
  const kinds=Object.keys(INCIDENT_DEFS);
  const kind=forceKind||kinds[Math.floor(Math.random()*kinds.length)];
  const def=INCIDENT_DEFS[kind];
  const dist=kind==="bank"?"الحي التجاري":kind==="hit"?"الحي الحكومي":kind==="fire"?"المنطقة الصناعية":pick(window.DISTRICTS).name;
  const inc={id:"IN"+Date.now()%1000000, kind, title:def.title, icon:def.icon, dist, stage:0, active:true,
    log:[`اليوم ${S.day} ${clockNow()}: ${def.icon} ${def.title} — ${dist}`], ignored:0, nextTick:(S._tick||0)+6, decided:[]};
  S.incidents.unshift(inc);
  pushIncidentStage(inc);
  save(); return inc;
}
function pushIncidentStage(inc){
  const S=window.S; const st=INCIDENT_DEFS[inc.kind].stages[Math.min(inc.stage,INCIDENT_DEFS[inc.kind].stages.length-1)];
  const pol=window.INVESTIGATORS.find(p=>p.id==="pol");
  const intel=window.INVESTIGATORS.find(p=>p.id==="int");
  inboxAdd("pol",`🚨 ${pol.name}: ${st.police}`);
  inboxAdd("int",`🛰️ ${intel.name}: ${st.intel}`);
  S.chats.pol.push({me:false,text:`🚨 ${st.police} (${inc.title} — ${inc.dist})`});
  S.chats.int.push({me:false,text:`${st.intel} (${inc.title})`});
  addNews(`${inc.icon} ${inc.title}`,`${st.press} — ${inc.dist}.`,"alert");
  addFile("حوادث",`${inc.title} — مرحلة ${inc.stage+1}`,`شرطة: ${st.police} | استخبارات: ${st.intel}`);
  inc.log.push(`مرحلة ${inc.stage+1}: ${st.press}`);
  if(!S.alertQueue.includes(inc.id)) S.alertQueue.push(inc.id);
  try{toast(`🚨 ${inc.title} — تحتاج قرارك`);}catch(e){}
}
function inboxAdd(from,text){
  const S=window.S; S.inbox.unshift({day:S.day,time:clockNow(),from,text});
  if(S.inbox.length>30)S.inbox.pop();
}
function clockNow(){ return String(window.S.hour).padStart(2,"0")+":"+String(window.S.min).padStart(2,"0"); }
function decideIncident(id, choiceId){
  incidentGuards(); const S=window.S;
  const inc=S.incidents.find(i=>i.id===id&&i.active); if(!inc)return;
  const st=INCIDENT_DEFS[inc.kind].stages[Math.min(inc.stage,INCIDENT_DEFS[inc.kind].stages.length-1)];
  const ch=st.choices.find(c=>c.id===choiceId)||{id:"wait",label:"تأجيل"};
  inc.decided.push({stage:inc.stage,choice:ch.id,day:S.day});
  S.alertQueue=S.alertQueue.filter(x=>x!==id);
  resolveChoice(inc, ch);
  save(); renderAll();
  if(inc.active && S.alertQueue.includes(inc.id)) paintIncidentAlert(inc);
  else { document.getElementById("modal").classList.add("hidden"); showAlertQueue(); }
}
function snoozeIncident(id){
  const S=window.S; S.alertQueue=S.alertQueue.filter(x=>x!==id);
  const inc=S.incidents.find(i=>i.id===id); if(inc){inc.ignored++; inc.log.push(`أجّلت القرار — الوضع يتطور بدونك…`);}
  save(); renderAll();
  document.getElementById("modal").classList.add("hidden"); showAlertQueue();
}
function resolveChoice(inc, ch){
  const S=window.S; const bad=inc.ignored>0;
  const eff={
    storm:{ok:"اقتحام ناجح: قُبض على 3 وحرر الرهائن بإصابات طفيفة.",bad:"الاقتحام المتأخر كلفنا غالياً: رهينة مصاب ومسلح هارب.",rep:{cit:4,pol:3,media:3},money:2000},
    talk:{ok:"التفاوض كسب وقتاً: خرجت رهينتان بسلام والمحاصرون مرتبكون.",bad:"المفاوضة طالت فهرب زعيمهم من الباب الخلفي.",rep:{cit:2,media:1},money:500},
    wait:{ok:"المراقبة كشفت سيارة الهروب — تتبعناها لوكر العصابة!",bad:"الانتظار شجعهم: نهبوا الخزينة وهربوا عبر الأنفاق.",rep:{cit:-5,media:-5,polit:-3}},
    deal:{ok:"تبادل ناجح تحت المراقبة: الرهائن أحرار والمال مرصود.",bad:"الصفقة انفجرت: أخذوا السيارة وتركوا فخاً.",rep:{cit:3,media:2},money:1000},
    snipe:{ok:"قنص دقيق أنهى المواجهة بلا خسائر مدنية. بطولة!",bad:"رصاصة طائشة أصابت مدنياً — الصحافة تشتعل.",rep:{cit:bad?-6:5,media:bad?-7:4,polit:2}},
    letgo:{ok:"تتبع ذكي: تركناهم يخرجون وقبضنا على الشبكة كاملة لاحقاً.",bad:"خرجوا ولم يعودوا… والشارع يتهمك بالجبن.",rep:{cit:bad?-6:3,pol:2}},
    cordon:{ok:"التطويق حصر النار ومنع امتدادها للأحياء.",bad:"التطويق المتأخر حبس المدنيين مع المسلحين.",rep:{cit:3,pol:2}},
    raid:{ok:"مداهمة خاطفة: قُبض على المتورطين وضُبطت أسلحة.",bad:"مداهمة متسرعة: بريء أصيب والمهاجم الحقيقي هرب.",rep:{cit:bad?-6:4,media:bad?-6:3},heat:bad?8:0},
    calm:{ok:"الإسعاف أولاً أنقذ أرواحاً وكسب قلوب الحي.",bad:"الهدوء فُسر ضعفاً فتوسعت الاشتباكات.",rep:{cit:4,media:2}},
    storm2:{ok:"اقتحام السوق حرر المحتجزين وقبض على الخلية.",bad:"اقتحام دامٍ: إصابات مدنية وتحقيق داخلي!",rep:{cit:bad?-8:5,media:bad?-8:4},heat:bad?12:0},
    talk2:{ok:"ممر آمن مقابل استسلام — بلا قطرة دم.",bad:"استغلوا التفاوض للهرب بسيارة إسعاف مسروقة!",rep:{cit:2,media:1}},
    siege:{ok:"الحصار خنقهم فاستسلموا فجراً.",bad:"الحصار طال فتدخلت العصابة الأم وفكته بالقوة.",rep:{pol:2,cit:1}},
    search:{ok:"بحث سري: وجدناه مخدراً بمستودع قبل نقله!",bad:"التكتم أضاع 12 ساعة ثمينة.",rep:{polit:3,media:1}},
    public:{ok:"الضغط الشعبي أجبر الخاطفين على التفاوض علناً.",bad:"الإعلان نبههم فنقلوه لمكان مجهول.",rep:{media:3,polit:2}},
    watch:{ok:"المراقبة كشفت شبكة المراقبة المضادة — قبضنا على وسيط!",bad:"راقبنا بصمت بينما نُقل عبر 3 سيارات وضاع.",rep:{cit:-3,media:-2}},
    pay:{ok:"فدية مرصودة قادتنا للوكر وحُرر المسؤول!",bad:"دُفعت الفدية وضاع الأثر — فضيحة.",rep:{cit:bad?-7:4,polit:bad?-5:3},money:bad?-20000:0},
    trap:{ok:"كمين محكم: حُرر المسؤول وقُبض على الخاطفين!",bad:"الكمين انكشف: اشتباك وخاطف هارب.",rep:{pol:3,cit:bad?-4:4}},
    refuse:{ok:"الصلابة أجبرتهم على التراجع.",bad:"رفضك كلف المسؤول حياته تقريباً — أزمة سياسية!",rep:{polit:-8,media:-6,cit:-5}},
    evac:{ok:"إخلاء سريع أنقذ مئات الأرواح.",bad:"تأخر الإخلاء: اختناقات وإصابات.",rep:{cit:bad?-5:5,media:3}},
    save:{ok:"حماية المخازن المجاورة منعت كارثة مضاعفة.",bad:"ركزنا على المخازن واحترقت ورش العمال.",rep:{cit:2,bus:3}},
    inv:{ok:"تحفظ جنائي أثناء الإطفاء: أدلة الحرق المفتعل محفوظة!",bad:"الانشغال بالأدلة أبطأ الإطفاء.",rep:{jud:3,media:1}},
    risk:{ok:"إخماد بطولي في اللحظة الأخيرة! المدينة تهتف باسمك.",bad:"المخاطرة انفجرت: إصابات بصفوف الإطفاء.",rep:{cit:bad?-6:7,media:bad?-5:6,pol:-2}},
    pull:{ok:"سحب حكيم حفظ الأرواح.",bad:"الانسحاب ترك المنطقة تحترق — خسائر بملايين.",rep:{cit:-4,bus:-4},money:-5000},
    demo:{ok:"تفجير وقائي مسيطر أنقذ المنطقة. هندسة عبقرية!",bad:"التفجير خرج عن السيطرة جزئياً.",rep:{cit:3,media:2}},
    lock:{ok:"الاستنفار طمأن المسؤولين والناس.",bad:"الإغلاق شل المدينة وغضب التجار.",rep:{polit:3,bus:-3}},
    hunt:{ok:"مطاردة صامتة: قبضنا على السائق المتورط!",bad:"الصمت أضاع الخيط الأول.",rep:{pol:2}},
    guard:{ok:"حماية مشددة منعت هجوماً ثانياً.",bad:"حماية المسؤولين فقط أغضبت المواطنين.",rep:{polit:3,cit:-2}},
    hold:{ok:"التوقيف القانوني كشف شبكة التسليح!",bad:"الموقوف بريء فعلاً — فضيحة توقيف!",rep:{jud:bad?-4:3,media:bad?-5:2},heat:bad?8:0},
    release:{ok:"المراقبة قادتنا للقناص الحقيقي!",bad:"أفلتناه ولم يعد…",rep:{cit:-4,media:-3}},
    press2:{ok:"استجواب حازم انتزع الاعتراف قانونياً.",bad:"الضغط الزائد ولّد شكوى تعذيب — تحقيق داخلي!",rep:{jud:-3,media:-4},heat:10},
  }[ch.id]||{ok:"نُفذ القرار.",rep:{}};
  const win=!bad&&Math.random()<0.75;
  const txt=win?eff.ok:(eff.bad||eff.ok);
  inc.stage++;
  inc.ignored=0;
  if(eff.rep)for(const[k,v]of Object.entries(eff.rep))rep(k,win?v:Math.round(v*1.2));
  if(eff.money)S.money=Math.max(0,S.money+(eff.money||0));
  if(eff.heat)S.internal.heat+=eff.heat;
  inc.log.push(`قرارك [${ch.label}]: ${txt}`);
  inboxAdd(win?"pol":"media",`${win?"✅":"❌"} ${inc.title}: ${txt}`);
  addNews(`${win?"✅":"❌"} ${inc.title}`,txt,win?"good":"bad");
  addFile("حوادث",`${inc.title} — قرار`,txt);
  if(inc.stage>=INCIDENT_DEFS[inc.kind].stages.length){ finishIncident(inc, win); }
  else { inc.nextTick=(S._tick||0)+8; if(!S.alertQueue.includes(inc.id))S.alertQueue.push(inc.id); }
}
function finishIncident(inc, win){
  inc.active=false;
  inc.log.push(win?`أُغلق بنجاح يوم ${window.S.day}.`:`أُغلق بخسائر يوم ${window.S.day} — ستتذكر المدينة.`);
  if(win){ window.S.stats.solved++; window.S.money+=3000; }
  else { rep("cit",-3); }
  inboxAdd("pol",`${win?"🏁 أُغلق الملف بنجاح.":"🏁 أُغلق الملف بخسائر — التقرير على مكتبك."} (${inc.title})`);
}
/* العالم يستمر بدونك: تجاهل متكرر = نهاية سيئة تلقائية */
function incidentTick(){
  incidentGuards(); const S=window.S; S._tick=(S._tick||0)+1;
  // محفز تلقائي: سالفة كل ~3-6 دقائق لعب إن لم يوجد نشط
  if(activeIncidents().length<2 && Math.random()<0.02) startIncident();
  for(const inc of activeIncidents()){
    if((S._tick||0)>=inc.nextTick && !S.alertQueue.includes(inc.id)){
      if(inc.ignored>=2){
        // انتهى لوحده بشكل سيئ
        inc.log.push(`تجاهلته طويلاً فانفجر الوضع بدونك!`);
        inboxAdd("media",`🔥 ${inc.title}: تفاقم بدون تدخل القيادة!`);
        addNews(`🔥 تفاقم ${inc.title}`,`تجاهل القيادة فاقم الأزمة في ${inc.dist}. الصحافة والشارع يغليان.`,"bad");
        rep("cit",-6); rep("media",-6); rep("polit",-3); S.internal.heat+=4;
        inc.stage++;
        if(inc.stage>=INCIDENT_DEFS[inc.kind].stages.length) finishIncident(inc,false);
        else { inc.nextTick=(S._tick||0)+8; S.alertQueue.push(inc.id); }
      } else {
        inc.ignored++;
        S.alertQueue.push(inc.id);
      }
    }
  }
  showAlertQueue();
}
function showAlertQueue(force){
  try{
    const S=window.S; if(!S)return;
    incidentGuards();
    if(force && !S.alertQueue.length){ const a=activeIncidents()[0]; if(a) S.alertQueue.push(a.id); }
    if(!document.getElementById("modal").classList.contains("hidden"))return;
    // لا تقتحم الشاشة أثناء تسجيل الدخول أو أثناء تفاعل المستخدم النشط (آخر 20 ثانية) — إلا إذا طلبها بنفسه
    if(!force && document.getElementById("boot") && !document.getElementById("boot").classList.contains("gone"))return;
    if(!force && Date.now()-(window._lastTap||0)<20000)return;
    if(window._activeChat||window._activeOfficer)return;
    if(!S.alertQueue||!S.alertQueue.length)return;
    const inc=S.incidents.find(i=>i.id===S.alertQueue[0]&&i.active);
    if(!inc){S.alertQueue.shift();return;}
    paintIncidentAlert(inc);
  }catch(e){}
}
function paintIncidentAlert(inc){
  const st=INCIDENT_DEFS[inc.kind].stages[Math.min(inc.stage,INCIDENT_DEFS[inc.kind].stages.length-1)];
  document.getElementById("modal").classList.remove("hidden");
  document.getElementById("modal-card").innerHTML=`
   <div class="alert-flash">🚨 عاجل إلى مكتبك — ${escHtml(inc.title)}</div>
   <div class="row" style="justify-content:flex-start"><button type="button" class="btn" onclick="snoozeIncident('${inc.id}')">✕ إغلاق مؤقت (أقرر لاحقاً من القيادة)</button></div>
   <div class="mut small">${escHtml(inc.dist)} • اليوم ${window.S.day} ${clockNow()} ${inc.ignored?`• تجاهل ×${inc.ignored} (الوضع يتفاقم!)`:""}</div>
   <div class="msg"><span class="who">👮 قائد الشرطة:</span> ${escHtml(st.police)}</div>
   <div class="msg"><span class="who">🛰️ الاستخبارات:</span> ${escHtml(st.intel)}</div>
   <div class="msg"><span class="who">📰 الصحافة تنشر:</span> ${escHtml(st.press)}</div>
   <div class="mut small">قرارك الآن يحدد المرحلة التالية:</div>
   <div style="display:grid;gap:8px;margin-top:8px">
    ${st.choices.map(c=>`<button type="button" class="btn primary" onclick="decideIncident('${inc.id}','${c.id}')">${escHtml(c.label)}<div class="mut" style="font-size:11px">${escHtml(c.hint)}</div></button>`).join("")}
    <button type="button" class="btn" onclick="snoozeIncident('${inc.id}')">⏸️ أجّل القرار (خطر التفاقم)</button>
   </div>`;
}
