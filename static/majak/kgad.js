/* 고가네 앱 공용 광고 도우미 — 애드센스 한 단위(kg-apps-display) + 게임 광고(H5 adBreak)
 * ★정책: 디스플레이 광고를 '보면 보상' 으로 쓰면 애드센스 위반이다. 보상·중간 광고는 오직 adBreak(게임용 H5) 로만.
 *   adBreak 가 아직 안 열린 계정이면 광고 없이 그냥 보상을 준다(=넉넉하게). 과금 유도 없음.
 * ★아이폰 앱(웹뷰)·apps 호스트 밖에서는 광고를 아예 안 띄운다(앱은 나중에 애드몹).
 */
(function () {
  var PUB = 'ca-pub-2256918215878866', SLOT = '7542421318';
  function inApp() { try { return !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.kg); } catch (e) { return false; } }
  var ON = !inApp() && location.hostname === 'apps.kohganemultishop.org';
  window.adsbygoogle = window.adsbygoogle || [];
  var ex = document.querySelector('script[src*="adsbygoogle.js"]');
  if (ON && ex) { ex.setAttribute('data-ad-client', PUB); ex.setAttribute('data-ad-frequency-hint', '45s'); }
  if (ON && !ex) {
    var s = document.createElement('script'); s.async = true; s.crossOrigin = 'anonymous';
    s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + PUB;
    s.setAttribute('data-ad-client', PUB); s.setAttribute('data-ad-frequency-hint', '45s');
    document.head.appendChild(s);
  }
  var H5 = function (o) { window.adsbygoogle.push(o); };
  if (ON) { try { H5({ preloadAdBreaks: 'on', sound: 'on' }); } catch (e) {} }

  /* 배너: 자리(el) 안에 반응형 단위 하나. 안 채워지면 자리를 접어 빈 칸이 안 남게 */
  function banner(el, opt) {
    if (!el) return;
    if (!ON) { el.style.display = 'none'; return; }
    opt = opt || {};
    el.innerHTML = '';
    var lab = document.createElement('div');
    lab.textContent = opt.label || '광고'; lab.style.cssText = 'font-size:10px;letter-spacing:.08em;opacity:.45;margin:0 0 3px;text-align:center';
    var ins = document.createElement('ins');
    ins.className = 'adsbygoogle'; ins.style.display = 'block';
    if (opt.h) { ins.style.height = opt.h + 'px'; }
    ins.setAttribute('data-ad-client', PUB); ins.setAttribute('data-ad-slot', SLOT);
    ins.setAttribute('data-ad-format', opt.format || 'auto');
    ins.setAttribute('data-full-width-responsive', 'true');
    el.appendChild(lab); el.appendChild(ins); el.style.display = '';
    try { window.adsbygoogle.push({}); } catch (e) {}
    setTimeout(function () {
      if (ins.getAttribute('data-ad-status') === 'unfilled' || ins.offsetHeight < 10) el.style.display = 'none';
    }, opt.wait || 3500);
  }

  /* 중간 광고(층·판 사이): adBreak 'next'. 없거나 안 열렸으면 그냥 지나간다 */
  function breakAd(name, done) {
    var called = false; function fin() { if (!called) { called = true; done && done(); } }
    if (!ON) return fin();
    try {
      H5({ type: 'next', name: name || 'break', adBreakDone: fin });
      setTimeout(fin, 9000);                     // 광고 쪽이 답이 없으면 게임을 막지 않는다
    } catch (e) { fin(); }
  }

  /* 보상: adBreak 'reward' 가 준비됐으면 보고 받기, 아니면 광고 없이 그냥 준다 */
  function reward(name, give, opt) {
    opt = opt || {};
    var given = false; function g(viaAd) { if (!given) { given = true; give(!!viaAd); } }
    if (!ON) return g(false);
    var shown = false;
    try {
      H5({
        type: 'reward', name: name || 'reward',
        beforeReward: function (showAdFn) { shown = true; showAdFn(); },
        adViewed: function () { g(true); },
        adDismissed: function () { opt.onSkip && opt.onSkip(); },
        adBreakDone: function (info) { if (!shown) g(false); }
      });
      setTimeout(function () { if (!shown) g(false); }, 2500);
    } catch (e) { g(false); }
  }
  window.KGAD = { on: ON, banner: banner, breakAd: breakAd, reward: reward };
})();
