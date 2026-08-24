/* replay.js — 비행 리플레이
 * 목적: 자유비행 중 카메라 경로를 0.2s 간격 샘플링, 재생(보간), 속도 조절, 저장/불러오기
 * 의존성: window.SWEFM.waitViewer, window.Cesium
 * 저장키: swefm_replays
 */
(function () {
  "use strict";

  const KEY_REPLAYS = "swefm_replays";
  const MAX_SLOTS = 5;
  const SAMPLE_INTERVAL = 200;    // ms
  const MAX_DURATION = 5 * 60 * 1000; // 5분
  const MAX_FRAMES = MAX_DURATION / SAMPLE_INTERVAL; // 1500

  /* ── 스토리지 헬퍼 ── */
  function load(key, def) {
    try { return JSON.parse(localStorage.getItem(key)) || def; } catch { return def; }
  }
  function save(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch { console.warn("[swefm/replay] 저장 실패"); }
  }

  /* ── 카메라 프레임 추출 ── */
  function getFrame(viewer) {
    try {
      const cam = viewer.camera;
      let lat, lon, alt;
      if (cam.positionCartographic) {
        const c = cam.positionCartographic;
        const R = window.Cesium ? Cesium.Math.toDegrees : (r => r * 180 / Math.PI);
        lat = R(c.latitude); lon = R(c.longitude); alt = c.height;
      } else if (window.Cesium && Cesium.Cartographic && cam.position) {
        const c = Cesium.Cartographic.fromCartesian(cam.position);
        lat = Cesium.Math.toDegrees(c.latitude);
        lon = Cesium.Math.toDegrees(c.longitude);
        alt = c.height;
      } else return null;
      return { lat, lon, alt, heading: cam.heading, pitch: cam.pitch, roll: cam.roll || 0, ts: Date.now() };
    } catch { return null; }
  }

  /* ── 선형 보간 ── */
  function lerp(a, b, t) { return a + (b - a) * t; }
  function lerpFrame(f0, f1, t) {
    return {
      lat: lerp(f0.lat, f1.lat, t),
      lon: lerp(f0.lon, f1.lon, t),
      alt: lerp(f0.alt, f1.alt, t),
      heading: lerp(f0.heading, f1.heading, t),
      pitch: lerp(f0.pitch, f1.pitch, t),
      roll: lerp(f0.roll || 0, f1.roll || 0, t)
    };
  }

  /* ── 메인 로직 ── */
  function buildUI(viewer) {
    // 링버퍼
    let buffer = [];
    let recording = false;
    let recordTimer = null;

    // 재생 상태
    let playing = false;
    let playFrameIdx = 0;
    let playTimer = null;
    let playSpeed = 1;
    let inputBlockOverlay = null;
    let currentPath = null;

    /* 녹화 */
    function startRecording() {
      buffer = [];
      recording = true;
      recordTimer = setInterval(() => {
        try {
          const f = getFrame(viewer);
          if (!f) return;
          buffer.push(f);
          if (buffer.length > MAX_FRAMES) buffer.shift();
        } catch { /* 무시 */ }
      }, SAMPLE_INTERVAL);
      updateRecBtn();
    }

    function stopRecording() {
      recording = false;
      if (recordTimer) { clearInterval(recordTimer); recordTimer = null; }
      currentPath = buffer.length > 0 ? [...buffer] : null;
      updateRecBtn();
      renderSlots();
    }

    /* 재생 */
    function startPlayback(path, speed) {
      if (!path || path.length < 2) { console.warn("[swefm/replay] 경로 없음"); return; }
      if (!window.Cesium) { console.warn("[swefm/replay] Cesium 없음"); return; }
      playing = true;
      playSpeed = speed || 1;
      playFrameIdx = 0;
      currentPath = path;

      // 오버레이 (입력 차단)
      inputBlockOverlay = document.createElement("div");
      inputBlockOverlay.id = "swefm-replay-overlay";
      inputBlockOverlay.style.cssText = `position:fixed;inset:0;z-index:8900;cursor:not-allowed;`;
      inputBlockOverlay.addEventListener("touchstart", e => e.preventDefault(), { passive: false });
      inputBlockOverlay.addEventListener("mousedown", e => e.stopPropagation(), true);
      document.body.appendChild(inputBlockOverlay);

      updateProgress(0);
      progressBar.style.display = "flex";

      const interval = SAMPLE_INTERVAL / playSpeed;
      playTimer = setInterval(() => {
        if (playFrameIdx >= path.length - 1) { stopPlayback(); return; }
        try {
          const f0 = path[playFrameIdx], f1 = path[playFrameIdx + 1];
          const frame = lerpFrame(f0, f1, 0.5);
          viewer.camera.setView({
            destination: Cesium.Cartesian3.fromDegrees(frame.lon, frame.lat, frame.alt),
            orientation: { heading: frame.heading, pitch: frame.pitch, roll: frame.roll }
          });
        } catch (e) { console.warn("[swefm/replay] 재생 프레임 오류", e); }
        playFrameIdx++;
        updateProgress(playFrameIdx / (path.length - 1));
      }, interval);
    }

    function stopPlayback() {
      playing = false;
      if (playTimer) { clearInterval(playTimer); playTimer = null; }
      if (inputBlockOverlay && inputBlockOverlay.parentNode) {
        inputBlockOverlay.parentNode.removeChild(inputBlockOverlay);
        inputBlockOverlay = null;
      }
      progressBar.style.display = "none";
      renderSlots();
    }

    /* ESC 중단 */
    document.addEventListener("keydown", e => {
      if ((e.key === "Escape" || e.key === "Tab") && playing) {
        e.preventDefault();
        stopPlayback();
      }
    });

    /* 슬롯 저장/불러오기 */
    function saveToSlot(idx, path, name) {
      const replays = load(KEY_REPLAYS, []);
      while (replays.length <= idx) replays.push(null);
      replays[idx] = { name: name || `리플레이 ${idx + 1}`, frames: path, ts: Date.now() };
      replays.length = Math.min(replays.length, MAX_SLOTS);
      save(KEY_REPLAYS, replays);
    }

    function deleteSlot(idx) {
      const replays = load(KEY_REPLAYS, []);
      replays[idx] = null;
      save(KEY_REPLAYS, replays);
    }

    /* ── UI ── */
    const btn = document.createElement("button");
    btn.id = "swefm-replay-btn";
    btn.title = "리플레이";
    btn.textContent = "⏺";
    btn.style.cssText = `position:fixed;bottom:76px;right:12px;z-index:9000;
      width:44px;height:44px;border-radius:50%;border:none;background:rgba(0,0,0,.65);
      color:#FF6666;font-size:20px;cursor:pointer;touch-action:manipulation;`;
    document.body.appendChild(btn);

    const panel = document.createElement("div");
    panel.id = "swefm-replay-panel";
    panel.style.cssText = `display:none;position:fixed;bottom:130px;right:12px;z-index:9000;
      width:280px;max-height:70vh;overflow-y:auto;background:rgba(15,15,25,.92);
      color:#eee;border-radius:10px;padding:10px;font-size:13px;
      box-shadow:0 4px 20px rgba(0,0,0,.6);`;
    document.body.appendChild(panel);

    // 진행바
    const progressBar = document.createElement("div");
    progressBar.id = "swefm-replay-progress";
    progressBar.style.cssText = `display:none;position:fixed;bottom:0;left:0;right:0;z-index:9100;
      height:36px;background:rgba(0,0,0,.7);align-items:center;padding:0 12px;gap:8px;`;
    progressBar.innerHTML = `
      <span style="color:#aaa;font-size:11px">재생중 (ESC 중단)</span>
      <div id="swefm-replay-bar-track" style="flex:1;height:6px;background:rgba(255,255,255,.2);border-radius:3px">
        <div id="swefm-replay-bar-fill" style="height:100%;width:0%;background:#FF6666;border-radius:3px;transition:width .1s"></div>
      </div>
      <button id="swefm-replay-stop-btn" style="background:#c33;border:none;color:#fff;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px">중단</button>
    `;
    document.body.appendChild(progressBar);
    progressBar.querySelector("#swefm-replay-stop-btn").onclick = stopPlayback;

    function updateProgress(t) {
      const fill = document.getElementById("swefm-replay-bar-fill");
      if (fill) fill.style.width = `${(t * 100).toFixed(1)}%`;
    }

    function updateRecBtn() {
      btn.textContent = recording ? "⏹" : "⏺";
      btn.style.color = recording ? "#FF9900" : "#FF6666";
      btn.title = recording ? "녹화 중단" : "리플레이";
    }

    function renderSlots() {
      const replays = load(KEY_REPLAYS, []);
      const hasPath = currentPath && currentPath.length >= 2;
      const durSec = hasPath ? ((currentPath.length * SAMPLE_INTERVAL) / 1000).toFixed(0) : 0;

      panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <b>비행 리플레이</b>
          <button id="swefm-replay-close" style="background:none;border:none;color:#aaa;font-size:16px;cursor:pointer">✕</button>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
          <button id="swefm-rec-start" style="${bstyle('#933','#fff')}" ${recording ? "disabled" : ""}>⏺ 녹화 시작</button>
          <button id="swefm-rec-stop" style="${bstyle('#662','#fff')}" ${!recording ? "disabled" : ""}>⏹ 녹화 중단</button>
        </div>
        ${hasPath ? `
          <div style="background:rgba(255,255,255,.06);border-radius:6px;padding:6px 8px;margin-bottom:8px">
            <div style="color:#aaa;font-size:11px">현재 경로: ${currentPath.length}프레임 (${durSec}초)</div>
            <div style="display:flex;gap:6px;margin-top:6px;align-items:center;flex-wrap:wrap">
              <span style="font-size:11px;color:#aaa">속도:</span>
              <select id="swefm-replay-speed" style="background:#222;color:#eee;border:none;border-radius:4px;padding:2px 4px;font-size:11px">
                <option value="0.5">0.5×</option>
                <option value="1" selected>1×</option>
                <option value="2">2×</option>
              </select>
              <button id="swefm-replay-play" style="${bstyle('#226','#fff')}" ${playing ? "disabled" : ""}>▶ 재생</button>
              <button id="swefm-replay-save-slot" style="${bstyle('#242','#fff')}">💾 슬롯 저장</button>
            </div>
          </div>
        ` : `<div style="color:#777;margin-bottom:8px;font-size:12px">녹화된 경로 없음</div>`}
        <div style="font-weight:600;margin:4px 0;color:#88BBFF">저장된 리플레이</div>
        ${Array.from({ length: MAX_SLOTS }, (_, i) => {
          const r = replays[i];
          if (!r) return `<div style="color:#555;font-size:12px;padding:4px 0">슬롯 ${i + 1}: 비어 있음</div>`;
          const dur = ((r.frames.length * SAMPLE_INTERVAL) / 1000).toFixed(0);
          return `<div style="display:flex;align-items:center;gap:4px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.07)">
            <span style="flex:1;font-size:12px">${r.name} (${dur}초)</span>
            <button class="swefm-slot-play" data-idx="${i}" style="${bstyle('#226','#fff')} font-size:11px;padding:2px 6px">▶</button>
            <button class="swefm-slot-del" data-idx="${i}" style="background:none;border:none;color:#f66;cursor:pointer;padding:0 4px">✕</button>
          </div>`;
        }).join("")}
      `;

      panel.querySelector("#swefm-replay-close").onclick = () => { panel.style.display = "none"; };
      panel.querySelector("#swefm-rec-start").onclick = startRecording;
      panel.querySelector("#swefm-rec-stop").onclick = stopRecording;

      if (hasPath && !playing) {
        panel.querySelector("#swefm-replay-play").onclick = () => {
          const spd = parseFloat(panel.querySelector("#swefm-replay-speed").value) || 1;
          startPlayback(currentPath, spd);
          panel.style.display = "none";
        };
        panel.querySelector("#swefm-replay-save-slot").onclick = () => {
          const replays2 = load(KEY_REPLAYS, []);
          let slot = replays2.findIndex(r => !r);
          if (slot === -1) slot = 0;
          const name = prompt(`슬롯 ${slot + 1} 이름`, `리플레이 ${slot + 1}`);
          if (name === null) return;
          saveToSlot(slot, currentPath, name.trim());
          renderSlots();
        };
      }

      panel.querySelectorAll(".swefm-slot-play").forEach(el => {
        el.onclick = () => {
          const replays2 = load(KEY_REPLAYS, []);
          const r = replays2[+el.dataset.idx];
          if (r) { startPlayback(r.frames, 1); panel.style.display = "none"; }
        };
      });

      panel.querySelectorAll(".swefm-slot-del").forEach(el => {
        el.onclick = () => { deleteSlot(+el.dataset.idx); renderSlots(); };
      });
    }

    function bstyle(bg, fg) {
      return `background:${bg};color:${fg};border:none;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:11px;touch-action:manipulation;min-height:30px`;
    }

    btn.onclick = () => {
      if (recording) { stopRecording(); }
      else {
        if (panel.style.display === "none") { renderSlots(); panel.style.display = "block"; }
        else panel.style.display = "none";
      }
    };
  }

  /* ── 초기화 ── */
  function init() {
    try {
      window.SWEFM.waitViewer(viewer => {
        try { buildUI(viewer); } catch (e) { console.warn("[swefm/replay] UI 초기화 실패", e); }
      });
    } catch (e) {
      console.warn("[swefm/replay] 초기화 실패", e);
    }
  }

  init();
})();
