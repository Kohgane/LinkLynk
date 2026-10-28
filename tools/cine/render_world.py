#!/usr/bin/env python3
"""Blender (bpy) render of an open-data world along the SWEF arrival path.
usage: render_world.py <slug> <dest-h> <dest-r> <dest-p> <fps> <dur> <samples> [frame_start frame_end]
Camera path = same as the live app: lookAt(center=(lon,lat,h*0.35), heading 20°-70°→20°, pitch -34°→p, range min(6r,40km)→r)."""
import sys, json, math, os
import numpy as np, bpy, bmesh
from mathutils import Vector, Matrix
slug, H, R, P, FPS, DUR, SMP = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]), int(sys.argv[7])
F0 = int(sys.argv[8]) if len(sys.argv) > 8 else 0
F1 = int(sys.argv[9]) if len(sys.argv) > 9 else 10**9
meta = json.load(open(f"{slug}/meta.json")); dem = np.load(f"{slug}/dem.npy")
DEM_N = int(os.environ.get("DEM_N", "1200"))
if dem.shape[0] > DEM_N:
    from scipy.ndimage import zoom; dem = zoom(dem, DEM_N/dem.shape[0], order=1).astype(np.float32)
TEX_MAX = int(os.environ.get("TEX_MAX", "6144"))
def tex_path(p):
    from PIL import Image; Image.MAX_IMAGE_PIXELS = None
    im = Image.open(p)
    if im.size[0] <= TEX_MAX: return p
    q = p.replace(".png", f"_{TEX_MAX}.jpg")
    if not os.path.exists(q): im.resize((TEX_MAX, TEX_MAX), Image.LANCZOS).save(q, quality=92)
    return q
N = dem.shape[0]; km = meta["km"]; lat = meta["lat"]
HAZE_NEAR = float(os.environ.get("HAZE_NEAR", "9000")); HAZE_FAR = float(os.environ.get("HAZE_FAR", "170000"))
SUN_ELEV = float(os.environ.get("SUN_ELEV", "19")); SUN_AZ = float(os.environ.get("SUN_AZ", "250"))   # golden hour, light from the west-southwest
size = km*1000.0
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# --- terrain mesh: rows north->south, cols west->east; local ENU meters, center at origin ---
xs = np.linspace(-size/2, size/2, N); ys = np.linspace(size/2, -size/2, N)
X, Y = np.meshgrid(xs, ys)
# planet curvature drop so the far horizon dips like the live globe
Rm = 6371000.0; drop = (X*X + Y*Y)/(2*Rm)
Z = dem - drop
verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1).astype(np.float32)
idx = np.arange(N*N).reshape(N, N)
a = idx[:-1, :-1].ravel(); b = idx[:-1, 1:].ravel(); c = idx[1:, 1:].ravel(); d = idx[1:, :-1].ravel()
faces = np.stack([a, b, c, d], axis=1)
me = bpy.data.meshes.new("terrain")
me.vertices.add(len(verts)); me.vertices.foreach_set("co", verts.ravel())
me.loops.add(len(faces)*4); me.polygons.add(len(faces))
me.loops.foreach_set("vertex_index", faces.ravel())
me.polygons.foreach_set("loop_start", np.arange(0, len(faces)*4, 4)); me.polygons.foreach_set("loop_total", np.full(len(faces), 4))
uv = me.uv_layers.new(name="uv")
u = (X.ravel() + size/2)/size; v = (Y.ravel() + size/2)/size
uvs = np.stack([u[faces.ravel()], v[faces.ravel()]], axis=1).astype(np.float32)
uv.data.foreach_set("uv", uvs.ravel())
me.validate(); me.update()
ob = bpy.data.objects.new("terrain", me); sc.collection.objects.link(ob)
for p in me.polygons: p.use_smooth = True
def ground_mat(name, path):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.95; bsdf.inputs["Specular IOR Level"].default_value = 0.15
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(os.path.abspath(tex_path(path))); tex.image.use_half_precision = True
    hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = float(os.environ.get("SAT", "1.35")); hs.inputs["Value"].default_value = 1.10   # P25-1028: satellite colour is muted
    nt.links.new(tex.outputs["Color"], hs.inputs["Color"]); nt.links.new(hs.outputs["Color"], bsdf.inputs["Base Color"])
    # P25-1028 aerial perspective: far ground becomes transparent so the camera sees the real sky through it.
    # The haze colour is therefore always the sky's own colour in that direction, and the mesh edge vanishes into it.
    out = nt.nodes["Material Output"]; cam = nt.nodes.new("ShaderNodeCameraData")
    ramp = nt.nodes.new("ShaderNodeMapRange"); ramp.inputs["From Min"].default_value = HAZE_NEAR; ramp.inputs["From Max"].default_value = HAZE_FAR
    ramp.inputs["To Min"].default_value = 0.0; ramp.inputs["To Max"].default_value = 1.0; ramp.clamp = True
    curve = nt.nodes.new("ShaderNodeMath"); curve.operation = "POWER"; curve.inputs[1].default_value = 0.75   # fast early rise, like real scattering
    tint = nt.nodes.new("ShaderNodeMixRGB") if hasattr(bpy.types, "ShaderNodeMixRGB") else None
    trans = nt.nodes.new("ShaderNodeBsdfTransparent"); trans.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    mixs = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(cam.outputs["View Distance"], ramp.inputs["Value"]); nt.links.new(ramp.outputs["Result"], curve.inputs[0]); nt.links.new(curve.outputs["Value"], mixs.inputs["Fac"])
    nt.links.new(bsdf.outputs["BSDF"], mixs.inputs[1]); nt.links.new(trans.outputs["BSDF"], mixs.inputs[2]); nt.links.new(mixs.outputs["Shader"], out.inputs["Surface"])
    mat.blend_method = "BLEND"
    return mat
me.materials.append(ground_mat("ground", f"{slug}/tex.png"))
# --- outer LOD ring (coarse, hides the box edge at the horizon); verts under the inner box are sunk out of sight ---
if os.path.exists(f"{slug}_outer/dem.npy"):
    om = json.load(open(f"{slug}_outer/meta.json")); od = np.load(f"{slug}_outer/dem.npy"); ON = od.shape[0]; osize = om["km"]*1000.0
    oxs = np.linspace(-osize/2, osize/2, ON); oys = np.linspace(osize/2, -osize/2, ON)
    OX, OY = np.meshgrid(oxs, oys); OZ = od - (OX*OX + OY*OY)/(2*Rm) - 40.0
    inside = (np.abs(OX) < size/2*0.97) & (np.abs(OY) < size/2*0.97); OZ[inside] = -6000.0
    overts = np.stack([OX.ravel(), OY.ravel(), OZ.ravel()], axis=1).astype(np.float32)
    oidx = np.arange(ON*ON).reshape(ON, ON)
    oa = oidx[:-1, :-1].ravel(); ob_ = oidx[:-1, 1:].ravel(); oc = oidx[1:, 1:].ravel(); od_ = oidx[1:, :-1].ravel()
    ofaces = np.stack([oa, ob_, oc, od_], axis=1)
    ome = bpy.data.meshes.new("outer")
    ome.vertices.add(len(overts)); ome.vertices.foreach_set("co", overts.ravel())
    ome.loops.add(len(ofaces)*4); ome.polygons.add(len(ofaces))
    ome.loops.foreach_set("vertex_index", ofaces.ravel())
    ome.polygons.foreach_set("loop_start", np.arange(0, len(ofaces)*4, 4)); ome.polygons.foreach_set("loop_total", np.full(len(ofaces), 4))
    ouv = ome.uv_layers.new(name="uv")
    ou = (OX.ravel() + osize/2)/osize; ov = (OY.ravel() + osize/2)/osize
    ouv.data.foreach_set("uv", np.stack([ou[ofaces.ravel()], ov[ofaces.ravel()]], axis=1).astype(np.float32).ravel())
    ome.validate(); ome.update()
    oob = bpy.data.objects.new("outer", ome); sc.collection.objects.link(oob)
    for p in ome.polygons: p.use_smooth = True
    ome.materials.append(ground_mat("ground_outer", f"{slug}_outer/tex.png"))
# --- world: physically based Nishita sky at golden hour (P25-1028) — consistent horizon colour for the aerial perspective ---
w = bpy.data.worlds.new("sky"); sc.world = w; w.use_nodes = True
sky = w.node_tree.nodes.new("ShaderNodeTexSky"); sky.sky_type = "MULTIPLE_SCATTERING"; sky.sun_disc = False
sky.sun_elevation = math.radians(SUN_ELEV); sky.sun_rotation = math.radians(SUN_AZ); sky.altitude = 0; sky.air_density = 1.3; sky.ozone_density = 1.2
bg = w.node_tree.nodes["Background"]; bg.inputs["Strength"].default_value = float(os.environ.get("SKY_STR", "0.10"))   # physical sky units -> tone down for AgX
# below the horizon the physical sky is black; mirror the just-above-horizon colour downwards so haze (transparent ground) reads as sky fog
wn = w.node_tree.nodes; wl = w.node_tree.links
tc = wn.new("ShaderNodeTexCoord"); sep = wn.new("ShaderNodeSeparateXYZ"); comb = wn.new("ShaderNodeCombineXYZ")
ab = wn.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; ad = wn.new("ShaderNodeMath"); ad.operation = "ADD"; ad.inputs[1].default_value = 0.004
wl.new(tc.outputs["Generated"], sep.inputs["Vector"]); wl.new(sep.outputs["Z"], ab.inputs[0]); wl.new(ab.outputs["Value"], ad.inputs[0])
wl.new(sep.outputs["X"], comb.inputs["X"]); wl.new(sep.outputs["Y"], comb.inputs["Y"]); wl.new(ad.outputs["Value"], comb.inputs["Z"])
wl.new(comb.outputs["Vector"], sky.inputs["Vector"])
w.node_tree.links.new(sky.outputs["Color"], bg.inputs["Color"])
bpy.ops.object.light_add(type="SUN", location=(0, 0, 20000)); sun = bpy.context.object
sun.data.energy = float(os.environ.get("SUN_E", "9.0")); sun.data.angle = math.radians(0.6); sun.data.color = (1.0, 0.84, 0.66)
# Blender sun points along its local -Z; aim it from azimuth (Nishita: 0 = north, clockwise) and elevation
az = math.radians(SUN_AZ); el = math.radians(SUN_ELEV)
sun_dir = Vector((math.sin(az)*math.cos(el), math.cos(az)*math.cos(el), math.sin(el)))   # direction TO the sun (ENU)
sun.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
# --- camera ---
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.sensor_fit = "VERTICAL"; cam.data.angle_y = math.radians(60); cam.data.clip_end = 400000; cam.data.clip_start = 20
center = Vector((0.0, 0.0, H*0.35))
START_R = min(max(3.2*R, 26000.0), (40000.0 - H*0.35)/0.559)   # P25-1028: closer start — relief fills the frame instead of a map view
END_R = max(2.5*R, 6000.0); END_R = min(END_R, START_R*0.6)      # the live app flies the last stretch itself (P17 endRange)
json.dump({"startRange": START_R, "endRange": END_R, "endPitch": P}, open(f"{slug}/path.json", "w"))
RES = int(os.environ.get("RES_W", "720"))
def pose(t):
    e = 4*t*t*t if t < 0.5 else 1 - ((-2*t+2)**3)/2
    h = math.radians(20 - 70*(1-e)); p = math.radians(P)*e + math.radians(-24)*(1-e)   # P25-1028: shallower start pitch
    rng = END_R + (START_R - END_R)*(1-e)
    d = Vector((math.sin(h)*math.cos(p), math.cos(h)*math.cos(p), math.sin(p)))  # view dir ENU
    cam.location = center - d*rng
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
# --- render settings ---
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SMP; sc.cycles.use_denoising = True
try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception: pass
sc.render.resolution_x = RES; sc.render.resolution_y = RES*16//9; sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"; sc.render.film_transparent = False
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Punchy"; sc.view_settings.exposure = float(os.environ.get("EXPO", "0.35"))
sc.cycles.transparent_max_bounces = 12
NF = round(FPS*DUR); os.makedirs(f"{slug}/frames", exist_ok=True)
for i in range(NF):
    if i < F0 or i > F1: continue
    pose(i/(NF-1) if NF > 1 else 1.0)
    sc.render.filepath = os.path.abspath(f"{slug}/frames/f{i:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("frame", i, flush=True)
