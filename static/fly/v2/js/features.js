(function(){
  "use strict";

  const app = window.SWEF_V2;
  if (!app || app.bareMode) return;

  const { DESTS, VEHICLES, PORTALS, TRIALS, SIGS, DREAM_SKIES, FILMS } = app.data;
  const viewerOf = ()=>app.viewer;
  const journeyEntities = [];
  const portalEntities = [];
  const post = { film: null, motionBlur: null, fog: null, filmIndex: 0, blurLevel: 0, savedStates: null };
  let dreamPrim = null;
  let dreamSky = "";
  let dreamMat = null;
  let motionJ = null;
  let mbPrevV = null;
  let mbPrevP = null;
  let mbLast = 0;
  let mbScale = 0;
  let atmoH = 1000;
  let atmoFlash = 0;
  let atmoPrevH = 0;
  let atmoUp = null;
  let atmoTmp = null;
  let avatarEmoji = "";
  let avatarSize = parseInt(localStorage.getItem("ef_av_size") || (app.IS_TOUCH ? "42" : "68"), 10);
  let avatarPick = localStorage.getItem("ef_av_emoji") || "";

  if (!app.IS_TOUCH && !localStorage.getItem("ef_av_size")) avatarSize = 68;

  function vjLoad(key){ try { return JSON.parse(localStorage.getItem(key) || "[]"); } catch (_) { return []; } }
  function vjSave(key, value){ localStorage.setItem(key, JSON.stringify(value)); }

  function setLocalTime(hours){
    if (!viewerOf()) return;
    const lon = Cesium.Math.toDegrees(viewerOf().camera.positionCartographic.longitude) || 0;
    const utc = hours - lon / 15;
    const d = new Date();
    const base = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) + utc * 3600 * 1000;
    viewerOf().clock.currentTime = Cesium.JulianDate.fromDate(new Date(base));
    const hh = String(Math.floor(hours) % 24).padStart(2, "0");
    const mm = String(Math.round((hours % 1) * 60)).padStart(2, "0");
    const label = document.getElementById("timeLabel");
    if (label) label.textContent = hh + ":" + mm;
  }

  // §6 PostProcessStage는 켜는 순간 lazy 생성하고 끄면 stage.enabled=false로 완전히 비활성화한다.
  function ensureFilmStage(){
    if (post.film) return post.film;
    const fs = `uniform sampler2D colorTexture; uniform sampler2D depthTexture; in vec2 v_textureCoordinates; uniform float u_mode; uniform float u_time;
vec3 sat(vec3 c,float s){float l=dot(c,vec3(0.299,0.587,0.114));return mix(vec3(l),c,s);} vec3 filmic(vec3 c){ c=max(vec3(0.0),c-0.004); return (c*(6.2*c+0.5))/(c*(6.2*c+1.7)+0.06); }
void main(){ vec2 uv=v_textureCoordinates;
if(u_mode>5.5 && u_mode<6.5 && uv.y>0.45){ float t=smoothstep(0.45,0.95,uv.y); vec2 muv=vec2(uv.x,0.92-uv.y*0.85); vec3 a=texture(colorTexture,uv).rgb; vec3 b=texture(colorTexture,muv).rgb; vec3 c=mix(a,b,smoothstep(0.04,0.5,t)); c=sat(c,0.8); c=pow(c,vec3(1.15)); c*=vec3(0.88,1.0,1.1); out_FragColor=vec4(c,1.0); return; }
vec4 col=texture(colorTexture,uv); vec3 c=col.rgb; float l=dot(c,vec3(0.299,0.587,0.114));
if(u_mode<0.5){ }
else if(u_mode<1.5){ c=sat(c,1.45); c=pow(c,vec3(0.92)); c*=vec3(1.05,1.0,0.97); }
else if(u_mode<2.5){ c=sat(c,1.25); c*=vec3(1.18,0.96,0.78); c=pow(c,vec3(0.88)); }
else if(u_mode<3.5){ c=sat(c,0.12); c=pow(c,vec3(1.3)); c+=vec3(0.02,0.03,0.06); }
else if(u_mode<4.5){ c=sat(c,1.15); c=c*0.82+0.16; vec2 d=uv-0.5; c*=1.0-dot(d,d)*0.8; }
else if(u_mode<5.5){ vec3 glow=pow(max(c-0.5,0.0),vec3(1.0))*vec3(0.3,1.5,1.8); c=sat(c,1.35); c=mix(c, c*vec3(0.5,1.15,1.4), 0.5); c+=glow*0.9; c=pow(c,vec3(0.88)); }
else if(u_mode<6.5){ c=sat(c,0.8); c=pow(c,vec3(1.15)); c*=vec3(0.88,1.0,1.1); }
else if(u_mode<7.5){ c=sat(c,1.3); c += (1.0-l)*vec3(0.10,0.015,0.13); c *= vec3(1.16,0.94,0.82); c += pow(max(c-0.55,0.0),vec3(1.0))*vec3(1.2,0.6,1.1)*0.7; c = filmic(c*1.15); }
else if(u_mode<8.5){ c=sat(c,1.7); c = filmic(c*1.25); c = c*c*(3.0-2.0*c); c *= vec3(1.06,1.0,1.14); }
else if(u_mode<9.5){ c=sat(c,0.82); c = c*0.74 + vec3(0.17,0.11,0.13); c = mix(c, c*vec3(1.04,0.94,1.0), 0.5); c = pow(c,vec3(1.06)); }
else if(u_mode<10.5){ c=sat(c,1.18); c += (0.55-l)*vec3(-0.09,0.015,0.11); c *= vec3(1.24,0.96,0.70); c = filmic(c*1.18); c = max(c, vec3(0.02,0.03,0.05)); }
else if(u_mode<11.5){ float dpt = texture(depthTexture, uv).r; vec2 ndc = uv*2.0-1.0; vec4 ep = czm_inverseProjection * vec4(ndc, 0.99, 1.0); vec3 dirEC = normalize(ep.xyz/ep.w); vec3 dirWC = normalize(czm_inverseViewRotation * dirEC); vec3 o = czm_viewerPositionWC; vec3 radii = vec3(6378137.0, 6378137.0, 6356752.314); vec3 oS = o/radii; vec3 dS = dirWC/radii; float A2=dot(dS,dS); float B2=2.0*dot(oS,dS); float C2=dot(oS,oS)-1.0; float disc=B2*B2-4.0*A2*C2; float tHit=(disc>0.0)? (-B2-sqrt(max(disc,0.0)))/(2.0*A2) : -1.0; float hit=(tHit>0.0)?1.0:0.0; float skyM=(1.0-hit)*step(0.9999999,dpt); vec3 up=normalize(o); float elv=clamp(dot(dirWC,up),-0.05,1.0); vec3 skyCol=mix(vec3(1.0,0.60,0.40), vec3(0.55,0.68,0.95), smoothstep(-0.02,0.14,elv)); skyCol=mix(skyCol, vec3(0.50,0.29,0.65), smoothstep(0.12,0.5,elv)); vec3 east=normalize(cross(vec3(0.0,0.0,1.0),up)); vec3 north=cross(up,east); float az=atan(dot(dirWC,east),dot(dirWC,north)); float b1=sin(az*3.0+elv*7.0+u_time*0.14)*0.5+0.5; float b2=sin(az*6.5-u_time*0.09)*0.5+0.5; skyCol += vec3(0.08,0.20,0.14)*b1*b2*smoothstep(0.06,0.5,elv); c = mix(c, skyCol, skyM*0.9); c = sat(c,1.1); c = filmic(c*1.05); }
if(u_mode>0.5){ float g=fract(sin(dot(uv*837.0+vec2(u_time*0.7,u_time*1.3), vec2(12.9898,78.233)))*43758.5453); float lum=dot(c,vec3(0.299,0.587,0.114)); c += (g-0.5)*0.03*(0.25+0.75*smoothstep(0.05,0.5,lum)); }
out_FragColor=vec4(c,col.a); }`;
    post.film = viewerOf().scene.postProcessStages.add(new Cesium.PostProcessStage({
      fragmentShader: fs,
      uniforms: { u_mode: ()=>post.filmIndex, u_time: ()=>(performance.now() % 100000) / 1000 }
    }));
    post.film.enabled = false;
    return post.film;
  }

  function ensureMotionBlurStage(){
    if (post.motionBlur) return post.motionBlur;
    const mbfs = `uniform sampler2D colorTexture; uniform sampler2D depthTexture;
uniform mat4 u_J; uniform float u_scale; uniform float u_clamp; in vec2 v_textureCoordinates;
void main(){ vec2 uv=v_textureCoordinates; vec4 col=texture(colorTexture,uv); if(u_scale<=0.0){ out_FragColor=col; return; } float d=czm_readDepth(depthTexture,uv); vec4 eye=czm_windowToEyeCoordinates(gl_FragCoord.xy, d); vec4 pc=u_J*eye; if(abs(pc.w)<1e-6){ out_FragColor=col; return; } vec2 puv=(pc.xy/pc.w)*0.5+0.5; vec2 vel=(uv-puv)*u_scale; float l=length(vel); if(l<0.0006){ out_FragColor=col; return; } if(l>u_clamp) vel*=u_clamp/l; vec4 acc=vec4(0.0); for(int i=0;i<8;i++){ float t=(float(i)+0.5)/8.0-0.5; acc+=texture(colorTexture, clamp(uv+vel*t, vec2(0.002), vec2(0.998))); } out_FragColor=acc*0.125; }`;
    post.motionBlur = viewerOf().scene.postProcessStages.add(new Cesium.PostProcessStage({
      fragmentShader: mbfs,
      uniforms: { u_J: ()=>motionJ, u_scale: ()=>mbScale, u_clamp: 0.045 }
    }));
    post.motionBlur.enabled = false;
    return post.motionBlur;
  }

  function ensureFogStage(){
    if (post.fog) return post.fog;
    const fogfs = `uniform sampler2D colorTexture; uniform sampler2D depthTexture;
uniform float u_fogOn; uniform float u_camH; uniform vec3 u_upEC; uniform float u_flash; in vec2 v_textureCoordinates;
void main(){ vec2 uv=v_textureCoordinates; vec4 col=texture(colorTexture,uv); vec3 c=col.rgb; float d=czm_readDepth(depthTexture,uv); if(u_fogOn>0.5 && d<0.9999999){ vec4 eye=czm_windowToEyeCoordinates(gl_FragCoord.xy, d); float dist=length(eye.xyz); vec3 vdir=eye.xyz/max(dist,1.0); float hFrag=u_camH + dot(vdir,u_upEC)*dist; float hAvg=max(1.0,(u_camH+hFrag)*0.5); float density=0.000022*exp(-hAvg/1600.0); float fog=1.0-exp(-density*dist); float sunAmt=pow(max(dot(vdir,czm_sunDirectionEC),0.0),8.0); vec3 fogCol=mix(vec3(0.60,0.71,0.90), vec3(1.0,0.80,0.58), sunAmt); c=mix(c,fogCol,clamp(fog,0.0,0.85)); } if(u_flash>0.001){ c=mix(c,vec3(0.96,0.97,1.0),u_flash*0.8); c*=1.0+u_flash*0.25; } out_FragColor=vec4(c,col.a); }`;
    post.fog = viewerOf().scene.postProcessStages.add(new Cesium.PostProcessStage({
      fragmentShader: fogfs,
      uniforms: {
        u_fogOn: ()=>((app.state.fogSuppressed || localStorage.getItem("swef_atmo") === "0" || dreamPrim) ? 0 : 1),
        u_camH: ()=>atmoH,
        u_upEC: ()=>atmoUp,
        u_flash: ()=>atmoFlash
      }
    }));
    post.fog.enabled = true;
    return post.fog;
  }

  function applyPostprocessState(){
    if (post.film) post.film.enabled = post.filmIndex > 0 && !app.state.postprocessSuspended;
    if (post.motionBlur) post.motionBlur.enabled = post.blurLevel > 0 && !app.state.postprocessSuspended;
    if (post.fog) post.fog.enabled = !app.state.postprocessSuspended && localStorage.getItem("swef_atmo") !== "0" && !app.state.fogSuppressed && !dreamPrim;
  }

  function setFilm(index){
    post.filmIndex = Math.max(0, Math.min(FILMS.length - 1, index | 0));
    if (post.filmIndex > 0) ensureFilmStage();
    applyPostprocessState();
    document.querySelectorAll(".filmc").forEach((el, idx)=>el.classList.toggle("on", idx === post.filmIndex));
  }

  function mbLevel(){ const v = localStorage.getItem("swef_mb"); return v !== null ? parseInt(v, 10) : 0; }
  function setMotionBlurLevel(level){
    post.blurLevel = Math.max(0, Math.min(2, level | 0));
    localStorage.setItem("swef_mb", String(post.blurLevel));
    if (post.blurLevel > 0) ensureMotionBlurStage();
    applyPostprocessState();
  }

  function setAtmosphereEnabled(on){
    localStorage.setItem("swef_atmo", on ? "1" : "0");
    if (on) ensureFogStage();
    applyPostprocessState();
  }

  function setCloudMode(mode, silent){
    app.state.cloudMode = mode | 0;
    const label = document.getElementById("cloudLbl");
    if (label) label.textContent = ["구름 OFF","구름 1","구름 2"][app.state.cloudMode] || ("구름 " + app.state.cloudMode);
    const btn = document.getElementById("btnCloud");
    if (btn) btn.classList.toggle("on", app.state.cloudMode > 0);
    if (!silent) app.toast("☁️ " + (label ? label.textContent : app.state.cloudMode));
  }

  function cycleCloudMode(){
    setCloudMode((app.state.cloudMode + 1) % 3);
  }

  function dreamOff(){
    if (!dreamPrim) return;
    viewerOf().scene.primitives.remove(dreamPrim);
    dreamPrim = null;
    dreamSky = "";
    dreamMat = null;
    viewerOf().scene.skyAtmosphere.show = true;
    applyPostprocessState();
    const btn = document.getElementById("btnDream");
    if (btn) btn.classList.remove("on");
  }

  function dreamOn(sky){
    if (dreamPrim && dreamSky === sky) return;
    if (dreamPrim && dreamMat) {
      dreamMat.uniforms.image = sky;
      dreamSky = sky;
      return;
    }
    viewerOf().scene.skyAtmosphere.show = false;
    dreamMat = Cesium.Material.fromType("Image", { image: sky });
    const appa = new Cesium.MaterialAppearance({
      flat: true,
      translucent: false,
      material: dreamMat,
      renderState: { cull: { enabled: false }, depthTest: { enabled: true } }
    });
    dreamPrim = viewerOf().scene.primitives.add(new Cesium.Primitive({
      geometryInstances: new Cesium.GeometryInstance({
        geometry: new Cesium.EllipsoidGeometry({
          radii: new Cesium.Cartesian3(400000, 400000, 400000),
          vertexFormat: Cesium.VertexFormat.POSITION_AND_ST
        })
      }),
      appearance: appa,
      asynchronous: false,
      allowPicking: false
    }));
    dreamSky = sky;
    applyPostprocessState();
    const btn = document.getElementById("btnDream");
    if (btn) btn.classList.add("on");
  }

  function toggleDream(){
    const free = localStorage.getItem("swef_gate4") === "1";
    if (dreamPrim) {
      if (!free) return dreamOff();
      app.state.dreamIndex = ((app.state.dreamIndex || 0) + 1) % DREAM_SKIES.length;
      if (app.state.dreamIndex === 0) return dreamOff();
      dreamOn(DREAM_SKIES[app.state.dreamIndex]);
      return app.toast("🌌 세계 " + (app.state.dreamIndex + 1) + "/" + DREAM_SKIES.length);
    }
    app.state.dreamIndex = 0;
    dreamOn(DREAM_SKIES[0]);
    if (!free) app.toast("🌌 드림스카이 — 여정을 쌓으면 더 많은 세계가 열린다");
  }

  function refreshPortals(){
    portalEntities.splice(0).forEach((entity)=>viewerOf().entities.remove(entity));
    const c = document.createElement("canvas");
    c.width = c.height = 32;
    const x = c.getContext("2d");
    const g = x.createRadialGradient(16, 16, 1, 16, 16, 15);
    g.addColorStop(0, "rgba(255,255,255,.75)");
    g.addColorStop(.5, "rgba(190,230,255,.28)");
    g.addColorStop(1, "rgba(190,230,255,0)");
    x.fillStyle = g;
    x.fillRect(0, 0, 32, 32);
    const speck = c.toDataURL();
    const r = document.createElement("canvas");
    r.width = r.height = 256;
    const y = r.getContext("2d");
    const rg = y.createRadialGradient(128, 128, 66, 128, 128, 124);
    rg.addColorStop(0, "rgba(120,220,255,0)");
    rg.addColorStop(.5, "rgba(140,230,255,.95)");
    rg.addColorStop(.72, "rgba(255,190,90,.95)");
    rg.addColorStop(1, "rgba(255,190,90,0)");
    y.fillStyle = rg;
    y.beginPath(); y.arc(128, 128, 124, 0, Math.PI * 2); y.fill();
    const ring = r.toDataURL();
    PORTALS.forEach((portal)=>{
      portal._pos = Cesium.Cartesian3.fromDegrees(portal.lon, portal.lat, portal.alt);
      const open = portal.open || (portal.unlock && localStorage.getItem(portal.unlock));
      portalEntities.push(viewerOf().entities.add(open ? {
        position: portal._pos,
        billboard: { image: ring, width: 170, height: 170, scaleByDistance: new Cesium.NearFarScalar(400, 2.2, 60000, 0.15) },
        label: { text: "✨ ???", font: "14px sans-serif", fillColor: Cesium.Color.WHITE, showBackground: true, backgroundColor: new Cesium.Color(0,0,0,0.5), pixelOffset: new Cesium.Cartesian2(0, -105), scaleByDistance: new Cesium.NearFarScalar(400, 1, 40000, 0.3) }
      } : {
        position: portal._pos,
        billboard: { image: speck, width: 9, height: 9, translucencyByDistance: new Cesium.NearFarScalar(600, 0.55, 7000, 0.0) }
      }));
    });
  }

  function portalTick(){
    if (!viewerOf() || !PORTALS.length) return;
    if (app.state.portalCooldown > 0) { app.state.portalCooldown -= 1; return; }
    const cam = viewerOf().camera.positionWC;
    for (const portal of PORTALS) {
      if (!portal._pos || Cesium.Cartesian3.distance(cam, portal._pos) >= 420) continue;
      app.state.portalCooldown = 1200;
      dreamOn(portal.sky);
      const key = portal.lat.toFixed(3) + "," + portal.lon.toFixed(3);
      let pv = [];
      try { pv = JSON.parse(localStorage.getItem("swef_portals") || "[]"); }
      catch (_) {}
      if (pv.indexOf(key) < 0) {
        pv.push(key);
        localStorage.setItem("swef_portals", JSON.stringify(pv));
        app.toast("🌀 차원의 문 " + pv.length + "/" + PORTALS.length);
        // §데이터 이식 미션 3호: 포탈 카운트가 PORTALS 길이에 도달하면 swef_gate3를 연다.
        if (pv.length >= PORTALS.length && !localStorage.getItem("swef_gate3")) {
          localStorage.setItem("swef_gate3", "1");
          setTimeout(()=>app.toast("👑 모든 차원을 여행한 자 — 전설이 깨어났다"), 1200);
          setTimeout(()=>app.toast("✨ 탈것 목록을 보라"), 3200);
          refreshPortals();
        }
      }
      break;
    }
  }

  function godTrial(name){
    for (const trial of TRIALS) {
      if (trial.names.indexOf(name) < 0) continue;
      let done = [];
      try { done = JSON.parse(localStorage.getItem(trial.key) || "[]"); }
      catch (_) {}
      if (done.indexOf(name) >= 0) return;
      done.push(name);
      localStorage.setItem(trial.key, JSON.stringify(done));
      if (done.length < trial.names.length) app.toast(trial.icon + " " + trial.title + " " + done.length + "/" + trial.names.length + " — " + name);
      else {
        localStorage.setItem(trial.gate, "1");
        app.toast(trial.done);
        setTimeout(()=>app.toast(trial.hint), 2400);
        refreshPortals();
      }
      return;
    }
  }

  function renderJourney(){
    if (!viewerOf()) return;
    journeyEntities.splice(0).forEach((entity)=>viewerOf().entities.remove(entity));
    const visits = vjLoad("swef_visits");
    const stars = vjLoad("swef_stars");
    visits.forEach((visit)=>{
      journeyEntities.push(viewerOf().entities.add({ position: Cesium.Cartesian3.fromDegrees(visit.lo, visit.la, 400), point: { pixelSize: 7, color: Cesium.Color.fromCssColorString("#39d98a"), outlineColor: Cesium.Color.BLACK, outlineWidth: 1, translucencyByDistance: new Cesium.NearFarScalar(5e5, 1, 9e6, 0.3) } }));
    });
    stars.forEach((star)=>{
      journeyEntities.push(viewerOf().entities.add({ position: Cesium.Cartesian3.fromDegrees(star.lo, star.la, 400), point: { pixelSize: 7, color: Cesium.Color.GOLD, outlineColor: Cesium.Color.BLACK, outlineWidth: 1, translucencyByDistance: new Cesium.NearFarScalar(5e5, 1, 9e6, 0.3) } }));
    });
    const list = document.getElementById("journeyList");
    if (!list) return;
    let html = "";
    if (stars.length) html += '<div class="meta">⭐ 가고 싶은 곳 ' + stars.length + '</div>';
    stars.slice(0, 25).forEach((star, idx)=>{ html += '<div class="journey-item"><span>⭐ ' + star.n + '</span><button data-t="s' + idx + '">비행</button></div>'; });
    if (visits.length) html += '<div class="meta">📍 가본 곳 ' + visits.length + '</div>';
    visits.slice(-15).reverse().forEach((visit, idx)=>{ html += '<div class="journey-item"><span>📍 ' + new Date(visit.ts).toLocaleDateString() + '</span><button data-t="v' + (visits.length - 1 - idx) + '">비행</button></div>'; });
    list.innerHTML = html || '<div class="meta">아직 기록이 없어 — 위 버튼으로 시작</div>';
    list.querySelectorAll("button").forEach((button)=>{
      button.onclick = ()=>{
        const token = button.getAttribute("data-t");
        const item = token[0] === "s" ? stars[parseInt(token.slice(1), 10)] : visits[parseInt(token.slice(1), 10)];
        if (!item) return;
        app.flyToCartesian(Cesium.Cartesian3.fromDegrees(item.lo, item.la, 2600), { duration: 4.2, complete: ()=>app.markTravelSettling() });
      };
    });
  }

  function vjTrack(silent){
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((position)=>{
      localStorage.setItem("swef_vj_auto", "1");
      const la = position.coords.latitude;
      const lo = position.coords.longitude;
      const visits = vjLoad("swef_visits");
      const near = visits.some((visit)=>{
        const dy = (visit.la - la) * 111;
        const dx = (visit.lo - lo) * 111 * Math.cos(la * 0.017453);
        // §데이터 이식 여정 시스템의 25km 중복 제거 규칙을 유지한다.
        return dy * dy + dx * dx < 625;
      });
      if (!near) {
        visits.push({ la, lo, ts: Date.now() });
        vjSave("swef_visits", visits);
        app.toast("🧭 새 발자국 — 이 기기에만 저장");
        // §데이터 이식 미션 4호: 발자국 3곳이면 swef_gate4를 연다.
        if (visits.length >= 3 && !localStorage.getItem("swef_gate4")) {
          localStorage.setItem("swef_gate4", "1");
          setTimeout(()=>app.toast("🌠 여정자의 증표 — 드림스카이가 모든 세계를 기억한다"), 1200);
        }
      } else if (!silent) app.toast("🧭 이미 기록된 지역이야");
      renderJourney();
    }, ()=>{ if (!silent) app.toast("위치 권한이 필요해"); }, { enableHighAccuracy: false, timeout: 9000, maximumAge: 600000 });
  }

  function vjImportFile(file){
    const reader = new FileReader();
    reader.onload = ()=>{
      try {
        const json = JSON.parse(reader.result);
        const feats = json.features || [];
        const stars = vjLoad("swef_stars");
        let add = 0;
        for (const ft of feats) {
          const co = ft.geometry && ft.geometry.coordinates;
          if (!co || co.length < 2) continue;
          // §데이터 이식 Takeout JSON 파서를 그대로 유지한다.
          const nm = (ft.properties && ((ft.properties.location && ft.properties.location.name) || ft.properties.Title || ft.properties.name)) || "⭐";
          if (stars.some((x)=>Math.abs(x.la - co[1]) < 1e-4 && Math.abs(x.lo - co[0]) < 1e-4)) continue;
          stars.push({ la: co[1], lo: co[0], n: String(nm).slice(0, 40) });
          add += 1;
        }
        vjSave("swef_stars", stars);
        app.toast("⭐ " + add + "곳 가져옴");
        renderJourney();
      } catch (_) {
        app.toast("파일 형식을 못 읽었어 (Takeout JSON 맞아?)");
      }
    };
    reader.readAsText(file);
  }

  function tuneVehicle(sp, ag){
    const veh = app.state.vehicle;
    if (!veh) return;
    veh.sp = sp;
    veh.ag = ag;
    // §데이터 이식 기체 튜닝 저장키 swef_tune_*를 유지한다.
    localStorage.setItem("swef_tune_" + veh.n, JSON.stringify({ sp: veh.sp, ag: veh.ag }));
  }

  function pickVehicle(index){
    const veh = VEHICLES[index];
    if (!veh) return;
    if (veh.lock && !localStorage.getItem(veh.lock)) return app.toast("🔒 모든 차원의 문을 지나온 자만이…");
    app.state.vehicleIndex = index;
    app.state.vehicle = Object.assign({}, veh);
    godTrial(veh.n);
    try {
      const saved = JSON.parse(localStorage.getItem("swef_tune_" + veh.n) || "null");
      if (saved) Object.assign(app.state.vehicle, saved);
    } catch (_) {}
    app.setUnderwaterMode(app.state.vehicle.cat === "sub" || app.state.vehicle.cat === "tunnel");
    app.goFree();
    app.emit("vehicle", app.state.vehicle);
  }

  function applySig(dest){
    if (!app.state.signatureReady || app.state.currentTab !== "user") return;
    const sig = SIGS[dest.n];
    if (!sig) return;
    // §조작 시그니처는 유저 탭에서만, 부팅 12초 후부터 작동한다.
    setFilm(sig.f);
    setLocalTime(sig.t);
    setCloudMode(sig.c, true);
    app.toast("🎬 시그니처 — " + FILMS[sig.f][0]);
  }

  function updateMotionBlur(dtMs){
    if (!post.motionBlur) return;
    const cam = viewerOf().camera;
    const V = cam.viewMatrix;
    const P = cam.frustum.projectionMatrix;
    const dt = dtMs || (mbLast ? Math.min(100, performance.now() - mbLast) : 16.6);
    mbLast = performance.now();
    if (post.blurLevel > 0 && mbPrevV && P) {
      const invV = Cesium.Matrix4.inverse(V, new Cesium.Matrix4());
      const A = Cesium.Matrix4.multiply(mbPrevV, invV, new Cesium.Matrix4());
      Cesium.Matrix4.multiply(mbPrevP, A, motionJ);
      const shutter = post.blurLevel === 2 ? 1.0 : 0.5;
      mbScale = (app.state.postprocessSuspended ? 0 : 1) * shutter * Math.min(1.0, 16.6 / dt);
    } else mbScale = 0;
    mbPrevV = Cesium.Matrix4.clone(V, mbPrevV || new Cesium.Matrix4());
    if (P) mbPrevP = Cesium.Matrix4.clone(P, mbPrevP || new Cesium.Matrix4());
  }

  function updateFog(dtMs){
    if (!viewerOf()) return;
    const cam = viewerOf().camera;
    try {
      atmoH = cam.positionCartographic.height;
      const up = Cesium.Cartesian3.normalize(cam.positionWC, atmoTmp);
      Cesium.Matrix4.multiplyByPointAsVector(cam.viewMatrix, up, atmoUp);
      const bands = [1200, 2500, 6000];
      if (app.state.cloudMode > 0 && atmoPrevH > 0) {
        for (const b of bands) {
          if ((atmoPrevH - b) * (atmoH - b) < 0) { atmoFlash = 1.0; break; }
        }
      }
      atmoPrevH = atmoH;
      atmoFlash *= Math.pow(0.02, (dtMs || 16.6) / 500);
      if (atmoFlash < 0.002) atmoFlash = 0;
    } catch (_) {}
  }

  function updateAvatar(){
    const el = document.getElementById("avWrap");
    if (!el) return;
    // §데이터 이식 👻 숨김과 PC 기본 68px 규칙을 유지한다.
    if (app.state.mode !== "free" || localStorage.getItem("swef_avhide") === "1") {
      el.style.display = "none";
      return;
    }
    el.style.display = "block";
    const veh = app.state.vehicle || VEHICLES[0];
    const emoji = avatarPick || veh.e;
    if (emoji !== avatarEmoji) {
      avatarEmoji = emoji;
      if (emoji.indexOf("img:") === 0) el.innerHTML = '<img src="' + emoji.slice(4) + '" style="height:' + Math.round(avatarSize * 1.7) + 'px;filter:drop-shadow(0 12px 14px rgba(0,0,0,.6))" alt="">';
      else el.textContent = emoji;
    }
    const r = -(app.state.roll || 0);
    const t = performance.now() / 1000;
    const spd = Math.abs(app.state.speedKmh / 3.6 || 0);
    const spdN = Math.min(1, spd / 900);
    // §데이터 이식 보빙·질주 리듬·숙임·부스트 진동을 v2 아바타 DOM에 유지한다.
    const bob = Math.sin(t * 2.6) * (4.5 * (1 - spdN * 0.75));
    const gallop = Math.sin(t * 9.0) * (1.6 * spdN);
    const boost = !!(app.keys && app.keys.shift);
    const shX = boost ? (Math.random() - 0.5) * 2.2 : 0;
    const shY = boost ? (Math.random() - 0.5) * 2.2 : 0;
    const pitchLean = spdN * 6;
    el.style.transform = 'translateX(-50%) translate(' + shX.toFixed(1) + 'px,' + (bob + gallop + shY).toFixed(1) + 'px) rotate(' + ((r * 57.3) + (Math.sin(t * 2.6) * 1.2 * (1 - spdN))).toFixed(1) + 'deg) skewX(' + (-pitchLean * 0.25).toFixed(1) + 'deg)';
    const fs2 = boost ? Math.round(avatarSize * 1.2) : avatarSize;
    const img = el.querySelector("img");
    if (img) img.style.height = Math.round(fs2 * 1.7) + "px";
    el.style.fontSize = fs2 + "px";
  }

  app.toggleAllPostprocess = function(force){
    post.savedStates = {
      film: post.film ? post.film.enabled : null,
      motionBlur: post.motionBlur ? post.motionBlur.enabled : null,
      fog: post.fog ? post.fog.enabled : null
    };
    if (post.film) post.film.enabled = !!force;
    if (post.motionBlur) post.motionBlur.enabled = !!force;
    if (post.fog) post.fog.enabled = !!force;
  };
  app.restoreAllPostprocess = function(){
    if (!post.savedStates) return;
    if (post.film && post.savedStates.film != null) post.film.enabled = post.savedStates.film;
    if (post.motionBlur && post.savedStates.motionBlur != null) post.motionBlur.enabled = post.savedStates.motionBlur;
    if (post.fog && post.savedStates.fog != null) post.fog.enabled = post.savedStates.fog;
    post.savedStates = null;
  };

  Object.assign(app, {
    FILMS,
    PORTALS,
    setFilm,
    setLocalTime,
    setMotionBlurLevel,
    setAtmosphereEnabled,
    setCloudMode,
    cycleCloudMode,
    toggleDream,
    pickVehicle,
    tuneVehicle,
    setAvatarSize(px){ avatarSize = Math.max(24, px|0); const v = app.state.vehicle; if (v) app.emit("vehicle", v); },
    applySig,
    vjTrack,
    vjImportFile,
    vjRender: renderJourney,
    refreshPortals,
    dreamOff,
    dreamOn
  });

  app.on("ready", ()=>{
    motionJ = Cesium.Matrix4.clone(Cesium.Matrix4.IDENTITY);
    atmoUp = new Cesium.Cartesian3(0, 1, 0);
    atmoTmp = new Cesium.Cartesian3();
    app.state.vehicle = Object.assign({}, VEHICLES[0]);
    app.state.vehicleIndex = 0;
    setLocalTime(17.5);
    setCloudMode(0, true);
    setMotionBlurLevel(mbLevel());
    if (localStorage.getItem("swef_atmo") !== "0") ensureFogStage();
    refreshPortals();
    renderJourney();
  });

  app.on("frame", ({ dtMs })=>{
    updateMotionBlur(dtMs);
    updateFog(dtMs);
    if (dreamPrim) dreamPrim.modelMatrix = Cesium.Transforms.eastNorthUpToFixedFrame(viewerOf().camera.positionWC);
    portalTick();
    updateAvatar();
    applyPostprocessState();
  });
})();
