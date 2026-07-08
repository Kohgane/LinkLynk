// LinkLynk 프론트 로직

// ── PWA: service worker 등록 + 설치 유도 ──
let deferredPrompt = null;
if('serviceWorker' in navigator){
  window.addEventListener('load', ()=> navigator.serviceWorker.register('/sw.js').catch(()=>{}));
}
window.addEventListener('beforeinstallprompt', (e)=>{
  e.preventDefault(); deferredPrompt = e;
  showInstallBtn();
});
function showInstallBtn(){
  if(document.getElementById('installBar')) return;
  const bar = document.createElement('div');
  bar.id='installBar';
  bar.style.cssText='position:fixed;bottom:92px;left:50%;transform:translateX(-50%);width:calc(100% - 40px);max-width:440px;background:var(--mint);color:var(--mint-ink);padding:13px 16px;border-radius:14px;font-weight:700;font-size:14px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 8px 32px rgba(34,233,164,.35);z-index:60;animation:pageIn .4s';
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
async function boot(){
  try{
    const r = await fetch('/api/me');
    const d = await r.json();
    if(d.ok){ showApp(d); }
    else { showAuth(); }
  }catch(e){ showAuth(); }
}

function showAuth(){
  document.getElementById('authView').classList.remove('hidden');
  document.getElementById('appView').classList.add('hidden');
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
  document.getElementById('avatar').textContent = initial;
  // 프로필 주소
  const base = location.origin;
  document.getElementById('profileUrl').textContent = me.handle ? `${base}/u/${me.handle}` : '프로필 주소 미설정';
  window.__me = me;
  renderUsage(me);
  renderKeyStatus(me);
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
  if(page==='stats'){ refreshMe(); loadStats(); }
  else if(page==='settings'){ refreshMe(); }
}
async function refreshMe(){
  try{ const me = await (await fetch('/api/me')).json(); if(me.ok){ window.__me=me; renderUsage(me); renderKeyStatus(me); renderHandle(me);} }catch(e){}
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
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on'); channel = el.dataset.ch;
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
      ? {deeplink:url, channel, tone:'friendly', productName:pname}
      : {url, channel, tone:'friendly', productName:pname};
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
function renderResult(d){
  const link = d.deeplink;
  const draft = d.blogDraft;
  window.__lastResult = d;
  let draftUI = '';
  if(draft){
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
      <div class="card">
        <div class="card-lbl">내 간편 링크</div>
        <div class="linkline"><div class="url">${link}</div>
          <button class="btn-copy" onclick="copyText('${link}', this)">복사</button></div>
      </div>
      ${draftUI}
    </div>`;
  document.getElementById('result').scrollIntoView({behavior:'smooth',block:'start'});
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
    <div class="disc">💡 본글 먼저 올리고, 답글로 1→2→3→4→5 순서로 이어달면 돼요. 링크는 답글 4·5에만.</div>
    <div class="card-actions">
      <button class="btn btn-mint" onclick="copyText(${JSON.stringify(parts.join('\\n\\n')).replace(/"/g,'&quot;')}, this)">전체 복사</button>
      <button class="btn btn-ghost" onclick="window.open('https://threads.net','_blank')">쓰레드 열기</button>
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
    <div class="disc">💡 이미지 올리고 캡션에 붙여넣기. 링크는 프로필(내 프로필 주소)에 걸어두세요.</div>
    <div class="card-actions">
      <button class="btn btn-mint" onclick="copyText(document.getElementById('draft').innerText, this)">캡션 복사</button>
      ${tags?`<button class="btn btn-ghost" onclick="copyText(${JSON.stringify(tags).replace(/"/g,'&quot;')}, this)">해시태그만 복사</button>`:''}
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
  const c = (str||'').trim().charCodeAt(0);
  if(c >= 0xAC00 && c <= 0xD7A3){ return CHO[Math.floor((c-0xAC00)/588)]; }
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
        html += `<div class="nia-item" style="animation-delay:${Math.min(gi*20,300)}ms">
          <div class="nia-body" onclick="copyText('${l.deeplink}', this.parentNode.querySelector('.nia-act'))">
            <div class="nia-name ${(!l.product_name||l.product_name==='쿠팡 상품'||l.product_name==='이 상품')?'noname':''}">${esc(dispName)} <span style="font-size:12px;opacity:.6">${CH_ICON[l.channel]||''}</span></div>
            <div class="nia-sub">${timeAgo(l.created_at)} · ${l.deeplink.replace('https://link.coupang.com','쿠팡')}</div>
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
  }catch(e){}
}

// ── 나이아가라 인덱스 드래그 스크롤 + 큰 글자 오버레이 ──
function attachRailDrag(){
  const rail = document.querySelector('#nia-rail-fixed .nia-rail') || document.querySelector('.nia-rail');
  if(!rail) return;
  const spans = [...rail.querySelectorAll('span')];
  const list = document.querySelector('.nia-list');
  let active=false, lastKey=null, rafId=null;
  let targetY=0, smoothY=0;
  let lastMoveT=0, velocity=0, lastRawY=0;   // 속도 추적
  let settleTimer=null, settled=false;       // 멈춤 감지

  // 곡선 렌더. settle(멈춤)이면 정점 크게, 이동중이면 작게 (영상: 움직일땐 15px, 멈추면 37px)
  function render(y, big){
    // 목표 실측 곡선: σ50(완만한 넓은 활) + 정점 돌출 중앙 살짝 넘게
    const peakScale = big ? 3.0 : 2.0;
    const sigmaWide = 78;                 // 아주 완만한 넓은 활 (더 부드럽게)
    const sigmaPeak = 22;                 // 정점도 부드럽게
    spans.forEach(s=>{
      const r = s.getBoundingClientRect();
      const cy = (r.top + r.bottom)/2;
      const dist = Math.abs(cy - y);
      const gWide = Math.exp(-(dist*dist)/(2*sigmaWide*sigmaWide));
      const gPeak = Math.exp(-(dist*dist)/(2*sigmaPeak*sigmaPeak));
      const scale = 1 + gPeak*(peakScale-1);
      // 돌출: 완만한 활 크게(중앙 살짝 넘게) + 정점 추가
      const shiftX = -gWide*185 - gPeak*35;   // 완만한 활 → 중앙 살짝 넘게
      s.style.transform = `translate3d(${shiftX}px,0,0) scale(${scale})`;
      const on = s.classList.contains('on');
      s.style.opacity = on ? (0.78 + gPeak*0.22) : (0.28 + gWide*0.4 + gPeak*0.3);
      s.style.color = (gPeak>0.3 && on) ? 'var(--mint-bright)' : (gPeak>0.3 ? 'var(--text)' : '');
      s.style.zIndex = gPeak>0.4 ? 6 : '';
    });
  }
  function reset(){ spans.forEach(s=>{ s.style.transform=''; s.style.opacity=''; s.style.color=''; s.style.zIndex=''; }); }

  function nearest(y){
    let best=null,bd=1e9;
    for(const s of spans){ const r=s.getBoundingClientRect(); const d=Math.abs((r.top+r.bottom)/2-y); if(d<bd){bd=d;best=s;} }
    return best;
  }

  // 리스트 페이드 (영상: 빠르게 이동중=숨김, 멈춤/느림=나타남)
  let listShown = null;
  function showList(show){
    if(!list || listShown===show) return;
    listShown = show;
    list.classList.remove('idle');
    list.style.transition = 'opacity .22s cubic-bezier(.22,1,.36,1)';
    list.style.opacity = show ? '1' : '0';
  }

  // 나이아가라: 드래그한 초성 그룹만 보이게, 나머지는 숨김
  let shownGroup = undefined;
  function showGroup(key){
    if(!list || shownGroup===key) return;
    shownGroup = key;
    const labels = list.querySelectorAll('.nia-glabel');
    const items = list.querySelectorAll('.nia-item');
    if(key===null){
      // 아무 그룹도 표시 안 함
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

  // 60fps 보간 — 적응형(멀면 빠르게 따라가고, 가까우면 부드럽게 안착)
  function loop(){
    const gap = Math.abs(targetY - smoothY);
    // 거리 클수록 빠르게(0.5), 가까울수록 부드럽게(0.22) → 즉각적이되 스무스한 착지
    const lerp = gap > 80 ? 0.5 : (gap > 25 ? 0.34 : 0.22);
    smoothY += (targetY - smoothY) * lerp;
    if(gap < 0.4) smoothY = targetY;
    render(smoothY, settled && Math.abs(velocity)<0.4);
    if(active || Math.abs(targetY-smoothY) > 0.4) rafId=requestAnimationFrame(loop);
    else rafId=null;
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
    if(key!==lastKey){
      lastKey = key;
      const on = s.classList.contains('on');
      if(navigator.vibrate) navigator.vibrate(on?6:2);
      showGroup(on ? key : null);   // 활성 초성 그룹만 보이게 (나이아가라식)
    }
  }
  function end(){
    active=false; lastKey=null; settled=false;
    clearTimeout(settleTimer);
    if(rafId){ cancelAnimationFrame(rafId); rafId=null; }
    // 손 떼면 곡선이 부드럽게 풀리며 초성들이 일렬로 정렬
    let ease = 1;
    const releaseY = smoothY;
    (function relax(){
      ease *= 0.82;                       // 매 프레임 82%로 감쇠 → 부드럽게 0으로
      if(ease < 0.03){ reset(); return; }
      renderDamped(releaseY, ease);       // 곡선 크기를 ease배로 줄여가며 렌더
      requestAnimationFrame(relax);
    })();
    if(list){ list.classList.remove('idle'); list.style.opacity=''; }
  }
  // 풀림 전용 렌더 (기존 곡선을 ease배 축소)
  function renderDamped(y, ease){
    const sigmaWide=78, sigmaPeak=22;
    spans.forEach(s=>{
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

  // Pointer Events로 통합 — iOS/안드로이드/데스크탑 모두 동일 작동
  // (touch/mouse 따로 처리하면 안드로이드에서 좌표·타이밍 문제 발생)
  rail.addEventListener('pointerdown', e=>{
    e.preventDefault();
    active=true;
    lastRawY=e.clientY; lastMoveT=performance.now();
    try{ rail.setPointerCapture(e.pointerId); }catch(_){}
    moveTo(e.clientY);
  });
  rail.addEventListener('pointermove', e=>{
    if(!active) return;
    e.preventDefault();
    moveTo(e.clientY);
  });
  rail.addEventListener('pointerup', e=>{ if(active){ end(); try{ rail.releasePointerCapture(e.pointerId); }catch(_){} } });
  rail.addEventListener('pointercancel', end);
  rail.addEventListener('pointerleave', e=>{ /* capture 중이라 leave 무시 */ });
  // 안드로이드 크롬: 부모 스크롤/제스처가 레일 터치를 가로채지 않도록
  rail.addEventListener('touchstart', e=>e.preventDefault(), {passive:false});
  rail.addEventListener('touchmove', e=>e.preventDefault(), {passive:false});
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
