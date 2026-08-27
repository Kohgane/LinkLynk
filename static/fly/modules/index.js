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
  window.SWEFM = {
    waitViewer,
    version: "0.2",
    _btnQueue: [],
    _registerButtonImpl: null,
    registerButton: function(cfg) {
      try {
        if (window.SWEFM._registerButtonImpl) {
          window.SWEFM._registerButtonImpl(cfg);
        } else {
          window.SWEFM._btnQueue.push(cfg);
        }
      } catch(e) {
        console.warn("[swefm] registerButton error", e);
      }
    }
  };
  log("modules ready");

  // 서브모듈 동적 로드
  const BASE = (function(){
    try {
      const scripts = document.querySelectorAll("script[src]");
      for(let s of scripts){
        if(s.src && s.src.includes("modules/index.js")){
          const u = new URL(s.src, location.href);
          return u.href.replace(/index\.js.*$/, "");
        }
      }
    } catch(e){ /* 무시 */ }
    return "modules/";
  })();

  const MODULES = ["launcher.js","favorites.js","replay.js","hud.js","share.js","compare.js","camera-feel.js","foreground.js","settings.js","flight-sound.js"];
  let loaded = false;
  const _loadedMods = [];

  function loadModules(){
    if(loaded) return;
    loaded = true;
    MODULES.forEach(function(mod){
      try {
        import(BASE + mod).then(function(){
          _loadedMods.push(mod);
          console.log("[swefm] loaded", mod);
        }).catch(function(err){
          console.warn("[swefm] failed", mod, err);
          // import 실패 시 script 태그로 폴백
          try {
            var s = document.createElement("script");
            s.src = BASE + mod;
            s.onload = function(){ _loadedMods.push(mod); console.log("[swefm] loaded", mod); };
            s.onerror = function(e2){ console.warn("[swefm] failed", mod, e2); };
            document.head.appendChild(s);
          } catch(e2){ console.warn("[swefm] failed", mod, e2); }
        });
      } catch(e){
        console.warn("[swefm] failed", mod, e);
        // import() 자체 미지원 환경
        try {
          var s = document.createElement("script");
          s.src = BASE + mod;
          s.onload = function(){ _loadedMods.push(mod); console.log("[swefm] loaded", mod); };
          s.onerror = function(e2){ console.warn("[swefm] failed", mod, e2); };
          document.head.appendChild(s);
        } catch(e2){ console.warn("[swefm] failed", mod, e2); }
      }
    });
  }

  window.SWEFM.debug = function(){
    try {
      var viewer = (window.SWEF && window.SWEF.viewer) || window.viewer;
      console.table({
        loadedModules: _loadedMods.join(", ") || "(none)",
        "window.SWEF": !!(window.SWEF),
        viewer: !!(viewer),
        "swefm-DOM count": document.querySelectorAll("[id^=swefm-]").length
      });
    } catch(e){
      console.warn("[swefm] debug error", e);
    }
  };

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
