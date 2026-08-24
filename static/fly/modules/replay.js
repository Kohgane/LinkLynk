/* replay.js — 비행 리플레이 모듈
 * 목적: 자유비행 카메라 경로 샘플링 및 재생
 * 의존성: window.Cesium, window.SWEFM.waitViewer
 * 저장키: swefm_replays
 */
(function () {
  "use strict";

  const LS_REPLAYS = "swefm_replays";
  const SAMPLE_INTERVAL = 200;   // ms
  const MAX_DURATION = 5 * 60 * 1000; // 5분
  const MAX_SAMPLES = MAX_DURATION / SAMPLE_INTERVAL; // 1500
  const MAX_SLOTS = 5;

  /* ── 유틸 ── */
  function loadJSON(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch (e) { return fallback; }
  }
  function saveJSON(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { console.warn("[swefm/replay] save failed", e); }
  }
  function rad2deg(r) { return r * 180 / Math.PI; }

  function getCameraFrame(viewer) {
    try {
      const C = window.Cesium;
      let carto;
      if (viewer.camera.positionCartographic) {
        carto = viewer.camera.positionCartographic;
      } else if (C && C.Cartographic && C.Cartesian3) {
        carto = C.Cartographic.fromCartesian(viewer.camera.position);
      } else return null;
      return {
        lat: rad2deg(carto.latitude),
        lon: rad2deg(carto.longitude),
        alt: carto.height,
        heading: viewer.camera.heading || 0,
        pitch: viewer.camera.pitch || 0,
        roll: viewer.camera.roll || 0,
        t: Date.now()
      };
    } catch (e) { return null; }
  }

  function lerp(a, b, t) { return a + (b - a) * t; }
  function lerpFrame(f1, f2, t) {
    return {
      lat: lerp(f1.lat, f2.lat, t),
      lon: lerp(f1.lon, f2.lon, t),
      alt: lerp(f1.alt, f2.alt, t),
      heading: lerp(f1.heading, f2.heading, t),
      pitch: lerp(f1.pitch, f2.pitch, t),
      roll: lerp(f1.roll, f2.roll, t)
    };
  }

  function applyCameraFrame(viewer, frame) {
    try {
      const C = window.Cesium;
      if (!C || !C.Cartesian3) return;
      if (typeof viewer.camera.setView === "function") {
        viewer.camera.setView({
          destination: C.Cartesian3.fromDegrees(frame.lon, frame.lat, frame.alt),
          orientation: { heading: frame.heading, pitch: frame.pitch, roll: frame.roll }
        });
      }
    } catch (e) { console.warn("[swefm/replay] setView failed", e); }
  }

  /* ── 상태 ── */
  let recording = false;
  let ringBuffer = [];
  let sampleTimer = null;
  let isPlaying = false;
  let playRaf = null;
  let overlay = null;
  let progressBar = null;
  let speedMult = 1;
  let currentViewer = null;
  let escHandler = null;

  /* ── 녹화 ── */
  function startRecording(viewer) {
    if (recording) return;
    recording = true;
    ringBuffer = [];
    sampleTimer = setInterval(() => {
      const frame = getCameraFrame(viewer);
      if (!frame) return;
      if (ringBuffer.length >= MAX_SAMPLES) ringBuffer.shift();
      ringBuffer.push(frame);
    }, SAMPLE_INTERVAL);
    console.log("[swefm/replay] 녹화 시작");
  }

  function stopRecording() {
    recording = false;
    clearInterval(sampleTimer);
    sampleTimer = null;
    console.log("[swefm/replay] 녹화 정지, frames:", ringBuffer.length);
  }

  /* ── 재생 ── */
  function startPlayback(viewer, frames, speed) {
    if (!frames || frames.length < 2) return console.warn("[swefm/replay] 프레임 부족");
    if (isPlaying) stopPlayback();
    isPlaying = true;
    speedMult = speed || 1;

    /* 오버레이(입력 차단) */
    overlay = document.createElement("div");
    overlay.id = "swefm-replay-overlay";
    Object.assign(overlay.style, {
      position: "fixed", inset: "0", zIndex: "9998",
      background: "transparent", cursor: "default"
    });
    document.body.appendChild(overlay);

    /* 진행바 컨테이너 */
    const progressContainer = document.createElement("div");
    progressContainer.id = "swefm-replay-progress";
    Object.assign(progressContainer.style, {
      position: "fixed", bottom: "20px", left: "50%", transform: "translateX(-50%)",
      width: "60vw", maxWidth: "400px", height: "8px",
      background: "rgba(0,0,0,0.5)", borderRadius: "4px", zIndex: "9999"
    });
    progressBar = document.createElement("div");
    Object.assign(progressBar.style, {
      height: "100%", width: "0%", background: "#4af", borderRadius: "4px",
      transition: "width 0.1s linear"
    });
    progressContainer.appendChild(progressBar);
    document.body.appendChild(progressContainer);

    const totalDuration = (frames[frames.length - 1].t - frames[0].t) / speedMult;
    const startWall = performance.now();

    function tick(now) {
      if (!isPlaying) return;
      const elapsed = (now - startWall) * speedMult;
      const progress = elapsed / (frames[frames.length - 1].t - frames[0].t);
      if (progressBar) progressBar.style.width = Math.min(progress * 100, 100) + "%";

      if (progress >= 1) { stopPlayback(); return; }

      /* 보간 */
      const targetT = frames[0].t + elapsed;
      let i = 0;
      while (i < frames.length - 2 && frames[i + 1].t < targetT) i++;
      const f1 = frames[i], f2 = frames[i + 1];
      const t = (targetT - f1.t) / (f2.t - f1.t);
      applyCameraFrame(viewer, lerpFrame(f1, f2, Math.max(0, Math.min(1, t))));

      playRaf = requestAnimationFrame(tick);
    }
    playRaf = requestAnimationFrame(tick);

    /* ESC 종료 */
    escHandler = (e) => { if (e.key === "Escape") stopPlayback(); };
    document.addEventListener("keydown", escHandler, { passive: false });
  }

  function stopPlayback() {
    isPlaying = false;
    if (playRaf) { cancelAnimationFrame(playRaf); playRaf = null; }
    if (overlay) { overlay.remove(); overlay = null; }
    const pc = document.getElementById("swefm-replay-progress");
    if (pc) pc.remove();
    progressBar = null;
    if (escHandler) { document.removeEventListener("keydown", escHandler); escHandler = null; }
    console.log("[swefm/replay] 재생 종료");
  }

  /* ── 슬롯 관리 ── */
  function saveSlot(name) {
    const replays = loadJSON(LS_REPLAYS, []);
    const slot = { name: name || ("리플레이 " + new Date().toLocaleTimeString()), frames: ringBuffer.slice(), ts: Date.now() };
    replays.unshift(slot);
    saveJSON(LS_REPLAYS, replays.slice(0, MAX_SLOTS));
  }

  function exportSlot(slot) {
    try {
      const blob = new Blob([JSON.stringify(slot, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "swefm_replay.json"; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { console.warn("[swefm/replay] export failed", e); }
  }

  function importSlot() {
    try {
      const input = document.createElement("input");
      input.type = "file"; input.accept = ".json";
      input.addEventListener("change", () => {
        const file = input.files[0]; if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
          try {
            const slot = JSON.parse(ev.target.result);
            if (!slot.frames || !Array.isArray(slot.frames)) return console.warn("[swefm/replay] invalid file");
            const replays = loadJSON(LS_REPLAYS, []);
            replays.unshift(slot);
            saveJSON(LS_REPLAYS, replays.slice(0, MAX_SLOTS));
            renderSlots();
          } catch (e) { console.warn("[swefm/replay] import parse failed", e); }
        };
        reader.readAsText(file);
      }, { passive: false });
      input.click();
    } catch (e) { console.warn("[swefm/replay] import failed", e); }
  }

  /* ── UI ── */
  function buildUI(viewer) {
    currentViewer = viewer;
    /* 자동 녹화 시작 */
    startRecording(viewer);

    const panel = document.createElement("div");
    panel.id = "swefm-replay-panel";
    Object.assign(panel.style, {
      position: "fixed", top: "60px", left: "280px", zIndex: "9999",
      background: "rgba(20,20,30,0.92)", color: "#eee", borderRadius: "8px",
      padding: "8px", width: "260px", maxHeight: "70vh", overflowY: "auto",
      fontFamily: "sans-serif", fontSize: "13px", display: "none",
      boxShadow: "0 2px 12px rgba(0,0,0,0.6)"
    });

    /* 녹화 제어 */
    const recRow = document.createElement("div");
    Object.assign(recRow.style, { display: "flex", gap: "4px", marginBottom: "6px" });

    const recStatus = document.createElement("span");
    recStatus.textContent = "🔴 녹화 중";

    const btnToggleRec = makeBtn("⏹ 정지", () => {
      if (recording) { stopRecording(); btnToggleRec.textContent = "⏺ 시작"; recStatus.textContent = "⚫ 정지"; }
      else { startRecording(viewer); btnToggleRec.textContent = "⏹ 정지"; recStatus.textContent = "🔴 녹화 중"; }
    });

    const btnSaveSlot = makeBtn("💾 저장", () => {
      const name = prompt("슬롯 이름:", "") || undefined;
      saveSlot(name);
      renderSlots();
    });

    const btnImport = makeBtn("⬆", importSlot);
    btnImport.title = "가져오기";

    recRow.append(recStatus, btnToggleRec, btnSaveSlot, btnImport);
    panel.appendChild(recRow);

    /* 재생 속도 */
    const speedRow = document.createElement("div");
    Object.assign(speedRow.style, { display: "flex", gap: "4px", marginBottom: "6px", alignItems: "center" });
    const speedLabel = document.createElement("span");
    speedLabel.textContent = "속도:";
    [0.5, 1, 2].forEach(s => {
      const b = makeBtn(s + "×", () => { speedMult = s; speedRow.querySelectorAll("button").forEach(btn => btn.style.fontWeight = "normal"); b.style.fontWeight = "bold"; });
      if (s === 1) b.style.fontWeight = "bold";
      speedRow.appendChild(b);
    });
    speedRow.prepend(speedLabel);
    panel.appendChild(speedRow);

    /* 슬롯 목록 */
    const slotEl = document.createElement("div");
    panel.appendChild(slotEl);

    function renderSlots() {
      slotEl.innerHTML = "<div style='margin-bottom:4px;font-weight:bold'>저장된 리플레이</div>";
      const replays = loadJSON(LS_REPLAYS, []);
      if (!replays.length) { slotEl.innerHTML += "<div>없음</div>"; return; }
      replays.forEach((slot, idx) => {
        const row = document.createElement("div");
        Object.assign(row.style, { display: "flex", alignItems: "center", gap: "4px", padding: "3px 0", borderBottom: "1px solid #333" });

        const btnPlay = makeBtn("▶ " + slot.name, () => startPlayback(viewer, slot.frames, speedMult));
        Object.assign(btnPlay.style, { flex: "1", textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });

        const btnExp = makeBtn("⬇", () => exportSlot(slot));
        btnExp.title = "내보내기";
        Object.assign(btnExp.style, { minWidth: "30px" });

        const btnDel = makeBtn("🗑", () => {
          const replays = loadJSON(LS_REPLAYS, []);
          replays.splice(idx, 1);
          saveJSON(LS_REPLAYS, replays);
          renderSlots();
        });
        Object.assign(btnDel.style, { minWidth: "30px" });

        row.append(btnPlay, btnExp, btnDel);
        slotEl.appendChild(row);
      });
    }

    panel.renderSlots = renderSlots;
    renderSlots();

    document.body.appendChild(panel);

    /* 토글 버튼 */
    const toggle = makeBtn("🎬", () => {
      const vis = panel.style.display === "none";
      panel.style.display = vis ? "block" : "none";
      if (vis) renderSlots();
    });
    toggle.id = "swefm-replay-toggle";
    Object.assign(toggle.style, {
      position: "fixed", top: "10px", left: "60px", zIndex: "10000",
      minWidth: "44px", minHeight: "44px", fontSize: "18px"
    });
    document.body.appendChild(toggle);
  }

  function makeBtn(text, onClick) {
    const b = document.createElement("button");
    b.textContent = text;
    Object.assign(b.style, {
      background: "rgba(60,60,80,0.9)", color: "#eee", border: "1px solid #555",
      borderRadius: "5px", padding: "4px 7px", cursor: "pointer",
      minHeight: "44px", fontSize: "13px"
    });
    if (onClick) b.addEventListener("click", onClick, { passive: false });
    return b;
  }

  /* ── 초기화 ── */
  try {
    window.SWEFM.waitViewer(function (viewer) {
      try { buildUI(viewer); console.log("[swefm/replay] ready"); }
      catch (e) { console.warn("[swefm/replay] buildUI failed", e); }
    });
  } catch (e) { console.warn("[swefm/replay] init failed", e); }

  window.SWEFM.replay = { startRecording, stopRecording, startPlayback, stopPlayback };
})();
