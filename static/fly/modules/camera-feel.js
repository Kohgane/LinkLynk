/* camera-feel.js — Cesium 카메라 필름/핸드헬드 느낌
 * 규칙: preRender 상대 오프셋 적용 + 다음 프레임 역적용으로 누적 드리프트 방지
 * 저장키: swefm_camfeel (off|subtle|cinematic)
 */
(function () {
  "use strict";

  var STORAGE_KEY = "swefm_camfeel";
  var PRESETS = ["off", "subtle", "cinematic"];
  var PRESET_CONFIG = {
    off: { noiseMinDeg: 0, noiseMaxDeg: 0, overshootMaxDeg: 0 },
    subtle: { noiseMinDeg: 0.05, noiseMaxDeg: 0.16, overshootMaxDeg: 0.24 },
    cinematic: { noiseMinDeg: 0.09, noiseMaxDeg: 0.30, overshootMaxDeg: 0.40 }
  };

  var MAX_TOTAL_OFFSET_RAD = degToRad(0.5);
  var OVERSHOOT_DURATION_SEC = 0.15;
  var EARTH_RADIUS_M = 6378137;

  var state = {
    preset: loadPreset(),
    initialized: false,
    launcherRegistered: false,
    viewer: null,
    removePreRender: null,
    lastApplied: zeroOffset(),
    lastTsMs: 0,
    lastCarto: null,
    lastHpr: null,
    prevTurnSpeed: 0,
    prevRates: { yaw: 0, pitch: 0, roll: 0 },
    overshoot: { active: false, startTsMs: 0, yawAmp: 0, pitchAmp: 0, rollAmp: 0 },
    phases: {
      yaw: [Math.random() * Math.PI * 2, Math.random() * Math.PI * 2, Math.random() * Math.PI * 2],
      pitch: [Math.random() * Math.PI * 2, Math.random() * Math.PI * 2, Math.random() * Math.PI * 2],
      roll: [Math.random() * Math.PI * 2, Math.random() * Math.PI * 2, Math.random() * Math.PI * 2]
    }
  };

  function degToRad(d) { return d * Math.PI / 180; }
  function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function zeroOffset() { return { yaw: 0, pitch: 0, roll: 0 }; }

  function normalizeRad(a) {
    var p = Math.PI * 2;
    var r = a % p;
    if (r > Math.PI) r -= p;
    if (r < -Math.PI) r += p;
    return r;
  }

  function hasOffset(o) {
    return !!(o && (o.yaw || o.pitch || o.roll));
  }

  function safeGetPreset(v) {
    return PRESETS.indexOf(v) !== -1 ? v : "subtle";
  }

  function loadPreset() {
    try {
      return safeGetPreset(localStorage.getItem(STORAGE_KEY));
    } catch (e) {
      return "subtle";
    }
  }

  function savePreset(preset) {
    try {
      localStorage.setItem(STORAGE_KEY, preset);
    } catch (e) {
      console.warn("[swefm/camfeel] preset 저장 실패", e);
    }
  }

  function showStatus(msg) {
    try {
      var id = "swefm-camfeel-toast";
      var el = document.getElementById(id);
      if (!el) {
        el = document.createElement("div");
        el.id = id;
        el.style.cssText = "position:fixed;bottom:70px;left:12px;z-index:99999;" +
          "background:rgba(0,0,0,.78);color:#fff;border-radius:6px;padding:8px 12px;" +
          "font-size:12px;line-height:1.4;pointer-events:none;opacity:0;transition:opacity .25s;";
        document.body.appendChild(el);
      }
      el.textContent = msg;
      el.style.opacity = "1";
      clearTimeout(el._hideTimer);
      el._hideTimer = setTimeout(function () {
        el.style.opacity = "0";
      }, 1800);
    } catch (e) {
      console.warn("[swefm/camfeel] 상태 표시 실패", e);
    }
  }

  function applyOffset(cam, offset) {
    if (!cam || !offset) return;
    cam.lookRight(offset.yaw);
    cam.lookUp(offset.pitch);
    cam.twistRight(offset.roll);
  }

  function revertOffset(cam, offset) {
    if (!cam || !offset) return;
    cam.twistRight(-offset.roll);
    cam.lookUp(-offset.pitch);
    cam.lookRight(-offset.yaw);
  }

  function clearLastApplied() {
    try {
      if (!state.viewer || !state.viewer.camera) return;
      if (!hasOffset(state.lastApplied)) return;
      revertOffset(state.viewer.camera, state.lastApplied);
    } catch (e) {
      console.warn("[swefm/camfeel] 오프셋 원복 실패", e);
    } finally {
      state.lastApplied = zeroOffset();
    }
  }

  function pseudoSimplex3(tSec, phases, f1, f2, f3) {
    var n = Math.sin((Math.PI * 2 * f1 * tSec) + phases[0]) +
      0.5 * Math.sin((Math.PI * 2 * f2 * tSec) + phases[1]) +
      0.25 * Math.sin((Math.PI * 2 * f3 * tSec) + phases[2]);
    return n / 1.75;
  }

  function estimateSpeedMps(carto, prevCarto, dtSec) {
    if (!carto || !prevCarto || dtSec <= 0) return 0;
    var meanLat = (carto.latitude + prevCarto.latitude) * 0.5;
    var dNorth = (carto.latitude - prevCarto.latitude) * EARTH_RADIUS_M;
    var dEast = (carto.longitude - prevCarto.longitude) * EARTH_RADIUS_M * Math.cos(meanLat);
    var dUp = (carto.height - prevCarto.height);
    var dist = Math.sqrt((dNorth * dNorth) + (dEast * dEast) + (dUp * dUp));
    return dist / dtSec;
  }

  function buildNoiseOffset(nowMs, speedMps) {
    var cfg = PRESET_CONFIG[state.preset] || PRESET_CONFIG.subtle;
    var speedNorm = clamp(speedMps / 450, 0, 1);
    var ampDeg = lerp(cfg.noiseMaxDeg, cfg.noiseMinDeg, speedNorm);
    var ampRad = degToRad(ampDeg);
    var t = nowMs / 1000;

    return {
      yaw: ampRad * pseudoSimplex3(t, state.phases.yaw, 0.45, 1.10, 2.55),
      pitch: ampRad * pseudoSimplex3(t, state.phases.pitch, 0.55, 1.35, 2.85),
      roll: (ampRad * 0.65) * pseudoSimplex3(t, state.phases.roll, 0.40, 0.90, 2.40)
    };
  }

  function triggerOvershoot(nowMs, maxAmpRad) {
    var prevRates = state.prevRates;
    var base = clamp(state.prevTurnSpeed * 0.055, degToRad(0.06), maxAmpRad);

    var yawDir = prevRates.yaw >= 0 ? 1 : -1;
    var pitchDir = prevRates.pitch >= 0 ? 1 : -1;
    var rollDir = prevRates.roll >= 0 ? 1 : -1;

    state.overshoot = {
      active: true,
      startTsMs: nowMs,
      yawAmp: base * yawDir,
      pitchAmp: base * 0.70 * pitchDir,
      rollAmp: base * 0.30 * rollDir
    };
  }

  function buildOvershootOffset(nowMs) {
    if (!state.overshoot.active) return zeroOffset();

    var ageSec = (nowMs - state.overshoot.startTsMs) / 1000;
    if (ageSec >= OVERSHOOT_DURATION_SEC || ageSec < 0) {
      state.overshoot.active = false;
      return zeroOffset();
    }

    var t = ageSec / OVERSHOOT_DURATION_SEC;
    var spring = Math.sin(t * Math.PI * 2.2) * Math.exp(-3.0 * t);

    return {
      yaw: state.overshoot.yawAmp * spring,
      pitch: state.overshoot.pitchAmp * spring,
      roll: state.overshoot.rollAmp * spring
    };
  }

  function clampTotalOffset(offset) {
    var len = Math.sqrt(offset.yaw * offset.yaw + offset.pitch * offset.pitch + offset.roll * offset.roll);
    if (!isFinite(len) || len <= MAX_TOTAL_OFFSET_RAD || len === 0) return offset;
    var s = MAX_TOTAL_OFFSET_RAD / len;
    return {
      yaw: offset.yaw * s,
      pitch: offset.pitch * s,
      roll: offset.roll * s
    };
  }

  function onPreRender() {
    try {
      var viewer = state.viewer;
      if (!viewer || !viewer.camera) return;

      if (hasOffset(state.lastApplied)) {
        revertOffset(viewer.camera, state.lastApplied);
        state.lastApplied = zeroOffset();
      }

      var nowMs = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
      if (state.preset === "off") {
        state.lastTsMs = nowMs;
        state.lastCarto = viewer.camera.positionCartographic || null;
        state.lastHpr = { heading: viewer.camera.heading, pitch: viewer.camera.pitch, roll: viewer.camera.roll || 0 };
        state.prevTurnSpeed = 0;
        state.prevRates = { yaw: 0, pitch: 0, roll: 0 };
        state.overshoot.active = false;
        return;
      }

      var cam = viewer.camera;
      var carto = cam.positionCartographic || null;
      var hpr = { heading: cam.heading, pitch: cam.pitch, roll: cam.roll || 0 };

      if (!state.lastTsMs || !state.lastHpr) {
        state.lastTsMs = nowMs;
        state.lastCarto = carto;
        state.lastHpr = hpr;
        return;
      }

      var dtSec = Math.max((nowMs - state.lastTsMs) / 1000, 1 / 240);

      var speedMps = estimateSpeedMps(carto, state.lastCarto, dtSec);

      var dh = normalizeRad(hpr.heading - state.lastHpr.heading);
      var dp = normalizeRad(hpr.pitch - state.lastHpr.pitch);
      var dr = normalizeRad(hpr.roll - state.lastHpr.roll);
      var rates = {
        yaw: dh / dtSec,
        pitch: dp / dtSec,
        roll: dr / dtSec
      };

      var turnSpeed = Math.sqrt((rates.yaw * rates.yaw) + (rates.pitch * rates.pitch) + (0.35 * rates.roll * rates.roll));
      var maxOvershootRad = degToRad((PRESET_CONFIG[state.preset] || PRESET_CONFIG.subtle).overshootMaxDeg);
      if (!state.overshoot.active && state.prevTurnSpeed > 0.35 && turnSpeed < state.prevTurnSpeed * 0.28) {
        triggerOvershoot(nowMs, maxOvershootRad);
      }

      var noise = buildNoiseOffset(nowMs, speedMps);
      var overshoot = buildOvershootOffset(nowMs);
      var total = clampTotalOffset({
        yaw: noise.yaw + overshoot.yaw,
        pitch: noise.pitch + overshoot.pitch,
        roll: noise.roll + overshoot.roll
      });

      applyOffset(cam, total);
      state.lastApplied = total;

      state.lastTsMs = nowMs;
      state.lastCarto = carto;
      state.lastHpr = hpr;
      state.prevTurnSpeed = turnSpeed;
      state.prevRates = rates;
    } catch (e) {
      console.warn("[swefm/camfeel] preRender 처리 실패", e);
      state.lastApplied = zeroOffset();
    }
  }

  function attach(viewer) {
    if (!viewer || !viewer.scene || !viewer.scene.preRender) {
      console.warn("[swefm/camfeel] viewer.scene.preRender 없음");
      return;
    }
    if (state.removePreRender) return;

    state.viewer = viewer;
    viewer.scene.preRender.addEventListener(onPreRender);
    state.removePreRender = function () {
      try {
        viewer.scene.preRender.removeEventListener(onPreRender);
      } catch (e) {
        console.warn("[swefm/camfeel] preRender 해제 실패", e);
      }
      clearLastApplied();
      state.removePreRender = null;
    };
  }

  function cyclePreset() {
    var i = PRESETS.indexOf(state.preset);
    var next = PRESETS[(i + 1) % PRESETS.length];
    state.preset = next;
    savePreset(next);

    if (next === "off") {
      state.overshoot.active = false;
      clearLastApplied();
    }

    showStatus("카메라 필: " + next);
  }

  function registerLauncher() {
    if (state.launcherRegistered) return;

    if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
      window.SWEFM.registerButton({
        id: "swefm-camfeel",
        icon: "🎥",
        label: "카메라 필",
        onClick: cyclePreset
      });
      state.launcherRegistered = true;
    } else {
      console.warn("[swefm/camfeel] SWEFM.registerButton 없음 — 런처 등록 건너뜀");
    }
  }

  function cleanup() {
    try {
      if (state.removePreRender) state.removePreRender();
      else clearLastApplied();
    } catch (e) {
      console.warn("[swefm/camfeel] cleanup 실패", e);
    }
  }

  function initWithViewer(viewer) {
    if (!viewer) {
      console.warn("[swefm/camfeel] viewer 없음");
      return;
    }
    if (state.initialized) return;
    state.initialized = true;
    registerLauncher();
    attach(viewer);

    window.addEventListener("pagehide", cleanup);
    window.addEventListener("beforeunload", cleanup);
  }

  function init() {
    registerLauncher();

    try {
      if (window.SWEFM && typeof window.SWEFM.waitViewer === "function") {
        window.SWEFM.waitViewer(function (viewer) {
          initWithViewer(viewer);
        });
        return;
      }
    } catch (e) {
      console.warn("[swefm/camfeel] SWEFM.waitViewer 실패", e);
    }

    function tryInit(tries) {
      var viewer = (window.SWEF && window.SWEF.viewer) || window.viewer;
      if (viewer) {
        initWithViewer(viewer);
        return;
      }
      if (tries >= 20) {
        console.warn("[swefm/camfeel] viewer 준비 대기 종료");
        return;
      }
      setTimeout(function () { tryInit(tries + 1); }, 500);
    }

    window.addEventListener("swef:ready", function () {
      var viewer = (window.SWEF && window.SWEF.viewer) || window.viewer;
      initWithViewer(viewer);
    });

    tryInit(0);
  }

  init();
})();
