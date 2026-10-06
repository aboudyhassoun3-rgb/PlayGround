/* ===== Auth: حسابات محلية + حفظ لكل حساب ===== */
window.ADMIN_EMAIL = "aboudyhassoun3@gmail.com";
window.Auth = {
  USERS_KEY: "judge_city_users_v1",
  SESSION_KEY: "judge_city_session_v1",
  users(){ try{return JSON.parse(localStorage.getItem(this.USERS_KEY)||"{}")}catch(e){return {}} },
  saveUsers(u){ localStorage.setItem(this.USERS_KEY, JSON.stringify(u)); },
  session(){ return (localStorage.getItem(this.SESSION_KEY)||"").toLowerCase(); },
  setSession(e){ if(e)localStorage.setItem(this.SESSION_KEY,e.toLowerCase()); else localStorage.removeItem(this.SESSION_KEY); },
  current(){ const e=this.session(); if(!e)return null; const u=this.users()[e]; return u?{...u}:null; },
  isAdmin(){ return this.session()===window.ADMIN_EMAIL.toLowerCase(); },
  saveKey(){ const e=this.session()||"guest"; return window.GAME_CONFIG.SAVE_KEY+"::"+e; },
  async sha(s){
    try{
      const b=await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
      return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("");
    }catch(e){ let h=0; for(let i=0;i<s.length;i++){h=(h*31+s.charCodeAt(i))|0;} return "h"+Math.abs(h); }
  },
  validEmail(e){ return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e); },
  async signup(name,email,pass){
    email=email.trim().toLowerCase(); name=name.trim();
    if(name.length<2) throw new Error("اكتب اسمك");
    if(!this.validEmail(email)) throw new Error("البريد غير صحيح");
    if((pass||"").length<4) throw new Error("كلمة السر 4 أحرف على الأقل");
    const u=this.users();
    if(u[email]) throw new Error("هذا البريد مسجل — سجل الدخول");
    const salt=Math.random().toString(36).slice(2);
    u[email]={name,email,salt,hash:await this.sha(salt+"::"+pass),created:Date.now()};
    this.saveUsers(u); this.setSession(email); return u[email];
  },
  async login(email,pass){
    email=email.trim().toLowerCase();
    const u=this.users()[email];
    if(!u) throw new Error("لا يوجد حساب بهذا البريد — أنشئ حساباً");
    const h=await this.sha(u.salt+"::"+pass);
    if(h!==u.hash) throw new Error("كلمة السر خطأ");
    this.setSession(email); return u;
  },
  logout(){ this.setSession(null); location.reload(); },
  list(){ return Object.values(this.users()); },
  remove(email){ const u=this.users(); delete u[email.toLowerCase()]; this.saveUsers(u); localStorage.removeItem(window.GAME_CONFIG.SAVE_KEY+"::"+email.toLowerCase()); },
  async setPass(email,pass){ const u=this.users(); const k=email.toLowerCase(); if(!u[k])return; u[k].salt=Math.random().toString(36).slice(2); u[k].hash=await this.sha(u[k].salt+"::"+pass); this.saveUsers(u); }
};
