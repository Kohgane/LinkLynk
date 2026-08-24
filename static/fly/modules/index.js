/* SWEF modules — 진입점 (Copilot 작업 영역)
 * 규칙: index.html 수정 금지. window.SWEF 훅과 자체 UI(swefm- 접두)만 사용.
 * 저장키는 swefm_ 접두, 기존 ef_* 키는 침범 금지.
 */
(function(){
  "use strict";
  const log = (...a)=>console.log("[swefm]",...a);
  function waitViewer(cb, tries){
    tries = tries||0;
    const v = (window.SWEF && window.SWEF.viewer) || window.viewer;
    if (v) return cb(v);
    if (tries > 20) return log("viewer 없음 — 모듈 대기 종료");
    setTimeout(()=>waitViewer(cb, tries+1), 500);
  }

  /* registerButton: launcher.js 로드 전 호출될 경우 큐에 저장 */
  const _btnQueue = [];
  function registerButton(cfg){
    try {
      if(typeof window.SWEFM._launcherItems !== "undefined"){
        // launcher.js 가 _launcherItems를 설정했으면 위임
        // (launcher.js 에서 덮어씌움)
      }
      _btnQueue.push(cfg);
    } catch(e){ console.warn("[swefm] registerButton 실패", e); }
  }

  /* debug: 각 모듈 로드·DOM 존재 여부 출력 */
  function debug(){
    try {
      const MODS = ["launcher.js","favorites.js","replay.js","hud.js","share.js","compare.js"];
      const domIds = {
        "launcher.js": "swefm-launcher",
        "favorites.js": "swefm-favs-btn",
        "replay.js": "swefm-replay-btn",
        "hud.js": "swefm-hud-toggle",
        "share.js": "swefm-share-panel",
        "compare.js": "swefm-compare-panel"
      };
      const rows = MODS.map(function(m){
        const id = domIds[m];
        const el = id ? document.getElementById(id) : null;
        return { module: m, dom_id: id||"-", dom_exists: el ? "✓" : "✗" };
      });
      if(typeof console.table === "function"){ console.table(rows); }
      else { rows.forEach(function(r){ console.log("[swefm/debug]", JSON.stringify(r)); }); }
      log("등록된 런처 버튼 큐:", _btnQueue.map(function(b){ return b.id||b.label; }));
    } catch(e){ console.warn("[swefm] debug 실패", e); }
  }

  window.SWEFM = { waitViewer, version: "0.3", registerButton, debug, _btnQueue };
  log("modules ready");

  // 서브모듈 동적 로드
  const BASE = (function(){
    try {
      const scripts = document.querySelectorAll("script[src]");
      for(let s of scripts){
        if(s.src && s.src.includes("modules/index.js")){
          return s.src.replace("index.js","");
        }
      }
    } catch(e){ /* 무시 */ }
    return "modules/";
  })();

  const MODULES = ["launcher.js","favorites.js","replay.js","hud.js","share.js","compare.js"];
  let loaded = false;

  function loadModules(){
    if(loaded) return;
    loaded = true;
    MODULES.forEach(function(mod){
      try {
        import(BASE + mod).catch(function(){
          // import 실패 시 script 태그로 폴백
          try {
            var s = document.createElement("script");
            s.src = BASE + mod;
            s.onerror = function(){ console.warn("[swefm] 모듈 로드 실패:", mod); };
            document.head.appendChild(s);
          } catch(e2){ console.warn("[swefm] 모듈 삽입 실패:", mod, e2); }
        });
      } catch(e){
        // import() 자체 미지원 환경
        try {
          var s = document.createElement("script");
          s.src = BASE + mod;
          s.onerror = function(){ console.warn("[swefm] 모듈 로드 실패:", mod); };
          document.head.appendChild(s);
        } catch(e2){ console.warn("[swefm] 모듈 삽입 실패:", mod, e2); }
      }
    });
  }

  window.addEventListener("swef:ready", function(){ loadModules(); });
  if(window.SWEF && window.SWEF.viewer){ loadModules(); }
  // DOMContentLoaded 후에도 시도 (viewer 준비 전에 index.js가 실행된 경우)
  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", function(){
      setTimeout(loadModules, 200);
    });
  } else {
    setTimeout(loadModules, 200);
  }
})();
