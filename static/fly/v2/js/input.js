(function(){
  "use strict";

  const app = window.SWEF_V2;
  if (!app) return;

  const keys = app.keys = app.keys || Object.create(null);

  function shouldIgnoreKey(event){
    const tag = event.target && event.target.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  }

  function clampPitch(camera){
    const pmax = Cesium.Math.toRadians(58);
    const pmin = Cesium.Math.toRadians(-85);
    if (camera.pitch > pmax) camera.setView({ orientation: { heading: camera.heading, pitch: pmax, roll: camera.roll } });
    if (camera.pitch < pmin) camera.setView({ orientation: { heading: camera.heading, pitch: pmin, roll: camera.roll } });
  }

  function bindPointerLook(canvas){
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    canvas.addEventListener("mousedown", (event)=>{
      if (event.button !== 0) return;
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
    });
    window.addEventListener("mousemove", (event)=>{
      if (!dragging || !app.viewer) return;
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      app.viewer.camera.lookRight(dx * 0.0035);
      app.viewer.camera.lookUp(-dy * 0.0035);
      clampPitch(app.viewer.camera);
    });
    window.addEventListener("mouseup", ()=>{ dragging = false; });
  }

  function bindTouchLook(canvas){
    let touchId = null;
    let pinchDistance = 0;
    let lastX = 0;
    let lastY = 0;
    const skip = (event)=>{
      const tag = event.target && event.target.tagName;
      return tag === "INPUT" || tag === "BUTTON" || tag === "SELECT";
    };
    canvas.addEventListener("touchstart", (event)=>{
      if (event.touches.length === 1 && !skip(event)) {
        const touch = event.touches[0];
        touchId = touch.identifier;
        lastX = touch.clientX;
        lastY = touch.clientY;
      }
    }, { passive: true });
    canvas.addEventListener("touchmove", (event)=>{
      if (!app.viewer || event.touches.length !== 1 || touchId == null || skip(event)) return;
      const touch = Array.from(event.touches).find((it)=>it.identifier === touchId);
      if (!touch) return;
      const dx = touch.clientX - lastX;
      const dy = touch.clientY - lastY;
      lastX = touch.clientX;
      lastY = touch.clientY;
      // §조작 한 손가락 드래그는 조작 패드 없이 화면 전체에서 시선 조작을 맡는다.
      app.viewer.camera.lookRight(dx * 0.004);
      app.viewer.camera.lookUp(-dy * 0.004);
      clampPitch(app.viewer.camera);
      event.preventDefault();
    }, { passive: false });
    document.addEventListener("touchstart", (event)=>{
      if (event.touches.length === 2 && !skip(event)) {
        const [a, b] = event.touches;
        pinchDistance = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      }
    }, { capture: true, passive: true });
    document.addEventListener("touchmove", (event)=>{
      if (!app.viewer || event.touches.length !== 2 || pinchDistance <= 0 || skip(event)) return;
      const [a, b] = event.touches;
      const next = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      const dz = (next - pinchDistance) / Math.max(40, pinchDistance);
      let step = 200;
      try { step = Math.max(60, app.viewer.camera.positionCartographic.height * 0.9); }
      catch (_) {}
      // §조작 두 손가락 핀치는 document 레벨 캡처로 전진/후진을 수행한다.
      app.viewer.camera.moveForward(dz * step * 2.2);
      pinchDistance = next;
      event.preventDefault();
    }, { capture: true, passive: false });
    document.addEventListener("touchend", (event)=>{
      if (event.touches.length < 2) pinchDistance = 0;
      if (touchId != null && !Array.from(event.touches).some((it)=>it.identifier === touchId)) touchId = null;
    }, { capture: true, passive: true });
  }

  function bindKeyboard(){
    window.addEventListener("keydown", (event)=>{
      if (shouldIgnoreKey(event)) return;
      const key = event.key.toLowerCase();
      keys[key] = true;
      if (["w","a","s","d","q","e","shift"].includes(key)) event.preventDefault();
    });
    window.addEventListener("keyup", (event)=>{ keys[event.key.toLowerCase()] = false; });
  }

  function bindWheel(canvas){
    canvas.addEventListener("wheel", (event)=>{
      if (!app.viewer || app.state.mode !== "free") return;
      let step = 3;
      try { step = Math.max(3, app.viewer.camera.positionCartographic.height * 0.0012); }
      catch (_) {}
      // §조작 PC 휠은 고도 비례 전진/후진으로 사용한다.
      app.viewer.camera.moveForward(-event.deltaY * step);
      event.preventDefault();
    }, { passive: false });
  }

  function updateFlight(dt){
    if (!app.viewer || app.state.mode !== "free") return;
    const c = app.viewer.camera;
    const veh = app.state.vehicle || { ag: 1 };
    const speed = app.currentSpeed() * dt;
    const turn = 1.35 * (veh.ag || 1) * dt;
    const pitch = 0.85 * (veh.ag || 1) * dt;
    if (keys.w) c.moveForward(speed);
    if (keys.s) c.moveBackward(speed);
    if (keys.a) c.moveLeft(speed * 0.7);
    if (keys.d) c.moveRight(speed * 0.7);
    if (keys.q) c.moveDown(speed * 0.5);
    if (keys.e) c.moveUp(speed * 0.5);
    if (keys.arrowleft) c.lookLeft(turn);
    if (keys.arrowright) c.lookRight(turn);
    if (keys.arrowup) c.lookUp(pitch);
    if (keys.arrowdown) c.lookDown(pitch);
    clampPitch(c);
  }

  app.on("ready", ()=>{
    bindKeyboard();
    bindPointerLook(app.viewer.canvas);
    bindTouchLook(app.viewer.canvas);
    bindWheel(app.viewer.canvas);
  });
  app.on("frame", ({ dt })=>updateFlight(dt));
})();
