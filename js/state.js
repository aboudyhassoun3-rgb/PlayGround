/* ===== State: save/load + memory ===== */
window.S = null;
function defaultState(){
  return {
    v:1, city:"المدينة الجديدة", day:1, hour:8, min:0, money:120000, stateFund:25000,
    budget:{police:30,intel:25,ops:20,courts:10,prisons:8,equip:7},
    econ:{unemp:18, growth:2, corrup:22, policeFund:50, intelFund:50},
    rep:{cit:55,pol:60,polit:50,media:50,crim:20,jud:60,bus:50},
    cases:[], officers:[], squads:[], prisoners:[], news:[], files:[],
    gangs: window.GANG_DEFS.map(g=>({...g,members:8+Math.floor(Math.random()*8),turf:["الحي الفقير"],income:rnd(20000,60000),mood:"هادئة",heat:10})),
    chats:{int:[],cid:[],pol:[],det1:[],det2:[],det3:[],meeting:[],radio:[]},
    memory:{}, // charId -> [facts]
    emergencies:[], bribes:[], internal:{heat:0,open:false}, appeals:[],
    plot:{stage:0,notes:[]}, stats:{solved:0,errors:0,arrests:0},
    seq:{case:1,off:1,news:1}, pendingEvents:[], activeTab:"dash",
    intelReports:0, lastSalaryDay:1, conspiraciesFound:[],
    incidents:[], inbox:[], alertQueue:[], _tick:0,
    informants:[], season:{no:1,startDay:1,theme:0,solvedAtStart:0}, prank:{xp:0},
    novel:{}, chase:null, quick:null, flash:null, pressCd:0, informSeq:1
  };
}
function save(){ try{localStorage.setItem(window.Auth?window.Auth.saveKey():window.GAME_CONFIG.SAVE_KEY, JSON.stringify(window.S));}catch(e){} }
function load(){ try{const k=window.Auth?window.Auth.saveKey():window.GAME_CONFIG.SAVE_KEY; const s=localStorage.getItem(k); if(s)return JSON.parse(s);
  // ترحيل حفظ قديم للحساب الجديد
  const old=localStorage.getItem(window.GAME_CONFIG.SAVE_KEY); if(old){try{localStorage.setItem(k,old);return JSON.parse(old);}catch(e){}}
  return null;}catch(e){return null;} }
function wipe(){ try{localStorage.removeItem(window.Auth?window.Auth.saveKey():window.GAME_CONFIG.SAVE_KEY);}catch(e){} window.S=defaultState(); save(); }
function addMemory(charId, fact){
  window.S.memory[charId]=window.S.memory[charId]||[];
  window.S.memory[charId].push(`يوم ${window.S.day}: ${fact}`);
  if(window.S.memory[charId].length>30) window.S.memory[charId].shift();
}
function memOf(charId){ return (window.S.memory[charId]||[]).slice(-8).join("\n"); }
function addFile(kind,title,body){ window.S.files.unshift({day:window.S.day,kind,title,body}); if(window.S.files.length>300)window.S.files.pop(); }
function addNews(title,body,tone="info"){
  window.S.news.unshift({id:window.S.seq.news++,day:window.S.day,title,body,tone});
  if(window.S.news.length>80)window.S.news.pop();
  addFile("صحافة",title,body);
}
function rep(key,delta){ window.S.rep[key]=Math.max(0,Math.min(100,(window.S.rep[key]||50)+delta)); }
function toast(msg){ const d=document.createElement("div");d.className="toast";d.textContent=msg;document.getElementById("toast").appendChild(d);setTimeout(()=>d.remove(),3200); }
function fmt(n){ return Number(Math.round(n)).toLocaleString("en"); }
