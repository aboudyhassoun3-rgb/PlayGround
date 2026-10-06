/* LuxeTok — TikTok clone + Admin panel | Admin: aboudyhassoun3@gmail.com */
const ADMIN_EMAIL = 'aboudyhassoun3@gmail.com';
const DB_KEY = 'luxetok_db_v5';
const SES_KEY = 'luxetok_session_v5';
/* لا فيديوهات مزيفة: تبدأ المنصة فارغة والمحتوى من المستخدمين فقط */
const AV = (kind, n)=>`https://randomuser.me/api/portraits/${kind}/${n}.jpg`;

function seedDB(){
  const now=Date.now(), H=3600e3;
  const users=[
    {id:'u_admin',name:'عبود حسون',username:'aboudy_official',email:ADMIN_EMAIL,pass:'admin123',type:'admin',verified:true,artist:false,bio:'مؤسس المنصة 👑',avatar:AV('men',22),followers:[],following:[],coins:100,banned:false,created:now-30*24*H},
    {id:'u1',name:'سارة أحمد',username:'sara_dailies',email:'sara@demo.com',pass:'123456',type:'user',verified:false,artist:false,bio:'يوميات وأفكار من حياتي • حساب تجريبي',avatar:AV('women',44),followers:[],following:[],coins:20,banned:false,created:now-9*24*H},
    {id:'u2',name:'عمر التقني',username:'omar_tech',email:'omar@demo.com',pass:'123456',type:'user',verified:true,artist:false,bio:'شروحات تقنية مبسطة • حساب تجريبي موثّق',avatar:AV('men',32),followers:['u1'],following:[],coins:35,banned:false,created:now-8*24*H},
    {id:'u3',name:'فرقة صوت المدينة',username:'cityvoice_band',email:'cityvoice@demo.com',pass:'123456',type:'artist',verified:true,artist:true,bio:'فرقة موسيقية مستقلة • حساب فنان تجريبي',avatar:AV('men',52),followers:['u1','u2'],following:[],coins:40,banned:false,created:now-7*24*H},
    {id:'u4',name:'كريم المصور',username:'karim_shoots',email:'karim@demo.com',pass:'123456',type:'user',verified:false,artist:false,bio:'تصوير ومونتاج • حساب تجريبي',avatar:AV('men',67),followers:[],following:['u2','u3'],coins:20,banned:false,created:now-5*24*H}
  ];
  return {users,videos:[],reports:[],verifyRequests:[],
    settings:{siteName:'LuxeTok',announcement:'أهلاً بك في LuxeTok — انشر أول فيديو لك 🎬'},
    gifts:[],messages:[],activity:[],lives:[],blocks:[],sounds:[]};
}
function loadDB(){try{const d=JSON.parse(localStorage.getItem(DB_KEY));if(d&&d.users)return migrateDB(d);}catch(e){}const d=seedDB();localStorage.setItem(DB_KEY,JSON.stringify(d));return d;}
let DB=loadDB();
function migrateDB(d){d.blocks=d.blocks||[];d.activity=d.activity||[];d.lives=d.lives||[];d.gifts=d.gifts||[];d.messages=d.messages||[];d.liveMsgs=d.liveMsgs||[];d.reports=d.reports||[];d.verifyRequests=d.verifyRequests||[];d.sounds=d.sounds||[];d.users.forEach(u=>{u.followers=u.followers||[];u.following=u.following||[];u.coins=u.coins||0;});d.videos.forEach(v=>{v.uniqueViewers=v.uniqueViewers||[];v.sponsored=v.sponsored||0;v.tags=v.tags||[];v.likedBy=v.likedBy||[];v.savedBy=v.savedBy||[];v.comments=v.comments||[];});return d;}
/* مشاهدة دقيقة: إجمالي + مشاهدون فريدون (عضوي/مروّج منفصلان بشفافية) */
function totalViews(v){return (v.views||0)+(v.sponsored||0);}
function countView(v){const m=me();const id=m?m.id:'anon';v.uniqueViewers=v.uniqueViewers||[];
  if(v.uniqueViewers.length<5000&&!v.uniqueViewers.includes(id))v.uniqueViewers.push(id);
  v.views=(v.views||0)+1;save();}
function save(){try{localStorage.setItem(DB_KEY,JSON.stringify(DB));}catch(e){toast('مساحة التخزين ممتلئة — احذف صوراً أو بيانات قديمة ⚠️');}}
function isBlocked(a,b){if(!a||!b)return false;return (DB.blocks||[]).some(x=>(x.by===a&&x.target===b)||(x.by===b&&x.target===a));}
function hiddenUser(u){if(!u)return true;if(u.banned)return true;const m=me();if(m&&isBlocked(m.id,u.id))return true;return false;}
function me(){try{const id=JSON.parse(localStorage.getItem(SES_KEY));return DB.users.find(u=>u.id===id&&!u.banned)||null;}catch(e){return null;}}
function setSession(id){localStorage.setItem(SES_KEY,JSON.stringify(id));}
function logout(){localStorage.removeItem(SES_KEY);location.reload();}
function isAdmin(u){return u&&(u.email===ADMIN_EMAIL||u.type==='admin');}
function userById(id){return DB.users.find(u=>u.id===id);}
function badge(u){if(!u)return '';if(u.artist)return ' <i class="fa-solid fa-microphone gold-v" title="فنان"></i> <i class="fa-solid fa-circle-check verified" title="موثق"></i>';if(u.verified)return ' <i class="fa-solid fa-circle-check verified" title="موثق"></i>';return '';}
function avatarHTML(u,cls){cls=cls||'';return `<div class="avatar ${cls}">${u.avatar?`<img src="${u.avatar}" onerror="this.remove()">`:''}${(u.name||'L')[0]}</div>`;}

/* ---------- Router ---------- */
let feedTab='foryou', currentProfile=null, profileTab='videos', adminTab='overview', openCommentsFor=null, activeChat=null, tempVideoSrc=null;
function go(r){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.r===r));
  document.querySelectorAll('#bottomNav button').forEach(b=>b.classList.toggle('active',b.dataset.r===r));
  const map={feed:'view-feed',discover:'view-discover',following:'view-following',live:'view-live',inbox:'view-inbox',profile:'view-profile',admin:'view-admin',sound:'view-sound'};
  document.getElementById(map[r]).classList.add('active');
  const titles={feed:'',discover:'اكتشف',following:'أتابعهم',live:'بث مباشر',inbox:'صندوق الوارد',profile:'',admin:'لوحة الأدمِن'};
  const rt=document.getElementById('routeTitle');if(rt)rt.textContent=titles[r]||'';
  applySoundUI();
  if(r==='feed')renderFeed(); if(r==='following')renderFollowing();
  if(r==='discover')renderDiscover(); if(r==='live')renderLive();
  if(r==='inbox')renderInbox(); if(r==='admin')renderAdmin();
  window.scrollTo(0,0);
}
function goMyProfile(){const m=me();if(!m){openAuth();return;}openProfile(m.id);}
function openProfile(id){currentProfile=id;profileTab='videos';renderProfile();go('profile');}

/* ---------- Feed ---------- */
function feedVideos(){
  let list=DB.videos.filter(v=>{if(v.hidden)return false;const u=userById(v.userId);return u&&!hiddenUser(u);});
  if(feedTab==='following'){const m=me();list=list.filter(v=>m&&m.following&&m.following.includes(v.userId));}
  if(feedTab==='artists'){list=list.filter(v=>{const u=userById(v.userId);return u&&(u.artist||u.verified);});}
  list.sort((a,b)=>(b.pinned-a.pinned)||(b.featured-a.featured)||(b.likes-a.likes));
  return list;
}
function videoCard(v){
  const u=userById(v.userId)||{name:'مستخدم محذوف',username:'deleted',avatar:''};
  const m=me();const liked=m&&v.likedBy.includes(m.id);const saved=m&&v.savedBy.includes(m.id);
  const following=m&&m.following&&m.following.includes(u.id);
  return `<div class="vcard" data-vid="${v.id}">
    <div class="video-wrap" data-vid="${v.id}">
      ${v.featured?'<span class="featured-ribbon">⭐ مميز • LUXE</span>':''}${v.pinned?'<span class="featured-ribbon" style="top:40px">📌 مثبت</span>':''}
      <video src="${v.src}" poster="${v.poster}" loop muted playsinline preload="metadata"></video>
      <div class="tt-overlay">
        <div class="tt-top-btns">${isAdmin(me())?`<button class="mini gold" onclick="event.stopPropagation();go('admin')">👑 أدمِن</button>`:''}</div>
        <button class="mute-btn" onclick="event.stopPropagation();toggleMute('${v.id}')">${typeof soundOn!=='undefined'&&soundOn?'🔊':'🔇'}</button>
        <div class="tt-caption">
          <div class="uname"><span onclick="openProfile('${u.id}')">@${u.username} ${badge(u)}</span>${m&&m.id!==u.id?`<button class="tt-follow-btn ${following?'following':''}" onclick="event.stopPropagation();toggleFollow('${u.id}')">${following?'أتابعه':'متابعة'}</button>`:''}</div>
          <div class="title">${esc(v.title)}</div>
          <div class="title">${v.tags.map(t=>`<span class="tag" onclick="event.stopPropagation();searchTag('${t}')">#${t}</span>`).join(' ')}</div>
          <div class="tt-meta">منذ ${timeAgo(v.created)} • ${fmt(totalViews(v))} مشاهدة${(v.sponsored||0)>0?' • 🚀 مروّج':''}</div>
          <div class="sound-marquee" onclick="event.stopPropagation();openVideoSound('${v.id}')"><i class="fa-solid fa-compact-disc"></i><marquee scrollamount="3">♫ ${esc(v.sound)} — ${esc(v.title)}</marquee></div>
        </div>
        <div class="tt-rail">
          <div style="display:flex;flex-direction:column;align-items:center">
            <div class="tt-avatar" onclick="openProfile('${u.id}')">${u.avatar?`<img src="${u.avatar}" onerror="this.remove()">`:''}${(u.name||'L')[0]}</div>
            ${m&&m.id!==u.id?`<button class="follow-plus" onclick="event.stopPropagation();toggleFollow('${u.id}')">${following?'✓':'+'}</button>`:''}
          </div>
          <button class="tt-act ${liked?'liked':''}" onclick="event.stopPropagation();toggleLike('${v.id}')"><i class="fa-solid fa-heart"></i><small>${fmt(v.likes)}</small></button>
          <button class="tt-act" onclick="event.stopPropagation();openComments('${v.id}')"><i class="fa-solid fa-comment-dots"></i><small>${v.comments.length}</small></button>
          <button class="tt-act ${saved?'saved':''}" onclick="event.stopPropagation();toggleSave('${v.id}')"><i class="fa-solid fa-bookmark"></i><small>${fmt(v.savedBy.length)}</small></button>
          <button class="tt-act" onclick="event.stopPropagation();openShare('${v.id}')"><i class="fa-solid fa-share"></i><small>${fmt(v.shares)}</small></button>
          <button class="tt-act" onclick="event.stopPropagation();fsVideo('${v.id}')"><i class="fa-solid fa-expand" style="font-size:20px"></i><small>ملء</small></button>
          <button class="tt-act" onclick="event.stopPropagation();reportVideo('${v.id}')"><i class="fa-solid fa-flag" style="font-size:20px"></i><small>بلاغ</small></button>
        </div>
        <div class="tt-progress"><span id="pg-${v.id}"></span></div>
      </div>
    </div></div>`;
}
function renderFeedInto(el,list){
  el.innerHTML=list.length?list.map(videoCard).join(''):`<div class="empty">لا توجد فيديوهات هنا بعد — كن أول من ينشر! 🚀<br><br><button class="btn primary" onclick="openUpload()">نشر فيديو</button></div>`;
  observeVideos(el);
}
function renderFeed(){renderFeedInto(document.getElementById('feed'),feedVideos());}
function renderFollowing(){const m=me();const list=DB.videos.filter(v=>{if(v.hidden)return false;const u=userById(v.userId);return u&&!hiddenUser(u)&&m&&m.following&&m.following.includes(v.userId);});renderFeedInto(document.getElementById('followingFeed'),list);}
function setFeedTab(t){feedTab=t;const ids={foryou:'tabForYou',following:'tabFollowing',artists:'tabArtists'};Object.values(ids).forEach(id=>document.getElementById(id).classList.remove('on'));document.getElementById(ids[t]).classList.add('on');renderFeed();}
let io=null;
const _viewTimers={};
let soundOn=false;
try{soundOn=localStorage.getItem('luxetok_sound')==='1';}catch(e){}
function applySoundUI(){
  const tb=document.getElementById('soundTopBtn');if(tb){tb.textContent=soundOn?'🔊':'🔇';tb.classList.toggle('on',soundOn);}
  const hint=document.getElementById('soundHint');if(hint)hint.classList.toggle('show',!soundOn);
  document.querySelectorAll('.mute-btn').forEach(b=>b.textContent=soundOn?'🔊':'🔇');
}
function toggleGlobalSound(force){soundOn=force===true?true:!soundOn;try{localStorage.setItem('luxetok_sound',soundOn?'1':'0');}catch(e){}
  document.querySelectorAll('.feed video').forEach(vd=>{vd.muted=!soundOn;if(soundOn)vd.play().catch(()=>{});});
  applySoundUI();toast(soundOn?'الصوت مفعّل 🔊':'تم كتم الصوت 🔇');}
function observeVideos(root){
  if(io)io.disconnect();
  io=new IntersectionObserver(es=>{es.forEach(e=>{
    const vd=e.target.querySelector('video');if(!vd)return;
    const vid=e.target.querySelector('.video-wrap').dataset.vid;
    if(e.isIntersecting&&e.intersectionRatio>.6){
      vd.muted=!soundOn;
      vd.play().catch(()=>{vd.muted=true;vd.play().catch(()=>{});});
      // عدّ مشاهدة حقيقية: بعد مشاهدة فعلية لثانيتين
      clearTimeout(_viewTimers[vid]);
      _viewTimers[vid]=setTimeout(()=>{const v=DB.videos.find(x=>x.id===vid);if(v&&!vd.paused)countView(v);},2500);
    }else{vd.pause();clearTimeout(_viewTimers[vid]);}
  });},{root:root,threshold:.6});
  root.querySelectorAll('.vcard').forEach(c=>{
    io.observe(c);
    const wrap=c.querySelector('.video-wrap');const vd=c.querySelector('video');const vid=wrap.dataset.vid;
    vd.addEventListener('timeupdate',()=>{const p=document.getElementById('pg-'+vid);if(p&&vd.duration)p.style.width=(vd.currentTime/vd.duration*100)+'%';});
    // ضغطة = تشغيل/إيقاف + تفعيل الصوت (مثل تيك توك)، ضغطتان = لايك
    let lastTap=0;
    wrap.onclick=(e)=>{
      if(e.target.closest('.tt-rail')||e.target.closest('.tt-caption')||e.target.closest('button'))return;
      const now=Date.now();
      if(now-lastTap<300){doubleLike(e,vid);}else{setTimeout(()=>{if(Date.now()-lastTap>=300){
        if(vd.muted&&!soundOn){soundOn=true;try{localStorage.setItem('luxetok_sound','1');}catch(e2){}vd.muted=false;applySoundUI();}
        vd.paused?vd.play():vd.pause();}},310);}
      lastTap=now;
    };
    // swipe up/down handled natively by snap scroll; add touch hint
    wrap.ontouchstart=ev=>{wrap._y=ev.touches[0].clientY;};
  });
}
function toggleMute(vid){const card=document.querySelector(`.video-wrap[data-vid="${vid}"] video`);if(!card)return;card.muted=!card.muted;soundOn=!card.muted;try{localStorage.setItem('luxetok_sound',soundOn?'1':'0');}catch(e){}if(!card.muted)card.play().catch(()=>{});applySoundUI();}
function refreshFeed(){feedTab='foryou';const ids={foryou:'tabForYou',following:'tabFollowing',artists:'tabArtists'};Object.values(ids).forEach(id=>{const el=document.getElementById(id);if(el)el.classList.remove('on');});const fy=document.getElementById('tabForYou');if(fy)fy.classList.add('on');go('feed');const f=document.getElementById('feed');if(f)f.scrollTop=0;toast('تم التحديث ✨');}
document.addEventListener('keydown',e=>{
  const tag=(document.activeElement&&document.activeElement.tagName)||'';
  if(tag==='INPUT'||tag==='TEXTAREA')return;
  const f=document.getElementById('feed');
  if(!document.getElementById('view-feed').classList.contains('active'))return;
  if(e.key==='ArrowDown')f.scrollBy({top:f.clientHeight,behavior:'smooth'});
  if(e.key==='ArrowUp')f.scrollBy({top:-f.clientHeight,behavior:'smooth'});
  if(e.key==='m'||e.key==='M')toggleGlobalSound();
});

/* ---------- Interactions (كلها حقيقية وتُسجَّل في سجل النشاط) ---------- */
function logAct(type,from,to,videoId,text){DB.activity=DB.activity||[];DB.activity.unshift({id:'a'+Date.now()+Math.floor(Math.random()*999),type,from,to,videoId:videoId||null,text:text||'',time:Date.now()});DB.activity=DB.activity.slice(0,300);}
function earnCoins(u,n){u.coins=(u.coins||0)+n;}
function toggleLike(id){const m=me();if(!m){openAuth();return;}const v=DB.videos.find(x=>x.id===id);if(!v)return;const i=v.likedBy.indexOf(m.id);const owner=userById(v.userId);
  if(i>=0){v.likedBy.splice(i,1);v.likes--;}else{v.likedBy.push(m.id);v.likes++;if(owner&&owner.id!==m.id){earnCoins(owner,1);logAct('like',m.id,owner.id,v.id,'');}}
  save();refreshCards();}
function doubleLike(e,id){const h=document.getElementById('bigHeart');h.classList.add('pop');setTimeout(()=>h.classList.remove('pop'),400);const m=me();if(!m){openAuth();return;}const v=DB.videos.find(x=>x.id===id);if(v&&!v.likedBy.includes(m.id)){v.likedBy.push(m.id);v.likes++;const owner=userById(v.userId);if(owner&&owner.id!==m.id){earnCoins(owner,1);logAct('like',m.id,owner.id,v.id,'');}save();refreshCards();}}
function toggleSave(id){const m=me();if(!m){openAuth();return;}const v=DB.videos.find(x=>x.id===id);const i=v.savedBy.indexOf(m.id);if(i>=0)v.savedBy.splice(i,1);else{v.savedBy.push(m.id);toast('تم الحفظ في المفضلة 🔖');}save();refreshCards();}
function toggleFollow(id){const m=me();if(!m){openAuth();return;}if(m.id===id)return;const u=userById(id);if(!u||u.banned)return;if(isBlocked(m.id,id)){toast('لا يمكن التفاعل مع حساب محظور ⛔');return;}m.following=m.following||[];const i=m.following.indexOf(id);if(i>=0){m.following.splice(i,1);u.followers=u.followers.filter(x=>x!==m.id);toast('تم إلغاء المتابعة');}else{m.following.push(id);u.followers=u.followers||[];u.followers.push(m.id);logAct('follow',m.id,u.id,null,'');toast('تمت المتابعة ✅');}save();refreshAll();}
function updateBadges(){const m=me();const n=m?(DB.activity||[]).filter(a=>a.to===m.id).length:0;
  const p=document.getElementById('inboxPill');if(p){p.textContent=n||'';p.style.display=n?'inline-block':'none';}
  const b=document.getElementById('bottomInboxBadge');if(b){b.textContent=n>99?'99+':(n||'');b.style.display=n?'inline-block':'none';}}
function refreshCards(){renderFeed();renderSide();renderRail();updateBadges();}
function refreshAll(){refreshCards();renderProfile();renderSuggestions();updateBadges();}

/* comments */
function openComments(id){openCommentsFor=id;renderComments();openModal('commentsModal');}
function renderComments(){const v=DB.videos.find(x=>x.id===openCommentsFor);if(!v)return;document.getElementById('cCount').textContent='('+v.comments.length+')';
  document.getElementById('commentList').innerHTML=v.comments.map(c=>{const u=userById(c.userId)||{name:'؟',username:'؟',avatar:''};c.likes=c.likes||[];const m=me();const cl=m&&c.likes.includes(m.id);
    return `<div class="comment">${avatarHTML(u,'sm')}<div class="comment-body"><b>@${u.username}${badge(u)}</b><p>${esc(c.text)}</p><small class="muted">${timeAgo(c.time)}</small></div><button class="clike ${cl?'':''}" onclick="toggleClike('${c.id}')">❤️ ${c.likes.length||''}</button></div>`;}).join('')||'<div class="empty">كن أول المعلقين ✨</div>';}
function toggleClike(cid){const m=me();if(!m){openAuth();return;}const v=DB.videos.find(x=>x.id===openCommentsFor);if(!v)return;const c=v.comments.find(x=>x.id===cid);if(!c)return;c.likes=c.likes||[];const i=c.likes.indexOf(m.id);if(i>=0)c.likes.splice(i,1);else c.likes.push(m.id);save();renderComments();}
function sendComment(){const m=me();if(!m){openAuth();return;}const t=document.getElementById('commentText').value.trim();if(!t)return;const v=DB.videos.find(x=>x.id===openCommentsFor);if(!v)return;if(!v.allowComments){toast('التعليقات معطلة لهذا الفيديو');return;}v.comments.push({id:'c'+Date.now(),userId:m.id,text:t,time:Date.now()});const owner=userById(v.userId);if(owner&&owner.id!==m.id)logAct('comment',m.id,owner.id,v.id,t);document.getElementById('commentText').value='';save();renderComments();refreshCards();toast('تم نشر تعليقك ✅');}

/* share / duet / report */
let shareTarget=null;
function openShare(id){shareTarget=id;const v=DB.videos.find(x=>x.id===id);if(v){v.shares++;save();refreshCards();}openModal('shareModal');}
function doDuet(id){const m=me();if(!m){openAuth();return;}closeModal('shareModal');toast('🎬 لعمل ديو: ارفع فيديوك وسنضعه بجانبه');openUpload();}
function videoLink(id){return location.href.split('#')[0]+'#video-'+id;}
async function copyVideoLink(){if(!shareTarget)return;const link=videoLink(shareTarget);
  try{await navigator.clipboard.writeText(link);toast('تم نسخ الرابط 🔗');}
  catch(e){prompt('انسخ الرابط:',link);}}
function downloadVideo(){if(!shareTarget)return;const v=DB.videos.find(x=>x.id===shareTarget);if(!v)return;
  const a=document.createElement('a');a.href=v.src;a.download='luxetok-'+v.id+'.mp4';a.target='_blank';document.body.appendChild(a);a.click();a.remove();toast('بدأ التحميل ⬇️');}
function saveSharedVideo(){const m=me();if(!m){openAuth();return;}if(shareTarget)toggleSave(shareTarget);closeModal('shareModal');}
function useSound(s){const m=me();if(!m){openAuth();return;}openModal('uploadModal');setTimeout(()=>{const sel=document.getElementById('upSound');if(sel){for(const o of sel.options){if(o.text===s){sel.value=o.value||o.text;sel.selectedIndex=o.index;}}}toast('🎵 تصوير على: '+s);},80);}
function fsVideo(id){const w=document.querySelector(`.video-wrap[data-vid="${id}"]`);if(!w)return;
  if(document.fullscreenElement){document.exitFullscreen().catch(()=>{});return;}
  if(w.requestFullscreen)w.requestFullscreen().catch(()=>{toast('غير مدعوم على هذا المتصفح');});
  else if(w.webkitEnterFullscreen)w.webkitEnterFullscreen();}
function reportVideo(id){const m=me();if(!m){openAuth();return;}const r=prompt('سبب البلاغ؟');if(!r)return;DB.reports.push({id:'r'+Date.now(),videoId:id,by:m.id,reason:r,status:'pending',time:Date.now()});save();toast('تم إرسال البلاغ للإدارة 🛡️');}

/* ---------- Upload ---------- */
function openUpload(){const m=me();if(!m){openAuth();toast('سجل الدخول أولاً للنشر 🔑');return;}refreshSoundSelects();openModal('uploadModal');}
function previewUpload(inp){const f=inp.files[0];if(!f)return;tempVideoSrc=URL.createObjectURL(f);const pv=document.getElementById('upPrev');pv.src=tempVideoSrc;pv.style.display='block';pv.play();document.getElementById('dropHint').style.opacity='.25';}
function resolveSound(selId){const sel=document.getElementById(selId);const name=sel?sel.value:'الصوت الأصلي 🎵';const s=(DB.sounds||[]).find(x=>x.title===name);return{name,id:s?s.id:null};}
function publishVideo(){const m=me();if(!m)return;
  if(!tempVideoSrc){toast('اختر فيديو أولاً من جهازك 🎬');return;}
  const title=document.getElementById('upTitle').value.trim()||'فيديو جديد';
  const tags=(document.getElementById('upTags').value.trim()||'جديد').split(/\s+/).map(s=>s.replace('#','')).filter(Boolean).slice(0,5);
  const snd=resolveSound('upSound');
  DB.videos.unshift({id:'v'+Date.now(),userId:m.id,src:tempVideoSrc,poster:'',title,desc:document.getElementById('upDesc').value,tags,sound:snd.name,soundId:snd.id,likes:0,views:0,sponsored:0,uniqueViewers:[],shares:0,likedBy:[],savedBy:[],featured:false,pinned:false,hidden:false,allowComments:document.getElementById('upComments').checked,created:Date.now(),comments:[]});
  earnCoins(m,10);
  save();closeModal('uploadModal');tempVideoSrc=null;document.getElementById('upPrev').style.display='none';document.getElementById('dropHint').style.opacity='1';
  toast('🎉 تم النشر! +10 عملات 🪙');go('feed');renderFeed();renderRail();}

/* ---------- Discover / search ---------- */
function onSearch(q){q=(q||'').trim();if(!q){renderDiscover();return;}go('discover');
  const q2=q.replace('#','');
  const vids=DB.videos.filter(v=>{if(v.hidden)return false;const u=userById(v.userId);return u&&!hiddenUser(u)&&(v.title.includes(q2)||(v.tags||[]).some(t=>t.includes(q2)));});
  const usrs=DB.users.filter(u=>!hiddenUser(u)&&(u.name.includes(q2)||u.username.includes(q2)));
  document.getElementById('discoverGrid').innerHTML=
    usrs.map(u=>`<div class="pv-thumb" onclick="openProfile('${u.id}')" style="display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#2b1055,#7597de);flex-direction:column;gap:6px;min-height:140px">${avatarHTML(u)}<small>@${u.username}</small></div>`).join('')+
    vids.map(v=>`<div class="pv-thumb" onclick="playVideo('${v.id}')"><video src="${v.src}" ${v.poster?`poster="${v.poster}"`:''} preload="metadata" muted playsinline></video><small>▶ ${fmt(totalViews(v))}</small></div>`).join('')||'<div class="empty">لا نتائج — جرّب كلمة أخرى 🔍</div>';
}
function searchTag(t){const s=document.getElementById('topSearch');if(s)s.value='#'+t;onSearch(t);}
function renderDiscover(){
  const counts={};DB.videos.forEach(v=>v.tags.forEach(t=>counts[t]=(counts[t]||0)+1));
  const top=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,10);
  document.getElementById('trendChips').innerHTML=top.map(([t,c])=>`<button onclick="searchTag('${t}')"> #${t} <small>(${c})</small></button>`).join('');
  document.getElementById('discoverGrid').innerHTML=DB.videos.filter(v=>{if(v.hidden)return false;const u=userById(v.userId);return u&&!hiddenUser(u);}).map(v=>`<div class="pv-thumb" onclick="playVideo('${v.id}')"><video src="${v.src}" ${v.poster?`poster="${v.poster}"`:''} preload="metadata" muted playsinline></video><small>▶ ${fmt(totalViews(v))}</small></div>`).join('')||'<div class="empty">لا فيديوهات بعد — كن أول من ينشر 🎬<br><br><button class="btn primary big-touch" onclick="openUpload()">+ إنشاء فيديو</button></div>';
  renderSounds();
}
/* ---------- مكتبة الأصوات: الفنان ينشر أغنية والناس تستخدمها ---------- */
let currentSound=null,_audio=null,_playingSnd=null,_sndFile=null,_sndData=null;
const BUILTIN_SOUNDS=['الصوت الأصلي 🎵','إيقاع عربي حماسي 🔥','عود شرقي 🎻','تريند الرقص 💃','سينمائي فاخر 🎬'];
function soundUses(id){return DB.videos.filter(v=>!v.hidden&&v.soundId===id).length;}
function refreshSoundSelects(){['upSound','camSound'].forEach(sid=>{const sel=document.getElementById(sid);if(!sel)return;const cur=sel.value;
  sel.innerHTML=BUILTIN_SOUNDS.map(s=>`<option>${esc(s)}</option>`).join('')+(DB.sounds||[]).map(s=>{const u=userById(s.userId)||{};return `<option value="${esc(s.title)}">🎵 ${esc(s.title)} — ${esc(u.name||'')}</option>`;}).join('');
  if(cur)sel.value=cur;});}
function renderSounds(){
  const m=me();const ub=document.getElementById('uploadSoundBtn');if(ub)ub.style.display=(m&&(m.artist||isAdmin(m)))?'inline-flex':'none';
  const lib=(DB.sounds||[]);
  document.getElementById('soundsRow').innerHTML=
    BUILTIN_SOUNDS.map(s=>{const n=DB.videos.filter(v=>!v.hidden&&!v.soundId&&v.sound===s).length;return `<div class="sound-card" onclick="useBuiltinSound(this)" data-sound="${esc(s)}"><b>🎵 ${esc(s)}</b><br><small>${n} ${n===1?'فيديو':'فيديوهات'}</small></div>`;}).join('')+
    lib.map(s=>{const u=userById(s.userId)||{};const n=soundUses(s.id);const playing=_playingSnd===s.id;
    return `<div class="sound-card lib"><b>🎵 ${esc(s.title)}</b><br><small>by ${esc(u.name||'؟')} ${badge(u)} • ${n} استخدام${s.temp?' • مؤقت ⏳':''}</small><div class="sound-btns"><button class="mini" onclick="previewLibrarySound('${s.id}')">${playing?'⏸ إيقاف':'▶ تشغيل'}</button><button class="mini gold" onclick="useSound('${s.id}')">🎬 استخدام</button>${m&&(m.id===s.userId||isAdmin(m))?`<button class="mini danger" onclick="delSound('${s.id}')">حذف</button>`:''}</div></div>`;}).join('');
}
function openSoundUpload(){const m=me();if(!m){openAuth();return;}if(!(m.artist||isAdmin(m))){toast('نشر الأغاني لحسابات الفنانين 🎤 — اطلب التوثيق من حسابك');return;}
  _sndFile=null;_sndData=null;document.getElementById('sndTitle').value='';const fi=document.getElementById('sndFile');if(fi)fi.value='';document.getElementById('sndPrev').textContent='لم يُختر ملف بعد';openModal('soundModal');}
function previewSound(inp){const f=inp.files&&inp.files[0];if(!f)return;_sndFile=f;
  if(f.size<=2.5*1024*1024){const r=new FileReader();r.onload=()=>{_sndData=r.result;document.getElementById('sndPrev').textContent='✅ '+f.name+' (حفظ دائم)';};r.readAsDataURL(f);}
  else{_sndData=null;document.getElementById('sndPrev').textContent='⚠️ '+f.name+' (كبير — يعمل لجلسة واحدة)';}}
function publishSound(){const m=me();if(!m||!(m.artist||isAdmin(m)))return;const t=document.getElementById('sndTitle').value.trim();if(!t){toast('أدخل اسم الأغنية');return;}if(!_sndFile){toast('اختر ملفاً صوتياً');return;}
  let title=t;if((DB.sounds||[]).some(s=>s.title===title))title=t+' — '+m.username;
  const src=_sndData||URL.createObjectURL(_sndFile);
  DB.sounds=DB.sounds||[];DB.sounds.unshift({id:'s'+Date.now(),userId:m.id,title,src,temp:!_sndData,created:Date.now()});
  save();closeModal('soundModal');refreshSoundSelects();renderSounds();toast('🎵 تم نشر أغنيتك!');}
function previewLibrarySound(id){const s=(DB.sounds||[]).find(x=>x.id===id);if(!s||!s.src){toast('لا يوجد ملف صوتي');return;}
  if(_playingSnd===id&&_audio&&!_audio.paused){_audio.pause();_playingSnd=null;renderSounds();if(currentSound===id&&document.getElementById('view-sound').classList.contains('active'))openSound(id);return;}
  if(_audio)_audio.pause();_audio=new Audio(s.src);_audio.play().catch(()=>toast('تعذر التشغيل'));_playingSnd=id;renderSounds();
  _audio.onended=()=>{_playingSnd=null;renderSounds();};}
function useBuiltinSound(el){const name=el.dataset.sound;openUpload();setTimeout(()=>{refreshSoundSelects();const sel=document.getElementById('upSound');if(sel)sel.value=name;toast('🎵 التصوير على: '+name);},80);}
function useSound(id){const s=(DB.sounds||[]).find(x=>x.id===id);if(!s)return;closeModal('shareModal');openUpload();setTimeout(()=>{refreshSoundSelects();const sel=document.getElementById('upSound');if(sel)sel.value=s.title;toast('🎵 التصوير على: '+s.title);},80);}
function delSound(id){const m=me();const s=(DB.sounds||[]).find(x=>x.id===id);if(!s||!m||!(m.id===s.userId||isAdmin(m)))return;if(!confirm('حذف "'+s.title+'"?'))return;
  DB.sounds=DB.sounds.filter(x=>x.id!==id);DB.videos.forEach(v=>{if(v.soundId===id)v.soundId=null;});save();refreshSoundSelects();renderSounds();toast('تم حذف الصوت 🗑');}
function openVideoSound(vid){const v=DB.videos.find(x=>x.id===vid);if(!v)return;if(v.soundId&&(DB.sounds||[]).some(s=>s.id===v.soundId))openSound(v.soundId);else toast('🎵 '+v.sound);}
function openSound(id){const s=(DB.sounds||[]).find(x=>x.id===id);if(!s){toast('الصوت غير متوفر');return;}const u=userById(s.userId)||{};currentSound=id;
  const playing=_playingSnd===id;
  document.getElementById('soundPage').innerHTML=`<div class="sound-hero"><div class="disc ${playing?'spin':''}">💿</div><div><h2>🎵 ${esc(s.title)}</h2><p class="muted link" onclick="openProfile('${u.id||''}')">by ${esc(u.name||'؟')} ${badge(u)}</p><p class="muted">${soundUses(id)} فيديو يستخدمه • منذ ${timeAgo(s.created)}</p><div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap"><button class="btn ghost sm" onclick="previewLibrarySound('${s.id}');setTimeout(()=>openSound('${s.id}'),150)">${playing?'⏸ إيقاف':'▶ تشغيل'}</button><button class="btn primary sm" onclick="useSound('${s.id}')">🎬 استخدام الصوت</button></div></div></div>`;
  document.getElementById('soundGrid').innerHTML=DB.videos.filter(v=>!v.hidden&&v.soundId===id&&!hiddenUser(userById(v.userId))).map(v=>`<div class="pv-thumb" onclick="playVideo('${v.id}')"><video src="${v.src}" ${v.poster?`poster="${v.poster}"`:''} preload="metadata" muted playsinline></video><small>▶ ${fmt(totalViews(v))}</small></div>`).join('')||'<div class="empty">لا فيديوهات بهذا الصوت بعد — كن أول من يستخدمه 🎬<br><br><button class="btn primary big-touch" onclick="useSound(\''+s.id+'\')">🎬 استخدام الصوت</button></div>';
  go('sound');}

/* ---------- Live Rooms (غرف حقيقية: كاميرا المذيع + مشاهدون + شات + هدايا) ---------- */
let liveState=null;
function pruneViewers(l){l.viewers=(l.viewers||[]).filter(v=>Date.now()-v.time<45000);return l;}
function liveViewCount(l){pruneViewers(l);return (l.viewers||[]).length;}
function renderLive(){
  const m=me();const lives=(DB.lives||[]).filter(l=>userById(l.userId)&&!hiddenUser(userById(l.userId)));
  const myLive=m&&lives.find(l=>l.userId===m.id);
  document.getElementById('liveGrid').innerHTML=
    `<div class="live-card live-start-card" onclick="${m?'openStartLive()':'openAuth()'}"><div class="cover start">🎥</div>
      <div class="info"><b>${myLive?'أنت على الهواء 🔴':'🎥 ابدأ بثك المباشر'}</b><br><small>${myLive?esc(myLive.title):'تحدث مع جمهورك لحظياً'}</small></div></div>`+
    (lives.filter(l=>!m||l.userId!==m.id).map(l=>{const u=userById(l.userId);const ng=(DB.gifts||[]).filter(g=>g.liveId===l.id).reduce((s,g)=>s+g.count,0);
      return `<div class="live-card" onclick="openLiveRoom('${l.id}')">
      <div class="cover">${u.avatar?`<img src="${u.avatar}" onerror="this.remove()">`:esc((u.name||'L')[0])}<span>🔴 LIVE</span></div>
      <div class="info"><b>${esc(u.name)}</b>${badge(u)}<br><small>${esc(l.title)}</small><br><small class="muted">👁 ${liveViewCount(l)} • 🎁 ${ng} • ${timeAgo(l.started)}</small></div></div>`;}).join('')||
    (myLive?'':'<div class="empty">لا توجد بثوث مباشرة الآن — كن أول من يبث 🎥</div>'));
}
function openStartLive(){const m=me();if(!m){openAuth();return;}if((DB.lives||[]).some(l=>l.userId===m.id)){const ex=DB.lives.find(l=>l.userId===m.id);openLiveRoom(ex.id);return;}openModal('startLiveModal');}
function confirmStartLive(){const m=me();if(!m)return;const t=document.getElementById('liveTitleInput').value.trim()||'بث مباشر مع المتابعين';
  DB.lives=DB.lives||[];const l={id:'l'+Date.now(),userId:m.id,title:t,started:Date.now(),viewers:[],likes:0};DB.lives.unshift(l);save();closeModal('startLiveModal');openLiveRoom(l.id);}
function refreshLiveDB(){try{const d=JSON.parse(localStorage.getItem(DB_KEY));if(d&&d.users)DB=migrateDB(d);}catch(e){}}
async function openLiveRoom(liveId){
  const m=me();if(!m){openAuth();return;}
  refreshLiveDB();const l=(DB.lives||[]).find(x=>x.id===liveId);
  if(!l){toast('انتهى هذا البث');renderLive();return;}
  const owner=userById(l.userId);if(!owner||hiddenUser(owner)){toast('غير متاح ⛔');return;}
  closeLiveRoom(true);
  liveState={liveId,role:l.userId===m.id?'owner':'viewer',stream:null,facing:'user',muted:false};
  if(!l.viewers.some(v=>v.id===m.id))l.viewers.push({id:m.id,time:Date.now()});
  save();openModal('liveModal');renderLiveRoom();
  if(liveState.role==='owner')await startOwnerCam();else toast('انضممت للبث 🎉');
  liveState.hb=setInterval(()=>{refreshLiveDB();const lv=(DB.lives||[]).find(x=>x.id===liveId);if(!lv){closeLiveRoom();toast('انتهى البث');return;}
    const ex=lv.viewers.findIndex(v=>v.id===m.id);if(ex>=0)lv.viewers[ex].time=Date.now();else lv.viewers.push({id:m.id,time:Date.now()});save();renderLiveRoom();},8000);
}
async function startOwnerCam(){
  const v=document.getElementById('liveOwnerVideo');
  try{
    if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)throw 0;
    if(liveState.stream)liveState.stream.getTracks().forEach(t=>t.stop());
    liveState.stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:liveState.facing,width:{ideal:720}},audio:true});
    v.srcObject=liveState.stream;v.style.display='block';document.getElementById('liveStageFallback').style.display='none';
    document.getElementById('liveFlipBtn').style.display='flex';document.getElementById('liveMuteBtn').style.display='flex';
    await v.play().catch(()=>{});
  }catch(e){v.style.display='none';document.getElementById('liveStageFallback').style.display='flex';toast('تعذر تشغيل كاميرا البث — تحقق من الإذن 🔒');}
}
async function liveFlip(){if(!liveState||liveState.role!=='owner')return;liveState.facing=liveState.facing==='user'?'environment':'user';await startOwnerCam();}
function liveMuteToggle(){if(!liveState||!liveState.stream)return;liveState.muted=!liveState.muted;liveState.stream.getAudioTracks().forEach(t=>t.enabled=!liveState.muted);document.getElementById('liveMuteBtn').querySelector('.e').textContent=liveState.muted?'🔇':'🎙';}
function renderLiveRoom(){
  if(!liveState||!document.getElementById('liveModal').classList.contains('open'))return;
  refreshLiveDBSilent();
  const l=(DB.lives||[]).find(x=>x.id===liveState.liveId);if(!l)return;
  const owner=userById(l.userId);if(!owner)return;const m=me();
  document.getElementById('liveOwnerChip').innerHTML=`${owner.avatar?`<img src="${owner.avatar}" onerror="this.remove()">`:esc((owner.name||'L')[0])}<div><b>${esc(owner.name)}</b>${badge(owner)}<br><small>${esc(l.title)}</small></div>${m&&m.id!==owner.id?`<span class="chip-follow" onclick="event.stopPropagation();toggleFollow('${owner.id}');renderLiveRoom()">${m.following&&m.following.includes(owner.id)?'✓':'متابعة'}</span>`:''}`;
  const dur=Math.floor((Date.now()-l.started)/1000);const dm=String(Math.floor(dur/60)).padStart(2,'0'),ds=String(dur%60).padStart(2,'0');
  document.getElementById('liveViewers').textContent=`👁 ${liveViewCount(l)} • ${dm}:${ds}`;
  document.getElementById('liveLikes').textContent=fmt(l.likes||0);
  document.getElementById('liveOwnerAvatar').innerHTML=`${owner.avatar?`<img src="${owner.avatar}" onerror="this.remove()">`:''}${esc((owner.name||'L')[0])}`;
  document.getElementById('liveFallbackNote').textContent=liveState.role==='viewer'?'📡 الدردشة والهدايا لحظية • الفيديو الكامل عبر الأجهزة يحتاج سيرفر بث':'كاميرتك تعمل الآن 🎥';
  if(liveState.role==='owner'){document.getElementById('liveEndBtn').style.display='block';}
  const msgs=(DB.liveMsgs||[]).filter(x=>x.liveId===l.id).slice(-40);
  const box=document.getElementById('liveChat');
  box.innerHTML=msgs.map(x=>{if(x.sys)return `<div class="lmsg sys">${esc(x.text)}</div>`;const u=userById(x.from)||{name:'؟'};return `<div class="lmsg"><b>${esc(u.name)}:</b> ${esc(x.text)}</div>`;}).join('')||'<div class="lmsg sys">رحّب بالمشاهدين 👋</div>';
  box.scrollTop=box.scrollHeight;
}
function refreshLiveDBSilent(){try{const d=JSON.parse(localStorage.getItem(DB_KEY));if(d&&d.users){DB=migrateDB(d);}}catch(e){}}
function sendLiveMsg(){if(!liveState)return;const m=me();if(!m)return;const inp=document.getElementById('liveMsgInput');const t=inp.value.trim();if(!t)return;
  refreshLiveDB();DB.liveMsgs=DB.liveMsgs||[];  DB.liveMsgs.push({id:'lm'+Date.now(),liveId:liveState.liveId,from:m.id,text:t.slice(0,200),time:Date.now()});
  DB.liveMsgs=DB.liveMsgs.slice(-300);save();inp.value='';renderLiveRoom();}
function sendLiveHeart(){if(!liveState)return;refreshLiveDB();const l=(DB.lives||[]).find(x=>x.id===liveState.liveId);if(!l)return;l.likes=(l.likes||0)+1;save();
  const h=document.createElement('div');h.className='float-heart';h.textContent=['❤️','🧡','💜','💖'][Math.floor(Math.random()*4)];h.style.right=(10+Math.random()*50)+'px';document.getElementById('liveHearts').appendChild(h);setTimeout(()=>h.remove(),1600);renderLiveRoom();}
function toggleLiveGifts(){const g=document.getElementById('liveGiftBar');g.style.display=g.style.display==='none'?'flex':'none';}
function sendLiveGift(e,c){if(!liveState)return;const m=me();if(!m){openAuth();return;}
  refreshLiveDB();const l=(DB.lives||[]).find(x=>x.id===liveState.liveId);if(!l){toast('انتهى البث');return;}
  if(l.userId===m.id){toast('لا يمكنك إرسال هدية لنفسك');return;}
  if((m.coins||0)<c){toast('رصيدك لا يكفي — اكسب عملات بالنشر والتفاعل 🪙');return;}
  m.coins-=c;const owner=userById(l.userId);if(owner)earnCoins(owner,c);
  DB.gifts=DB.gifts||[];DB.gifts.push({id:'g'+Date.now(),from:m.id,to:l.userId,liveId:l.id,kind:e,count:c,time:Date.now()});
  DB.liveMsgs=DB.liveMsgs||[];DB.liveMsgs.push({id:'lm'+Date.now()+'g',liveId:l.id,sys:true,text:`${m.name} أرسل ${e} (${c} 🪙)`,time:Date.now()});
  save();renderRail();
  const big=document.createElement('div');big.className='gift-fly';big.textContent=e;document.querySelector('#liveModal .live-room').appendChild(big);setTimeout(()=>big.remove(),1800);
  renderLiveRoom();}
function liveShare(){if(!liveState)return;const l=(DB.lives||[]).find(x=>x.id===liveState.liveId);if(!l)return;const link=location.href.split('#')[0]+'#live-'+l.id;
  if(navigator.clipboard)navigator.clipboard.writeText(link).then(()=>toast('تم نسخ رابط البث 🔗')).catch(()=>prompt('انسخ الرابط:',link));}
function openLiveOwner(){if(!liveState)return;const l=(DB.lives||[]).find(x=>x.id===liveState.liveId);if(l)openProfile(l.userId);}
function endLive(){if(!liveState)return;const m=me();
  DB.lives=(DB.lives||[]).filter(l=>l.id!==liveState.liveId);
  DB.liveMsgs=(DB.liveMsgs||[]).filter(x=>x.liveId!==liveState.liveId);
  save();closeLiveRoom();renderLive();toast('تم إنهاء البث');}
function closeLiveRoom(silent){
  if(liveState){
    clearInterval(liveState.hb);
    if(liveState.stream){liveState.stream.getTracks().forEach(t=>t.stop());liveState.stream=null;}
    try{const m=me();if(m){refreshLiveDB();const l=(DB.lives||[]).find(x=>x.id===liveState.liveId);if(l){l.viewers=(l.viewers||[]).filter(v=>v.id!==m.id);save();}}}catch(e){}
    const v=document.getElementById('liveOwnerVideo');if(v){v.pause();v.removeAttribute('src');v.load();v.style.display='none';}
    document.getElementById('liveStageFallback').style.display='flex';
    document.getElementById('liveFlipBtn').style.display='none';document.getElementById('liveMuteBtn').style.display='none';document.getElementById('liveEndBtn').style.display='none';
    document.getElementById('liveGiftBar').style.display='none';document.getElementById('liveHearts').innerHTML='';
    liveState=null;
  }
  if(!silent)closeModal('liveModal');else{closeModal('liveModal');}
  renderLive();
}

/* ---------- Inbox: رسائل حقيقية + سجل نشاط حقيقي ---------- */
let inboxTab='msgs';
function setInboxTab(t,btn){inboxTab=t;document.querySelectorAll('.inbox-tabs button').forEach(b=>b.classList.remove('on'));if(btn)btn.classList.add('on');
  document.getElementById('inboxList').style.display=t==='msgs'?'flex':'none';
  document.getElementById('chatBox').style.display=t==='msgs'?'flex':'none';
  let ap=document.getElementById('activityPane');
  if(t==='activity'){if(!ap){ap=document.createElement('div');ap.id='activityPane';ap.className='inbox-list';ap.style.gridColumn='1/-1';document.querySelector('.inbox-wrap').appendChild(ap);}ap.style.display='flex';renderActivity();}else if(ap)ap.style.display='none';}
function renderActivity(){const m=me();const ap=document.getElementById('activityPane');if(!ap)return;
  if(!m){ap.innerHTML='<div class="empty">سجل الدخول لعرض نشاطك 🔑</div>';return;}
  const list=(DB.activity||[]).filter(a=>a.to===m.id).slice(0,50);
  ap.innerHTML=list.map(a=>{const u=userById(a.from)||{name:'مستخدم',username:'؟',avatar:''};const v=a.videoId?DB.videos.find(x=>x.id===a.videoId):null;
    const txt=a.type==='like'?'أعجب بفيديوك ❤️':a.type==='comment'?'علّق على فيديوك 💬':a.type==='follow'?'بدأ بمتابعتك ➕':'تفاعل معك';
    const ctxt=a.type==='comment'&&a.text?' — "'+esc(a.text.slice(0,60))+'"':'';
    return `<div class="inbox-item" onclick="${v?"go('feed')":`openProfile('${u.id}')`}">${avatarHTML(u,'sm')}<div><b>${esc(u.name)}</b> ${txt}${ctxt}<br><small class="muted">${timeAgo(a.time)}${v?' • '+esc(v.title.slice(0,30)):''}</small></div></div>`;}).join('')||'<div class="empty">لا نشاط بعد — انشر فيديو وتفاعل مع الآخرين ✨</div>';}
function renderInbox(){
  const m=me();if(!m){document.getElementById('inboxList').innerHTML='<div class="empty">سجل الدخول لعرض رسائلك 🔑</div>';return;}
  const others=DB.users.filter(u=>!hiddenUser(u)&&u.id!==m.id);
  const withMsgs=others.map(u=>({u,last:[...DB.messages].reverse().find(x=>(x.from===m.id&&x.to===u.id)||(x.from===u.id&&x.to===m.id))})).sort((a,b)=>(b.last?b.last.time:0)-(a.last?a.last.time:0));
  document.getElementById('inboxList').innerHTML=withMsgs.map(({u,last})=>`<div class="inbox-item ${activeChat===u.id?'on':''}" onclick="openChat('${u.id}')">${avatarHTML(u,'sm')}<div><b>${esc(u.name)}</b>${badge(u)}<br><small>${last?esc(last.text.slice(0,30))+' • '+timeAgo(last.time):'ابدأ المحادثة...'}</small></div></div>`).join('')||'<div class="empty">لا مستخدمون بعد</div>';
  const pill=document.getElementById('inboxPill');if(pill){const n=(DB.activity||[]).filter(a=>a.to===m.id).length;pill.textContent=n||'';pill.style.display=n?'inline-block':'none';}
  updateBadges();
}
function openChat(id){activeChat=id;const u=userById(id);if(!u||u.banned)return;const m=me();if(m&&isBlocked(m.id,id)){toast('لا يمكن مراسلة حساب محظور ⛔');return;}document.getElementById('chatName').textContent=u.name;document.getElementById('chatStatus').textContent='@'+u.username;document.getElementById('chatAvatar').innerHTML=u.avatar?`<img src="${u.avatar}" style="width:100%;height:100%;border-radius:50%;object-fit:cover">`:esc((u.name||'؟')[0]);renderMsgs();renderInbox();}
function renderMsgs(){const m=me();if(!m||!activeChat)return;const list=DB.messages.filter(x=>(x.from===m.id&&x.to===activeChat)||(x.from===activeChat&&x.to===m.id));
  document.getElementById('chatMsgs').innerHTML=list.map(x=>`<div class="msg ${x.from===m.id?'me':'them'}">${esc(x.text)}</div>`).join('')||'<div class="empty">لا رسائل بعد — قل مرحباً 👋</div>';
  document.getElementById('chatMsgs').scrollTop=1e6;}
function sendMsg(){const m=me();if(!m){openAuth();return;}if(!activeChat){toast('اختر محادثة أولاً');return;}const t=document.getElementById('chatText').value.trim();if(!t)return;const other=userById(activeChat);if(!other||other.banned||isBlocked(m.id,activeChat)){toast('لا يمكن المراسلة ⛔');return;}DB.messages.push({id:'m'+Date.now(),from:m.id,to:activeChat,text:t,time:Date.now()});document.getElementById('chatText').value='';save();renderMsgs();renderInbox();}

/* ---------- Profile (TikTok exact) ---------- */
function renderProfile(){
  const u=userById(currentProfile)||me();
  if(!u){document.getElementById('profileHero').innerHTML='<div class="empty">سجّل الدخول لعرض حسابك 🔑<br><br><button class="btn primary big-touch" onclick="openAuth()">تسجيل الدخول</button></div>';document.getElementById('profileGrid').innerHTML='';return;}
  const m=me();const isMine=m&&m.id===u.id;
  const vids=DB.videos.filter(v=>v.userId===u.id&&!v.hidden);
  const likes=vids.reduce((s,v)=>s+v.likes,0);
  const avImg=u.avatar?`<img src="${u.avatar}" onerror="this.remove()">`:'';
  const typeLabel=u.type==='artist'?'🎤 فنان':u.type==='admin'?'👑 الإدارة':u.type==='brand'?'🏢 علامة تجارية':'';
  const following=m&&m.following&&m.following.includes(u.id);
  document.getElementById('profileHero').innerHTML=`
    <div class="back-row"><button onclick="go('feed')" aria-label="رجوع">‹</button><b>@${esc(u.username)}</b><span class="back-acts"><button onclick="copyProfileLink('${u.id}')" aria-label="مشاركة">⤴</button><button onclick="profileMenu('${u.id}')" aria-label="المزيد">•••</button></span></div>
    <div class="tt-avatar-big">${avImg}${esc((u.name||'L')[0])}</div>
    <h2>${esc(u.name)} ${badge(u)}</h2>
    <div class="handle">@${esc(u.username)}${typeLabel?' • '+typeLabel:''}</div>
    <div class="pstats-tt">
      <div onclick="openFollowList('${u.id}','following')"><b>${fmt((u.following||[]).length)}</b><small>أتابعهم</small></div>
      <div onclick="openFollowList('${u.id}','followers')"><b>${fmt((u.followers||[]).length)}</b><small>متابِعون</small></div>
      <div><b>${fmt(likes)}</b><small>الإعجابات</small></div>
    </div>
    <div class="tt-btns">${isMine
      ?`<button class="btn ghost big-touch" onclick="openEditProfile()">تعديل الملف الشخصي</button><button class="btn ghost sq" onclick="copyProfileLink('${u.id}')" aria-label="مشاركة">⤴</button>`
      :`<button class="btn ${following?'ghost':'primary'} big-touch" onclick="toggleFollow('${u.id}')">${following?'أتابعه ✓':'متابعة'}</button><button class="btn ghost big-touch" onclick="openChat('${u.id}');go('inbox')">مراسلة</button><button class="btn ghost sq" onclick="profileMenu('${u.id}')" aria-label="المزيد">•••</button>`}</div>
    <p class="tt-bio">${esc(u.bio||'')}</p>`;
  const prev=document.getElementById('avatarEditPrev');if(prev)prev.innerHTML=`<div class="tt-avatar-big" style="width:64px;height:64px;font-size:24px">${avImg}${esc((u.name||'L')[0])}</div>`;
  const pv=document.getElementById('avatarPrevImg');if(pv)pv.src=(m&&m.avatar)||'';
  let list=vids, locked=false;
  if(profileTab==='liked'){if(isMine)list=DB.videos.filter(v=>m&&v.likedBy.includes(m.id));else{list=[];locked=true;}}
  if(profileTab==='saved'){if(isMine)list=DB.videos.filter(v=>m&&v.savedBy.includes(m.id));else{list=[];locked=true;}}
  const ptabs=document.querySelectorAll('#profileTabs button');
  if(ptabs[0])ptabs[0].innerHTML='<i class="fa-solid fa-table-cells"></i>';
  if(ptabs[1])ptabs[1].innerHTML=`<i class="fa-solid fa-${isMine?'heart':'lock'}"></i>`;
  if(ptabs[2])ptabs[2].innerHTML=`<i class="fa-solid fa-bookmark"></i>`;
  document.getElementById('profileGrid').innerHTML=locked
    ?'<div class="empty">🔒 هذا القسم خاص بصاحب الحساب</div>'
    :list.map(v=>`<div class="pv-thumb" onclick="playVideo('${v.id}')">${v.src?`<video src="${v.src}" ${v.poster?`poster="${v.poster}"`:''} preload="metadata" muted playsinline></video>`:''}<small>▶ ${fmt(totalViews(v))}</small>${v.pinned?'<em class="pin">📌 مثبت</em>':''}</div>`).join('')||'<div class="empty">لا فيديوهات بعد 🚀<br><br><button class="btn primary big-touch" onclick="openUpload()">+ إنشاء</button></div>';
  document.querySelectorAll('#profileTabs button').forEach((b,i)=>b.classList.toggle('on',['videos','liked','saved'][i]===profileTab));
}
/* تشغيل فيديو محدد من الشبكة داخل الفيد */
function playVideo(id){feedTab='foryou';const fy=document.getElementById('tabForYou');if(fy){document.querySelectorAll('.tiktok-tabs button').forEach(b=>b.classList.remove('on'));fy.classList.add('on');}go('feed');renderFeed();
  setTimeout(()=>{const f=document.getElementById('feed');const c=f&&f.querySelector(`.vcard[data-vid="${id}"]`);if(f&&c)f.scrollTo({top:c.offsetTop,behavior:'auto'});},120);}
/* نسخ رابط الحساب (حقيقي) */
async function copyProfileLink(id){const u=userById(id);if(!u)return;const link=location.href.split('#')[0]+'#user-'+u.username;
  try{await navigator.clipboard.writeText(link);toast('تم نسخ رابط الحساب 🔗');}catch(e){prompt('انسخ الرابط:',link);}}
/* قائمة ••• (حقيقية) */
function profileMenu(id){const u=userById(id);if(!u)return;const m=me();
  const isMine=m&&m.id===id;const following=m&&m.following&&m.following.includes(id);
  const blocked=m&&isBlocked(m.id,id);const iBlocked=m&&blocked&&(DB.blocks||[]).some(x=>x.by===m.id&&x.target===id);
  let rows='';
  rows+=`<button onclick="copyProfileLink('${id}');closeModal('menuModal')">🔗 مشاركة الحساب</button>`;
  if(!isMine&&m){
    rows+=`<button onclick="toggleFollow('${id}');closeModal('menuModal')">${following?'➖ إلغاء المتابعة':'➕ متابعة'}</button>`;
    rows+=`<button onclick="closeModal('menuModal');openChat('${id}');go('inbox')">✉️ مراسلة</button>`;
    rows+=`<button onclick="reportUser('${id}')">🚩 إبلاغ عن الحساب</button>`;
    rows+=`<button class="${iBlocked?'':'danger'}" onclick="toggleBlockUser('${id}')">${iBlocked?'✅ إلغاء الحظر':'⛔ حظر الحساب'}</button>`;
  }
  if(isMine){rows+=`<button onclick="closeModal('menuModal');openEditProfile()">✏️ تعديل الملف الشخصي</button>`;rows+=`<button onclick="logout()">🚪 تسجيل الخروج</button>`;}
  if(isAdmin(m)&&!isMine){rows+=`<button class="danger" onclick="closeModal('menuModal');go('admin')">👑 إدارة هذا الحساب</button>`;}
  document.getElementById('menuList').innerHTML=rows;
  document.getElementById('menuTitle').textContent='@'+u.username;
  openModal('menuModal');}
function toggleBlockUser(id){const m=me();if(!m||m.id===id)return;DB.blocks=DB.blocks||[];
  const i=DB.blocks.findIndex(x=>x.by===m.id&&x.target===id);
  if(i>=0){DB.blocks.splice(i,1);toast('تم إلغاء الحظر ✅');}
  else{m.following=(m.following||[]).filter(x=>x!==id);const u=userById(id);if(u){u.followers=(u.followers||[]).filter(x=>x!==m.id);m.followers=(m.followers||[]).filter(x=>x!==id);u.following=(u.following||[]).filter(x=>x!==m.id);}
    DB.blocks.push({by:m.id,target:id,time:Date.now()});toast('تم حظر الحساب ⛔');}
  save();closeModal('menuModal');refreshAll();}
function reportUser(id){const m=me();if(!m){openAuth();return;}const r=prompt('سبب الإبلاغ عن هذا الحساب؟');if(!r)return;
  DB.reports.push({id:'r'+Date.now(),userId:id,by:m.id,reason:r,status:'pending',time:Date.now()});save();closeModal('menuModal');toast('تم إرسال البلاغ للإدارة 🛡️');}
/* قوائم المتابِعين / يتابعهم (حقيقية) */
function openFollowList(uid,kind){const u=userById(uid);if(!u)return;const m=me();
  const ids=kind==='followers'?(u.followers||[]):(u.following||[]);
  document.getElementById('followTitle').textContent=(kind==='followers'?'المتابِعون':'أتابعهم')+' ('+ids.length+')';
  document.getElementById('followList').innerHTML=ids.map(fid=>{const x=userById(fid);if(!x||x.banned)return'';const f=m&&m.following&&m.following.includes(fid);
    return `<div class="frow" onclick="closeModal('followModal');openProfile('${x.id}')">${avatarHTML(x,'sm')}<div class="frow-info"><b>${esc(x.name)}</b>${badge(x)}<br><small class="muted">@${esc(x.username)}</small></div>${m&&m.id!==fid?`<button class="mini" onclick="event.stopPropagation();toggleFollow('${fid}');openFollowList('${uid}','${kind}')">${f?'أتابعه ✓':'متابعة'}</button>`:''}</div>`;}).join('')||'<div class="empty">القائمة فارغة</div>';
  openModal('followModal');}
function setProfileTab(t,btn){profileTab=t;document.querySelectorAll('#profileTabs button').forEach(b=>b.classList.remove('on'));if(btn)btn.classList.add('on');renderProfile();}
function openEditProfile(){const m=me();if(!m)return;window._avatarData='';const f=document.getElementById('avatarFile');if(f)f.value='';document.getElementById('p_bio').value=m.bio||'';const pv=document.getElementById('avatarPrevImg');if(pv)pv.src=m.avatar||'';openModal('profileModal');}
/* رفع صورة شخصية من الجهاز (تُصغَّر وتُحفظ محلياً) */
function handleAvatarFile(inp){const f=inp.files&&inp.files[0];if(!f)return;
  if(!f.type.startsWith('image/')){toast('اختر ملف صورة ⚠️');return;}
  if(f.size>8*1024*1024){toast('الصورة كبيرة — حد أقصى 8MB ⚠️');return;}
  const img=new Image();const url=URL.createObjectURL(f);
  img.onload=()=>{try{const s=256;const cv=document.createElement('canvas');cv.width=cv.height=s;const r=Math.max(s/img.width,s/img.height);const w=img.width*r,h=img.height*r;cv.getContext('2d').drawImage(img,(s-w)/2,(s-h)/2,w,h);window._avatarData=cv.toDataURL('image/jpeg',0.82);URL.revokeObjectURL(url);document.getElementById('avatarPrevImg').src=window._avatarData;toast('تم تجهيز الصورة ✅ اضغط حفظ');}catch(e){toast('تعذر قراءة الصورة ⚠️');}};
  img.onerror=()=>toast('تعذر قراءة الصورة ⚠️');img.src=url;}
function clearAvatar(){window._avatarData='__clear__';document.getElementById('avatarPrevImg').src='';const f=document.getElementById('avatarFile');if(f)f.value='';}
function saveProfile(){const m=me();if(!m)return;const bio=document.getElementById('p_bio').value.trim();if(bio)m.bio=bio;
  if(window._avatarData==='__clear__')m.avatar='';
  else if(window._avatarData)m.avatar=window._avatarData;
  window._avatarData='';save();closeModal('profileModal');renderProfile();renderRail();renderSuggestions();toast('تم حفظ حسابك ✅');}
function requestVerify(){const m=me();if(!m)return;DB.verifyRequests.push({id:'q'+Date.now(),userId:m.id,kind:document.getElementById('v_type').value,reason:document.getElementById('v_reason').value,status:'pending',time:Date.now()});save();closeModal('profileModal');toast('تم إرسال طلب التوثيق للإدارة ✅');}

/* ---------- Side / rail ---------- */
function renderSide(){
  const counts={};DB.videos.filter(v=>!v.hidden).forEach(v=>(v.tags||[]).forEach(t=>counts[t]=(counts[t]||0)+1));
  const top=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,5);
  document.getElementById('sideTrends').innerHTML=top.map(([t,c])=>`<div class="trend-row" onclick="searchTag('${t}')"><span>#${t}</span><small>${c} ${c===1?'فيديو':'فيديوهات'}</small></div>`).join('')||'<div class="empty">لا هاشتاغات بعد</div>';
  document.getElementById('sideArtists').innerHTML=DB.users.filter(u=>(u.artist||u.verified)&&!hiddenUser(u)).slice(0,4).map(u=>`<div class="sug" onclick="openProfile('${u.id}')">${avatarHTML(u,'sm')}<div><b style="font-size:13px">${esc(u.name)}</b>${badge(u)}<br><small class="muted">@${u.username}</small></div></div>`).join('')||'<div class="empty">لا حسابات موثقة بعد</div>';
}
function renderSuggestions(){renderSide();
  const m0=me();
  document.getElementById('suggested').innerHTML=DB.users.filter(u=>!hiddenUser(u)&&(!m0||u.id!==m0.id)).slice(0,4).map(u=>`<div class="sug">${avatarHTML(u,'sm')}<div><b style="font-size:13px">${u.name}</b>${badge(u)}<br><small class="muted">@${u.username}</small></div><button class="mini" onclick="toggleFollow('${u.id}')">تابع</button></div>`).join('');
}
function renderRail(){const m=me();
  document.getElementById('railLogin').style.display=m?'none':'block';
  document.getElementById('railUser').style.display=m?'block':'none';
  const at=document.getElementById('authTopBtn');if(at){at.textContent=m?('👋 '+m.name.split(' ')[0]):'تسجيل الدخول';at.onclick=m?()=>{if(confirm('تسجيل الخروج؟'))logout();}:openAuth;}
  const showAdmin=m&&isAdmin(m);
  document.getElementById('navAdmin').style.display=showAdmin?'flex':'none';
  document.getElementById('adminTopBtn').style.display=showAdmin?'block':'none';
  if(m){document.getElementById('coinBal').textContent=fmt(m.coins||0);
    document.getElementById('railUser').innerHTML=`<div class="sug">${avatarHTML(m)}<div><b>${m.name}</b>${badge(m)}<br><small class="muted">@${m.username}</small></div></div><button class="btn ghost block sm" onclick="goMyProfile()">عرض حسابي</button> <button class="btn ghost block sm" onclick="logout()">خروج</button>`;}
}

/* ---------- Auth ---------- */
function openAuth(){openModal('authModal');}
function openModal(id){document.getElementById(id).classList.add('open');}
function closeModal(id){document.getElementById(id).classList.remove('open');}
function doAuth(mode){
  const name=document.getElementById('a_name').value.trim()||'مستخدم فاخر';
  const email=document.getElementById('a_email').value.trim().toLowerCase();
  const pass=document.getElementById('a_pass').value;
  const type=document.getElementById('a_type').value;
  if(!email||!pass){toast('أدخل البريد وكلمة المرور ⚠️');return;}
  if(mode==='register'){
    if(DB.users.some(u=>u.email===email)){toast('هذا البريد مسجل — سجل الدخول');return;}
    let h=0;for(const c of email)h=(h*31+c.charCodeAt(0))%100;
    const u={id:'u'+Date.now(),name,username:email.split('@')[0].replace(/[^a-z0-9_]/gi,'')+'_'+Math.floor(Math.random()*99),email,pass,type:type==='artist'?'artist':type,verified:false,artist:type==='artist',bio:type==='artist'?'🎤 فنان':'عضو جديد في LuxeTok ✨',avatar:AV(h%2?'men':'women',h),followers:[],following:[],coins:20,banned:false,created:Date.now()};
    if(email===ADMIN_EMAIL){u.type='admin';u.verified=true;u.artist=false;u.coins=100;}
    DB.users.push(u);save();setSession(u.id);closeModal('authModal');afterLogin();toast('🎉 أهلاً بك! هدية الترحيب: 20 عملة 🪙');
  }else{
    const u=DB.users.find(x=>x.email===email&&x.pass===pass);
    if(!u){toast('بيانات خاطئة — تحقق أو أنشئ حساباً ⚠️');return;}
    if(u.banned){toast('⛔ هذا الحساب محظور');return;}
    setSession(u.id);closeModal('authModal');afterLogin();toast('نورت يا '+u.name+' 👑');
  }
}
function quickAdminLogin(){
  let a=DB.users.find(u=>u.email===ADMIN_EMAIL);
  if(!a){a={id:'u_admin',name:'عبود حسون',username:'aboudy_official',email:ADMIN_EMAIL,pass:'admin123',type:'admin',verified:true,artist:false,bio:'مؤسس المنصة 👑',avatar:AV('men',22),followers:[],following:[],coins:100,banned:false,created:Date.now()};DB.users.push(a);save();}
  a.banned=false;save();setSession(a.id);closeModal('authModal');afterLogin();go('admin');toast('👑 مرحباً بعودتك أيها الأدمِن!');
}
function afterLogin(){renderRail();renderSuggestions();renderFeed();updateBadges();}

/* ---------- ADMIN ---------- */
function renderAdmin(){
  const m=me();const gate=document.getElementById('adminGate');const panel=document.getElementById('adminPanel');
  if(!m||!isAdmin(m)){panel.style.display='none';
    gate.innerHTML=`<div class="admin-hero" style="border-color:var(--pink)"><div><h2>🔒 منطقة الأدمِن الخاصة</h2><p>هذه اللوحة مخصصة فقط للإيميل الملكي:<br><code style="direction:ltr;display:inline-block">aboudyhassoun3@gmail.com</code></p></div><div style="display:flex;gap:8px"><button class="btn gold sm" onclick="quickAdminLogin()">👑 دخول الأدمِن</button><button class="btn ghost sm" onclick="openAuth()">تسجيل الدخول</button></div></div>`;
    return;}
  gate.innerHTML='';panel.style.display='block';
  const tv=DB.videos.length,tu=DB.users.length,tl=DB.videos.reduce((s,v)=>s+(v.likes||0),0),org=DB.videos.reduce((s,v)=>s+(v.views||0),0),spon=DB.videos.reduce((s,v)=>s+(v.sponsored||0),0),uniq=new Set(DB.videos.flatMap(v=>v.uniqueViewers||[])).size;
  document.getElementById('adminStats').innerHTML=`
    <div class="stat">👥<b>${tu}</b><small>مستخدم</small></div>
    <div class="stat">🎬<b>${tv}</b><small>فيديو</small></div>
    <div class="stat">❤️<b>${fmt(tl)}</b><small>إعجاب حقيقي</small></div>
    <div class="stat">👁<b>${fmt(org+spon)}</b><small>مشاهدة (${fmt(org)} عضوية)</small></div>
    <div class="stat">🧍<b>${fmt(uniq)}</b><small>مشاهد فريد</small></div>
    <div class="stat">🚀<b>${fmt(spon)}</b><small>مشاهدات مروّجة</small></div>
    <div class="stat">🚩<b>${DB.reports.filter(r=>r.status==='pending').length}</b><small>بلاغ معلق</small></div>
    <div class="stat">✅<b>${DB.verifyRequests.filter(r=>r.status==='pending').length}</b><small>طلب توثيق</small></div>`;
  document.getElementById('verifyPill').textContent=DB.verifyRequests.filter(r=>r.status==='pending').length||'';
  document.getElementById('reportPill').textContent=DB.reports.filter(r=>r.status==='pending').length||'';
  renderAdminTab();
}
function setAdminTab(t,btn){adminTab=t;document.querySelectorAll('#adminTabs button').forEach(b=>b.classList.remove('on'));btn.classList.add('on');renderAdminTab();}
function renderAdminTab(){
  const el=document.getElementById('adminContent');
  if(adminTab==='overview'){
    el.innerHTML=`<h3>📊 نظرة عامة</h3><p class="muted">${esc(DB.settings.announcement||'')}</p><canvas id="ch" width="700" height="220" style="width:100%;background:#0a0a18;border-radius:12px"></canvas>
    <h4>🔥 الأكثر مشاهدة (عضوية + مروّجة بشفافية)</h4><table><tr><th>الفيديو</th><th>الناشر</th><th>عضوية</th><th>مروّجة</th><th>فرّاد</th><th>إعجابات</th></tr>${[...DB.videos].sort((a,b)=>totalViews(b)-totalViews(a)).slice(0,8).map(v=>{const u=userById(v.userId)||{};return `<tr><td>${esc(v.title.slice(0,30))}</td><td>@${u.username||'؟'}</td><td>${fmt(v.views||0)}</td><td>${fmt(v.sponsored||0)}</td><td>${fmt((v.uniqueViewers||[]).length)}</td><td>${fmt(v.likes||0)}</td></tr>`;}).join('')||'<tr><td colspan="6">لا فيديوهات بعد</td></tr>'}</table>`;
    drawChart();
  }
  if(adminTab==='users'){
    el.innerHTML=`<h3>👥 إدارة المستخدمين (${DB.users.length})</h3><table><tr><th>المستخدم</th><th>الإيميل</th><th>النوع</th><th>الحالة</th><th>متابِعون</th><th>إجراءات</th></tr>${DB.users.map(u=>`<tr><td><b>${u.name}</b><br><small>@${u.username}</small></td><td style="direction:ltr">${u.email}</td><td>${u.type==='admin'?'👑 أدمِن':u.artist?'🎤 فنان':u.verified?'✅ موثق':'👤 عادي'}</td><td>${u.banned?'⛔ محظور':'🟢 نشط'}</td><td>${(u.followers||[]).length}</td><td style="white-space:normal;min-width:280px">
      <button class="mini ok" onclick="adminVerify('${u.id}')">توثيق ✅</button>
      <button class="mini gold" onclick="adminArtist('${u.id}')">فنان 🎤</button>
      <button class="mini" onclick="adminBan('${u.id}')">${u.banned?'فك الحظر':'حظر'}</button>
      <button class="mini danger" onclick="adminDelUser('${u.id}')">حذف</button></td></tr>`).join('')}</table>`;
  }
  if(adminTab==='videos'){
    el.innerHTML=`<h3>🎬 إدارة الفيديوهات (${DB.videos.length})</h3>${DB.videos.length?`<table><tr><th>العنوان</th><th>الناشر</th><th>❤️ حقيقي</th><th>👁 عضوية</th><th>🚀 مروّجة</th><th>🧍 فرّاد</th><th>الحالة</th><th>إجراءات</th></tr>${DB.videos.map(v=>{const u=userById(v.userId)||{};return `<tr><td>${esc(v.title.slice(0,25))}</td><td>@${u.username||'؟'}</td><td>${fmt(v.likes||0)}</td><td>${fmt(v.views||0)}</td><td>${fmt(v.sponsored||0)}</td><td>${fmt((v.uniqueViewers||[]).length)}</td><td>${v.hidden?'🙈 مخفي':v.featured?'⭐ مميز':v.pinned?'📌 مثبت':'✅ ظاهر'}</td><td style="white-space:normal;min-width:300px"><button class="mini gold" onclick="adminPromote('${v.id}')">ترويج 🚀</button><button class="mini gold" onclick="adminFeat('${v.id}')">تمييز ⭐</button><button class="mini" onclick="adminPin('${v.id}')">تثبيت 📌</button><button class="mini" onclick="adminHide('${v.id}')">${v.hidden?'إظهار':'إخفاء'}</button><button class="mini danger" onclick="adminDelVideo('${v.id}')">حذف</button></td></tr>`;}).join('')}</table>`:'<div class="empty">لا فيديوهات بعد — ستظهر هنا فيديوهات المستخدمين الحقيقية 🎬</div>'}`;
  }
  if(adminTab==='verify'){
    const list=DB.verifyRequests;
    el.innerHTML=`<h3>✅ طلبات التوثيق</h3>${list.length?`<table><tr><th>المستخدم</th><th>النوع المطلوب</th><th>السبب</th><th>الحالة</th><th>إجراء</th></tr>${list.map(q=>{const u=userById(q.userId)||{};return `<tr><td>${u.name} (@${u.username})</td><td>${q.kind==='artist'?'🎤 فنان ذهبي':q.kind==='brand'?'🏢 علامة':'✅ توثيق أزرق'}</td><td>${esc(q.reason||'—')}</td><td>${q.status}</td><td>${q.status==='pending'?`<button class="mini ok" onclick="verifyDecision('${q.id}',true)">قبول</button> <button class="mini danger" onclick="verifyDecision('${q.id}',false)">رفض</button>`:'—'}</td></tr>`;}).join('')}</table>`:'<div class="empty">لا طلبات حالياً</div>'}`;
  }
  if(adminTab==='reports'){
    el.innerHTML=`<h3>🚩 البلاغات</h3>${DB.reports.length?`<table><tr><th>المُبلغ عنه</th><th>المُبلغ</th><th>السبب</th><th>الحالة</th><th>إجراء</th></tr>${DB.reports.map(r=>{const by=userById(r.by)||{};let target='—',acts='';
      if(r.videoId){const v=DB.videos.find(x=>x.id===r.videoId);target='🎬 '+(v?esc(v.title.slice(0,25)):'(محذوف)');if(r.status==='pending')acts=`<button class="mini danger" onclick="reportDecision('${r.id}','hide')">إخفاء الفيديو</button> `;}
      else if(r.userId){const t=userById(r.userId);target='👤 @'+(t?t.username:'محذوف');if(r.status==='pending')acts=`<button class="mini danger" onclick="reportDecision('${r.id}','ban')">حظر الحساب</button> `;}
      if(r.status==='pending')acts+=`<button class="mini" onclick="reportDecision('${r.id}','dismiss')">تجاهل</button>`;else acts='—';
      return `<tr><td>${target}</td><td>@${by.username||'؟'}</td><td>${esc(r.reason)}</td><td>${r.status}</td><td>${acts}</td></tr>`;}).join('')}</table>`:'<div class="empty">لا بلاغات 🎉</div>'}`;
  }
  if(adminTab==='settings'){
    el.innerHTML=`<h3>⚙️ إعدادات المنصة</h3><label>اسم المنصة</label><input id="s_name" value="${esc(DB.settings.siteName)}"><br><br><label>الإعلان العلوي</label><input id="s_ann" value="${esc(DB.settings.announcement)}"><br><br><button class="btn gold" onclick="saveSettings()">حفظ الإعدادات 💾</button>`;
  }
}
function adminPromote(id){if(!needAdmin())return;const v=DB.videos.find(x=>x.id===id);if(!v)return;
  const cur=v.sponsored||0;
  const n=prompt(`ترويج "${v.title.slice(0,30)}"\nالمشاهدات المروّجة الحالية: ${cur}\nأدخل إجمالي المشاهدات المروّجة المطلوب (0 للإلغاء، بشفافية تامة):`,String(cur||1000));
  if(n===null)return;const num=Math.max(0,Math.floor(Number(n)||0));v.sponsored=num;v.featured=num>0?true:v.featured;
  save();renderAdmin();renderFeed();toast(num>0?`🚀 تم ترويج الفيديو (${num} مشاهدة مروّجة)`:'تم إلغاء الترويج');}
function drawChart(){const c=document.getElementById('ch');if(!c)return;const x=c.getContext('2d');
  const top=[...DB.videos].filter(v=>!v.hidden).sort((a,b)=>totalViews(b)-totalViews(a)).slice(0,8);
  x.clearRect(0,0,700,220);x.fillStyle='#a9a3c7';x.font='12px Cairo';
  if(!top.length){x.fillText('لا بيانات بعد — انشر فيديوهات لتظهر الإحصائيات',20,110);return;}
  const max=Math.max(...top.map(v=>totalViews(v)),1);
  x.fillText('الأعلى مشاهدة: عضوية (وردي) + مروّجة (ذهبي)',20,20);
  top.forEach((v,i)=>{const bw=560,px=150,py=36+i*20,org=v.views||0,sp=v.sponsored||0;
    x.fillStyle='#a9a3c7';x.fillText(String(v.title).slice(0,16),8,py+6);
    const wo=Math.max(org/max*bw,org>0?3:0),ws=Math.max(sp/max*bw,sp>0?3:0);
    x.fillStyle='#fe2c55';x.fillRect(px,py-6,wo,12);
    x.fillStyle='#f5c518';x.fillRect(px+wo,py-6,ws,12);
    x.fillStyle='#fff';x.fillText(fmt(org+sp),px+wo+ws+6,py+6);});}
/* admin actions */
function needAdmin(){const m=me();if(!m||!isAdmin(m)){toast('🔒 للأدمِن فقط');return false;}return true;}
function adminVerify(id){if(!needAdmin())return;const u=userById(id);u.verified=true;save();renderAdmin();toast('تم توثيق '+u.name+' ✅');}
function adminArtist(id){if(!needAdmin())return;const u=userById(id);u.artist=!u.artist;if(u.artist)u.verified=true;u.type=u.artist?'artist':u.type;save();renderAdmin();renderSuggestions();toast(u.artist?'أصبح فناناً ذهبياً 🎤':'تم إلغاء لقب فنان');}
function adminBan(id){if(!needAdmin())return;const u=userById(id);if(u.email===ADMIN_EMAIL){toast('لا يمكن حظر الأدمِن الملكي 👑');return;}u.banned=!u.banned;save();renderAdmin();toast(u.banned?'تم الحظر ⛔':'تم فك الحظر ✅');}
function adminDelUser(id){if(!needAdmin())return;const u=userById(id);if(!u)return;if(u.email===ADMIN_EMAIL){toast('لا يمكن حذف الأدمِن 👑');return;}if(!confirm('حذف '+u.name+' وكل بياناته؟'))return;DB.users=DB.users.filter(x=>x.id!==id);DB.videos=DB.videos.filter(v=>v.userId!==id);DB.messages=(DB.messages||[]).filter(m=>m.from!==id&&m.to!==id);DB.activity=(DB.activity||[]).filter(a=>a.from!==id&&a.to!==id);DB.reports=(DB.reports||[]).filter(r=>r.by!==id);DB.verifyRequests=(DB.verifyRequests||[]).filter(q=>q.userId!==id);DB.lives=(DB.lives||[]).filter(l=>l.userId!==id);save();renderAdmin();toast('تم الحذف 🗑');}
function adminFeat(id){if(!needAdmin())return;const v=DB.videos.find(x=>x.id===id);v.featured=!v.featured;save();renderAdmin();toast('تم التحديث ⭐');}
function adminPin(id){if(!needAdmin())return;DB.videos.forEach(v=>v.pinned=false);DB.videos.find(x=>x.id===id).pinned=true;save();renderAdmin();toast('تم التثبيت 📌');}
function adminHide(id){if(!needAdmin())return;const v=DB.videos.find(x=>x.id===id);v.hidden=!v.hidden;save();renderAdmin();renderFeed();toast(v.hidden?'تم الإخفاء 🙈':'تم الإظهار ✅');}
function adminDelVideo(id){if(!needAdmin())return;if(!confirm('حذف الفيديو نهائياً؟'))return;DB.videos=DB.videos.filter(v=>v.id!==id);save();renderAdmin();renderFeed();toast('تم حذف الفيديو 🗑');}
function verifyDecision(qid,ok){if(!needAdmin())return;const q=DB.verifyRequests.find(x=>x.id===qid);q.status=ok?'approved':'rejected';const u=userById(q.userId);if(ok&&u){if(q.kind==='artist'){u.artist=true;u.verified=true;u.type='artist';}else if(q.kind==='brand'){u.verified=true;u.type='brand';}else{u.verified=true;}}save();renderAdmin();toast(ok?'تم قبول التوثيق ✅':'تم الرفض');}
function reportDecision(rid,act){if(!needAdmin())return;const r=DB.reports.find(x=>x.id===rid);if(!r)return;
  if(act==='hide'){const v=DB.videos.find(x=>x.id===r.videoId);if(v)v.hidden=true;r.status='actioned';}
  else if(act==='ban'){const t=userById(r.userId);if(t&&t.email!==ADMIN_EMAIL){t.banned=true;r.status='actioned';}else{r.status='dismissed';toast('لا يمكن حظر الأدمِن 👑');}}
  else r.status='dismissed';save();renderAdmin();toast('تمت معالجة البلاغ 🛡️');}
function saveSettings(){if(!needAdmin())return;DB.settings.siteName=document.getElementById('s_name').value;DB.settings.announcement=document.getElementById('s_ann').value;save();toast('تم الحفظ 💾');}
function exportDB(){if(!needAdmin())return;const blob=new Blob([JSON.stringify(DB,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='luxetok-backup.json';a.click();toast('تم تحميل النسخة الاحتياطية 💾');}
function resetDemo(){if(!needAdmin())return;if(!confirm('استعادة بيانات الديمو؟'))return;DB=seedDB();save();renderAdmin();renderFeed();renderSuggestions();toast('تمت الاستعادة ✨');}

/* ---------- TikTok Camera Studio (كاميرا حقيقية + مؤثرات لحظية) ---------- */
const FILTERS=[
  {n:'عادي',f:'none'},{n:'دافئ',f:'sepia(.35) saturate(1.5)'},{n:'بارد',f:'saturate(1.15) hue-rotate(-18deg) brightness(1.06)'},
  {n:'أبيض وأسود',f:'grayscale(1) contrast(1.12)'},{n:'عتيق',f:'sepia(.7) contrast(.95) brightness(.95)'},
  {n:'مشرق',f:'brightness(1.28) saturate(1.25)'},{n:'درامي',f:'contrast(1.4) saturate(.75)'},{n:'وردي',f:'saturate(1.6) hue-rotate(18deg)'}
];
let camStream=null,camFacing='user',camFilterIdx=0,camBeauty=false,recorder=null,recChunks=[],recElapsed=0,recMax=15,recTimerInt=null,cdSecs=0,recordedBlob=null,recordedURL=null,recordedCover='',camRaf=null;
function currentFilter(){const base=FILTERS[camFilterIdx].f;const b=camBeauty?' brightness(1.07) saturate(1.14)':'';return (base==='none'?'':base)+b||'none';}
async function openCamera(){const m=me();if(!m){openAuth();toast('سجل الدخول أولاً للتصوير 🔑');return;}
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){toast('الكاميرا تحتاج اتصالاً آمناً (HTTPS) 📷');return;}
  if(typeof MediaRecorder==='undefined'){toast('التسجيل غير مدعوم على هذا المتصفح ⚠️');return;}
  openModal('cameraModal');camResetUI();renderFilterSheet();refreshSoundSelects();await startCamStream();}
function camResetUI(){recElapsed=0;recordedBlob=null;if(recordedURL)URL.revokeObjectURL(recordedURL);recordedURL=null;
  document.getElementById('camCanvas').style.display='block';document.getElementById('camPreview').style.display='none';
  document.getElementById('camDetails').style.display='none';document.getElementById('camBottom').style.display='block';
  document.getElementById('camRail').style.display='flex';document.getElementById('recProg').style.width='0';
  document.getElementById('recBtn').disabled=false;document.getElementById('recBtn').classList.remove('rec');
  document.getElementById('nextBtn').style.visibility='hidden';updRecTime();}
function updRecTime(){const e=document.getElementById('recTime');if(e)e.textContent=fmtTime(recElapsed)+' / '+fmtTime(recMax);}
function fmtTime(s){s=Math.floor(s);return '00:'+String(s).padStart(2,'0');}
async function startCamStream(){
  const msg=document.getElementById('camMsg');if(msg)msg.textContent='جارِ تشغيل الكاميرا... 📷';
  stopCamStream();
  try{
    camStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:camFacing,width:{ideal:720},height:{ideal:1280}},audio:{echoCancellation:true,noiseSuppression:true}});
    const live=document.getElementById('camLive');live.srcObject=camStream;await live.play().catch(()=>{});
    const cv=document.getElementById('camCanvas');cv.width=540;cv.height=960;
    if(msg)msg.textContent='اختر مؤثراً 🎨 ثم اضغط زر التسجيل 🔴';
    camLoop();
  }catch(e){if(msg)msg.textContent='تعذر الوصول للكاميرا/المايك — امنح الإذن من المتصفح 🔒';toast('فشل تشغيل الكاميرا 🔒');}
}
function stopCamStream(){if(camRaf)cancelAnimationFrame(camRaf);camRaf=null;if(camStream){camStream.getTracks().forEach(t=>t.stop());camStream=null;}}
function camLoop(){const live=document.getElementById('camLive');const cv=document.getElementById('camCanvas');if(!live||!cv)return;
  const ctx=cv.getContext('2d');
  const draw=()=>{if(!camStream){return;}camRaf=requestAnimationFrame(draw);
    if(live.readyState<2)return;ctx.save();ctx.filter=currentFilter();
    const vw=live.videoWidth,vh=live.videoHeight;if(!vw)return;
    const target=540/960, ratio=vw/vh;let sw,sh,sx,sy;
    if(ratio>target){sh=vh;sw=vh*target;sx=(vw-sw)/2;sy=0;}else{sw=vw;sh=vw/target;sx=0;sy=(vh-sh)/2;}
    ctx.drawImage(live,sx,sy,sw,sh,0,0,540,960);ctx.restore();};
  draw();}
function renderFilterSheet(){const el=document.getElementById('camFilters');if(!el||el.children.length)return;
  el.innerHTML=FILTERS.map((f,i)=>`<button class="fx ${i===camFilterIdx?'on':''}" onclick="setCamFilter(${i})"><div class="sw" style="filter:${f.f}"></div>${f.n}</button>`).join('');}
function setCamFilter(i){camFilterIdx=i;document.querySelectorAll('.fx').forEach((b,j)=>b.classList.toggle('on',j===i));}
function toggleFilterSheet(){const el=document.getElementById('camFilters');el.style.display=el.style.display==='none'?'flex':'none';}
function toggleBeauty(){camBeauty=!camBeauty;document.getElementById('beautyBtn').classList.toggle('on',camBeauty);toast(camBeauty?'التجميل مفعّل ✨':'التجميل متوقف');}
async function flipCamera(){camFacing=camFacing==='user'?'environment':'user';if(document.getElementById('cameraModal').classList.contains('open'))await startCamStream();}
function setRecMax(n,btn){if(recorderActive())return;recMax=n;document.querySelectorAll('.cam-durs button').forEach(b=>{if(b.textContent.includes('s'))b.classList.remove('on');});btn.classList.add('on');updRecTime();}
function recActive(){return recorder&&recorder.state==='recording';}
function recPaused(){return recorder&&recorder.state==='paused';}
function recorderActive(){return recActive()||recPaused();}
function cycleCountdown(){cdSecs=cdSecs===0?3:cdSecs===3?10:0;const b=document.getElementById('cdBtn');if(b)b.textContent=cdSecs===0?'⏱ بدون مؤقت':'⏱ '+cdSecs+' ثوانٍ';toast(cdSecs?('المؤقت: '+cdSecs+' ثوانٍ ⏱'):'بدون مؤقت');}
function recToggle(){if(recActive()){pauseRecording();return;}if(recPaused()){resumeRecording();return;}
  if(recordedBlob){toast('لديك تسجيل جاهز — اضغط التالي ✓ أو أعد التصوير');return;}
  if(cdSecs>0){runCountdown(cdSecs,startRecording);}else startRecording();}
function runCountdown(n,cb){const ov=document.getElementById('cdOverlay');ov.style.display='block';let c=n;ov.textContent=c;
  const iv=setInterval(()=>{c--;if(c<=0){clearInterval(iv);ov.style.display='none';cb();}else ov.textContent=c;},1000);}
function pickMime(){const cands=['video/mp4','video/webm;codecs=vp9,opus','video/webm'];for(const c of cands){try{if(MediaRecorder.isTypeSupported(c))return c;}catch(e){}}return '';}
function startRecording(){
  if(!camStream){toast('الكاميرا غير جاهزة');return;}
  try{
    const canvas=document.getElementById('camCanvas');
    const cvs=canvas.captureStream(30);
    const tracks=[...cvs.getVideoTracks(),...camStream.getAudioTracks()];
    const stream=new MediaStream(tracks);
    const mime=pickMime();
    recorder=new MediaRecorder(stream,mime?{mimeType:mime,videoBitsPerSecond:4e6}:undefined);
  }catch(e){toast('تعذر بدء التسجيل ⚠️');return;}
  recChunks=[];recorder.ondataavailable=ev=>{if(ev.data&&ev.data.size)recChunks.push(ev.data);};
  recorder.onstop=finishRecording;
  recorder.start(400);
  document.getElementById('recBtn').classList.add('rec');
  document.getElementById('camMsg').textContent='🔴 جارِ التسجيل... اضغط مجدداً للإيقاف المؤقت';
  recTimerInt=setInterval(()=>{recElapsed+=0.2;updRecTime();document.getElementById('recProg').style.width=(recElapsed/recMax*100)+'%';if(recElapsed>=recMax)stopRecording();},200);
}
function pauseRecording(){if(!recActive())return;recorder.pause();clearInterval(recTimerInt);document.getElementById('recBtn').classList.remove('rec');document.getElementById('camMsg').textContent='⏸ إيقاف مؤقت — اضغط للمتابعة';}
function resumeRecording(){if(!recPaused())return;recorder.resume();document.getElementById('recBtn').classList.add('rec');document.getElementById('camMsg').textContent='🔴 جارِ التسجيل...';recTimerInt=setInterval(()=>{recElapsed+=0.2;updRecTime();document.getElementById('recProg').style.width=(recElapsed/recMax*100)+'%';if(recElapsed>=recMax)stopRecording();},200);}
function stopRecording(){if(!recorderActive())return;try{recorder.stop();}catch(e){}clearInterval(recTimerInt);}
function finishRecording(){
  document.getElementById('recBtn').classList.remove('rec');document.getElementById('recBtn').disabled=true;
  const type=recorder.mimeType||'video/webm';
  recordedBlob=new Blob(recChunks,{type});recChunks=[];
  if(recordedBlob.size<5000){toast('التسجيل قصير جداً — حاول مجدداً');camRetake();return;}
  if(recordedURL)URL.revokeObjectURL(recordedURL);
  recordedURL=URL.createObjectURL(recordedBlob);
  try{const cv=document.getElementById('camCanvas');const cc=document.createElement('canvas');cc.width=270;cc.height=480;cc.getContext('2d').drawImage(cv,0,0,270,480);recordedCover=cc.toDataURL('image/jpeg',0.7);}catch(e){recordedCover='';}
  const pv=document.getElementById('camPreview');pv.src=recordedURL;pv.style.display='block';
  document.getElementById('camCanvas').style.display='none';
  document.getElementById('nextBtn').style.visibility='visible';
  document.getElementById('camMsg').textContent='تم التسجيل ✅ ('+fmtTime(recElapsed)+') — اضغط التالي ✓';
  pv.play().catch(()=>{});
}
function camRetake(){if(recordedURL)URL.revokeObjectURL(recordedURL);recordedURL=null;recordedBlob=null;recElapsed=0;recorder=null;
  camResetUI();const pv=document.getElementById('camPreview');pv.pause();pv.removeAttribute('src');pv.load();}
function camNext(){if(!recordedURL){toast('سجّل أولاً 🎬');return;}
  document.getElementById('camBottom').style.display='none';document.getElementById('camRail').style.display='none';document.getElementById('camFilters').style.display='none';
  const mini=document.getElementById('camPreviewMini');mini.src=recordedURL;mini.play().catch(()=>{});
  document.getElementById('camDetails').style.display='flex';}
function camBackToRec(){document.getElementById('camDetails').style.display='none';document.getElementById('camBottom').style.display='block';document.getElementById('camRail').style.display='flex';}
function publishRecorded(){const m=me();if(!m||!recordedURL)return;
  const title=document.getElementById('camTitle').value.trim()||'فيديو جديد 🎬';
  const tags=(document.getElementById('camTags').value.trim()||'جديد').split(/\s+/).map(s=>s.replace('#','')).filter(Boolean).slice(0,5);
  const snd=resolveSound('camSound');
  DB.videos.unshift({id:'v'+Date.now(),userId:m.id,src:recordedURL,poster:recordedCover,title,desc:title,tags,sound:snd.name,soundId:snd.id,likes:0,views:0,sponsored:0,uniqueViewers:[],shares:0,likedBy:[],savedBy:[],featured:false,pinned:false,hidden:false,allowComments:document.getElementById('camComments').checked,created:Date.now(),comments:[]});
  earnCoins(m,10);save();closeCamera();toast('🎉 تم نشر فيديوك! +10 عملات 🪙');go('feed');renderFeed();renderRail();updateBadges();}
function closeCamera(){if(recorderActive()){try{recorder.stop();}catch(e){}recorder=null;}clearInterval(recTimerInt);stopCamStream();closeModal('cameraModal');}

/* ---------- utils ---------- */
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function timeAgo(t){const s=Math.floor((Date.now()-t)/1000);if(s<60)return 'الآن';const m=Math.floor(s/60);if(m<60)return 'منذ '+m+' د';const h=Math.floor(m/60);if(h<24)return 'منذ '+h+' س';const d=Math.floor(h/24);if(d<30)return 'منذ '+d+' يوم';return 'منذ '+Math.floor(d/30)+' شهر';}
function fmt(n){n=n||0;if(n>=1e6)return (n/1e6).toFixed(1)+'M';if(n>=1e3)return (n/1e3).toFixed(1)+'K';return ''+n;}
function toast(t){const e=document.getElementById('toast');e.textContent=t;e.classList.add('show');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('show'),2500);}
document.querySelectorAll('.modal').forEach(m=>m.addEventListener('click',e=>{if(e.target===m){if(m.id==='cameraModal')closeCamera();else if(m.id==='liveModal')closeLiveRoom();else m.classList.remove('open');}}));

/* init */
renderRail();renderSuggestions();renderFeed();renderDiscover();
applySoundUI();updateBadges();
if(me())afterLogin();
