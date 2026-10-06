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
  if(act==="promote"){ const i=RANKS.indexOf(o.rank); if(i<RANKS.length-1){o.rank=RANKS[i+1];o.salary+=300;o.history.push(`يوم ${window.S.day}: رُقّي إلى ${o.rank}`);addMemory(o.id,`رقيته إلى ${o.rank} — زادت ثقته بك.`);rep("pol",1);} }
  if(act==="warn"){o.history.push(`يوم ${window.S.day}: تحذير رسمي`);addMemory(o.id,`وجهت له تحذيراً — استياء خفيف.`);}
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
