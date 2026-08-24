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
  window.SWEFM = { waitViewer, version: "0.1" };
  log("modules ready");
})();
