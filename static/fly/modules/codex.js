/* codex.js — 탐험 도감 패널
 * 목적: SWEF 수집·미션 진행 현황을 한 화면에 표시
 * 데이터: localStorage 읽기 전용 (swef_gods, swef_kr, swef_portals, swef_gate1~4, swef_visits, swef_stars)
 * 저장키: 없음 (읽기 전용)
 */
(function () {
  "use strict";

  const ID = "swefm-codex";
  const PANEL_ID = "swefm-codex-panel";
  const STYLE_ID = "swefm-codex-style";

  /* ── 중복 초기화 방지 ── */
  if (document.getElementById(PANEL_ID)) return;

  /* ── localStorage 읽기 헬퍼 (읽기 전용, 쓰기 금지) ── */
  function readArr(key) {
    try {
      const v = JSON.parse(localStorage.getItem(key));
      return Array.isArray(v) ? v : [];
    } catch (e) {
      return [];
    }
  }

  function readGate(n) {
    try {
      return localStorage.getItem("swef_gate" + n) === "1";
    } catch (e) {
      return false;
    }
  }

  /* ── 진행 데이터 수집 ── */
  function collectData() {
    const gods    = readArr("swef_gods");
    const kr      = readArr("swef_kr");
    const portals = readArr("swef_portals");
    const visits  = readArr("swef_visits");
    const stars   = readArr("swef_stars");

    const gate1 = readGate(1);
    const gate2 = readGate(2);
    const gate3 = readGate(3);
    const gate4 = readGate(4);

    const godsN    = Math.min(gods.length,    4);
    const krN      = Math.min(kr.length,      4);
    const portalsN = Math.min(portals.length, 18);
    const gatesN   = [gate1, gate2, gate3, gate4].filter(Boolean).length;

    const completed = godsN + krN + portalsN + gatesN;
    const pct = Math.round(completed / 30 * 100);

    const allGates = gate1 && gate2 && gate3 && gate4;

    return {
      godsN, krN, portalsN, gatesN,
      gate1, gate2, gate3, gate4, allGates,
      visitsN: visits.length,
      starsN:  stars.length,
      completed, pct
    };
  }

  /* ── 스타일 주입 ── */
  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const css = `
#${PANEL_ID} {
  position: fixed; inset: 0; z-index: 99999;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,.55);
  font-family: 'Segoe UI', sans-serif;
}
#${PANEL_ID}.hidden { display: none; }
#${PANEL_ID} .cdx-box {
  position: relative;
  background: rgba(12,16,26,.96);
  color: #e8eaf0;
  border: 1px solid rgba(255,209,102,.25);
  border-radius: 16px;
  padding: 24px 20px 20px;
  width: min(92vw, 420px);
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 40px rgba(0,0,0,.7);
}
#${PANEL_ID} .cdx-close {
  position: absolute; top: 12px; right: 14px;
  background: none; border: none; color: #aaa;
  font-size: 20px; cursor: pointer; line-height: 1;
  padding: 4px 8px; border-radius: 6px;
}
#${PANEL_ID} .cdx-close:hover { color: #ffd166; }
#${PANEL_ID} .cdx-banner {
  text-align: center; font-size: 15px; font-weight: 700;
  color: #ffd166;
  background: rgba(255,209,102,.1);
  border: 1px solid rgba(255,209,102,.4);
  border-radius: 8px; padding: 8px 12px; margin-bottom: 16px;
}
#${PANEL_ID} .cdx-gauge-wrap {
  display: flex; flex-direction: column; align-items: center; margin-bottom: 20px;
}
#${PANEL_ID} .cdx-gauge-wrap svg { display: block; }
#${PANEL_ID} .cdx-gauge-pct {
  font-size: 22px; font-weight: 700; color: #ffd166; margin-top: 8px;
}
#${PANEL_ID} .cdx-gauge-sub { font-size: 12px; color: #8a8fa8; margin-top: 2px; }
#${PANEL_ID} .cdx-section-title {
  font-size: 13px; font-weight: 700; color: #ffd166;
  text-transform: uppercase; letter-spacing: .08em;
  margin: 0 0 10px; border-bottom: 1px solid rgba(255,209,102,.2); padding-bottom: 4px;
}
#${PANEL_ID} .cdx-row {
  display: flex; flex-direction: column; gap: 4px; margin-bottom: 14px;
}
#${PANEL_ID} .cdx-item {
  display: flex; align-items: center; gap: 6px; font-size: 14px; line-height: 1.5;
}
#${PANEL_ID} .cdx-hint {
  font-size: 12px; color: #8a8fa8; margin-left: 22px;
}
#${PANEL_ID} .cdx-check { margin-left: auto; font-size: 15px; }
`;
    const el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    document.head.appendChild(el);
  }

  /* ── 원형 게이지 SVG 생성 ── */
  function buildGaugeSVG(pct) {
    const r = 52, cx = 64, cy = 64, stroke = 10;
    const circ = 2 * Math.PI * r;
    const dash = (pct / 100) * circ;
    return `<svg width="128" height="128" viewBox="0 0 128 128" aria-hidden="true">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
    stroke="rgba(255,209,102,.15)" stroke-width="${stroke}"/>
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
    stroke="#ffd166" stroke-width="${stroke}"
    stroke-dasharray="${dash.toFixed(2)} ${(circ - dash).toFixed(2)}"
    stroke-dashoffset="0"
    stroke-linecap="round"
    transform="rotate(-90 ${cx} ${cy})"/>
</svg>`;
  }

  /* ── 패널 HTML 빌드 ── */
  function buildPanelHTML(d) {
    const banner = d.allGates
      ? `<div class="cdx-banner">👑 모든 전설을 깨운 자</div>`
      : "";

    const gauge = `
<div class="cdx-gauge-wrap">
  ${buildGaugeSVG(d.pct)}
  <div class="cdx-gauge-pct">${d.pct}%</div>
  <div class="cdx-gauge-sub">전체 완성률 (${d.completed}/30)</div>
</div>`;

    const checkMark = (done) => done ? `<span class="cdx-check">✅</span>` : "";

    const row1 = `
<div class="cdx-item">
  <span>🐲 사신의 시험 ${d.godsN}/4</span>
  ${checkMark(d.godsN >= 4)}
</div>
${d.godsN < 4 ? `<div class="cdx-hint">네 수호신을 모두 타 보라</div>` : ""}`;

    const row2 = `
<div class="cdx-item">
  <span>🏯 수호자의 길 ${d.krN}/4</span>
  ${checkMark(d.krN >= 4)}
</div>
${d.krN < 4 ? `<div class="cdx-hint">한반도의 숨은 수호자를 찾아라</div>` : ""}`;

    const row3 = `
<div class="cdx-item">
  <span>🌀 차원 여행자 ${d.portalsN}/18</span>
  ${checkMark(d.portalsN >= 18)}
</div>
${d.portalsN < 18 ? `<div class="cdx-hint">차원의 문을 더 발견하라</div>` : ""}`;

    const row4 = `
<div class="cdx-item">
  <span>🌠 여정자의 증표 ${d.gatesN}/4</span>
  ${checkMark(d.allGates)}
</div>
${!d.allGates ? `<div class="cdx-hint">전설의 관문을 하나씩 깨워라</div>` : ""}`;

    return `
<div role="dialog" aria-labelledby="cdx-title" class="cdx-box">
  <button class="cdx-close" aria-label="도감 닫기">✕</button>
  ${banner}
  <h2 id="cdx-title" style="margin:0 0 14px;font-size:17px;color:#ffd166;">📖 탐험 도감</h2>
  ${gauge}
  <p class="cdx-section-title">미션</p>
  <div class="cdx-row">${row1}${row2}${row3}${row4}</div>
  <p class="cdx-section-title">여정</p>
  <div class="cdx-row">
    <div class="cdx-item"><span>📍 발자국 ${d.visitsN}곳</span></div>
    <div class="cdx-item"><span>⭐ 별자리 ${d.starsN}곳</span></div>
  </div>
</div>`;
  }

  /* ── 패널 생성/삽입 ── */
  function createPanel() {
    const overlay = document.createElement("div");
    overlay.id = PANEL_ID;
    overlay.className = "hidden";
    overlay.setAttribute("aria-modal", "true");
    document.body.appendChild(overlay);
    return overlay;
  }

  /* ── 패널 열기/닫기 ── */
  let panel = null;
  let keyListener = null;
  let bgListener = null;

  function closePanel() {
    if (!panel) return;
    panel.classList.add("hidden");
    if (keyListener) {
      document.removeEventListener("keydown", keyListener);
      keyListener = null;
    }
    if (bgListener) {
      panel.removeEventListener("click", bgListener);
      bgListener = null;
    }
  }

  function openPanel() {
    if (!panel) return;
    try {
      const d = collectData();
      panel.innerHTML = buildPanelHTML(d);
      panel.classList.remove("hidden");

      /* 닫기 버튼 */
      const closeBtn = panel.querySelector(".cdx-close");
      if (closeBtn) closeBtn.addEventListener("click", closePanel);

      /* 배경 클릭 닫기 */
      if (bgListener) panel.removeEventListener("click", bgListener);
      bgListener = function (e) {
        if (e.target === panel) closePanel();
      };
      panel.addEventListener("click", bgListener);

      /* ESC 닫기 */
      if (keyListener) document.removeEventListener("keydown", keyListener);
      keyListener = function (e) {
        if (e.key === "Escape") closePanel();
      };
      document.addEventListener("keydown", keyListener);
    } catch (e) {
      console.warn("[swefm/codex] openPanel 실패", e);
    }
  }

  function togglePanel() {
    if (!panel) return;
    if (panel.classList.contains("hidden")) {
      openPanel();
    } else {
      closePanel();
    }
  }

  /* ── 초기화 ── */
  function init() {
    try {
      injectStyle();
      panel = createPanel();

      if (!window.SWEFM || typeof window.SWEFM.registerButton !== "function") {
        console.warn("[swefm/codex] SWEFM.registerButton 없음 — 런처 등록 생략");
        return;
      }

      window.SWEFM.registerButton({
        id: ID,
        icon: "📖",
        label: "도감",
        onClick: togglePanel
      });
    } catch (e) {
      console.warn("[swefm/codex] 초기화 실패, 모듈 비활성화", e);
    }
  }

  init();
})();
