/* flight-sound.js — 비행 화면 사운드 (순수 WebAudio API)
 * 저장키: swefm_sound ("on" / "off", 기본 "off")
 * 외부 라이브러리 금지 / 네트워크 요청 금지
 */
(function () {
  "use strict";

  var STORAGE_KEY = "swefm_sound";
  var EARTH_RADIUS_M = 6378137;

  /* ── 상태 ── */
  var state = {
    enabled: false,
    initialized: false,
    gestureReady: false,   // 첫 사용자 제스처 후 true
    ctx: null,             // AudioContext
    masterGain: null,      // master gain (on/off 용)

    /* 풍절음 */
    windSource: null,
    windFilter: null,
    windGain: null,

    /* 고도 앰비언스 (서브베이스) */
    subOsc: null,
    subGain: null,
    subActive: false,

    /* 부스터 스웰 */
    boostActive: false,
    boostLastMs: 0,
    boostCooldownMs: 1200,

    /* 속도 추정용 */
    lastCarto: null,
    lastTickMs: 0,
    lastSpeedMps: 0,
    lastAccel: 0,

    /* 갱신 타이머 */
    intervalId: null,
    gestureHandler: null
  };

  /* ── 유틸 ── */
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function loadEnabled() {
    try { return localStorage.getItem(STORAGE_KEY) === "on"; } catch (e) { return false; }
  }
  function saveEnabled(v) {
    try { localStorage.setItem(STORAGE_KEY, v ? "on" : "off"); } catch (e) {
      console.warn("[swefm/sound] 저장 실패", e);
    }
  }

  function showStatus(msg) {
    try {
      var id = "swefm-sound-toast";
      var el = document.getElementById(id);
      if (!el) {
        el = document.createElement("div");
        el.id = id;
        el.style.cssText =
          "position:fixed;bottom:70px;left:12px;z-index:99999;" +
          "background:rgba(0,0,0,.78);color:#fff;border-radius:6px;padding:8px 12px;" +
          "font-size:12px;line-height:1.4;pointer-events:none;opacity:0;transition:opacity .25s;";
        document.body.appendChild(el);
      }
      el.textContent = msg;
      el.style.opacity = "1";
      clearTimeout(el._hideTimer);
      el._hideTimer = setTimeout(function () { el.style.opacity = "0"; }, 1800);
    } catch (e) {
      console.warn("[swefm/sound] 상태 표시 실패", e);
    }
  }

  /* ── AudioContext 생성 ── */
  function createContext() {
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) { console.warn("[swefm/sound] WebAudio 미지원"); return false; }
      state.ctx = new Ctx();

      /* 마스터 게인 */
      state.masterGain = state.ctx.createGain();
      state.masterGain.gain.value = state.enabled ? 1.0 : 0.0;
      state.masterGain.connect(state.ctx.destination);

      buildWindLayer();
      buildSubLayer();

      state.gestureReady = true;
      return true;
    } catch (e) {
      console.warn("[swefm/sound] AudioContext 생성 실패", e);
      return false;
    }
  }

  /* ── 풍절음 레이어 ── */
  function buildWindLayer() {
    try {
      var ctx = state.ctx;
      /* 2초 화이트노이즈 버퍼 */
      var bufLen = Math.floor(ctx.sampleRate * 2);
      var buf = ctx.createBuffer(1, bufLen, ctx.sampleRate);
      var data = buf.getChannelData(0);
      for (var i = 0; i < bufLen; i++) data[i] = Math.random() * 2 - 1;

      var src = ctx.createBufferSource();
      src.buffer = buf;
      src.loop = true;

      var filter = ctx.createBiquadFilter();
      filter.type = "bandpass";
      filter.frequency.value = 200;
      filter.Q.value = 1.2;

      var gain = ctx.createGain();
      gain.gain.value = 0.02; // 잔류 앰비언스

      src.connect(filter);
      filter.connect(gain);
      gain.connect(state.masterGain);
      src.start();

      state.windSource = src;
      state.windFilter = filter;
      state.windGain = gain;
    } catch (e) {
      console.warn("[swefm/sound] 풍절음 레이어 생성 실패", e);
    }
  }

  /* ── 고도 앰비언스 (서브베이스) 레이어 ── */
  function buildSubLayer() {
    try {
      var ctx = state.ctx;

      var osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = 28;

      var gain = ctx.createGain();
      gain.gain.value = 0.0; // 처음엔 묵음

      osc.connect(gain);
      gain.connect(state.masterGain);
      osc.start();

      state.subOsc = osc;
      state.subGain = gain;
      state.subActive = false;

      /* 향후 확장점: 도시 소음(저고도), 새소리(중저고도) 등
         — 에셋 로드가 필요해 이번 범위에서는 제외 */
    } catch (e) {
      console.warn("[swefm/sound] 서브베이스 레이어 생성 실패", e);
    }
  }

  /* ── 속도 추정 ── */
  function estimateSpeed(carto, prevCarto, dtSec) {
    if (!carto || !prevCarto || dtSec <= 0) return 0;
    var meanLat = (carto.latitude + prevCarto.latitude) * 0.5;
    var dN = (carto.latitude - prevCarto.latitude) * EARTH_RADIUS_M;
    var dE = (carto.longitude - prevCarto.longitude) * EARTH_RADIUS_M * Math.cos(meanLat);
    var dU = (carto.height - prevCarto.height);
    return Math.sqrt(dN * dN + dE * dE + dU * dU) / dtSec;
  }

  /* ── 오디오 파라미터 갱신 (약 100ms 주기) ── */
  function updateAudio() {
    try {
      if (!state.ctx || !state.enabled) return;
      if (state.ctx.state === "suspended") return;

      var viewer = (window.SWEF && window.SWEF.viewer) || window.viewer;
      if (!viewer || !viewer.camera) return;

      var now = Date.now();
      var carto = viewer.camera.positionCartographic || null;
      var dtSec = state.lastTickMs ? Math.max((now - state.lastTickMs) / 1000, 0.05) : 0.1;
      var speed = estimateSpeed(carto, state.lastCarto, dtSec);

      if (!isFinite(speed) || speed < 0) speed = state.lastSpeedMps;
      var accel = dtSec > 0 ? (speed - state.lastSpeedMps) / dtSec : 0;

      state.lastCarto = carto;
      state.lastTickMs = now;
      state.lastAccel = accel;

      var RAMP = 0.2; // 초 단위 부드러운 전환 상수
      var t = state.ctx.currentTime;

      /* 풍절음 파라미터 */
      if (state.windFilter && state.windGain) {
        var speedNorm = clamp(speed / 2000, 0, 1);
        var targetFreq = 200 + speedNorm * (3500 - 200);
        var targetGain = 0.02 + speedNorm * (0.5 - 0.02);

        state.windFilter.frequency.setTargetAtTime(targetFreq, t, RAMP);
        state.windGain.gain.setTargetAtTime(targetGain, t, RAMP);
      }

      /* 고도 앰비언스 */
      if (state.subGain) {
        var altitude = carto ? carto.height : 0;
        if (altitude >= 2000 && !state.subActive) {
          state.subGain.gain.setTargetAtTime(0.06, t, 1.0); // ~3초 페이드인 (τ=1s)
          state.subActive = true;
        } else if (altitude < 2000 && state.subActive) {
          state.subGain.gain.setTargetAtTime(0.0, t, 0.5);
          state.subActive = false;
        }
      }

      /* 부스터 스웰: 속도 변화율 > 300 m/s² */
      if (Math.abs(accel) > 300) {
        var nowMs = now;
        var cooldownOk = nowMs - state.boostLastMs > state.boostCooldownMs;
        if (cooldownOk && !state.boostActive) {
          triggerBoostSwell(t);
          state.boostLastMs = nowMs;
        }
      }

      state.lastSpeedMps = speed;
    } catch (e) {
      console.warn("[swefm/sound] updateAudio 실패", e);
    }
  }

  /* ── 부스터 스웰 ── */
  function triggerBoostSwell(t) {
    try {
      if (!state.ctx) return;
      state.boostActive = true;

      var ctx = state.ctx;
      /* 0.3초 화이트노이즈 스웰 */
      var bufLen = Math.floor(ctx.sampleRate * 0.3);
      var buf = ctx.createBuffer(1, bufLen, ctx.sampleRate);
      var data = buf.getChannelData(0);
      for (var i = 0; i < bufLen; i++) data[i] = Math.random() * 2 - 1;

      var src = ctx.createBufferSource();
      src.buffer = buf;

      var gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0, t);
      gain.gain.linearRampToValueAtTime(0.15, t + 0.06);
      gain.gain.linearRampToValueAtTime(0.0, t + 0.3);

      src.connect(gain);
      gain.connect(state.masterGain);
      src.start(t);
      src.onended = function () {
        state.boostActive = false;
        try { gain.disconnect(); } catch (e2) { /* 무시 */ }
      };
    } catch (e) {
      console.warn("[swefm/sound] 부스터 스웰 실패", e);
      state.boostActive = false;
    }
  }

  /* ── 갱신 타이머 ── */
  function startInterval() {
    if (state.intervalId) return;
    state.intervalId = setInterval(updateAudio, 100);
  }

  function stopInterval() {
    if (state.intervalId) {
      clearInterval(state.intervalId);
      state.intervalId = null;
    }
  }

  /* ── AudioContext resume 헬퍼 ── */
  function tryResume(cb) {
    try {
      if (!state.ctx) {
        if (!createContext()) { if (cb) cb(false); return; }
      }
      if (state.ctx.state === "suspended") {
        state.ctx.resume().then(function () {
          if (cb) cb(true);
        }).catch(function (e) {
          console.warn("[swefm/sound] resume 실패", e);
          if (cb) cb(false);
        });
      } else {
        if (cb) cb(true);
      }
    } catch (e) {
      console.warn("[swefm/sound] tryResume 실패", e);
      if (cb) cb(false);
    }
  }

  /* ── ON / OFF ── */
  function soundOn() {
    state.enabled = true;
    saveEnabled(true);
    tryResume(function (ok) {
      if (!ok) { console.warn("[swefm/sound] AudioContext 활성화 실패"); return; }
      if (state.masterGain) {
        state.masterGain.gain.setTargetAtTime(1.0, state.ctx.currentTime, 0.1);
      }
      startInterval();
      showStatus("사운드 ON");
    });
  }

  function soundOff() {
    state.enabled = false;
    saveEnabled(false);
    stopInterval();
    if (state.ctx && state.masterGain) {
      try {
        state.masterGain.gain.setTargetAtTime(0.0, state.ctx.currentTime, 0.1);
        setTimeout(function () {
          try {
            if (state.ctx && state.ctx.state !== "suspended") {
              state.ctx.suspend().catch(function (e) {
                console.warn("[swefm/sound] suspend 실패", e);
              });
            }
          } catch (e) { console.warn("[swefm/sound] suspend 실패", e); }
        }, 400);
      } catch (e) { console.warn("[swefm/sound] OFF 처리 실패", e); }
    }
    showStatus("사운드 OFF");
  }

  /* ── 첫 사용자 제스처 처리 ── */
  function setupGestureListener() {
    if (state.gestureHandler) return;
    state.gestureHandler = function () {
      if (!state.gestureReady) {
        createContext();
        if (state.enabled) {
          tryResume(function () { startInterval(); });
        }
      }
      document.removeEventListener("pointerdown", state.gestureHandler, { once: true });
    };
    document.addEventListener("pointerdown", state.gestureHandler, { once: true });
  }

  /* ── 토글 ── */
  function toggle() {
    if (state.enabled) {
      soundOff();
    } else {
      soundOn();
    }
  }

  /* ── 런처 버튼 등록 ── */
  function registerLauncher() {
    if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
      window.SWEFM.registerButton({
        id: "swefm-sound",
        icon: "🔊",
        label: "사운드",
        onClick: toggle
      });
    } else {
      console.warn("[swefm/sound] SWEFM.registerButton 없음 — 런처 등록 건너뜀");
    }
  }

  /* ── 가시성/수명주기 ── */
  function setupLifecycle() {
    document.addEventListener("visibilitychange", function () {
      if (!state.ctx) return;
      if (document.hidden) {
        try { state.ctx.suspend().catch(function () {}); } catch (e) { /* 무시 */ }
      } else if (state.enabled) {
        tryResume(function () {});
      }
    });

    function cleanup() {
      stopInterval();
      try {
        if (state.ctx) state.ctx.close().catch(function () {});
      } catch (e) { /* 무시 */ }
    }
    window.addEventListener("pagehide", cleanup, { once: true });
    window.addEventListener("beforeunload", cleanup, { once: true });
  }

  /* ── 초기화 ── */
  function init() {
    try {
      state.enabled = loadEnabled(); // 기본 false (OFF)
      registerLauncher();
      setupGestureListener();
      setupLifecycle();

      /* enabled=true로 저장된 경우라도 제스처 전까지 AudioContext 생성 안 함 */
      /* 제스처 이후 startInterval 은 soundOn() 경로 또는 gestureHandler에서 처리 */
    } catch (e) {
      console.warn("[swefm/sound] init 실패", e);
    }
  }

  init();
})();
