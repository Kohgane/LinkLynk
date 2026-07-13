// LinkLynk 프론트 로직

// ── PWA: 캐시 문제 원천 차단 (서비스워커 제거 + 캐시 삭제) ──
let deferredPrompt = null;
if('serviceWorker' in navigator){
  // 기존 서비스워커 전부 제거 (캐시로 옛 코드 물리는 문제 해결)
  navigator.serviceWorker.getRegistrations().then(regs=>{
    regs.forEach(r=>r.unregister());
  }).catch(()=>{});
  // 모든 캐시 삭제
  if(window.caches){
    caches.keys().then(ks=>ks.forEach(k=>caches.delete(k))).catch(()=>{});
  }
}
window.addEventListener('beforeinstallprompt', (e)=>{
  e.preventDefault(); deferredPrompt = e;
  showInstallBtn();
});
function showInstallBtn(){
  if(document.getElementById('installBar')) return;
  const bar = document.createElement('div');
  bar.id='installBar';
  bar.style.cssText='position:fixed;bottom:92px;left:50%;transform:translateX(-50%);width:calc(100% - 40px);max-width:440px;background:var(--mint);color:var(--mint-ink);padding:13px 16px;border-radius:14px;font-weight:700;font-size:14px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 8px 32px rgba(255,255,255,.10);z-index:60;animation:pageIn .4s';
  bar.innerHTML='<span>📲 홈 화면에 앱으로 추가하기</span><span style="font-size:12px;opacity:.7">탭</span>';
  bar.onclick=async()=>{
    if(deferredPrompt){ deferredPrompt.prompt(); await deferredPrompt.userChoice; deferredPrompt=null; bar.remove(); }
  };
  document.body.appendChild(bar);
}
window.addEventListener('appinstalled', ()=>{ const b=document.getElementById('installBar'); if(b) b.remove(); });


let channel = "blog";
let mode = "auto"; // auto | manual
let authMode = "login"; // login | signup
let recent = [];

// ── 부팅: 로그인 상태 확인 ──
// ── 자동 임시저장: 앱을 나가거나 백그라운드로 가면 작성 중 초안을 앱 DB에 저장 ──
let __autoSavedHash = null;
function setupAutoSave(){
  const doAutoSave = () => {
    const d = window.__lastResult;
    if(!d || !d.blogDraft) return;
    const hash = (d.channel||'') + '|' + (d.blogDraft||'').slice(0,100);
    if(hash === __autoSavedHash) return;
    __autoSavedHash = hash;
    const payload = JSON.stringify({
      channel: d.channel || channel || 'blog',
      content: d.blogDraft,
      productName: d.productName || '',
      deeplink: d.deeplink || '',
      image: d.image || null,
      auto: true
    });
    try{
      const blob = new Blob([payload], {type:'application/json'});
      navigator.sendBeacon('/api/save-draft', blob);
    }catch(e){
      fetch('/api/save-draft',{method:'POST',headers:{'Content-Type':'application/json'},body:payload,keepalive:true}).catch(()=>{});
    }
  };
  document.addEventListener('visibilitychange', ()=>{ if(document.visibilityState==='hidden') doAutoSave(); });
  window.addEventListener('pagehide', doAutoSave);
  window.addEventListener('beforeunload', doAutoSave);
}

async function boot(){
  // ── 앱 나가면 작성 중이던 초안 자동 임시저장 (앱 내부 DB에만) ──
  setupAutoSave();
  // 북마클릿에서 넘어온 쿠팡 이미지 처리
  const params = new URLSearchParams(location.search);
  const bmkData = params.get('bmk');
  if(bmkData){
    try{
      const parsed = JSON.parse(decodeURIComponent(bmkData));
      window.__bmkImages = parsed;
      // URL 정리
      history.replaceState(null,'',location.pathname);
    }catch(e){}
  }
  try{
    const r = await fetch('/api/me');
    const d = await r.json();
    if(d.ok){ showApp(d); }
    else { showAuth(); }
  }catch(e){ showAuth(); }
}

// 소셜 로그인 버튼 (설정된 제공자만 표시)
async function renderSocialLogin(){
  const box = document.getElementById('socialLogin');
  if(!box) return;
  let status = {};
  try{ status = await (await fetch('/api/oauth-status')).json(); }catch(e){ return; }
  const providers = [
    {id:'google', label:'Google로 계속하기', bg:'#fff', color:'#222', border:'1px solid #dadce0', icon:'G'},
    {id:'kakao', label:'카카오로 계속하기', bg:'#FEE500', color:'#000', border:'none', icon:'K'},
    {id:'naver', label:'네이버로 계속하기', bg:'#03C75A', color:'#fff', border:'none', icon:'N'},
  ];
  const avail = providers.filter(p=>status[p.id]);
  if(!avail.length){ box.innerHTML=''; return; }
  box.innerHTML = `<div style="display:flex;align-items:center;gap:10px;margin:14px 0;color:var(--muted);font-size:12px">
      <div style="flex:1;height:1px;background:var(--line)"></div>또는<div style="flex:1;height:1px;background:var(--line)"></div>
    </div>` +
    avail.map(p=>`<a href="/auth/${p.id}/login" class="social-btn" style="display:flex;align-items:center;justify-content:center;gap:10px;background:${p.bg};color:${p.color};border:${p.border};border-radius:10px;padding:12px;margin-bottom:8px;font-weight:600;font-size:14px;text-decoration:none">
      <span style="width:20px;height:20px;border-radius:4px;display:grid;place-items:center;font-weight:800;font-size:13px">${p.icon}</span>
      ${p.label}
    </a>`).join('');
}

function showAuth(){
  document.getElementById('authView').classList.remove('hidden');
  document.getElementById('appView').classList.add('hidden');
  renderSocialLogin();
  // 로그인 에러 표시
  const perr = new URLSearchParams(location.search).get('login_error');
  if(perr){ toast('소셜 로그인 실패: '+perr); history.replaceState(null,'',location.pathname); }
  // 저장된 이메일 자동 입력
  try{
    const saved = localStorage.getItem('ll_email');
    if(saved){ const el=document.getElementById('a_email'); if(el && !el.value) el.value = saved; }
  }catch(e){}
}
function showApp(me){
  document.getElementById('authView').classList.add('hidden');
  document.getElementById('appView').classList.remove('hidden');
  // 아바타
  const initial = (me.handle || me.email || '?')[0].toUpperCase();
  const av=document.getElementById('avatar'); if(av) av.textContent = initial;
  // 프로필 주소
  const base = location.origin;
  document.getElementById('profileUrl').textContent = me.handle ? `${base}/u/${me.handle}` : '프로필 주소 미설정';
  window.__me = me;
  renderUsage(me);
  renderKeyStatus(me);
  if(me.has_sns) loadSnsAccounts();
  renderLlmPicker();
  loadRadar();
  // 북마클릿으로 가져온 쿠팡 이미지가 있으면 표시
  if(window.__bmkImages && window.__bmkImages.images){
    setTimeout(()=>showBmkImages(window.__bmkImages), 400);
  }
}
// 북마클릿으로 가져온 쿠팡 상세 이미지 갤러리
function showBmkImages(data){
  go('make');
  const result = document.getElementById('result');
  if(!result) return;
  const imgs = data.images || [];
  result.innerHTML = `<div class="card">
    <div class="card-lbl">📸 가져온 쿠팡 이미지 ${imgs.length}개 ${data.productName?'· '+esc(data.productName):''}</div>
    <div style="font-size:12px;color:var(--text-2);margin:6px 0 12px">길게 눌러 저장하거나, 블로그 초안에 넣을 수 있어요.</div>
    <div class="bmk-grid">${imgs.map(u=>`<img src="${u}" loading="lazy" onclick="window.open('${u}','_blank')">`).join('')}</div>
  </div>`;
  result.scrollIntoView({behavior:'smooth',block:'start'});
  window.__bmkImages = null;
}

// ── 인증 ──
function toggleAuth(){
  authMode = authMode === "login" ? "signup" : "login";
  const isSignup = authMode === "signup";
  document.getElementById('authTitle').textContent = isSignup ? "회원가입" : "로그인";
  document.getElementById('handleField').style.display = isSignup ? "block" : "none";
  document.querySelector('#authBtn .lbl').textContent = isSignup ? "가입하고 시작하기" : "로그인";
  document.getElementById('authSwitch').innerHTML = isSignup
    ? `이미 계정이 있으신가요? <a onclick="toggleAuth()">로그인</a>`
    : `계정이 없으신가요? <a onclick="toggleAuth()">회원가입</a>`;
  document.getElementById('authMsg').innerHTML = "";
}

async function doAuth(){
  const email = document.getElementById('a_email').value.trim();
  const pw = document.getElementById('a_pw').value;
  const handle = document.getElementById('a_handle').value.trim();
  const btn = document.getElementById('authBtn');
  const msg = document.getElementById('authMsg');
  msg.innerHTML = "";
  if(!email || !pw){ msg.innerHTML = `<div class="msg msg-err">이메일과 비밀번호를 입력하세요</div>`; return; }
  btn.classList.add('loading');
  try{
    const endpoint = authMode === "signup" ? '/api/signup' : '/api/login';
    const body = authMode === "signup" ? {email, password:pw, handle} : {email, password:pw};
    const r = await fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json();
    if(!d.ok){ msg.innerHTML = `<div class="msg msg-err">${d.error||'실패했어요'}</div>`; return; }
    // 이메일 기억 (다음 로그인 자동입력)
    try{ localStorage.setItem('ll_email', email); }catch(e){}
    // 성공 → me 다시 불러서 앱 진입
    const me = await (await fetch('/api/me')).json();
    showApp(me);
  }catch(e){
    msg.innerHTML = `<div class="msg msg-err">서버 연결 실패. 잠시 후 다시</div>`;
  }finally{
    btn.classList.remove('loading');
  }
}

async function logout(){
  await fetch('/api/logout', {method:'POST'});
  location.reload();
}

// ── 탭 전환 ──
function go(page){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('on'));
  document.getElementById('page-'+page).classList.add('on');
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on', t.dataset.p===page));
  // 나이아가라 레일은 프로필에서만
  const railEl = document.getElementById('nia-rail-fixed');
  if(railEl) railEl.style.display = (page==='profile') ? 'block' : 'none';
  if(page==='profile') loadProfile();
  if(page==='stats'){ refreshMe(); loadStats(); loadPosts('all'); }
  else if(page==='settings'){ refreshMe(); loadSnsAccounts(); }
}
async function refreshMe(){
  try{ const me = await (await fetch('/api/me')).json(); if(me.ok){ window.__me=me; renderUsage(me); renderKeyStatus(me); renderHandle(me); renderSns(me); renderClaude(me);} }catch(e){}
}

function renderHandle(me){
  const cur = document.getElementById('handleCurrent');
  const inp = document.getElementById('s_handle');
  if(!cur) return;
  if(me.handle){
    cur.innerHTML = `현재 주소: <b style="color:var(--mint)">linklynk.onrender.com/u/${me.handle}</b>`;
    if(inp) inp.value = me.handle;
  } else {
    cur.textContent = '아직 주소를 정하지 않았어요';
  }
}

async function saveHandle(){
  const handle = (document.getElementById('s_handle').value || '').trim().toLowerCase();
  const btn = document.getElementById('handleBtn');
  const msg = document.getElementById('handleMsg');
  msg.innerHTML = '';
  if(!handle){ msg.innerHTML = '<div class="msg msg-err">주소를 입력하세요</div>'; return; }
  btn.classList.add('loading');
  try{
    const r = await fetch('/api/handle', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({handle})});
    const d = await r.json();
    if(d.ok){
      msg.innerHTML = '<div class="msg msg-ok">저장됐어요! ✨</div>';
      if(window.__me) window.__me.handle = d.handle;
      renderHandle(window.__me || {handle:d.handle});
    } else {
      msg.innerHTML = `<div class="msg msg-err">${d.error||'저장 실패'}</div>`;
    }
  }catch(e){ msg.innerHTML = '<div class="msg msg-err">네트워크 오류</div>'; }
  btn.classList.remove('loading');
}

// ── 링크 생성 ──
function setMode(el){
  document.querySelectorAll('.mode').forEach(m=>m.classList.remove('on'));
  el.classList.add('on'); mode = el.dataset.mode;
  const pasteBox = document.getElementById('pasteBox');
  const searchBox = document.getElementById('searchBox');
  const topicBox = document.getElementById('topicBox');
  [pasteBox,searchBox,topicBox].forEach(b=>b&&b.classList.add('hidden'));
  if(mode==='search'){ if(searchBox) searchBox.classList.remove('hidden'); return; }
  if(mode==='topic'){ if(topicBox){ topicBox.classList.remove('hidden'); loadRadar(); } return; }
  if(pasteBox) pasteBox.classList.remove('hidden');
  const ta = document.getElementById('url');
  if(mode==='manual'){
    ta.placeholder = "이미 만든 파트너스 링크 붙여넣기\n예: link.coupang.com/a/...";
    document.querySelector('#go .lbl').textContent = "블로그 글 만들기";
  }else{
    ta.placeholder = "쿠팡 상품 페이지 주소 붙여넣기\n예: coupang.com/vp/products/...";
    document.querySelector('#go .lbl').textContent = "내 간편 링크 만들기";
  }
}

function setCh(el){
  el.closest('.chips').querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on'); channel = el.dataset.ch;
  // 이미 만든 초안이 있으면, 새 채널 형식으로 즉시 다시 생성
  const d = window.__lastResult;
  if(d && d.deeplink){
    regenForChannel(d.deeplink, d.productName || '');
  }
}
// 같은 링크로 현재 채널 형식의 글을 다시 생성 (딥링크 있으니 검색 안 함)
// 현재 고른 채널·말투·AI로 글 만들기
function writeWithSettings(){
  const d = window.__lastResult;
  if(!d || !d.deeplink){ toast('먼저 링크를 만들어주세요'); return; }
  regenForChannel(d.deeplink, d.productName || '');
}

async function regenForChannel(deeplink, pname){
  const result = document.getElementById('result');
  if(result) result.innerHTML = '<div class="card"><div style="text-align:center;padding:22px;color:var(--muted)">✍️ 글 쓰는 중…<br><span style="font-size:12px">다른 화면 가도 계속 진행돼요</span></div></div>';
  const jobId = 'gen-' + Date.now();
  const p = fetch('/api/generate-manual',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({deeplink, channel, tone:(window.curTone||'friendly'), productName:pname, provider:(window.__llmPick||null), extra:(document.getElementById('w_extra')?.value||'')})})
    .then(r=>r.json())
    .then(d=>{ if(!d.ok) throw new Error('생성 실패'); return {draft: d}; });
  startJob(jobId, '글 작성', p, (res)=>{
    const page = document.getElementById('page-make');
    if(page && !page.classList.contains('hidden')){
      window.__jobs[jobId].seen = true;
      renderResult(res.draft);
    }
  });
}
function setTone(el){
  const container = el.closest('.tone-scroll') || el.closest('.chips');
  if(container) container.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on'); window.curTone = el.dataset.tone;
  // 이미 만든 초안이 있으면 새 말투로 다시 생성
  const d = window.__lastResult;
  if(d && d.deeplink){
    regenForChannel(d.deeplink, d.productName || '');
  }
}
async function pasteUrl(){
  try{ const t = await navigator.clipboard.readText(); if(t) document.getElementById('url').value = t.trim(); }
  catch(e){ document.getElementById('url').focus(); }
}
// 파트너스 키 없을 때 안내 → 직접 붙여넣기 모드로 유도
function showKeyPrompt(){
  const el = document.getElementById('keyPrompt');
  if(el){ el.style.display='block'; el.scrollIntoView({behavior:'smooth', block:'center'}); return; }
  const box = document.createElement('div');
  box.id = 'keyPrompt';
  box.className = 'key-prompt';
  box.innerHTML = `
    <div class="kp-title">🔑 내 쿠팡 파트너스 키가 필요해요</div>
    <div class="kp-body">간편링크 자동생성으로 <b>내 수익</b>이 되려면 내 파트너스 키가 있어야 해요.<br>
    아직 승인 전이라면, 쿠팡에서 만든 링크를 <b>직접 붙여넣기</b>로 넣으면 블로그 글·프로필은 그대로 만들어져요.</div>
    <div class="kp-btns">
      <button class="btn btn-mint" onclick="go('settings');document.getElementById('keyPrompt').style.display='none'">설정에서 키 등록</button>
      <button class="btn btn-ghost" onclick="switchToManual()">링크 직접 붙여넣기</button>
    </div>`;
  const anchor = document.querySelector('#page-make .pastebox');
  if(anchor && anchor.parentNode) anchor.parentNode.insertBefore(box, anchor.nextSibling);
  box.scrollIntoView({behavior:'smooth', block:'center'});
}
function switchToManual(){
  const kp=document.getElementById('keyPrompt'); if(kp) kp.style.display='none';
  // 직접 붙여넣기 탭으로 전환
  const manualTab=document.querySelector('.mode[data-mode="manual"]');
  if(manualTab) manualTab.click();
  toast('쿠팡에서 만든 링크를 붙여넣어 주세요');
}

async function generate(){
  const url = document.getElementById('url').value.trim();
  const pname = (document.getElementById('pname')?.value || '').trim() || '쿠팡 상품';
  const go = document.getElementById('go');
  if(!url){ toast('링크를 먼저 붙여넣어 주세요'); return; }
  if(!/coupang/.test(url)){ toast('쿠팡 링크가 맞는지 확인해주세요'); return; }

  go.classList.add('loading');
  try{
    // 수동 모드(직접 붙여넣기)만 manual, 나머지는 auto (단축링크는 서버가 자동으로 펼쳐서 변환)
    const endpoint = mode === 'manual' ? '/api/generate-manual' : '/api/generate';
    const body = mode === 'manual'
      ? {deeplink:url, channel, tone:(window.curTone||'friendly'), productName:pname, skip_draft:true}
      : {url, channel, tone:(window.curTone||'friendly'), productName:pname, skip_draft:true};
    const r = await fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json();
    if(!d.ok){
      if(d.need_key){
        // 본인 파트너스 키 없음 → 안내 + 직접 붙여넣기 모드로 전환
        showKeyPrompt();
        return;
      }
      toast(d.error||'변환 실패'); if(d.need_login) showAuth(); return;
    }
    d.productName = pname;
    renderResult(d); addRecent(d);
    document.getElementById('url').value=''; const pn=document.getElementById('pname'); if(pn) pn.value='';
  }catch(e){ toast('서버 연결 실패'); }
  finally{ go.classList.remove('loading'); }
}
// 상품 검색 → 인기 상품 링크 자동 생성
async function doSearch(){
  const kw = (document.getElementById('searchKw').value||'').trim();
  const btn = document.getElementById('searchGo');
  if(kw.length<2){ toast('검색어를 2자 이상 입력하세요'); return; }
  btn.classList.add('loading');
  const result = document.getElementById('result');
  if(result) result.innerHTML = `<div class="card"><div class="radar-loading"><span class="spin-sm"></span><span>"${esc(kw)}" 상품 찾는 중…</span></div>
    <div class="prod-grid">${[1,2,3].map(()=>`<div class="prod-card skel"><div class="sk-line" style="width:100%;aspect-ratio:1;height:auto;border-radius:9px"></div><div class="sk-line" style="width:90%;margin-top:8px"></div><div class="sk-line" style="width:60%;margin-top:6px"></div></div>`).join('')}</div></div>`;
  try{
    const r = await fetch('/api/search-product',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword:kw})});
    const d = await r.json();
    if(d.ok){
      const priceTxt = d.price ? ` · ${Number(d.price).toLocaleString()}원` : '';
      const prods = d.products && d.products.length ? d.products : [{name:d.product_name, price:d.price, image:d.image, deeplink:d.deeplink, url:d.deeplink}];
      window.__searchProducts = prods;
      document.getElementById('result').innerHTML = `
        <div class="result">
          ${window.__lastTopics?`<button class="btn btn-ghost" style="margin-bottom:10px" onclick="backToTopics()">← 주제 목록으로 돌아가기</button>`:''}
          <div class="card">
            <div style="font-size:10px;font-weight:700;letter-spacing:.16em;color:var(--muted);margin-bottom:4px">PRODUCT SEARCH</div>
            <div style="font-size:17px;font-weight:600;color:var(--text);margin-bottom:12px">"${esc(kw)}" 검색 결과${d.cached?' (저장됨)':''}</div>
            <div class="prod-grid">
              ${prods.map((p,i)=>`
                <div class="prod-card">
                  <div class="prod-thumb">
                    ${p.image?`<img src="/img-proxy?u=${encodeURIComponent(p.image)}" loading="lazy" alt="">`:''}
                    ${p.isRocket?'<span class="prod-badge">로켓</span>':''}
                  </div>
                  <div class="prod-name">${esc(p.name||'')}</div>
                  <div class="prod-price">${p.price?Number(p.price).toLocaleString()+'원':''}</div>
                  <button class="pbtn" onclick="window.open('${p.deeplink}','_blank')">상품 보기</button>
                  <button class="pbtn" onclick="showResearch(${i},this)">특징 확인</button>
                  <button class="pbtn" onclick="copyText('${p.deeplink}', this)">파트너스 링크 복사</button>
                  <button class="pbtn pbtn-primary" onclick="pickProduct(${i})">이 상품으로 글쓰기</button>
                </div>`).join('')}
            </div>
          </div>
          <div id="imgResults"></div>
        </div>`;
    }
    else if(d.need_key){ toast('설정에서 파트너스 키를 먼저 등록하세요'); go('settings'); }
    else if(d.rate_limited){ toast(d.error); }
    else { toast(d.error||'검색 실패'); }
  }catch(e){ toast('검색 실패 — 네트워크 확인'); }
  btn.classList.remove('loading');
}
// 상품 이미지 검색 (쿠팡 크롤 없이 무료 이미지 검색)
async function findImages(keyword){
  const box = document.getElementById('imgResults');
  if(!box) return;
  box.innerHTML = '<div style="text-align:center;padding:20px;color:var(--muted);font-size:13px">🖼 이미지 찾는 중…</div>';
  try{
    const r = await fetch('/api/search-images',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword})});
    const d = await r.json();
    if(d.ok && d.images && d.images.length){
      window.__foundImages = d.images;
      box.innerHTML = `<div class="card" style="margin-top:12px">
        <div class="card-lbl">🖼 "${esc(keyword)}" 이미지 ${d.images.length}개</div>
        <div style="font-size:12px;color:var(--text-2);margin:4px 0 12px">탭해서 글에 넣을 이미지를 고르세요.</div>
        <div class="bmk-grid">${d.images.map((im,i)=>`<img src="/img-proxy?u=${encodeURIComponent(im.image)}" loading="lazy" onclick="pickImage(${i},this)" style="cursor:pointer">`).join('')}</div>
      </div>`;
    } else { box.innerHTML = '<div style="text-align:center;padding:16px;color:var(--muted);font-size:13px">이미지를 찾지 못했어요</div>'; }
  }catch(e){ box.innerHTML = '<div style="text-align:center;padding:16px;color:var(--muted);font-size:13px">이미지 검색 실패</div>'; }
}
// 이미지 선택 → 현재 초안에 넣기
function pickImage(idx, el){
  const im = (window.__foundImages||[])[idx];
  if(!im) return;
  // 선택 표시
  document.querySelectorAll('#imgResults img').forEach(i=>i.style.outline='');
  el.style.outline = '3px solid var(--mint)';
  window.__pickedImage = im.image;
  // 현재 결과(초안)가 있으면 이미지 교체
  if(window.__lastResult){ window.__lastResult.image = im.image; }
  toast('이미지 선택됨 — 글 만들 때 들어가요 🖼');
}

async function doSearchImagesOnly(){}

// 특징 확인 → 검색 리서치 블록 (이미지: NAVER SEARCH RESEARCH)
async function showResearch(i, btn){
  const p = (window.__searchProducts||[])[i];
  if(!p) return;
  const box = document.getElementById('imgResults');
  if(!box) return;
  const o = btn.textContent; btn.disabled = true; btn.innerHTML = '<span class="spin-sm"></span>';
  box.innerHTML = `<div class="card">
    <div class="radar-loading"><span class="spin-sm"></span><span>검색 결과 분석 중…</span></div>
    ${[1,2,3].map(()=>`<div class="rs-row skel"><div class="sk-line" style="width:92%"></div><div class="sk-line" style="width:70%;margin-top:8px"></div></div>`).join('')}
  </div>`;
  try{
    const d = await (await fetch('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({productName: p.name})})).json();
    const items = d.items || [];
    box.innerHTML = `<div class="card">
      <div style="font-size:9.5px;font-weight:700;letter-spacing:.18em;color:var(--muted);margin-bottom:8px">SEARCH RESEARCH</div>
      <div class="rs-name">${esc(p.name||'')}</div>
      <div class="rs-price">${p.price?Number(p.price).toLocaleString()+'원부터':''}</div>
      <div class="rs-tags">
        <a class="rs-link" href="https://search.naver.com/search.naver?query=${encodeURIComponent(p.name||'')}" target="_blank">네이버 상품 보기 ↗</a>
      </div>
      <div class="rs-h">검색 결과에서 확인할 특징 후보</div>
      <div class="rs-sub">글로 요약해 출처와 링크로 표시됩니다.</div>
      ${items.length ? items.map((it,n)=>`
        <div class="rs-row">
          <span class="rs-num">${String(n+1).padStart(2,'0')}</span>
          <div style="flex:1;min-width:0">
            <div class="rs-snip">${esc(it.snippet||'')}</div>
            <a class="rs-src" href="${it.url}" target="_blank">${esc((it.title||'').slice(0,34))}… ↗</a>
          </div>
        </div>`).join('') : '<div class="radar-empty">검색 결과를 못 가져왔어요</div>'}
    </div>`;
    box.scrollIntoView({behavior:'smooth', block:'start'});
  }catch(e){ box.innerHTML = '<div class="card"><div class="radar-empty">분석 실패</div></div>'; }
  btn.disabled = false; btn.textContent = o;
}

// 상품 카드 선택 → 그 상품으로 링크·글 준비
function pickProduct(i){
  const p = (window.__searchProducts||[])[i];
  if(!p) return;
  window.__lastResult = {deeplink: p.deeplink, productName: p.name, image: p.image, price: p.price, channel};
  showPicked(p.name, p.deeplink);
  toast('상품을 골랐어요 — 말투 고르고 글 만들기');
  const s3 = document.querySelectorAll('#page-make .step-card')[2];
  if(s3) s3.scrollIntoView({behavior:'smooth', block:'start'});
}

async function genFromSearch(deeplink, pname){
  document.getElementById('url').value = deeplink;
  document.getElementById('pname').value = pname;
  mode = 'manual';
  await generate();
}
function CH_LABEL(ch){ return ({blog:'네이버 블로그',insta:'인스타',threads:'쓰레드',x:'X',youtube:'유튜브'})[ch] || '블로그'; }

function renderResult(d){
  const link = d.deeplink;
  const draft = d.blogDraft;
  window.__lastResult = d;
  let draftUI = '';
  if(!draft){
    // 링크만 생성됨 → 말투·형식 고르고 글 만들기
    draftUI = `<div class="card">
      <div class="card-lbl">✍️ 글 만들기</div>
      <div style="font-size:13px;color:var(--text-2);line-height:1.6;margin:6px 0 12px">
        위에서 <b>채널</b>과 <b>말투</b>를 고른 뒤 아래를 누르세요. 고른 대로 글이 만들어져요.
      </div>
      <button class="btn btn-mint" onclick="writeWithSettings()"><span class="lbl">✍️ 이 설정으로 글 만들기</span></button>
    </div>`;
  }
  else if(draft){
    if(d.channel === 'threads'){ draftUI = renderThreads(draft, d); }
    else if(d.channel === 'blog'){ draftUI = renderBlogDraft(draft, d); }
    else if(d.channel === 'insta'){ draftUI = renderInsta(draft, d); }
    else if(d.channel === 'x'){ draftUI = renderX(draft, d); }
    else if(d.channel === 'youtube'){ draftUI = renderYoutube(draft, d); }
    else { draftUI = renderBlogDraft(draft, d); }
  } else {
    draftUI = `<div class="card"><div style="font-size:13px;color:var(--muted)">이번 달 무료 초안을 다 썼어요. Pro는 무제한이에요.</div></div>`;
  }
  document.getElementById('result').innerHTML = `
    <div class="result">
      ${window.__lastTopics?`<button class="btn btn-ghost" style="margin-bottom:10px" onclick="backToTopics()">← 주제 목록으로 돌아가기</button>`:''}
      <div class="card">
        <div class="card-lbl">내 간편 링크</div>
        <div class="linkline"><div class="url">${link}</div>
          <button class="btn-copy" onclick="copyText('${link}', this)">복사</button></div>
      </div>
      ${draftUI}
    </div>`;
  document.getElementById('result').scrollIntoView({behavior:'smooth',block:'start'});
  fillDefaultSchedule();
}

// ── 쓰레드: 6개 말풍선(본글+답글5), 각각 복사 ──
function renderThreads(draft, d){
  const parts = draft.split('\n===THREAD===\n');
  const labels = ['📌 본글 (링크 X)','💬 답글 1','💬 답글 2','💬 답글 3','💬 답글 4 (링크+고지)','💬 답글 5 (마무리)'];
  const bubbles = parts.map((p,i)=>`
    <div class="th-bubble">
      <div class="th-head"><span class="th-label">${labels[i]||('💬 답글 '+i)}</span>
        <button class="th-copy" onclick="copyText(${JSON.stringify(p).replace(/"/g,'&quot;')}, this)">복사</button></div>
      <div class="th-body">${esc(p)}</div>
    </div>`).join('');
  return `<div class="card">
    <div class="card-lbl">🧵 쓰레드 초안 · 본글 + 답글 5개</div>
    <div class="th-wrap">${bubbles}</div>
    <div class="disc">💡 아래 <b>예약/게시</b>를 쓰면 본글+답글 5개가 <b>답글체인으로 자동 발행</b>돼요.</div>
    <div id="accPicker">${renderAccountPicker('threads')}</div>
    <div style="margin:12px 0 4px">
      <div style="font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.1em;margin-bottom:8px">SCHEDULE · 예약 발행 (본글+답글 전부 자동)</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">
        <button class="chip" onclick="fillSched(1)">+1시간</button>
        <button class="chip" onclick="fillSched(3)">+3시간</button>
        <button class="chip" onclick="fillSchedAt(20)">오늘 20시</button>
        <button class="chip" onclick="fillSchedAt(9,1)">내일 9시</button>
      </div>
      <div style="background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:12px">
        <div style="font-size:12px;color:var(--text-2);margin-bottom:8px">원하는 날짜·시각 직접 지정</div>
        <input type="datetime-local" id="schedAt" style="width:100%;background:var(--surface-1);border:1px solid var(--line);border-radius:8px;color:var(--text);padding:12px;font-size:15px;margin-bottom:8px;color-scheme:dark">
        <button class="btn btn-mint" style="width:100%" onclick="scheduleThread(this)"><span class="lbl">⏰ 이 시각에 예약</span></button>
      </div>
    </div>
    <div class="card-actions">
      <button class="btn btn-mint" onclick="publishToSns('threads',this)">🚀 지금 바로 게시</button>
      <button class="btn btn-ghost" onclick="draftToThreads(this)">🧵 쓰레드 앱에서 쓰기</button>
      <button class="btn btn-ghost" onclick="copyText(${JSON.stringify(parts.join('\\n\\n')).replace(/"/g,'&quot;')}, this)">전체 복사</button>
      <button class="btn btn-ghost" onclick="saveDraft(this)">📥 앱에 저장</button>
    </div></div>`;
}

// ── 인스타: 캡션 + 해시태그 강조 ──
function renderInsta(draft, d){
  const hashIdx = draft.indexOf('#');
  const caption = hashIdx>0 ? draft.slice(0,hashIdx).trim() : draft;
  const tags = hashIdx>0 ? draft.slice(hashIdx).trim() : '';
  return `<div class="card">
    <div class="card-lbl">📷 인스타 초안 · 캡션 + 해시태그</div>
    <div class="ig-caption" id="draft">${esc(draft)}</div>
    ${tags?`<div class="ig-tags">${esc(tags)}</div>`:''}
    <div class="disc">💡 이미지 올리고 캡션에 붙여넣기. 링크는 내 링크 페이지에 걸어두세요.</div>
    <div class="card-actions">
      <button class="btn btn-mint" onclick="copyText(document.getElementById('draft').innerText, this)">캡션 복사</button>
      ${tags?`<button class="btn btn-ghost" onclick="copyText(${JSON.stringify(tags).replace(/"/g,'&quot;')}, this)">해시태그만 복사</button>`:''}
      <button class="btn btn-mint" onclick="publishToSns('instagram',this)">🚀 바로 게시</button>
      <button class="btn btn-ghost" onclick="saveDraft(this)">📥 임시저장</button>
      <button class="btn btn-ghost" onclick="saveAsImage(this)">📸 이미지 저장</button>
      <button class="btn btn-ghost" onclick="window.open('https://instagram.com','_blank')">인스타 열기</button>
    </div></div>`;
}

// ── X: 짧은 카드 + 글자수 ──
function renderX(draft, d){
  const len = draft.length;
  const over = len>280;
  return `<div class="card">
    <div class="card-lbl">𝕏 X(트위터) 초안 <span style="float:right;font-size:12px;color:${over?'var(--danger,#f66)':'var(--muted)'}">${len}/280자</span></div>
    <div class="x-card" id="draft">${esc(draft)}</div>
    ${over?'<div class="disc">⚠️ 280자를 넘어요. 줄여서 올리세요.</div>':''}
    <div class="card-actions">
      <button class="btn btn-mint" onclick="copyText(document.getElementById('draft').innerText, this)">복사</button>
      <button class="btn btn-mint" onclick="publishToSns('x',this)">🚀 바로 게시</button>
      <button class="btn btn-ghost" onclick="saveDraft(this)">📥 임시저장</button>
      <button class="btn btn-ghost" onclick="saveAsImage(this)">📸 이미지 저장</button>
      <button class="btn btn-ghost" onclick="window.open('https://x.com/compose/post','_blank')">X 열기</button>
    </div></div>`;
}

// ── 유튜브: 설명란 ──
function renderYoutube(draft, d){
  return `<div class="card">
    <div class="card-lbl">▶️ 유튜브 설명란 초안</div>
    <div class="yt-desc" id="draft">${esc(draft)}</div>
    <div class="disc">💡 영상 업로드할 때 설명란에 붙여넣기. 타임스탬프는 영상에 맞게 수정하세요.</div>
    <div class="card-actions">
      <button class="btn btn-mint" onclick="copyText(document.getElementById('draft').innerText, this)">설명란 복사</button>
      <button class="btn btn-ghost" onclick="saveAsImage(this)">📸 이미지 저장</button>
      <button class="btn btn-ghost" onclick="window.open('https://studio.youtube.com','_blank')">스튜디오 열기</button>
    </div></div>`;
}

// ── 블로그(네이버): 긴 글 + HTML 복사/다운로드 ──
function renderBlogDraft(draft, d){
  return `<div class="card">
    <div class="card-lbl">📝 네이버 블로그 초안 · 고지문구 포함</div>
    <div class="draftbox" id="draft">${esc(draft)}</div>
    <div class="disc">⚠️ 고지문구가 자동으로 들어갔어요. 이거 빼먹으면 계정 정지될 수 있어요.</div>
    <div class="card-actions">
      <button class="btn btn-mint" onclick="copyNaverHtml(this)">📋 글+이미지 통째 복사</button>
      <button class="btn btn-ghost" onclick="copyText(document.getElementById('draft').innerText, this)">텍스트만 복사</button>
      <button class="btn btn-ghost" onclick="downloadNaverHtml()">⬇ HTML 저장</button>
      <button class="btn btn-ghost" onclick="saveDraft(this)">📥 임시저장</button>
      <button class="btn btn-ghost" onclick="saveAsImage(this)">📸 이미지 저장</button>
      <button class="btn btn-ghost" onclick="window.open('https://blog.naver.com/postwrite','_blank')">블로그 열기</button>
    </div>
    <div class="hint">💡 "글+이미지 통째 복사" 누르고 네이버 블로그 글쓰기에 붙여넣으면 이미지·서식까지 들어가요.</div>
  </div>`;
}
// 네이버 HTML 통째 복사 (이미지+서식 포함 → 붙여넣으면 그대로)
async function copyNaverHtml(btn){
  const d = window.__lastResult;
  if(!d || !d.naverHtml){ toast('복사할 내용이 없어요'); return; }
  try{
    // HTML로 클립보드에 (리치 텍스트로 붙여넣기됨)
    const blob = new Blob([d.naverHtml], {type:'text/html'});
    const plain = new Blob([document.getElementById('draft').innerText], {type:'text/plain'});
    await navigator.clipboard.write([new ClipboardItem({'text/html':blob, 'text/plain':plain})]);
    const o=btn.textContent; btn.textContent='복사됨 ✓'; setTimeout(()=>btn.textContent=o,1500);
    toast('붙여넣기 하면 이미지·서식까지 들어가요');
  }catch(e){
    // 폴백: 텍스트만
    copyText(document.getElementById('draft').innerText, btn);
  }
}
// HTML 파일 다운로드
function downloadNaverHtml(){
  const d = window.__lastResult;
  if(!d || !d.naverHtml){ toast('저장할 내용이 없어요'); return; }
  const blob = new Blob([d.naverHtml], {type:'text/html;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const fname = (d.productName||'쿠팡추천').replace(/[^가-힣a-zA-Z0-9]/g,'_').slice(0,20);
  a.href = url; a.download = `${fname}_블로그.html`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url), 1000);
  toast('HTML 파일이 저장됐어요');
}
function addRecent(d){
  recent.unshift({link:d.deeplink, name:(d.productName||'쿠팡 상품'), ch:d.channel});
  if(recent.length>8) recent.pop();
  document.getElementById('reclist').innerHTML = `<div class="nia-wrap"><div class="nia-list">` +
    recent.map((r,i)=>`
      <button class="nia-item" style="animation-delay:${i*40}ms" onclick="copyText('${r.link}', this.querySelector('.nia-act'))">
        <div class="nia-ic">🛍️</div>
        <div class="nia-body">
          <div class="nia-name">${esc(r.name)}</div>
          <div class="nia-sub">${r.link.replace('https://','')}</div>
        </div>
        <div class="nia-act">복사</div>
      </button>`).join('') + `</div></div>`;
}

// ── 프로필 ──
function timeAgo(ts){
  const s = Math.floor(Date.now()/1000) - ts;
  if(s<3600) return Math.max(1,Math.floor(s/60))+'분 전';
  if(s<86400) return Math.floor(s/3600)+'시간 전';
  if(s<604800) return Math.floor(s/86400)+'일 전';
  return Math.floor(s/604800)+'주 전';
}
const CH_ICON = {blog:'📝', insta:'📷', threads:'🧵', x:'𝕏', youtube:'▶️', etc:'🔗'};
function getChosung(str){
  const CHO = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];
  // 쌍자음 → 기본 자음 (ㄲ→ㄱ 등, 인덱스는 기본 자음만 표시)
  const MERGE = {'ㄲ':'ㄱ','ㄸ':'ㄷ','ㅃ':'ㅂ','ㅆ':'ㅅ','ㅉ':'ㅈ'};
  const s = (str||'').trim();
  if(!s) return '#';
  const c = s.charCodeAt(0);
  if(c >= 0xAC00 && c <= 0xD7A3){ const ch = CHO[Math.floor((c-0xAC00)/588)]; return MERGE[ch]||ch; }
  if(c >= 0x3131 && c <= 0x314E){ // 자음만 있는 경우(ㄱ~ㅎ)
    const idx = CHO.indexOf(s[0]); if(idx>=0){ return MERGE[CHO[idx]]||CHO[idx]; }
  }
  if(c >= 65 && c <= 90) return String.fromCharCode(c);      // A-Z
  if(c >= 97 && c <= 122) return String.fromCharCode(c-32);  // a-z→대문자
  if(c >= 48 && c <= 57) return '#';                          // 숫자
  return '#';
}
async function loadProfile(){
  try{
    const d = await (await fetch('/api/my-links')).json();
    const box = document.getElementById('profileLinks');
    if(!d.ok || !d.links.length){ box.innerHTML = `<div class="empty">링크를 만들면 여기에 모여요</div>`; return; }
    // 전체 인덱스 (나이아가라: ㄱ~ㅎ, A~Z, # 항상 표시)
    const CHO = ['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];
    const ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    const FULL_INDEX = [...CHO, ...ALPHA, '#'];
    // 상품을 초성으로 그룹핑
    const sorted = [...d.links].sort((a,b)=>(a.product_name||'').localeCompare(b.product_name||'','ko'));
    const groups = {};
    sorted.forEach(l=>{ const k=getChosung(l.product_name||'쿠팡'); (groups[k]=groups[k]||[]).push(l); });
    // 인덱스 순서대로 그룹 렌더 (상품 있는 초성만 섹션 생성)
    let html = '', gi = 0;
    FULL_INDEX.forEach(k=>{
      if(!groups[k]) return;
      html += `<div class="nia-glabel" id="g-${encodeURIComponent(k)}">${k}</div>`;
      groups[k].forEach(l=>{
        const dispName = l.product_name && l.product_name!=='쿠팡 상품' && l.product_name!=='이 상품' ? l.product_name : ('쿠팡 링크 '+(l.deeplink||'').replace('https://link.coupang.com/a/','').slice(0,6));
        html += `<div class="nia-item" data-clicks="${l.clicks||0}" style="animation-delay:${Math.min(gi*20,300)}ms">
          <div class="nia-body" onclick="openLink(${l.id},'${l.deeplink}','${l.post_url||''}')">
            <div class="nia-name ${(!l.product_name||l.product_name==='쿠팡 상품'||l.product_name==='이 상품')?'noname':''}">${esc(dispName)} <span style="font-size:12px;opacity:.6">${CH_ICON[l.channel]||''}</span></div>
            <div class="nia-sub">${timeAgo(l.created_at)} · 조회 ${l.clicks||0}${l.post_url?' · <span style="color:var(--mint)">게시됨 '+(CH_ICON[l.post_channel]||'')+'</span>':''}</div>
          </div>
          <div class="nia-act" onclick="copyText('${l.deeplink}', this)">복사</div>
          <button class="nia-del" onclick="deleteLink(${l.id}, this)" title="삭제">🗑</button>
        </div>`;
        gi++;
      });
    });
    // 전체 인덱스 레일 — 상품 있으면 활성(민트), 없으면 흐리게(비활성)
    const rail = '<div class="nia-rail">' + FULL_INDEX.map(k=>{
      const has = !!groups[k];
      return `<span class="${has?'on':'off'}" ${has?`onclick="document.getElementById('g-${encodeURIComponent(k)}').scrollIntoView({behavior:'smooth',block:'start'})"`:''}>${k}</span>`;
    }).join('') + '</div>';
    box.innerHTML = `<div class="nia-wrap"><div class="nia-list">${html}</div></div>`;
    // 레일은 body 직속에 (page transform 영향 안 받게)
    let railEl = document.getElementById('nia-rail-fixed');
    if(railEl) railEl.remove();
    railEl = document.createElement('div');
    railEl.id = 'nia-rail-fixed';
    railEl.innerHTML = rail;
    document.body.appendChild(railEl);
    attachRailDrag();
  }catch(e){ console.error('[나이아 렌더 실패]', e); }
}

// ── 나이아가라 인덱스 드래그 스크롤 + 큰 글자 오버레이 ──
function attachRailDrag(){
  // ★DOM을 매번 새로 읽는다 (레일이 재생성돼도 옛 노드를 붙잡지 않게)
  const getRail = () => document.querySelector('#nia-rail-fixed .nia-rail');
  const getSpans = () => { const r = getRail(); return r ? [...r.querySelectorAll('span')] : []; };
  const getList = () => document.querySelector('.nia-list');
  const rail = getRail();
  if(!rail) return;
  let active=false, lastKey=null, rafId=null;
  let lastActiveKey=null;   // 마지막으로 멈춘 활성 초성 (손 떼면 유지)
  let targetY=0, smoothY=0;
  let lastMoveT=0, velocity=0, lastRawY=0;   // 속도 추적
  let settleTimer=null, settled=false;       // 멈춤 감지

  // 곡선 렌더. settle(멈춤)이면 정점 크게, 이동중이면 작게 (영상: 움직일땐 15px, 멈추면 37px)
  function render(y, big){
    // big: 0~1 연속값 (정점 크기 부드러운 전환). 곡선은 넓은 활 + 정점 돌출
    const peakScale = 2.0 + big*1.0;      // 2.0(이동중)~3.0(멈춤) 부드럽게
    const sigmaWide = 82;                 // 아주 완만한 넓은 활
    const sigmaPeak = 24;                 // 정점
    getSpans().forEach(s=>{
      const r = s.getBoundingClientRect();
      const cy = (r.top + r.bottom)/2;
      const dist = Math.abs(cy - y);
      const gWide = Math.exp(-(dist*dist)/(2*sigmaWide*sigmaWide));
      const gPeak = Math.exp(-(dist*dist)/(2*sigmaPeak*sigmaPeak));
      const scale = 1 + gPeak*(peakScale-1);
      const shiftX = -gWide*190 - gPeak*38;
      s.style.transform = `translate3d(${shiftX}px,0,0) scale(${scale})`;
      const on = s.classList.contains('on');
      s.style.opacity = on ? (0.8 + gPeak*0.2) : (0.28 + gWide*0.42 + gPeak*0.3);
      s.style.color = (gPeak>0.3 && on) ? 'var(--mint-bright)' : (gPeak>0.3 ? 'var(--text)' : '');
      s.style.zIndex = gPeak>0.4 ? 6 : '';
    });
  }
  function reset(){ getSpans().forEach(s=>{ s.style.transform=''; s.style.opacity=''; s.style.color=''; s.style.zIndex=''; }); }

  function nearest(y){
    let best=null,bd=1e9;
    for(const s of getSpans()){ const r=s.getBoundingClientRect(); const d=Math.abs((r.top+r.bottom)/2-y); if(d<bd){bd=d;best=s;} }
    return best;
  }

  // 리스트 페이드 (영상: 빠르게 이동중=숨김, 멈춤/느림=나타남)
  let listShown = null;
  function showList(show){
    if(!list || listShown===show) return;
    listShown = show;
    const list = getList();
    if(!list) return;
    list.classList.remove('idle');
    list.style.transition = 'opacity .22s cubic-bezier(.22,1,.36,1)';
    list.style.opacity = show ? '1' : '0';
  }

  // 나이아가라: 드래그한 초성 그룹만 보이게, 나머지는 숨김
  let shownGroup = undefined;
  function showGroup(key){
    const list = getList();
    if(!list || shownGroup===key) return;
    shownGroup = key;
    list.style.display=''; list.style.flexDirection='';
    // order 초기화 (조회수 모드에서 돌아올 때)
    list.querySelectorAll('.nia-item').forEach(el=>el.style.order='');
    const labels = list.querySelectorAll('.nia-glabel');
    const items = list.querySelectorAll('.nia-item');
    if(key===null){
      labels.forEach(el=>el.style.display='none');
      items.forEach(el=>el.style.display='none');
      return;
    }
    // 해당 초성 그룹만 표시
    let show=false;
    [...list.children].forEach(el=>{
      if(el.classList.contains('nia-glabel')){
        show = (el.id === 'g-'+encodeURIComponent(key));
        el.style.display = show ? '' : 'none';
      } else if(el.classList.contains('nia-item')){
        el.style.display = show ? '' : 'none';
      }
    });
  }

  // 스프링 물리 보간 — iOS처럼 자연스러운 감속·안착 (velocity 기반)
  let springVel = 0;   // 스프링 속도
  let peakEase = 0;    // 정점 크기 부드러운 전환 (0~1)
  function loop(){
    // 스프링: 목표로 당기는 힘(stiffness) + 감쇠(damping)
    const stiffness = 0.16;   // 당기는 강도 (낮을수록 부드럽게 따라감)
    const damping = 0.72;     // 감쇠 (0.7~0.8이 자연스러운 스프링감)
    const force = (targetY - smoothY) * stiffness;
    springVel = (springVel + force) * damping;
    smoothY += springVel;
    const gap = Math.abs(targetY - smoothY);
    if(gap < 0.3 && Math.abs(springVel) < 0.3){ smoothY = targetY; springVel = 0; }
    // 정점 크기도 부드럽게 전환 (탁 커지지 않고 스르륵)
    const wantBig = settled && Math.abs(velocity) < 0.35 ? 1 : 0;
    peakEase += (wantBig - peakEase) * 0.15;
    render(smoothY, peakEase);
    if(active || gap > 0.3 || Math.abs(springVel) > 0.3 || Math.abs(wantBig-peakEase) > 0.02)
      rafId = requestAnimationFrame(loop);
    else rafId = null;
  }

  function moveTo(clientY){
    // 속도 계산
    const now = performance.now();
    const dt = now - lastMoveT;
    if(dt>0){ velocity = (clientY - lastRawY) / dt; }
    lastRawY = clientY; lastMoveT = now;

    targetY = clientY;
    if(!rafId){ smoothY = clientY; rafId=requestAnimationFrame(loop); }

    const speed = Math.abs(velocity);

    // 멈춤 감지: 정지하면 정점 커짐 (그룹 표시는 아래 moveTo에서 즉시)
    settled = false;
    clearTimeout(settleTimer);
    settleTimer = setTimeout(()=>{ settled = true; }, 55);

    const s = nearest(clientY);
    if(!s) return;
    const key = s.textContent;
    const on = s.classList.contains('on');
    if(key!==lastKey){
      lastKey = key;
      if(navigator.vibrate) navigator.vibrate(on?6:2);
      // 활성 초성이면 그 그룹, 비활성이면 가장 가까운 활성 초성 그룹 표시
      if(on){ showGroup(key); lastActiveKey = key; }
      else {
        const nk = nearestActiveKey(clientY);
        if(nk){ showGroup(nk); lastActiveKey = nk; }
      }
    }
  }
  // 가장 가까운 '활성(상품 있는)' 초성 찾기
  function nearestActiveKey(y){
    let best=null, bd=1e9;
    for(const s of getSpans()){
      if(!s.classList.contains('on')) continue;
      const r=s.getBoundingClientRect();
      const d=Math.abs((r.top+r.bottom)/2 - y);
      if(d<bd){ bd=d; best=s.textContent; }
    }
    return best;
  }
  function end(){
    active=false; lastKey=null; settled=false;
    clearTimeout(settleTimer);
    if(rafId){ cancelAnimationFrame(rafId); rafId=null; }
    // 손 떼면 곡선이 부드럽게 풀림
    let ease = 1;
    const releaseY = smoothY;
    (function relax(){
      ease *= 0.85;
      if(ease < 0.03){ reset(); return; }
      renderDamped(releaseY, ease);
      requestAnimationFrame(relax);
    })();
    // ★손 떼면: 멈춘 초성이 있으면 그 초성 글 유지, 없으면 조회수 높은 순
    if(lastActiveKey){
      showGroup(lastActiveKey);   // 멈춘 초성 글 유지 → 읽을 수 있게
    } else {
      showByViews();
    }
    const list = getList();
    if(list){ list.classList.remove('idle'); list.style.opacity=''; }
  }
  // 조회수 높은 순 전체 표시 (손 뗐을 때)
  function showByViews(){
    const list = getList();
    if(!list) return;
    shownGroup = '__views__';
    const labels = list.querySelectorAll('.nia-glabel');
    labels.forEach(el=>el.style.display='none');
    const items = [...list.querySelectorAll('.nia-item')];
    // clicks 데이터로 정렬
    items.sort((a,b)=>(parseInt(b.dataset.clicks||0)-parseInt(a.dataset.clicks||0)));
    items.forEach((el,i)=>{
      el.style.display='';
      el.style.order = i;  // flex order로 재배치
    });
    list.style.display='flex';
    list.style.flexDirection='column';
  }
  // 풀림 전용 렌더 (기존 곡선을 ease배 축소)
  function renderDamped(y, ease){
    const sigmaWide=78, sigmaPeak=22;
    getSpans().forEach(s=>{
      const r=s.getBoundingClientRect();
      const cy=(r.top+r.bottom)/2;
      const dist=Math.abs(cy-y);
      const gWide=Math.exp(-(dist*dist)/(2*sigmaWide*sigmaWide))*ease;
      const gPeak=Math.exp(-(dist*dist)/(2*sigmaPeak*sigmaPeak))*ease;
      const scale=1+gPeak*2.0;
      const shiftX=-gWide*185 - gPeak*35;
      s.style.transform=`translate3d(${shiftX}px,0,0) scale(${scale})`;
      const on=s.classList.contains('on');
      s.style.opacity = on ? (0.78 + gPeak*0.22) : (0.28 + gWide*0.4 + gPeak*0.3);
      if(gPeak<0.1) s.style.color='';
    });
  }

  // ★document 위임: 레일이 몇 번 재생성돼도 절대 안 깨짐 (전역 핸들러 1회만 등록)
  if(!window.__niaDelegated){
    window.__niaDelegated = true;
    const inRail = (e) => {
      const r = document.querySelector('#nia-rail-fixed .nia-rail');
      if(!r) return false;
      const b = r.getBoundingClientRect();
      return e.clientX >= b.left - 8 && e.clientX <= b.right + 8 &&
             e.clientY >= b.top && e.clientY <= b.bottom;
    };
    document.addEventListener('pointerdown', e=>{
      const h = window.__niaHandlers;
      if(!h || !inRail(e)) return;
      e.preventDefault();
      h.start(e.clientY);
    }, {passive:false});
    document.addEventListener('pointermove', e=>{
      const h = window.__niaHandlers;
      if(!h || !h.isActive()) return;
      e.preventDefault();
      h.move(e.clientY);
    }, {passive:false});
    document.addEventListener('pointerup', ()=>{ const h=window.__niaHandlers; if(h && h.isActive()) h.end(); });
    document.addEventListener('pointercancel', ()=>{ const h=window.__niaHandlers; if(h && h.isActive()) h.end(); });
    // 레일 위에서 브라우저 기본 제스처(스크롤·뒤로가기) 차단
    document.addEventListener('touchstart', e=>{
      if(window.__niaHandlers && e.touches[0] && inRail(e.touches[0])) e.preventDefault();
    }, {passive:false});
    document.addEventListener('touchmove', e=>{
      const h = window.__niaHandlers;
      if(h && h.isActive()) e.preventDefault();
    }, {passive:false});
  }
  // 현재 레일의 핸들러를 전역에 등록 (재생성 시 갱신)
  window.__niaHandlers = {
    start: (y)=>{ active=true; lastRawY=y; lastMoveT=performance.now(); moveTo(y); },
    move: (y)=>{ moveTo(y); },
    end: ()=>{ end(); },
    isActive: ()=>active,
  };

  // 초기 상태: 조회수 높은 순 전체 표시 (손 뗀 상태와 동일)
  showByViews();
}
// 내 링크 클릭 → 게시한 글이 있으면 그 글로, 없으면 쿠팡으로
function openLink(id, deeplink, postUrl){
  if(postUrl){ window.open(postUrl, '_blank'); return; }   // 쓰레드 등 게시글로
  window.open('/r/'+id, '_blank');                          // 게시 안 했으면 쿠팡(클릭 카운트)
}

async function deleteLink(id, btn){
  if(!confirm('이 링크를 삭제할까요?')) return;
  try{
    const r = await fetch('/api/link/'+id, {method:'DELETE'});
    const d = await r.json();
    if(d.ok){
      const item = btn.closest('.nia-item');
      if(item){ item.style.transition='opacity .2s'; item.style.opacity='0'; setTimeout(()=>loadProfile(), 200); }
      toast('삭제됐어요');
    } else toast('삭제 실패');
  }catch(e){ toast('삭제 실패'); }
}

// 초안 카드를 이미지(PNG)로 저장 — 폰 스크롤캡처 안 될 때 대안
async function saveAsImage(btn){
  const card = btn.closest('.card');
  if(!card || typeof html2canvas==='undefined'){ toast('이미지 저장을 준비 못했어요'); return; }
  const o = btn.textContent; btn.textContent='만드는 중…';
  try{
    // 캡처용: 버튼줄 잠시 숨기고 배경 채움
    const actions = card.querySelector('.card-actions');
    const hint = card.querySelector('.hint');
    if(actions) actions.style.visibility='hidden';
    if(hint) hint.style.display='none';
    const canvas = await html2canvas(card, {backgroundColor:'#141B2E', scale:2, useCORS:true, logging:false});
    if(actions) actions.style.visibility='';
    if(hint) hint.style.display='';
    canvas.toBlob(blob=>{
      const url=URL.createObjectURL(blob);
      const a=document.createElement('a');
      const d=window.__lastResult||{};
      const fname=(d.productName||'초안').replace(/[^가-힣a-zA-Z0-9]/g,'_').slice(0,16);
      a.href=url; a.download=`${fname}_${d.channel||'글'}.png`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      toast('이미지로 저장했어요 📸');
    }, 'image/png');
  }catch(e){ toast('이미지 저장 실패'); }
  btn.textContent = o;
}

// AI 키 여러 개 한 번에 저장 (Gemini/OpenRouter/Claude)
// 강제 새로고침: 서비스워커·캐시 전부 지우고 최신 받기
async function hardRefresh(){
  try{
    if('serviceWorker' in navigator){
      const rs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(rs.map(r=>r.unregister()));
    }
    if(window.caches){
      const ks = await caches.keys();
      await Promise.all(ks.map(k=>caches.delete(k)));
    }
  }catch(e){}
  location.replace(location.pathname + '?fresh=' + Date.now());
}
// 현재 실행 중인 버전 표시 (디버깅용)
function showBuildInfo(){
  const el = document.getElementById('buildInfo');
  if(!el) return;
  const meta = document.querySelector('meta[name="build"]');
  const build = meta ? meta.content : '알 수 없음';
  const js = (document.querySelector('script[src*="app.js"]')||{}).src || '';
  const v = (js.match(/v=(\d+)/)||[])[1] || '?';
  const nia = window.__niaDelegated ? '✓ 나이아 최신' : '✗ 나이아 구버전';
  el.innerHTML = `빌드 ${esc(build)} · JS ${esc(v)}<br><span style="color:${window.__niaDelegated?'var(--mint)':'var(--err-tx)'}">${nia}</span>`;
}

async function saveAllLlmKeys(){
  const btn = document.getElementById('claudeBtn');
  const msg = document.getElementById('claudeMsg');
  msg.innerHTML = '';
  const fields = [
    {id:'k_gemini', name:'Gemini'},
    {id:'k_openrouter', name:'OpenRouter'},
    {id:'k_groq', name:'Groq'},
    {id:'k_anthropic', name:'Claude'},
  ];
  const toSave = fields.map(f=>({...f, val:(document.getElementById(f.id)?.value||'').trim()})).filter(f=>f.val);
  if(!toSave.length){ msg.innerHTML = '<div class="msg msg-err">키를 하나 이상 입력하세요</div>'; return; }
  btn.classList.add('loading');
  const done = [], failed = [];
  for(const f of toSave){
    try{
      const r = await fetch('/api/anthropic-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:f.val})});
      const d = await r.json();
      if(d.ok) done.push(f.name); else failed.push(f.name+': '+(d.error||''));
    }catch(e){ failed.push(f.name); }
  }
  btn.classList.remove('loading');
  msg.innerHTML = (done.length ? `<div class="msg msg-ok">${done.join(', ')} 연결됐어요 🧠</div>` : '')
    + (failed.length ? `<div class="msg msg-err">${failed.join(' / ')}</div>` : '');
  await refreshMe();
  renderLlmPicker();
}

async function saveClaudeKey(){
  const key = (document.getElementById('c_key').value||'').trim();
  const btn = document.getElementById('claudeBtn');
  const msg = document.getElementById('claudeMsg');
  msg.innerHTML='';
  if(!key){ msg.innerHTML='<div class="msg msg-err">Claude API 키를 입력하세요</div>'; return; }
  btn.classList.add('loading');
  try{
    const r = await fetch('/api/anthropic-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});
    const d = await r.json();
    if(d.ok){ msg.innerHTML='<div class="msg msg-ok">'+(d.message||'연결됐어요!')+' 🧠</div>'; if(window.__me){ window.__me.has_claude=true; window.__me.llm_provider=d.provider; } renderClaude(window.__me||{has_claude:true}); }
    else msg.innerHTML=`<div class="msg msg-err">${d.error||'연결 실패'}</div>`;
  }catch(e){ msg.innerHTML='<div class="msg msg-err">네트워크 오류</div>'; }
  btn.classList.remove('loading');
}
function renderClaude(me){
  const el = document.getElementById('claudeStatus');
  if(!el) return;
  const names = {gemini:'Gemini (무료)', openrouter:'OpenRouter (무료)', groq:'Groq (무료)', anthropic:'Claude'};
  const provs = (me.llm_providers||[]).map(p=>names[p]||p);
  el.innerHTML = provs.length ? '<span style="color:var(--mint)">✓ 연결됨: '+provs.join(' · ')+'</span>' : '연결 안 됨';
  // 북마클릿 코드 설정 (쿠팡 상세이미지 긁어서 우리 앱으로 — URL 파라미터 전달)
  const bmk = document.getElementById('bmk');
  if(bmk){
    const origin = location.origin;
    const code = `(function(){var imgs=[];document.querySelectorAll('img').forEach(function(i){var s=i.src||i.getAttribute('data-src')||'';if(s&&(s.indexOf('coupangcdn')>-1||s.indexOf('coupang')>-1)&&i.naturalWidth>200){imgs.push(s.split('?')[0])}});imgs=[...new Set(imgs)].slice(0,20);var t=((document.querySelector('h1')||{}).innerText||document.title).slice(0,80);if(!imgs.length){alert('상세 이미지를 못 찾았어요. 페이지를 끝까지 스크롤한 뒤 다시 눌러주세요.');return}var payload=encodeURIComponent(JSON.stringify({images:imgs,productName:t}));window.open(origin+'/?bmk='+payload,'_blank')})();`;
    bmk.href = 'javascript:' + encodeURIComponent(code);
  }
}

// 주제 먼저 생성 (Claude AI)
// ── 지금 뜨는 주제 레이더 (LIVE SIGNAL) ──
let radarCat = '추천';
let radarRange = '24시간';
async function loadRadar(refresh){
  const box = document.getElementById('trendRadarTop') || document.getElementById('trendRadar');
  if(!box) return;
  if(!box.dataset.init){
    box.dataset.init = '1';
    box.innerHTML = `<div style="padding:0">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <span class="live-dot"></span>
        <span style="font-size:10px;font-weight:700;letter-spacing:.16em;color:var(--muted)">LIVE SIGNAL</span>
      </div>
      <div style="font-size:19px;font-weight:600;color:var(--text);margin-bottom:6px;letter-spacing:-.01em">지금 뜨는 주제 레이더</div>
      <div style="font-size:12.5px;color:var(--text-2);margin-bottom:14px;line-height:1.5">생활·육아·건강과 직접 관련 있는 급상승 신호만 추천합니다.</div>

      <div class="seg" id="radarRange">
        ${['4시간','24시간','7일'].map(r=>`<button class="seg-btn ${r===radarRange?'on':''}" onclick="setRadarRange('${r}',this)">${r}</button>`).join('')}
        <button class="seg-btn seg-refresh" onclick="loadRadar(true)" title="새로고침">↻</button>
      </div>

      <div class="radar-cats" id="radarCats">
        ${['추천','전체','생활','육아','건강','날씨','쇼핑'].map(c=>`<button class="chip ${c===radarCat?'on':''}" onclick="setRadarCat('${c}',this)">${c}</button>`).join('')}
      </div>
      <div id="radarList"></div>
    </div>`;
  }
  const list = document.getElementById('radarList');
  // ★로딩 상태를 확실히 (스켈레톤)
  list.innerHTML = `<div class="radar-loading">
      <span class="spin-sm"></span><span>신호 수집 중…</span>
    </div>` + [1,2,3].map(()=>`<div class="radar-card skel">
      <div class="sk-line" style="width:30%"></div>
      <div class="sk-line" style="width:62%;height:18px;margin-top:10px"></div>
      <div class="sk-line" style="width:88%;margin-top:10px"></div>
      <div class="sk-line" style="width:46%;margin-top:14px;height:34px;border-radius:10px"></div>
    </div>`).join('');
  try{
    const d = await (await fetch(`/api/trend-radar?cat=${encodeURIComponent(radarCat)}&range=${encodeURIComponent(radarRange)}${refresh?'&refresh=1':''}`)).json();
    const items = d.items || [];
    if(!items.length){ list.innerHTML = '<div class="radar-empty">관련 신호가 없어요</div>'; return; }
    list.innerHTML = items.map((it,i)=>`
      <div class="radar-card">
        <div class="radar-top">
          <span class="radar-num">${String(i+1).padStart(2,'0')}</span>
          <div style="display:flex;gap:6px">
            <span class="radar-tag">${esc(it.cat)}</span>
            ${it.kind==='season'?'<span class="radar-tag">계절 추천</span>':(it.traffic?`<span class="radar-tag">${esc(it.traffic)}</span>`:'')}
          </div>
        </div>
        <div class="radar-title-row">
          <div class="radar-title">${esc(it.title)}</div>
          <div class="radar-meta">${it.kind==='season'?'계절 관심사':'급상승'}</div>
        </div>
        <div class="radar-hook">${esc(it.hook||'')}</div>
        <div class="radar-src">
          <span>${esc(it.source||'')}</span>
          ${it.url?`<a href="${it.url}" target="_blank">원본 보기 ↗</a>`:'<span></span>'}
        </div>
        <div class="radar-btns">
          <button class="rbtn rbtn-primary" onclick="refineTopic('${esc(it.title).replace(/'/g,'')}',this)">주제로 다듬기</button>
          <button class="rbtn" onclick="window.open('https://search.naver.com/search.naver?query=${encodeURIComponent(it.title)}','_blank')">네이버 확인</button>
        </div>
      </div>`).join('');
    const upd = new Date();
    list.insertAdjacentHTML('beforeend',
      `<div class="radar-foot">Google Trends Korea · 실시간에 가까운 검색 신호<br><span>${upd.getHours()<12?'오전':'오후'} ${String(upd.getHours()%12||12).padStart(2,'0')}:${String(upd.getMinutes()).padStart(2,'0')} 갱신</span></div>`);
  }catch(e){ list.innerHTML = '<div class="radar-empty">신호를 못 가져왔어요</div>'; }
}
function setRadarRange(r, el){
  radarRange = r;
  el.parentNode.querySelectorAll('.seg-btn').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  loadRadar();
}
function setRadarCat(c, el){
  radarCat = c;
  el.parentNode.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  loadRadar();
}
// 레이더 주제 → AI가 주제 기획 (로딩 표시 확실히)
function refineTopic(title, btn){
  if(btn){ btn.disabled = true; btn.innerHTML = '<span class="spin-sm"></span> 다듬는 중…'; }
  const el = document.getElementById('topicKw');
  if(el) el.value = title;
  doTopics().finally(()=>{ if(btn){ btn.disabled=false; btn.textContent='주제로 다듬기'; } });
}

async function doTopics(){
  const topic = (document.getElementById('topicKw').value||'').trim();
  const btn = document.getElementById('topicGo');
  if(!window.__me || !window.__me.has_claude){
    toast('설정에서 Claude API 키를 먼저 등록하세요'); go('settings'); return;
  }
  btn.classList.add('loading');
  const result = document.getElementById('result');
  result.innerHTML = `<div class="card">
    <div class="radar-loading"><span class="spin-sm"></span><span>AI가 주제 기획 중… (시각·표본·앵글 분석)</span></div>
    ${[1,2,3].map(()=>`<div class="radar-card skel"><div class="sk-line" style="width:55%;height:18px"></div><div class="sk-line" style="width:85%;margin-top:12px"></div><div class="sk-line" style="width:70%;margin-top:8px"></div><div class="sk-line" style="width:40%;margin-top:12px;height:30px;border-radius:9px"></div></div>`).join('')}
  </div>`;
  try{
    const r = await fetch('/api/claude-topics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic, provider:(window.__llmPick||null)})});
    const d = await r.json();
    if(d.ok && d.topics && d.topics.length){
      renderTopics(d.topics, d.now);
    }
    else if(d.need_key){ toast('설정에서 Claude API 키 먼저'); go('settings'); result.innerHTML=''; }
    else { toast(d.error||'주제 생성 실패'); result.innerHTML=''; }
  }catch(e){ toast('주제 생성 실패'); result.innerHTML=''; }
  btn.classList.remove('loading');
}
function renderTopics(topics, now){
  window.__lastTopics = topics;
  window.__lastTopicsNow = now;
  window.__topicIdx = 0;
  const total = topics.reduce((a,t)=>a + ((t.keywords||[]).length||0), 0);
  const result = document.getElementById('result');
  result.innerHTML = `
    <div class="card linkprod">
      <div class="lp-head">
        <div style="font-size:9.5px;font-weight:700;letter-spacing:.18em;color:var(--muted)">AI → COUPANG</div>
        <span class="lp-count">${total}개</span>
      </div>
      <div class="lp-title">답변에서 뽑은 연결 상품</div>
      <div class="lp-sub">주제를 고른 다음 상품 키워드를 누르면 쿠팡에서 실제 상품명을 검색합니다.</div>

      <div class="lp-tabs" id="lpTabs">
        ${topics.map((t,i)=>`<button class="lp-tab ${i===0?'on':''}" onclick="pickTopicTab(${i},this)">${i+1}. ${esc((t.title||'').slice(0,22))}${(t.title||'').length>22?'…':''}</button>`).join('')}
      </div>

      <div class="lp-detail" id="lpDetail"></div>
    </div>`;
  renderTopicDetail(0);
  result.scrollIntoView({behavior:'smooth', block:'start'});
}
function pickTopicTab(i, el){
  window.__topicIdx = i;
  el.parentNode.querySelectorAll('.lp-tab').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  renderTopicDetail(i);
}
function renderTopicDetail(i){
  const t = (window.__lastTopics||[])[i];
  const box = document.getElementById('lpDetail');
  if(!t || !box) return;
  const kws = t.keywords || [];
  box.innerHTML = `
    <div class="lp-dtitle">${esc(t.title||'')}</div>
    <div class="lp-dhook">${esc(t.hook || t.angle || '')}</div>
    ${(t.sample||t.time_context)?`<div class="lp-dmeta">${t.time_context?`🕐 ${esc(t.time_context)}`:''}${t.sample?`  👥 ${esc(t.sample)}`:''}</div>`:''}
    <div class="lp-kws">
      ${kws.map(k=>`<button class="lp-kw" data-kw="${esc(k)}">${esc(k)} <span>검색</span></button>`).join('')}
    </div>`;
  box.querySelectorAll('.lp-kw').forEach(b=>{
    b.addEventListener('click', ()=>{
      box.querySelectorAll('.lp-kw').forEach(x=>x.classList.remove('on'));
      b.classList.add('on');
      searchFromTopic(b.dataset.kw);
    });
  });
}

// 주제 목록으로 돌아가기 (왔다갔다 비교)
function backToTopics(){
  // 주제 모드로 전환
  const tm = [...document.querySelectorAll('.mode')].find(m=>m.dataset.mode==='topic');
  if(tm) setMode(tm);
  if(window.__lastTopics){
    renderTopics(window.__lastTopics, window.__lastTopicsNow);
  }
}

async function searchFromTopic(keyword){
  // 검색 모드로 전환 (setMode로 박스 토글 일관성)
  const sm = [...document.querySelectorAll('.mode')].find(m=>m.dataset.mode==='search');
  if(sm) setMode(sm);
  const kwInput = document.getElementById('searchKw');
  if(kwInput) kwInput.value = keyword;
  doSearch();
}

async function saveClaudeKeyOld(){}

async function saveSnsKey(){
  const key = (document.getElementById('z_key').value||'').trim();
  const btn = document.getElementById('snsBtn');
  const msg = document.getElementById('snsMsg');
  msg.innerHTML='';
  if(!key){ msg.innerHTML='<div class="msg msg-err">Zernio API 키를 입력하세요</div>'; return; }
  btn.classList.add('loading');
  try{
    const r = await fetch('/api/sns-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});
    const d = await r.json();
    if(d.ok){ msg.innerHTML='<div class="msg msg-ok">연결됐어요! ✨</div>'; if(window.__me) window.__me.has_sns=true; renderSns(window.__me||{has_sns:true}); loadSnsAccounts(); }
    else msg.innerHTML=`<div class="msg msg-err">${d.error||'연결 실패'}</div>`;
  }catch(e){ msg.innerHTML='<div class="msg msg-err">네트워크 오류</div>'; }
  btn.classList.remove('loading');
}
function renderSns(me){
  const el = document.getElementById('snsStatus');
  if(!el) return;
  el.innerHTML = me.has_sns ? '<span style="color:var(--mint)">✓ 연결됨 — 초안에서 바로 게시할 수 있어요</span>' : '연결 안 됨';
}

// 임시저장 (게시 안 함)
async function saveDraft(btn){
  const d = window.__lastResult;
  if(!d){ toast('⚠️ 초안 데이터가 없어요 (다시 만들어주세요)'); return; }
  if(!d.blogDraft){ toast('⚠️ 저장할 글이 없어요'); return; }
  const o = btn.textContent; btn.textContent='저장 중…';
  try{
    const r = await fetch('/api/save-draft',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({channel:d.channel, content:d.blogDraft, productName:d.productName||'', deeplink:d.deeplink||'', image:d.image||null})});
    if(r.status===401){ toast('⚠️ 로그인이 풀렸어요. 새로고침 해주세요'); btn.textContent=o; return; }
    const res = await r.json();
    if(res.ok){
      if(res.zernio_saved){ toast('Zernio에 초안 저장됨 📥 (대시보드 Posts에서 확인)'); }
      else { toast('임시저장했어요 📥'); }
      btn.textContent='저장됨 ✓';
    }
    else { toast('저장 실패: '+(res.error||r.status)); btn.textContent=o; }
  }catch(e){ toast('저장 오류: '+(e.message||e)); btn.textContent=o; }
}

// SNS 게시 (Zernio) — 실패 시 정확한 이유 표시
// 쓰레드 작성창 열기: 본글만 넣고, 답글은 순서대로 이어붙이게 도우미 제공
async function draftToThreads(btn){
  const d = window.__lastResult;
  if(!d || !d.blogDraft){ toast('⚠️ 초안이 없어요'); return; }
  const parts = d.blogDraft.split('\n===THREAD===\n').filter(Boolean);
  const main = parts[0] || '';
  window.__threadReplies = parts.slice(1);
  window.__threadReplyIdx = 0;
  // 앱에도 전체 백업
  try{
    await fetch('/api/save-draft',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({channel:'threads', content:d.blogDraft, productName:d.productName||'', deeplink:d.deeplink||'', image:d.image||null})});
  }catch(e){}
  // ★본글만 (쓰레드 500자 제한) → 쓰레드 작성창에서 임시저장/예약 가능
  const url = 'https://www.threads.net/intent/post?text=' + encodeURIComponent(main.slice(0, 480));
  window.open(url, '_blank');
  toast('본글이 들어갔어요. 답글은 아래 도우미로 하나씩 추가하세요 🧵');
  showReplyHelper();
}
// 답글 순서대로 복사 도우미
function showReplyHelper(){
  const reps = window.__threadReplies || [];
  if(!reps.length) return;
  let box = document.getElementById('replyHelper');
  if(!box){
    box = document.createElement('div');
    box.id = 'replyHelper';
    box.style.cssText = 'position:fixed;left:16px;right:16px;bottom:80px;background:var(--surface-1);border:1px solid var(--line);border-radius:14px;padding:14px;z-index:60;box-shadow:var(--shadow)';
    document.body.appendChild(box);
  }
  const i = window.__threadReplyIdx || 0;
  if(i >= reps.length){
    box.innerHTML = `<div style="font-size:13px;color:var(--text-2);text-align:center">답글 ${reps.length}개 다 복사했어요 ✓
      <button class="btn-sm ghost" style="margin-left:8px" onclick="document.getElementById('replyHelper').remove()">닫기</button></div>`;
    return;
  }
  box.innerHTML = `<div style="font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.1em;margin-bottom:6px">답글 ${i+1} / ${reps.length} — 쓰레드에서 ⊕ 눌러 추가 후 붙여넣기</div>
    <div style="font-size:13px;color:var(--text);line-height:1.5;max-height:60px;overflow:hidden;margin-bottom:10px">${esc(reps[i].slice(0,80))}${reps[i].length>80?'…':''}</div>
    <div style="display:flex;gap:8px">
      <button class="btn-sm mint" style="flex:1" onclick="copyReplyNext(this)">📋 답글 ${i+1} 복사</button>
      <button class="btn-sm ghost" onclick="document.getElementById('replyHelper').remove()">닫기</button>
    </div>`;
}
function copyReplyNext(btn){
  const reps = window.__threadReplies || [];
  const i = window.__threadReplyIdx || 0;
  if(i >= reps.length) return;
  copyText(reps[i], btn);
  window.__threadReplyIdx = i + 1;
  setTimeout(showReplyHelper, 600);
}

// 연결된 SNS 계정 로드 (게시 대상 선택용)
async function loadSnsAccounts(){
  try{
    const d = await (await fetch('/api/sns-accounts')).json();
    window.__snsAccounts = d.accounts || [];
  }catch(e){ window.__snsAccounts = []; }
  return window.__snsAccounts;
}
// 계정 선택 칩 렌더 (플랫폼별)
function renderAccountPicker(platform){
  const accs = (window.__snsAccounts||[]).filter(a=>{
    const p = a.platform === 'twitter' ? 'x' : a.platform;
    return p === platform;
  });
  if(accs.length < 2) return '';   // 1개면 선택 불필요
  const sel = (window.__pickedAccount||{})[platform] || accs[0].accountId;
  return `<div style="margin:10px 0 4px">
    <div style="font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.1em;margin-bottom:6px">ACCOUNT · 게시할 계정</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      ${accs.map(a=>`<button class="chip ${a.accountId===sel?'on':''}" data-acc="${a.accountId}" data-plat="${platform}" onclick="pickAccount(this)">@${esc(a.name||'계정')}</button>`).join('')}
    </div></div>`;
}
function pickAccount(el){
  const plat = el.dataset.plat, id = el.dataset.acc;
  window.__pickedAccount = window.__pickedAccount || {};
  window.__pickedAccount[plat] = id;
  el.parentNode.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
}

// 프리셋 → 시각 입력칸에 채우기만 (게시는 유저가 버튼 눌러서)
function _toLocalInput(dt){
  const p = n => String(n).padStart(2,'0');
  return `${dt.getFullYear()}-${p(dt.getMonth()+1)}-${p(dt.getDate())}T${p(dt.getHours())}:${p(dt.getMinutes())}`;
}
function fillSched(hours){
  const el = document.getElementById('schedAt'); if(!el) return;
  el.value = _toLocalInput(new Date(Date.now() + hours*3600*1000));
  toast('시각이 채워졌어요 — 고쳐도 됩니다');
}
function fillSchedAt(hour, addDays){
  const el = document.getElementById('schedAt'); if(!el) return;
  const t = new Date();
  t.setDate(t.getDate() + (addDays||0));
  t.setHours(hour, 0, 0, 0);
  if(t <= new Date()) t.setDate(t.getDate()+1);
  el.value = _toLocalInput(t);
  toast('시각이 채워졌어요 — 고쳐도 됩니다');
}

// 빠른 예약: N시간 뒤
async function quickSchedule(hours, btn){
  const t = new Date(Date.now() + hours*3600*1000);
  window.__scheduleAt = t.toISOString();
  await publishToSns('threads', btn);
  window.__scheduleAt = null;
}
// 빠른 예약: 오늘/내일 특정 시각
async function quickScheduleAt(hour, btn, addDays){
  const t = new Date();
  t.setDate(t.getDate() + (addDays||0));
  t.setHours(hour, 0, 0, 0);
  if(t <= new Date()){ t.setDate(t.getDate()+1); }   // 이미 지났으면 다음 날
  window.__scheduleAt = t.toISOString();
  await publishToSns('threads', btn);
  window.__scheduleAt = null;
}

// 예약 게시 (원하는 시각 직접 지정)
async function scheduleThread(btn){
  const at = document.getElementById('schedAt');
  if(!at || !at.value){ toast('예약할 날짜·시각을 골라주세요'); at && at.focus(); return; }
  const t = new Date(at.value);
  if(isNaN(t.getTime())){ toast('시각이 올바르지 않아요'); return; }
  if(t <= new Date()){ toast('미래 시각을 골라주세요'); return; }
  window.__scheduleAt = t.toISOString();
  await publishToSns('threads', btn);
  window.__scheduleAt = null;
}
// 예약 입력창 기본값 = 1시간 뒤 (바로 쓰기 편하게)
function fillDefaultSchedule(){
  const at = document.getElementById('schedAt');
  if(!at || at.value) return;
  const t = new Date(Date.now() + 3600*1000);
  const pad = n=>String(n).padStart(2,'0');
  at.value = `${t.getFullYear()}-${pad(t.getMonth()+1)}-${pad(t.getDate())}T${pad(t.getHours())}:${pad(t.getMinutes())}`;
  at.min = at.value;
}


// 작업 완료 알림 (브라우저 알림 + 진동 + 화면 안 배너)
async function notifyDone(kind){
  try{
    if(navigator.vibrate) navigator.vibrate([40, 60, 40]);
    if('Notification' in window){
      if(Notification.permission === 'granted'){
        new Notification('LinkLynk', { body: `${kind} 완료됐어요`, icon: '/icon-192.png', tag: 'll-job' });
      }
    }
  }catch(e){}
  toast(`✅ ${kind} 완료됐어요`);
}
// 알림 권한 요청 (첫 작업 시 1회)
function askNotifyPermission(){
  try{
    if('Notification' in window && Notification.permission === 'default'){
      Notification.requestPermission();
    }
  }catch(e){}
}

// ── 백그라운드 작업: 화면을 나가도 계속 진행되고, 돌아오면 결과 표시 ──
window.__jobs = window.__jobs || {};   // {id: {status, result, kind}}
function startJob(id, kind, promise, onDone){
  askNotifyPermission();
  window.__jobs[id] = {status:'running', kind, startedAt:Date.now()};
  showJobBanner();
  promise.then(res=>{
    window.__jobs[id] = {status:'done', kind, result:res, at:Date.now()};
    if(onDone) onDone(res);
    showJobBanner();
    notifyDone(kind);
  }).catch(err=>{
    window.__jobs[id] = {status:'error', kind, error:String(err).slice(0,80), at:Date.now()};
    showJobBanner();
  });
  return id;
}
function runningJobs(){ return Object.entries(window.__jobs).filter(([,j])=>j.status==='running'); }
function doneJobs(){ return Object.entries(window.__jobs).filter(([,j])=>j.status==='done' && !j.seen); }
// 진행 중/완료 배너 (어느 화면에서든 보임)
function showJobBanner(){
  let el = document.getElementById('jobBanner');
  const running = runningJobs();
  const done = doneJobs();
  if(!running.length && !done.length){ if(el) el.remove(); return; }
  if(!el){
    el = document.createElement('div');
    el.id = 'jobBanner';
    el.style.cssText = 'position:fixed;left:16px;right:16px;bottom:78px;z-index:70;background:var(--surface-1);border:1px solid var(--line);border-radius:14px;padding:12px 14px;box-shadow:var(--shadow);font-size:13px;color:var(--text);display:flex;align-items:center;gap:10px';
    document.body.appendChild(el);
  }
  if(running.length){
    const kind = running[0][1].kind;
    el.innerHTML = `<span class="spin" style="width:16px;height:16px;border:2px solid rgba(255,255,255,.2);border-top-color:#fff;border-radius:50%;display:inline-block;animation:sp .8s linear infinite"></span>
      <span style="flex:1">${esc(kind)} 진행 중… (화면 이동해도 계속돼요)</span>`;
  } else if(done.length){
    const [id, j] = done[0];
    el.innerHTML = `<span style="flex:1">✅ ${esc(j.kind)} 완료됐어요</span>
      <button class="btn-sm mint" onclick="openJob('${id}')">결과 보기</button>`;
  }
}
function openJob(id){
  const j = window.__jobs[id];
  if(!j || j.status!=='done') return;
  j.seen = true;
  go('make');
  if(j.kind === 'AI 비교' && j.result) renderCompare(j.result.results, j.result.base);
  else if(j.result && j.result.draft) renderResult(j.result.draft);
  showJobBanner();
}

// AI 툴 선택 (등록된 AI만 표시). 유료(Claude)는 명시적으로 골라야만 사용
async function renderLlmPicker(){
  const box = document.getElementById('llmPicker');
  if(!box) return;
  let list = [];
  try{ const d = await (await fetch('/api/llm-list')).json(); list = d.providers || []; }catch(e){}
  if(!list.length){ box.innerHTML = ''; return; }
  window.__llmList = list;
  // 기본 선택: 무료 우선 (Claude 자동 선택 안 함 = 돈 안 나감)
  if(!window.__llmPick || !list.some(p=>p.id===window.__llmPick)){
    const free = list.find(p=>p.id==='gemini') || list.find(p=>p.id==='openrouter');
    window.__llmPick = (free || list[0]).id;
  }
  const PAID = {anthropic:true};
  box.innerHTML = `<div style="font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.1em;margin-bottom:6px">AI · 글 쓰는 도구</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
      ${list.map(p=>`<button class="chip ${p.id===window.__llmPick?'on':''}" onclick="pickLlm('${p.id}',this)">${esc(p.name)}${PAID[p.id]?' 💰':''}</button>`).join('')}
      ${list.length>1?`<button class="chip" onclick="openCompare()">⚖️ 비교</button>`:''}
    </div>
    <div style="font-size:11px;color:var(--muted);margin-top:6px">💰 = 유료(호출 시 과금). 선택한 도구로만 글을 씁니다.</div>`;
}
function pickLlm(id, el){
  if(id==='anthropic' && !confirm('Claude는 유료예요. 호출할 때마다 크레딧이 차감됩니다.\n그래도 사용할까요?')) return;
  window.__llmPick = id;
  el.parentNode.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  const d = window.__lastResult;
  if(d && d.deeplink) regenForChannel(d.deeplink, d.productName||'');
}
// 비교할 AI를 체크박스로 고르기
function openCompare(){
  const list = window.__llmList || [];
  if(list.length < 2){ toast('AI를 2개 이상 등록하세요'); return; }
  let box = document.getElementById('cmpModal');
  if(box) box.remove();
  box = document.createElement('div');
  box.id = 'cmpModal';
  box.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(6px);z-index:100;display:grid;place-items:center;padding:20px';
  box.innerHTML = `<div style="width:100%;max-width:380px;background:var(--surface-1);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:var(--shadow)">
    <div style="font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.14em;margin-bottom:4px">COMPARE</div>
    <div style="font-size:17px;font-weight:600;color:var(--text);margin-bottom:14px">비교할 AI 고르기</div>
    <div id="cmpList">
      ${list.map(p=>`
        <label class="cmp-row">
          <input type="checkbox" value="${p.id}" ${p.id!=='anthropic'?'checked':''}>
          <span class="cmp-box"></span>
          <span class="cmp-name">${esc(p.name)}${p.id==='anthropic'?' <span style="color:var(--warn-tx)">💰 유료</span>':''}</span>
        </label>`).join('')}
    </div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn btn-mint" style="flex:1" onclick="runCompare()"><span class="lbl">⚖️ 비교하기</span></button>
      <button class="btn btn-ghost" onclick="document.getElementById('cmpModal').remove()">취소</button>
    </div>
  </div>`;
  document.body.appendChild(box);
  box.addEventListener('click', e=>{ if(e.target===box) box.remove(); });
}
function runCompare(){
  const checked = [...document.querySelectorAll('#cmpList input:checked')].map(i=>i.value);
  if(checked.length < 2){ toast('2개 이상 고르세요'); return; }
  if(checked.includes('anthropic') && !confirm('Claude가 포함됐어요. 유료 호출이 발생합니다. 계속할까요?')) return;
  document.getElementById('cmpModal').remove();
  compareLlms(checked);
}

async function compareLlms(providers){
  const d = window.__lastResult;
  if(!d || !d.deeplink){ toast('먼저 상품을 골라 초안을 만들어주세요'); return; }
  const result = document.getElementById('result');
  if(result) result.innerHTML = '<div class="card"><div style="text-align:center;padding:26px;color:var(--muted)">⚖️ 각 AI로 글 쓰는 중…<br><span style="font-size:12px">다른 화면 가도 계속 진행돼요</span></div></div>';
  const jobId = 'cmp-' + Date.now();
  const p = fetch('/api/compare-write',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({productName:d.productName||'', deeplink:d.deeplink, tone:(window.curTone||'friendly'), providers})})
    .then(r=>r.json())
    .then(res=>{
      if(!res.ok || !res.results) throw new Error(res.error||'비교 실패');
      return {results: res.results, base: d};
    });
  startJob(jobId, 'AI 비교', p, (res)=>{
    // 아직 만들기 화면이면 바로 표시
    if(document.getElementById('page-make') && !document.getElementById('page-make').classList.contains('hidden')){
      window.__jobs[jobId].seen = true;
      renderCompare(res.results, res.base);
    }
  });
}

function renderCompare(results, d){
  const result = document.getElementById('result');
  result.innerHTML = `<div style="font-size:12px;color:var(--muted);margin:4px 0 12px">⚖️ AI별 결과 — 마음에 드는 걸 고르세요</div>` +
    results.map((r,i)=>{
      if(!r.ok) return `<div class="card" style="margin-bottom:12px"><div class="card-lbl">${esc(r.name)}</div><div style="color:var(--err-tx);font-size:13px">실패: ${esc(r.error||'')}</div></div>`;
      const parts = (r.content||'').split('\n===THREAD===\n');
      return `<div class="card" style="margin-bottom:12px">
        <div class="card-lbl">${esc(r.name)}</div>
        <div style="margin:8px 0;font-size:13.5px;line-height:1.65;color:var(--text);white-space:pre-wrap">${esc(parts[0]||'')}</div>
        <div style="font-size:12px;color:var(--text-2);margin-bottom:10px">답글 ${Math.max(0,parts.length-1)}개 · 탭해서 전체 보기</div>
        <div style="display:flex;gap:8px">
          <button class="btn-sm mint" onclick="useCompareResult(${i})">이 글 쓰기</button>
          <button class="btn-sm ghost" onclick="alert(${JSON.stringify(r.content).replace(/"/g,'&quot;')})">전체 보기</button>
        </div>
      </div>`;
    }).join('');
  window.__compareResults = results;
  window.__compareBase = d;
  result.scrollIntoView({behavior:'smooth',block:'start'});
}
function useCompareResult(i){
  const r = (window.__compareResults||[])[i];
  const d = window.__compareBase;
  if(!r || !r.ok || !d) return;
  window.__llmPick = r.provider;
  renderResult({...d, blogDraft: r.content, channel: 'threads'});
  toast(r.name + ' 글로 정했어요');
}

async function publishToSns(platform, btn){
  const d = window.__lastResult;
  if(!d){ toast('⚠️ 초안 데이터가 없어요 (다시 만들어주세요)'); return; }
  if(!d.blogDraft){ toast('⚠️ 게시할 글이 없어요'); return; }
  if(!window.__me || !window.__me.has_sns){
    toast('먼저 설정에서 SNS를 연결해주세요');
    go('settings'); return;
  }
  let content = d.blogDraft || '';
  // 쓰레드/X는 6분할 전체를 보냄 (서버가 답글체인으로 게시)
  const media = d.image ? [d.image] : [];
  const o = btn.textContent; btn.textContent='게시 중…'; btn.disabled=true;
  try{
    const accIds = {};
    const picked = (window.__pickedAccount||{})[platform];
    if(picked) accIds[platform] = picked;
    const r = await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({platforms:[platform], content, media, channel:d.channel, productName:d.productName||'', deeplink:d.deeplink||'', account_ids:accIds, scheduled_for:(window.__scheduleAt||null)})});
    if(r.status===401){ toast('⚠️ 로그인이 풀렸어요. 새로고침 해주세요'); btn.textContent=o; btn.disabled=false; return; }
    const res = await r.json();
    if(res.ok){
      const isSched = !!window.__scheduleAt;
      toast(isSched ? '예약됐어요! ⏰ 그 시각에 본글+답글 자동 게시' : '게시됐어요! 🚀');
      btn.textContent = isSched ? '예약 완료 ✓' : '게시 완료 ✓';
      if(res.post_url && !isSched){
        setTimeout(()=>{ if(confirm('게시됐어요! 지금 확인하러 갈까요?')) window.open(res.post_url,'_blank'); }, 300);
      }
    }
    else if(res.need_connect){ toast('설정에서 SNS 연결 먼저'); go('settings'); btn.textContent=o; btn.disabled=false; }
    else {
      toast('게시 실패: '+(res.error || r.status) + (res.detail ? ' / '+String(res.detail).slice(0,80) : ''));
      if(res.detail) console.log('게시 실패 상세:', res.detail);
      btn.textContent=o; btn.disabled=false;
    }
  }catch(e){ toast('게시 오류: '+(e.message||e)); btn.textContent=o; btn.disabled=false; }
}

// 게시물 목록
async function loadPosts(status, btn){
  if(btn){ document.querySelectorAll('.ptab').forEach(t=>t.classList.remove('on')); btn.classList.add('on'); }
  const box = document.getElementById('postList');
  if(!box) return;
  box.innerHTML = '<div class="empty">불러오는 중…</div>';
  try{
    const q = (status && status!=='all') ? '?status='+status : '';
    const d = await (await fetch('/api/posts'+q)).json();
    if(!d.ok || !d.posts.length){ box.innerHTML = '<div class="empty">아직 게시물이 없어요</div>'; return; }
    box.innerHTML = d.posts.map(p=>{
      const isPub = p.status==='published';
      const isSched = p.status==='scheduled';
      const isAuto = p.status==='autodraft';
      const badge = isPub ? '<span class="pbadge pub">게시완료</span>'
        : isSched ? '<span class="pbadge pub">⏰ 예약됨</span>'
        : (isAuto ? '<span class="pbadge draft">💾 자동저장</span>' : '<span class="pbadge draft">임시저장</span>');
      const preview = esc((p.content||'').slice(0,80));
      let actions;
      if(isPub || isSched){
        actions = p.post_url ? `<button class="btn-sm" onclick="window.open('${p.post_url}','_blank')">글 보기 ↗</button>` : '';
      } else {
        actions = `<button class="btn-sm" onclick="editPost(${p.id},this)">✏️ 편집</button>
          <button class="btn-sm mint" onclick="publishPost(${p.id},this)">🚀 게시</button>
          <button class="btn-sm" onclick="schedulePost(${p.id},this)">⏰ 예약</button>`;
      }
      return `<div class="post-item" id="post-${p.id}">
        <div class="post-top">${CH_LABEL(p.channel)} ${badge}</div>
        <div class="post-prev" id="prev-${p.id}">${preview}${(p.content||'').length>80?'…':''}</div>
        <div class="post-act">${actions}
          <button class="btn-sm ghost" onclick="deletePost(${p.id},this)">삭제</button></div>
      </div>`;
    }).join('');
  }catch(e){ box.innerHTML = '<div class="empty">불러오기 실패</div>'; }
}
// 임시저장 글 편집 (앱 안에서 직접 수정)
async function editPost(id, btn){
  const item = document.getElementById('post-'+id);
  if(!item) return;
  // 전체 내용 로드
  let full = '';
  try{ const d = await (await fetch('/api/post/'+id)).json(); if(d.ok) full = d.post.content; }
  catch(e){ toast('불러오기 실패'); return; }
  const prev = document.getElementById('prev-'+id);
  const act = item.querySelector('.post-act');
  // 편집 UI로 교체
  prev.innerHTML = `<textarea id="edit-${id}" style="width:100%;min-height:180px;background:var(--surface-2);border:1px solid var(--line);border-radius:8px;color:var(--text);font-size:13px;line-height:1.6;padding:10px;box-sizing:border-box">${esc(full)}</textarea>`;
  act.innerHTML = `<button class="btn-sm mint" onclick="saveEdit(${id},this)">💾 저장</button>
    <button class="btn-sm" onclick="publishEdited(${id},this)">🚀 저장 후 게시</button>
    <button class="btn-sm ghost" onclick="loadPosts('all')">취소</button>`;
}
async function saveEdit(id, btn){
  const content = document.getElementById('edit-'+id).value;
  btn.textContent='저장 중…';
  try{
    const r = await fetch('/api/post/'+id+'/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})});
    if((await r.json()).ok){ toast('수정했어요 ✏️'); loadPosts('all'); }
    else { toast('수정 실패'); btn.textContent='💾 저장'; }
  }catch(e){ toast('수정 실패'); btn.textContent='💾 저장'; }
}
async function publishEdited(id, btn){
  const content = document.getElementById('edit-'+id).value;
  btn.textContent='처리 중…'; btn.disabled=true;
  try{
    // 먼저 저장
    await fetch('/api/post/'+id+'/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})});
    // 게시
    const r = await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({post_id:id})});
    const res = await r.json();
    if(res.ok){ toast('게시됐어요! 🚀'); loadPosts('all'); }
    else if(res.need_connect){ toast('설정에서 SNS 연결 먼저'); go('settings'); }
    else { toast('게시 실패: '+(res.error||'')); btn.textContent='🚀 저장 후 게시'; btn.disabled=false; }
  }catch(e){ toast('게시 실패'); btn.textContent='🚀 저장 후 게시'; btn.disabled=false; }
}

// 저장된 글 예약 게시 (통계 → 내 게시물)
function schedulePost(id, btn){
  const item = document.getElementById('post-'+id);
  if(!item) return;
  const act = item.querySelector('.post-act');
  const now = new Date(Date.now() + 3600*1000);
  const p = n => String(n).padStart(2,'0');
  const def = `${now.getFullYear()}-${p(now.getMonth()+1)}-${p(now.getDate())}T${p(now.getHours())}:${p(now.getMinutes())}`;
  act.innerHTML = `<div style="width:100%">
    <div style="font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.1em;margin-bottom:6px">SCHEDULE</div>
    <input type="datetime-local" id="ps-${id}" value="${def}" style="width:100%;background:var(--surface-2);border:1px solid var(--line);border-radius:8px;color:var(--text);padding:10px;font-size:14px;margin-bottom:8px;color-scheme:dark">
    <div style="display:flex;gap:6px">
      <button class="btn-sm mint" style="flex:1" onclick="doSchedulePost(${id},this)">⏰ 이 시각에 예약</button>
      <button class="btn-sm ghost" onclick="loadPosts('all')">취소</button>
    </div></div>`;
}
async function doSchedulePost(id, btn){
  const el = document.getElementById('ps-'+id);
  if(!el || !el.value){ toast('시각을 골라주세요'); return; }
  const t = new Date(el.value);
  if(isNaN(t.getTime()) || t <= new Date()){ toast('미래 시각을 골라주세요'); return; }
  btn.textContent='예약 중…'; btn.disabled=true;
  try{
    const accIds = {};
    const picked = (window.__pickedAccount||{})['threads'];
    if(picked) accIds['threads'] = picked;
    const r = await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({post_id:id, scheduled_for:t.toISOString(), account_ids:accIds})});
    const res = await r.json();
    if(res.ok){ toast('예약됐어요! ⏰ 본글+답글 자동 게시'); loadPosts('all'); }
    else { toast('예약 실패: '+(res.error||'')); btn.textContent='⏰ 이 시각에 예약'; btn.disabled=false; }
  }catch(e){ toast('예약 실패'); btn.textContent='⏰ 이 시각에 예약'; btn.disabled=false; }
}

async function publishPost(id, btn){
  btn.textContent='게시 중…'; btn.disabled=true;
  try{
    const r = await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({post_id:id})});
    const res = await r.json();
    if(res.ok){ toast('게시됐어요! 🚀'); loadPosts('all',document.querySelector('.ptab')); }
    else if(res.need_connect){ toast('설정에서 SNS 연결 먼저'); go('settings'); }
    else { toast(res.error||'게시 실패'); btn.textContent='게시하기'; btn.disabled=false; }
  }catch(e){ toast('게시 실패'); btn.textContent='게시하기'; btn.disabled=false; }
}
async function deletePost(id, btn){
  if(!confirm('이 게시물을 삭제할까요?')) return;
  try{
    const r = await fetch('/api/post/'+id,{method:'DELETE'});
    if((await r.json()).ok){ btn.closest('.post-item').remove(); toast('삭제됐어요'); }
  }catch(e){ toast('삭제 실패'); }
}

// 연결된 SNS 계정 목록 로드 (게시 대상 선택용)
async function loadSnsAccounts(){
  try{
    const d = await (await fetch('/api/sns-accounts')).json();
    window.__snsAccounts = d.accounts || [];
    renderSnsAccounts();
  }catch(e){ window.__snsAccounts=[]; }
}
function renderSnsAccounts(){
  const el = document.getElementById('snsAccList');
  if(!el) return;
  const accts = window.__snsAccounts || [];
  if(!accts.length){ el.innerHTML=''; return; }
  const byPlat = {threads:'🧵',instagram:'📷',twitter:'𝕏',facebook:'📘',tiktok:'🎵'};
  el.innerHTML = '<div style="font-size:12px;color:var(--text-2);margin-top:10px">연결된 계정 '+accts.length+'개</div>' +
    accts.map(a=>`<div class="acc-chip">${byPlat[a.platform]||'📱'} ${esc(a.name)} <span style="opacity:.6">(${a.platform})</span></div>`).join('');
}

function copyProfileUrl(btn){
  const t = document.getElementById('profileUrl').textContent;
  copyText(t, btn);
}

// ── 통계/사용량 ──
async function loadStats(){
  try{
    const d = await (await fetch('/api/stats')).json();
    if(!d.ok) return;
    const el = document.getElementById('totalClicks');
    if(el) el.textContent = (d.total_clicks||0).toLocaleString();
    const CH = {blog:'📝',insta:'📷',threads:'🧵',x:'𝕏',youtube:'▶️',etc:'🔗'};
    const box = document.getElementById('topLinks');
    if(box){
      const withClicks = (d.top||[]).filter(t=>t.clicks>0);
      if(!withClicks.length){
        box.innerHTML = '<div style="text-align:center;color:var(--muted);font-size:13px;padding:16px 0">아직 클릭이 없어요. 프로필 주소를 인스타에 걸어보세요!</div>';
      } else {
        box.innerHTML = '<div style="font-size:12px;color:var(--text-2);font-weight:700;margin:16px 0 6px">가장 많이 클릭된 링크</div>' +
          withClicks.map(t=>`<div class="top-link"><span class="tl-ic">${CH[t.channel]||'🔗'}</span><span class="tl-name">${esc(t.product_name||'쿠팡 상품')}</span><span class="tl-clicks">${t.clicks}</span></div>`).join('');
      }
    }
  }catch(e){}
}

function renderUsage(me){
  const u = me.usage||{link_count:0,draft_count:0};
  const lim = me.limits||{link:30,draft:5};
  const pro = me.plan==='pro';
  const bar = (cur,max)=> pro ? '무제한' : `${cur} / ${max}`;
  const pct = (cur,max)=> pro ? 20 : Math.min(100, cur/max*100);
  const el = document.getElementById('usageCard');
  if(el) el.innerHTML = `
    <div class="usage-row"><div class="top-lbl"><span>쿠팡 링크</span><span>${bar(u.link_count,lim.link)}</span></div>
      <div class="bar"><i style="width:${pct(u.link_count,lim.link)}%"></i></div></div>
    <div class="usage-row"><div class="top-lbl"><span>블로그 초안</span><span>${bar(u.draft_count,lim.draft)}</span></div>
      <div class="bar"><i style="width:${pct(u.draft_count,lim.draft)}%"></i></div></div>
    ${pro?'':'<div style="margin-top:12px;padding:11px;background:var(--surface-2);border:1px solid var(--mint-deep);border-radius:10px;text-align:center;font-size:12px;color:var(--mint-bright);font-weight:600">Pro로 업그레이드하면 전부 무제한</div>'}`;
}

// ── 키 등록 ──
function renderKeyStatus(me){
  const el = document.getElementById('keyStatus');
  if(el) el.innerHTML = me.has_key
    ? '<span style="color:var(--mint-deep);font-weight:700">✓ 내 파트너스 키 등록됨</span>'
    : '아직 등록 안 됨 — 등록하면 내 수익으로 링크가 만들어져요';
}
async function saveKey(){
  const access = document.getElementById('k_access').value.trim();
  const secret = document.getElementById('k_secret').value.trim();
  const btn = document.getElementById('keyBtn');
  const msg = document.getElementById('keyMsg');
  msg.innerHTML = "";
  if(!access||!secret){ msg.innerHTML=`<div class="msg msg-err">access/secret 둘 다 입력하세요</div>`; return; }
  btn.classList.add('loading');
  try{
    const d = await (await fetch('/api/key',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({access,secret})})).json();
    if(!d.ok){ msg.innerHTML=`<div class="msg msg-err">${d.error||'저장 실패'}</div>`; return; }
    msg.innerHTML=`<div class="msg msg-ok">${d.message||'저장됐어요'}</div>`;
    document.getElementById('k_access').value=''; document.getElementById('k_secret').value='';
    refreshMe();
  }catch(e){ msg.innerHTML=`<div class="msg msg-err">서버 연결 실패</div>`; }
  finally{ btn.classList.remove('loading'); }
}

// ── 유틸 ──
function copyText(text, btn){
  navigator.clipboard.writeText(text).then(()=>{
    if(btn){ const o=btn.textContent; btn.textContent='복사됨'; btn.classList.add('done');
      setTimeout(()=>{btn.textContent=o; btn.classList.remove('done');},1500); }
  });
}
function esc(s){ return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function toast(m){
  const t=document.createElement('div'); t.className='toast'; t.textContent=m;
  document.body.appendChild(t); setTimeout(()=>t.remove(),2500);
}

boot();


// 하단 페이저: 섹션으로 점프
function jumpSec(n, el){
  document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));
  if(el) el.classList.add('on');
  const cards = document.querySelectorAll('#page-make .step-card');
  const target = cards[n-1];
  if(target) target.scrollIntoView({behavior:'smooth', block:'start'});
}
// 스크롤에 따라 페이저 활성 갱신
window.addEventListener('scroll', ()=>{
  const cards = [...document.querySelectorAll('#page-make .step-card')];
  if(!cards.length) return;
  let idx = 0;
  cards.forEach((c,i)=>{ if(c.getBoundingClientRect().top < window.innerHeight*0.4) idx = i; });
  document.querySelectorAll('.pg').forEach((p,i)=>p.classList.toggle('on', i===idx));
}, {passive:true});


// ── 스텝3 입력 폼 ──
window.__attachedImages = [];
function clearPicked(){
  const el = document.getElementById('pickedProd');
  if(el) el.classList.add('hidden');
  window.__lastResult = null;
  const l = document.getElementById('w_link'); if(l) l.value = '';
}
function showPicked(name, link){
  const el = document.getElementById('pickedProd');
  const nm = document.getElementById('pickedName');
  if(el && nm){ nm.textContent = name || ''; el.classList.remove('hidden'); }
  const l = document.getElementById('w_link');
  if(l && link) l.value = link;
}
function addImages(files){
  const box = document.getElementById('imgThumbs');
  if(!box || !files) return;
  [...files].slice(0, 12 - window.__attachedImages.length).forEach(f=>{
    const rd = new FileReader();
    rd.onload = e => {
      window.__attachedImages.push(e.target.result);
      renderThumbs();
    };
    rd.readAsDataURL(f);
  });
}
function renderThumbs(){
  const box = document.getElementById('imgThumbs');
  if(!box) return;
  box.innerHTML = window.__attachedImages.map((src,i)=>`<img src="${src}" onclick="removeImage(${i})" title="탭해서 삭제">`).join('');
}
function removeImage(i){
  window.__attachedImages.splice(i,1);
  renderThumbs();
}
