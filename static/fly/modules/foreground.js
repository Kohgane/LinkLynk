/* foreground.js — CesiumJS 카메라 상대 근경 요소
 * 새떼 / 부유 입자 / 구름 파편
 * 저장키: swefm_fg (off|subtle|rich)
 * 규칙: 월드 고정 배치 금지 — 매 preRender에서 카메라 상대 좌표로 갱신
 *       매 프레임 새 객체 할당 금지 — scratch Cartesian3 재사용
 */
(function () {
  "use strict";

  var STORAGE_KEY = "swefm_fg";
  var PRESETS = ["off", "subtle", "rich"];

  // ── 프리셋 설정 ──────────────────────────────────────────────────────────
  var PRESET_CFG = {
    off:    { birdCount: 0,  particleCount: 0,  cloudEnabled: false },
    subtle: { birdCount: 14, particleCount: 40,  cloudEnabled: true  },
    rich:   { birdCount: 28, particleCount: 40,  cloudEnabled: true  }
  };

  var MAX_BIRD_ALT_M       = 2000;
  var PARTICLE_LO_MAX_ALT  = 800;
  var PARTICLE_HI_MIN_ALT  = 4000;
  var CLOUD_MIN_ALT        = 800;
  var CLOUD_MAX_ALT        = 3000;
  var HIGH_SPEED_THRESHOLD = 200;   // m/s

  // ── 스프라이트 생성 ──────────────────────────────────────────────────────
  function makeBirdCanvas() {
    try {
      var c = document.createElement("canvas");
      c.width = 24; c.height = 12;
      var ctx = c.getContext("2d");
      ctx.fillStyle = "rgba(0,0,0,0)";
      ctx.fillRect(0, 0, 24, 12);
      ctx.strokeStyle = "#111";
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(2, 6);
      ctx.quadraticCurveTo(6, 2, 12, 5);
      ctx.quadraticCurveTo(18, 2, 22, 6);
      ctx.stroke();
      return c.toDataURL();
    } catch (e) { return null; }
  }

  function makeCloudCanvas() {
    try {
      var c = document.createElement("canvas");
      c.width = 128; c.height = 64;
      var ctx = c.getContext("2d");
      var grd = ctx.createRadialGradient(64, 32, 4, 64, 32, 50);
      grd.addColorStop(0,   "rgba(255,255,255,0.55)");
      grd.addColorStop(0.5, "rgba(255,255,255,0.25)");
      grd.addColorStop(1,   "rgba(255,255,255,0)");
      ctx.clearRect(0, 0, 128, 64);
      ctx.ellipse(64, 32, 58, 28, 0, 0, Math.PI * 2);
      ctx.fillStyle = grd;
      ctx.fill();
      return c.toDataURL();
    } catch (e) { return null; }
  }

  // ── 상태 ─────────────────────────────────────────────────────────────────
  var state = {
    preset: loadPreset(),
    viewer: null,
    handler: null,

    // 카메라 속도 추정
    lastCarto: null,
    lastTsMs: 0,
    cameraSpeed: 0,

    // 새떼
    birds: [],
    birdColl: null,
    birdSpawnTimer: 0,
    birdNextSpawn: 0,
    birdActive: false,

    // 부유 입자
    particles: [],
    partColl: null,

    // 구름 파편
    clouds: [],
    cloudColl: null,
    cloudTimer: 0,
    cloudNextSpawn: 0,

    // scratch Cartesian3 (매 프레임 재사용)
    _sc0: null, _sc1: null, _sc2: null
  };

  // ── localStorage ─────────────────────────────────────────────────────────
  function loadPreset() {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      return PRESETS.indexOf(v) !== -1 ? v : "subtle";
    } catch (e) { return "subtle"; }
  }
  function savePreset(p) {
    try { localStorage.setItem(STORAGE_KEY, p); } catch (e) {}
  }

  // ── 수학 헬퍼 ─────────────────────────────────────────────────────────────
  function rnd(min, max) { return min + Math.random() * (max - min); }
  function rndInt(min, max) { return Math.floor(rnd(min, max + 1)); }
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

  // 카메라의 right/up/direction 기준 월드 좌표 계산 (scratch 재사용)
  function offsetWorld(camera, fwd, right, up, scr) {
    var Cs = window.Cesium;
    scr.x = camera.position.x + camera.direction.x * fwd
          + camera.right.x    * right
          + camera.up.x       * up;
    scr.y = camera.position.y + camera.direction.y * fwd
          + camera.right.y    * right
          + camera.up.y       * up;
    scr.z = camera.position.z + camera.direction.z * fwd
          + camera.right.z    * right
          + camera.up.z       * up;
    return scr;
  }

  // ── 카메라 속도 추정 ──────────────────────────────────────────────────────
  function updateCameraSpeed(scene) {
    var Cs = window.Cesium;
    var now = Date.now();
    var dt = (now - state.lastTsMs) / 1000;
    if (dt < 0.05) return;
    try {
      var carto = scene.camera.positionCartographic;
      if (state.lastCarto && dt > 0) {
        var dLon = (carto.longitude - state.lastCarto.longitude) * 6378137;
        var dLat = (carto.latitude  - state.lastCarto.latitude)  * 6378137;
        var dAlt = carto.height - state.lastCarto.height;
        var dist = Math.sqrt(dLon * dLon + dLat * dLat + dAlt * dAlt);
        state.cameraSpeed = dist / dt;
      }
      if (!state.lastCarto) state.lastCarto = Cs.Cartographic.clone(carto);
      else Cs.Cartographic.clone(carto, state.lastCarto);
    } catch (e) {}
    state.lastTsMs = now;
  }

  // ── 새떼 ─────────────────────────────────────────────────────────────────
  var BIRD_PROTO = {
    show: false,
    // 카메라 상대 오프셋 (스폰 시점 고정)
    fwd: 0, right: 0, up: 0,
    // boids 이동 벡터 (카메라 right/up 평면)
    vRight: 0, vUp: 0, vFwd: 0,
    age: 0, lifetime: 0
  };

  function initBirds(cfg) {
    var Cs = window.Cesium;
    if (!state.birdColl) {
      var imgUrl = makeBirdCanvas();
      state.birdColl = new Cs.BillboardCollection();
      state.viewer.scene.primitives.add(state.birdColl);
      var n = 28; // rich 최대치 미리 할당
      for (var i = 0; i < n; i++) {
        var b = Object.create(BIRD_PROTO);
        b.show  = false;
        b.fwd   = 0; b.right = 0; b.up = 0;
        b.vRight = 0; b.vUp = 0; b.vFwd = 0;
        b.age = 0; b.lifetime = 0;
        var bb = state.birdColl.add({
          show: false,
          position: Cs.Cartesian3.ZERO.clone(),
          image: imgUrl || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=",
          scale: 0.8,
          color: new Cs.Color(0.05, 0.05, 0.05, 0.9),
          pixelOffset: new Cs.Cartesian2(0, 0),
          eyeOffset: Cs.Cartesian3.ZERO.clone(),
          alignedAxis: Cs.Cartesian3.ZERO.clone(),
          sizeInMeters: false,
          width: 24, height: 12
        });
        b._bb = bb;
        state.birds.push(b);
      }
    }
    scheduleNextBirdSpawn();
  }

  function scheduleNextBirdSpawn() {
    state.birdNextSpawn = Date.now() + rnd(30000, 90000);
  }

  function spawnFlock(cfg) {
    var Cs = window.Cesium;
    var camera = state.viewer.scene.camera;
    var carto = camera.positionCartographic;
    if (carto.height > MAX_BIRD_ALT_M) return;

    var count = rndInt(12, cfg.birdCount);
    var side  = Math.random() < 0.5 ? 1 : -1;
    var baseFwd   = rnd(300, 900);
    var baseRight = side * rnd(80, 250);
    var baseUp    = rnd(-30, 30);

    // 무리 속도: 옆으로 스쳐 지나가게
    var groupVRight = -side * rnd(4, 12);
    var groupVUp    = rnd(-1, 1);
    var groupVFwd   = rnd(-3, 3);

    var used = 0;
    for (var i = 0; i < state.birds.length && used < count; i++) {
      var b = state.birds[i];
      if (b.show) continue;
      b.fwd   = baseFwd   + rnd(-40, 40);
      b.right = baseRight + rnd(-30, 30);
      b.up    = baseUp    + rnd(-15, 15);
      b.vRight = groupVRight + rnd(-0.5, 0.5);
      b.vUp    = groupVUp    + rnd(-0.3, 0.3);
      b.vFwd   = groupVFwd   + rnd(-0.5, 0.5);
      b.age      = 0;
      b.lifetime = rnd(12, 25);
      b.show     = true;
      b._bb.show = true;
      used++;
    }
  }

  function updateBirds(dt, cfg) {
    var Cs   = window.Cesium;
    var cam  = state.viewer.scene.camera;
    var carto = cam.positionCartographic;
    var altOk = carto.height <= MAX_BIRD_ALT_M;
    var s = state._sc0;

    // boids 간단 응집: 무리 중심 끌림
    var cx = 0, cy = 0, cz_b = 0, cnt = 0;
    for (var i = 0; i < state.birds.length; i++) {
      var b = state.birds[i];
      if (!b.show) continue;
      cx += b.right; cy += b.up; cz_b += b.fwd; cnt++;
    }
    if (cnt > 0) { cx /= cnt; cy /= cnt; cz_b /= cnt; }

    for (var j = 0; j < state.birds.length; j++) {
      var b = state.birds[j];
      if (!b.show) continue;
      b.age += dt;
      if (b.age > b.lifetime || !altOk) {
        b.show = false; b._bb.show = false; continue;
      }
      // boids 응집 (가볍게)
      if (cnt > 1) {
        b.vRight += (cx - b.right) * 0.002 * dt;
        b.vUp    += (cy - b.up)    * 0.002 * dt;
      }
      b.right += b.vRight * dt;
      b.up    += b.vUp    * dt;
      b.fwd   += b.vFwd   * dt;

      offsetWorld(cam, b.fwd, b.right, b.up, s);
      b._bb.position = Cs.Cartesian3.fromElements(s.x, s.y, s.z, b._bb.position);
    }

    // 스폰 타이머
    if (altOk && cfg.birdCount > 0 && Date.now() >= state.birdNextSpawn) {
      spawnFlock(cfg);
      scheduleNextBirdSpawn();
    }
  }

  // ── 부유 입자 ─────────────────────────────────────────────────────────────
  function initParticles() {
    var Cs = window.Cesium;
    if (!state.partColl) {
      state.partColl = new Cs.PointPrimitiveCollection();
      state.viewer.scene.primitives.add(state.partColl);
      for (var i = 0; i < 40; i++) {
        var p = {
          show: false,
          // 카메라 상대 오프셋 (구체 내 랜덤)
          offR: 0, offU: 0, offF: 0,
          vR: 0, vU: 0, vF: 0,
          phase: rnd(0, Math.PI * 2),
          _pp: null
        };
        p._pp = state.partColl.add({
          show: false,
          position: Cs.Cartesian3.ZERO.clone(),
          color: Cs.Color.WHITE.clone(),
          pixelSize: 3
        });
        state.particles.push(p);
      }
    }
  }

  function resetParticle(p, mode) {
    // mode: 'lo' | 'hi'
    var r = rnd(30, 120);
    var theta = rnd(0, Math.PI * 2);
    var phi   = rnd(0, Math.PI);
    p.offF = r * Math.cos(phi);
    p.offR = r * Math.sin(phi) * Math.cos(theta);
    p.offU = r * Math.sin(phi) * Math.sin(theta);
    if (mode === 'lo') {
      p.vU  = rnd(-0.3, -0.05);
      p.vR  = rnd(-0.8, 0.8);
      p.vF  = rnd(-0.2, 0.2);
    } else {
      p.vU  = rnd(-0.05, 0.05);
      p.vR  = rnd(-0.1, 0.1);
      p.vF  = rnd(-0.1, 0.1);
    }
  }

  function updateParticles(dt, cfg) {
    var Cs   = window.Cesium;
    var cam  = state.viewer.scene.camera;
    var carto = cam.positionCartographic;
    var alt  = carto.height;
    var s    = state._sc1;

    var mode = null;
    var cnt  = 0;
    if (alt < PARTICLE_LO_MAX_ALT) {
      mode = 'lo'; cnt = 40;
    } else if (alt > PARTICLE_HI_MIN_ALT) {
      mode = 'hi'; cnt = 25;
    }

    for (var i = 0; i < state.particles.length; i++) {
      var p = state.particles[i];
      if (mode === null || cfg.particleCount === 0 || i >= cnt) {
        p.show = false; p._pp.show = false; continue;
      }
      if (!p.show) {
        resetParticle(p, mode);
        p.show = true; p._pp.show = true;
        p._pp.color = mode === 'lo'
          ? new Cs.Color(1, 0.97, 0.8, 0.7)
          : new Cs.Color(0.85, 0.95, 1, 0.6 + 0.3 * Math.random());
        p._pp.pixelSize = mode === 'lo' ? 3 : 2;
      }
      // 드리프트
      p.offR += p.vR * dt;
      p.offU += p.vU * dt;
      p.offF += p.vF * dt;
      // 구체 반경 벗어나면 반대편 재배치
      var dist = Math.sqrt(p.offR * p.offR + p.offU * p.offU + p.offF * p.offF);
      if (dist > 130) { resetParticle(p, mode); }

      offsetWorld(cam, p.offF, p.offR, p.offU, s);
      Cs.Cartesian3.fromElements(s.x, s.y, s.z, p._pp.position);
    }
  }

  // ── 구름 파편 ─────────────────────────────────────────────────────────────
  function initClouds() {
    var Cs = window.Cesium;
    if (!state.cloudColl) {
      var imgUrl = makeCloudCanvas();
      state.cloudColl = new Cs.BillboardCollection();
      state.viewer.scene.primitives.add(state.cloudColl);
      for (var i = 0; i < 3; i++) {
        var c = {
          show: false,
          fwd: 0, right: 0, up: 0,
          vF: 0, vR: 0,
          age: 0, lifetime: 0,
          _bb: null
        };
        c._bb = state.cloudColl.add({
          show: false,
          position: Cs.Cartesian3.ZERO.clone(),
          image: imgUrl || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=",
          scale: rnd(1.5, 3),
          color: new Cs.Color(1, 1, 1, 0.3),
          sizeInMeters: false,
          width: 128, height: 64
        });
        state.clouds.push(c);
      }
      scheduleNextCloud();
    }
  }

  function scheduleNextCloud() {
    state.cloudNextSpawn = Date.now() + rnd(15000, 40000);
  }

  function spawnCloud() {
    var Cs = window.Cesium;
    var cam = state.viewer.scene.camera;
    var carto = cam.positionCartographic;
    if (carto.height < CLOUD_MIN_ALT || carto.height > CLOUD_MAX_ALT) {
      scheduleNextCloud(); return;
    }
    var count = rndInt(1, 3);
    var used = 0;
    for (var i = 0; i < state.clouds.length && used < count; i++) {
      var c = state.clouds[i];
      if (c.show) continue;
      c.fwd      = rnd(50, 200);
      c.right    = rnd(-80, 80);
      c.up       = rnd(-20, 20);
      c.vF       = rnd(-15, -5);  // 앞에서 뒤로 스쳐감
      c.vR       = rnd(-5, 5);
      c.age      = 0;
      c.lifetime = rnd(4, 10);
      c.show     = true;
      c._bb.show = true;
      c._bb.scale = rnd(1.5, 3.5);
      used++;
    }
    scheduleNextCloud();
  }

  function updateClouds(dt, cfg) {
    var Cs  = window.Cesium;
    var cam = state.viewer.scene.camera;
    var carto = cam.positionCartographic;
    var alt  = carto.height;
    var s    = state._sc2;
    var altOk = alt >= CLOUD_MIN_ALT && alt <= CLOUD_MAX_ALT;

    for (var i = 0; i < state.clouds.length; i++) {
      var c = state.clouds[i];
      if (!c.show) continue;
      if (!altOk || !cfg.cloudEnabled) {
        c.show = false; c._bb.show = false; continue;
      }
      c.age += dt;
      if (c.age > c.lifetime) { c.show = false; c._bb.show = false; continue; }
      c.fwd   += c.vF * dt;
      c.right += c.vR * dt;
      offsetWorld(cam, c.fwd, c.right, c.up, s);
      c._bb.position = Cs.Cartesian3.fromElements(s.x, s.y, s.z, c._bb.position);
    }

    if (altOk && cfg.cloudEnabled && Date.now() >= state.cloudNextSpawn) {
      spawnCloud();
    }
  }

  // ── preRender 루프 ────────────────────────────────────────────────────────
  var _lastRenderMs = 0;
  function onPreRender(scene, time) {
    try {
      var now = Date.now();
      var dt  = Math.min((now - _lastRenderMs) / 1000, 0.1);
      if (_lastRenderMs === 0) dt = 0.016;
      _lastRenderMs = now;

      updateCameraSpeed(scene);

      var p = state.preset;
      // 고속/레이스 상태 → 전부 OFF
      if (isHighSpeed()) {
        hideAll(); return;
      }
      if (p === "off") { hideAll(); return; }
      var cfg = PRESET_CFG[p];

      updateBirds(dt, cfg);
      updateParticles(dt, cfg);
      updateClouds(dt, cfg);
    } catch (e) {
      console.warn("[swefm-fg] preRender error", e);
    }
  }

  function isHighSpeed() {
    if (state.cameraSpeed > HIGH_SPEED_THRESHOLD) return true;
    try {
      if (window.SWEF && window.SWEF.race) return true;
    } catch (e) {}
    return false;
  }

  function hideAll() {
    for (var i = 0; i < state.birds.length;     i++) { state.birds[i].show     = false; if (state.birds[i]._bb)  state.birds[i]._bb.show  = false; }
    for (var j = 0; j < state.particles.length; j++) { state.particles[j].show = false; if (state.particles[j]._pp) state.particles[j]._pp.show = false; }
    for (var k = 0; k < state.clouds.length;    k++) { state.clouds[k].show    = false; if (state.clouds[k]._bb) state.clouds[k]._bb.show  = false; }
  }

  // ── 초기화 ────────────────────────────────────────────────────────────────
  function init(viewer) {
    try {
      var Cs = window.Cesium;
      if (!Cs) { console.warn("[swefm-fg] Cesium 없음"); return; }
      state.viewer = viewer;
      // scratch Cartesian3 초기화
      state._sc0 = new Cs.Cartesian3();
      state._sc1 = new Cs.Cartesian3();
      state._sc2 = new Cs.Cartesian3();

      initBirds(PRESET_CFG[state.preset]);
      initParticles();
      initClouds();

      state.handler = viewer.scene.preRender.addEventListener(onPreRender);
      registerLauncher();
    } catch (e) {
      console.warn("[swefm-fg] init 실패", e);
    }
  }

  // ── 런처 등록 ─────────────────────────────────────────────────────────────
  function registerLauncher() {
    if (!window.SWEFM || typeof window.SWEFM.registerButton !== "function") {
      console.warn("[swefm-fg] SWEFM.registerButton 없음");
      return;
    }
    window.SWEFM.registerButton({
      id: "swefm-foreground",
      icon: "🕊",
      label: "근경",
      onClick: function () {
        var idx = PRESETS.indexOf(state.preset);
        state.preset = PRESETS[(idx + 1) % PRESETS.length];
        savePreset(state.preset);
        showToast(state.preset);
        if (state.preset !== "off") scheduleNextBirdSpawn();
      }
    });
  }

  function showToast(preset) {
    var msg = { off: "근경 OFF", subtle: "근경 SUBTLE", rich: "근경 RICH" }[preset] || preset;
    try {
      if (window.SWEFM && typeof window.SWEFM.showToast === "function") {
        window.SWEFM.showToast(msg); return;
      }
    } catch (e) {}
    // 간단 fallback
    try {
      var el = document.createElement("div");
      el.textContent = msg;
      el.style.cssText = "position:fixed;bottom:80px;left:50%;transform:translateX(-50%);"
        + "background:rgba(0,0,0,.7);color:#fff;padding:6px 16px;border-radius:20px;"
        + "font-size:13px;z-index:9999;pointer-events:none;";
      document.body.appendChild(el);
      setTimeout(function () { try { document.body.removeChild(el); } catch (e2) {} }, 1800);
    } catch (e) {}
  }

  // ── 진입 ─────────────────────────────────────────────────────────────────
  if (window.SWEFM && typeof window.SWEFM.waitViewer === "function") {
    window.SWEFM.waitViewer(init);
  } else {
    var _tries = 0;
    (function tryInit() {
      var v = (window.SWEF && window.SWEF.viewer) || window.viewer;
      if (v) { init(v); return; }
      if (++_tries < 20) setTimeout(tryInit, 500);
      else console.warn("[swefm-fg] viewer 대기 포기");
    })();
  }
})();
