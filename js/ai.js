/* ===== AI engine: OpenAI-compatible + local fallback ===== */
window.AI = {
  async chat({system, user, context="", maxTokens=450}) {
    const cfg = window.GAME_CONFIG;
    const url = (localStorage.getItem("ai_url")||cfg.AI_URL).trim();
    const key = (localStorage.getItem("ai_key")||cfg.AI_KEY).trim();
    let model = (localStorage.getItem("ai_model")||cfg.AI_MODEL).trim()||"gpt-5-mini";
    if(model==="auto") model="gpt-5-mini"; // المفتاح الحالي يدعم gpt-5-mini فقط
    const payload = (m)=>JSON.stringify({model:m, messages:[
          {role:"system",content:system+"\n\nقواعد صارمة: لا تكشف الحقيقة القاطعة أبداً. لا تقل 'الفاعل هو فلان'. استخدم درجات ثقة ومصادر. كن واقعياً وقاسياً أحياناً. الشهود قد يكذبون. ردود قصيرة (3-8 أسطر). بالعربية."+(context?"\n\nسياق القضية:\n"+context.slice(0,3500):"")},
          {role:"user",content:user}
        ], temperature:0.85, max_tokens:maxTokens});
    const post = async (m)=>{
      const ctrl = new AbortController();
      const t = setTimeout(()=>ctrl.abort(), 25000);
      try{
        const res = await fetch(url, {method:"POST", signal:ctrl.signal,
          headers:{"Content-Type":"application/json","Authorization":"Bearer "+key}, body: payload(m)});
        clearTimeout(t);
        if(!res.ok){ const txt=await res.text().catch(()=>""); throw new Error("HTTP "+res.status+" "+txt.slice(0,200)); }
        const j = await res.json();
        const txt = (j && j.choices && j.choices[0] && (j.choices[0].message?.content || j.choices[0].text)) || j?.content || j?.reply || "";
        if(txt && String(txt).trim().length>3) return {text:String(txt).trim().slice(0,2500), via:"ai"};
        throw new Error("empty");
      }catch(e){ clearTimeout(t); throw e; }
    };
    try {
      try{ return await post(model); }
      catch(e1){ if(model!=="gpt-5-mini") return await post("gpt-5-mini"); throw e1; }
    } catch(e){ return {text: window.AI.localFallback(system,user,context), via:"local"}; }
  },
  /* مولد محلي حسب الشخصية: لا يعطي الحقيقة أبداً */
  localFallback(system, user, context){
    const u = (user||"").slice(0,200);
    const sys = (system||"");
    if(sys.includes("مشتبه به")){
      const t = [
        `أنا؟ كنت… كنت بالبيت تلك الليلة، اسأل جيراني! (يفرك يديه بتوتر)\nلا أعرف شيئاً عن السيارة التي تتحدث عنها. نعم أعرف ${"بعض"} الشباب بالحي لكن علاقتي بهم سطحية.\nلماذا تتهمني أنا بالذات؟ هناك عشرات غيري!`,
        `(ببرود) محامي قال لي لا أجيب إلا بوجوده… لكن سأقول: خرجت من الورشة المغرب ولم أعد. هاتفي؟ كان مطفأً، الشحن كان فارغاً.\nالتحويل المالي الذي تذكره؟ دين قديم من صديق، لا علاقة له بأي شيء.`,
        `(بغضب مكتوم) هذه ثالث مرة تسألني نفس السؤال! كنت مع أخي، اسأله بنفسك.\nالبصمة؟ طبيعي… أنا أتردد على ذلك المكان كل يوم بحكم شغلي. هذا لا يعني شيئاً.`,
        `(بخوف واضح)… حسناً، سأكون صريحاً بشيء واحد فقط: رأيت شخصاً غريباً قرب الموقع تلك الليلة، لكنني خفت أن أتكلم حتى لا يظنوا أنني متورط.\nأخاف على عائلتي، هل تضمنون حمايتي إن تكلمت؟`
      ];
      return t[Math.floor(Math.random()*t.length)];
    }
    if(sys.includes("شاهد")){
      const t = [
        `يا سيدي أنا لم أرَ شيئاً بوضوح… كان الظلام… سيارة داكنة فقط، ولم أحفظ الرقم. أرجوك لا تكتب اسمي في المحضر، أخاف على أولادي.`,
        `سمعت صوت شجار ثم صوت محرك… الرجل الطويل كان يصرخ باسم… لا، نسيت. (ينظر للأرض) لا أريد مشاكل مع أحد، انسَ أنني قلت شيئاً.`,
        `الذي رأيته… (يتلعثم) كان يشبه أحد الشباب من الحارة، لكنني لست متأكداً. بيني وبين عائلته خلاف قديم ولا أريد أن يقال إنني لفقت له التهمة.`,
        `سأقول الحقيقة لكن بشرط الحماية: جاءتني رسالة تهديد بعد أول مرة تكلمت فيها. الشخص الذي رأيته يدفع مالاً لمن يسكت. احموني وسأشهد بكل شيء.`
      ];
      return t[Math.floor(Math.random()*t.length)];
    }
    if(sys.includes("محامي")){
      return `بصفتي دفاعاً عن موكلي أعترض: الدليل المقدم ظرفي ومنقوص — بصمة دون سياق، وشاهد واحد متردد وخائف.\nأطالب بـ: 1) استبعاد أي دليل غير محلل مخبرياً 2) مواجهة الشهود 3) الإفراج بكفالة لعدم كفاية الأدلة.\nموكلي بريء حتى تثبت الإدانة بدليلين مستقلين على الأقل.`;
    }
    const templates = [
      `وصلني طلبك: "${u}".\n• مصدر (موثوق 70%): رصدنا حركة مشبوهة تحتاج تأكيداً ميدانياً.\n• مصدر (متوسط 45%): شاهد يتحدث عن سيارة داكنة قرب الموقع، لكنه متردد وخائف.\n• مصدر (ضعيف 25%): معلومة غير مؤكدة عن تحويل مالي صغير.\nتوصيتي: لا تتحرك بقوة الآن. وسّع المراقبة 48 ساعة واطلب تحليل البصمات والاتصالات قبل أي توقيف. اليقين يحتاج دليلين مستقلين على الأقل.`,
      `حسب السياق المتاح:\n1) الدليل الحالي ظرفي وليس قاطعاً — بصمة أو رقم هاتف وحده لا يدين.\n2) هناك احتمال تضليل متعمد (شاهد مدفوع أو كاميرا معطلة).\n3) أقترح: استدعاء هادئ لشخصين للمقارنة، + تتبع مالي، + مراجعة سجل القضايا القديمة لعلها مرتبطة.\nلا أستطيع الجزم. القرار لك، لكن التسرع قد يصنع خطأً قضائياً.`,
      `تحديث ميداني:\n— المراقبة مستمرة على الحي، لا تحرك قبل أمرك.\n— نحتاج موارد: ${Math.floor(Math.random()*8)+3} عناصر إضافية وسيارة.\n— إذا ضغطنا الآن قد يهرب المشتبه أو تُتلف الأدلة.\nأرسل الأمر: (استمرار مراقبة / استدعاء / مداهمة) مع تحديد القوة، وسأنفذ فوراً.`,
      `من زاوية التحقيق النفسي:\nالمشتبه يتوتر عند سؤاله عن الليلة المحددة، لكن التوتر ليس دليلاً.\nالشاهد الثاني يحمي شخصاً على الأرجح (قريب/مصلحة).\nاقتراحي: مواجهة غير مباشرة بالأدلة المتسلسلة (بصمة → سيارة → هاتف → تحويل) بدل الاتهام المباشر، وراقب من يتصل بمن بعد الاستجواب.`
    ];
    return templates[Math.floor(Math.random()*templates.length)];
  }
};
