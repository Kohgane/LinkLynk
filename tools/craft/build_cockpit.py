#!/usr/bin/env python3
"""Procedural fighter-jet cockpit interior (pilot-eye at origin, forward = -Y, up = +Z) -> cockpit.glb
Built for SWEF v2 first-person view: canopy bow + side rails, glare shield, HUD combiner glass, instrument panel, side consoles."""
import bpy, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
out = sys.argv[-1] if sys.argv[-1].endswith(".glb") else os.path.join(ROOT, "static", "fly", "v2", "models", "cockpit.glb")
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
def mat(name, rgb, rough=0.6, metal=0.0, emit=None, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if emit: b.inputs["Emission Color"].default_value = (*emit[0], 1); b.inputs["Emission Strength"].default_value = emit[1]
    if alpha < 1: b.inputs["Alpha"].default_value = alpha; m.blend_method = "BLEND"
    return m
dark = mat("frame", (0.05, 0.055, 0.06), 0.55, 0.3)
rubber = mat("rubber", (0.02, 0.02, 0.025), 0.9)
panel = mat("panel", (0.03, 0.035, 0.04), 0.7)
glow = mat("glow", (0.1, 0.9, 0.5), 0.4, emit=((0.25, 1.0, 0.55), 2.5))
amber = mat("amber", (1.0, 0.6, 0.15), 0.4, emit=((1.0, 0.55, 0.12), 2.0))
glass = mat("glass", (0.6, 0.8, 0.9), 0.05, alpha=0.18)
objs = []
def add(ob, m):
    ob.data.materials.append(m); objs.append(ob); return ob
def tube(pts, r, m, name):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = r; cu.bevel_resolution = 4
    sp = cu.splines.new("NURBS"); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts): sp.points[i].co = (*p, 1.0)
    sp.use_endpoint_u = True; sp.order_u = 3
    ob = bpy.data.objects.new(name, cu); sc.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True); bpy.ops.object.convert(target="MESH")
    return add(ob, m)
def tubep(pts, r, m, name):  # straight-segment tube (POLY) for rectangular frames
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = r; cu.bevel_resolution = 3
    sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts): sp.points[i].co = (*p, 1.0)
    ob = bpy.data.objects.new(name, cu); sc.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True); bpy.ops.object.convert(target="MESH")
    return add(ob, m)
def box(loc, scale, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, scale=scale); o = bpy.context.object; o.rotation_euler = rot; return add(o, m)
# pilot eye at origin; forward = -Y; realistic reach: glare shield top ~0.22 m below the eye, ~0.8 m ahead
# --- canopy bow (front arch) + side rails + sill ---
arch = [(-0.80 + 1.60 * i / 20, -1.05 - 0.12 * math.sin(math.pi * i / 20), -0.10 + 0.80 * math.sin(math.pi * i / 20)) for i in range(21)]
tube(arch, 0.03, dark, "bow")
for s_ in (-1, 1):
    tube([(s_ * 0.80, -1.05, -0.10), (s_ * 0.84, -0.4, -0.06), (s_ * 0.86, 0.4, -0.04), (s_ * 0.84, 1.2, -0.08)], 0.03, dark, "rail%d" % s_)
    box((s_ * 0.82, 0.0, -0.40), (0.05, 1.2, 0.30), panel)  # cockpit side wall below the sill
# --- dashboard block: glare shield (top), instrument face (toward pilot) ---
box((0, -1.06, -0.56), (0.72, 0.30, 0.26), panel)                 # main dash body: y -1.36..-0.76, z -0.82..-0.30
box((0, -1.04, -0.295), (0.74, 0.34, 0.012), rubber)               # glare shield top skin
box((0, -1.37, -0.25), (0.74, 0.02, 0.05), rubber)                 # shield lip
# instrument face at y=-0.72 (front face of dash): MFDs + gauges
for x in (-0.36, 0.36):
    box((x, -0.755, -0.52), (0.13, 0.004, 0.11), glow)
    tubep([(x - 0.15, -0.75, -0.65), (x - 0.15, -0.75, -0.39), (x + 0.15, -0.75, -0.39), (x + 0.15, -0.75, -0.65), (x - 0.15, -0.75, -0.65)], 0.008, dark, "mfd%s" % x)
for i, x in enumerate((-0.12, 0.0, 0.12)):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.01, location=(x, -0.755, -0.46 + (0.05 if i == 1 else 0))); g = bpy.context.object; g.rotation_euler = (math.radians(90), 0, 0); add(g, amber if i != 1 else glow)
for k in range(6):  # warning/caution lights row
    box((-0.25 + 0.1 * k, -0.755, -0.66), (0.03, 0.003, 0.012), amber if k % 2 else glow)
# --- HUD combiner glass + frame + projector ---
box((0, -0.80, 0.0), (0.13, 0.002, 0.12), glass, (math.radians(10), 0, 0))
tubep([(-0.135, -0.80, -0.13), (-0.135, -0.805, 0.13), (0.135, -0.805, 0.13), (0.135, -0.80, -0.13)], 0.009, dark, "hudframe")
box((0, -0.92, -0.24), (0.09, 0.07, 0.04), rubber)
# --- lower structure: knees/floor, side consoles, stick, throttle ---
box((0, -0.55, -1.00), (0.75, 0.80, 0.25), panel)                  # floor/knee well
for s_ in (-1, 1):
    box((s_ * 0.60, -0.10, -0.62), (0.16, 0.60, 0.05), panel)      # side consoles
    for k in range(5): box((s_ * 0.60, -0.55 + 0.2 * k, -0.565), (0.05, 0.03, 0.006), glow if k % 2 else amber)
bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.36, location=(0.0, -0.42, -0.72)); add(bpy.context.object, rubber)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(0.0, -0.42, -0.53)); add(bpy.context.object, rubber)
box((-0.60, -0.40, -0.55), (0.05, 0.09, 0.04), rubber)
for o in objs: o.select_set(True)
bpy.ops.object.shade_smooth()
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_apply=True, use_selection=True)
print("exported", out, "tris", sum(len(o.data.polygons) for o in objs if o.type == "MESH"), "bytes", os.path.getsize(out))
