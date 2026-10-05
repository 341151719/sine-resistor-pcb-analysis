"""Generate a Blender model and render from the current V8 KiCad PCB.

The scene is intentionally procedural and auditable: the board outline and
top copper segments come from project.kicad_pcb, while component locations and
values come from audit/cpl_smt.csv.  Component bodies are engineering-level
approximations because the source project does not contain a complete set of
3D vendor models.

Run with Blender in background mode, for example:

    blender --background --python blender/generate_v8_pcb_scene.py

Set PROJECT_ROOT when running from another directory.
"""

from __future__ import annotations

import csv
import math
import os
import re
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
PCB_PATH = PROJECT_ROOT / "KICAD部分/正弦电阻V8_KiCad10.0.4_稳定性修正版_2026-09-04/project.kicad_pcb"
CPL_PATH = PROJECT_ROOT / "KICAD部分/正弦电阻V8_KiCad10.0.4_稳定性修正版_2026-09-04/audit/cpl_smt.csv"
OUT_DIR = Path(os.environ.get("BLENDER_OUT", PROJECT_ROOT / "blender/output"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOARD_THICKNESS = 1.6
BOARD_CORNER_RADIUS = 5.08
COPPER_Z = BOARD_THICKNESS + 0.035
SILK_Z = BOARD_THICKNESS + 0.22
VISUAL_TRACE_SCALE = 1.45


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_board_bounds(pcb_text: str):
    """Read the Edge.Cuts bounding box from the KiCad board file."""
    points = []
    edge_re = re.compile(
        r"\((?:gr_line|gr_arc)\s+(.*?)\n\s*\(layer \"Edge\.Cuts\"\)",
        re.DOTALL,
    )
    for block_match in edge_re.finditer(pcb_text):
        block = block_match.group(1)
        for tag in ("start", "mid", "end"):
            m = re.search(rf"\({tag}\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)", block)
            if m:
                points.append((float(m.group(1)), float(m.group(2))))
    if len(points) < 4:
        # These are the coordinates already independently confirmed in the
        # project when a malformed/older KiCad exporter omits arc text.
        return 89.965, 206.297, 51.64, 164.162
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def parse_copper_segments(pcb_text: str):
    """Return simple F.Cu segments for a single combined trace mesh."""
    result = []
    # Segment records do not contain nested records, so this is robust across
    # KiCad 8/9/10 formatting variants.
    for block_match in re.finditer(r"\(segment\s+(.*?)\n\s*\)", pcb_text, re.DOTALL):
        block = block_match.group(1)
        if '(layer "F.Cu")' not in block:
            continue
        sm = re.search(r"\(start\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)", block)
        em = re.search(r"\(end\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)", block)
        wm = re.search(r"\(width\s+(-?[0-9.]+)\)", block)
        if not (sm and em and wm):
            continue
        result.append(
            (
                float(sm.group(1)),
                float(sm.group(2)),
                float(em.group(1)),
                float(em.group(2)),
                float(wm.group(1)),
            )
        )
    return result


def read_components(cpl_path: Path):
    with cpl_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    components = []
    for row in rows:
        try:
            # CPL exports use a mirrored Y coordinate relative to the KiCad
            # board coordinate system used by Edge.Cuts and copper segments.
            x = float(row["PosX"])
            y = -float(row["PosY"])
            angle = float(row["Rot"])
        except (KeyError, TypeError, ValueError):
            continue
        components.append(
            {
                "ref": row.get("Ref", ""),
                "value": row.get("Val", ""),
                "package": row.get("Package", ""),
                "x": x,
                "y": y,
                "angle": angle,
                "side": row.get("Side", "top").lower(),
            }
        )
    return components


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        # Do not remove the default World or fonts; only generated datablocks
        # are present in a fresh background session.
        pass


def make_material(name, color, metallic=0.0, roughness=0.45):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if bsdf.inputs.get("Base Color"):
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if bsdf.inputs.get("Metallic"):
            bsdf.inputs["Metallic"].default_value = metallic
        if bsdf.inputs.get("Roughness"):
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


def assign_material(obj, material):
    if material and obj.data and hasattr(obj.data, "materials"):
        obj.data.materials.append(material)


def rounded_prism(name, width, height, depth, radius, z0, material, segments=8):
    """Create a rounded rectangle prism with dimensions in millimetres."""
    radius = min(radius, width / 2.0, height / 2.0)
    centers = [
        (width / 2 - radius, height / 2 - radius, 0.0),
        (-width / 2 + radius, height / 2 - radius, math.pi / 2),
        (-width / 2 + radius, -height / 2 + radius, math.pi),
        (width / 2 - radius, -height / 2 + radius, 3 * math.pi / 2),
    ]
    outline = []
    for cx, cy, start in centers:
        for i in range(segments + 1):
            theta = start + math.pi / 2 * i / segments
            outline.append((cx + radius * math.cos(theta), cy + radius * math.sin(theta)))

    verts = [(x, y, z0) for x, y in outline] + [(x, y, z0 + depth) for x, y in outline]
    n = len(outline)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    assign_material(obj, material)
    return obj


def add_cube(name, location, dimensions, material, rotation=0.0, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=(0.0, 0.0, rotation))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(obj, material)
    if bevel > 0:
        mod = obj.modifiers.new("soft_edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def add_cylinder(name, location, radius, depth, material, vertices=32, rotation=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
        rotation=rotation or (0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    assign_material(obj, material)
    return obj


def add_text(name, body, location, size, material, rotation=0.0, extrude=0.035, align="CENTER"):
    curve = bpy.data.curves.new(name + "Curve", type="FONT")
    curve.body = body
    curve.align_x = align
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = extrude
    curve.bevel_depth = 0.012
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler[2] = rotation
    assign_material(obj, material)
    return obj


def offset_xy(x, y, dx, dy, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return x + c * dx - s * dy, y + s * dx + c * dy


def add_trace_mesh(name, segments, material):
    verts = []
    faces = []
    z_bottom = COPPER_Z
    z_top = COPPER_Z + 0.07
    for x1, y1, x2, y2, width in segments:
        # Real copper is thin at this camera distance.  A modest visual
        # enlargement keeps the extracted routing legible without changing
        # the source geometry or its net connectivity.
        width *= VISUAL_TRACE_SCALE
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 0.02:
            continue
        nx = -dy / length * width / 2
        ny = dx / length * width / 2
        p = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
        base = len(verts)
        verts.extend([(a, b, z_bottom) for a, b in p] + [(a, b, z_top) for a, b in p])
        faces.extend(
            [
                (base, base + 3, base + 2, base + 1),
                (base + 4, base + 5, base + 6, base + 7),
                (base, base + 1, base + 5, base + 4),
                (base + 1, base + 2, base + 6, base + 5),
                (base + 2, base + 3, base + 7, base + 6),
                (base + 3, base, base + 4, base + 7),
            ]
        )
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    assign_material(obj, material)
    return obj


def package_dimensions(package):
    p = package.lower()
    if "c0805" in p or "r0805" in p or "l0805" in p:
        return 2.0, 1.25, 0.65
    if "soic-8" in p:
        return 4.9, 3.9, 1.55
    if "vssop-8" in p:
        return 3.0, 3.0, 1.25
    if "lqfp-48" in p:
        return 7.0, 7.0, 1.55
    if "to-263" in p:
        return 10.2, 10.4, 4.25
    if "sot-223" in p:
        return 6.5, 3.4, 1.9
    if "sop-6" in p:
        return 4.6, 3.7, 1.7
    if "cap-smd" in p:
        return 10.3, 10.3, 11.0
    if "smb" in p:
        return 4.3, 3.6, 2.0
    if "shunt" in p:
        return 10.0, 5.0, 3.0
    if "pinheader_1x05_p1.27" in p:
        return 6.35, 2.0, 5.5
    if "pinheader_1x05_p2.54" in p or "hdr-th_5p" in p:
        return 12.7, 2.54, 7.0
    if "conn-smd_l12.7" in p:
        return 12.7, 3.9, 5.2
    if "conn-smd_2060-453" in p:
        return 9.1, 7.0, 5.0
    if "conn-smd_2060-452" in p:
        return 6.6, 7.0, 5.0
    if "test-point" in p or "testpoint" in p:
        return 1.5, 1.5, 0.4
    if "fiducial" in p:
        return 1.0, 1.0, 0.15
    return 2.5, 2.5, 1.0


def component_material(ref, package, mats):
    p = package.lower()
    if ref.startswith("U") or "soic" in p or "lqfp" in p or "sop-6" in p:
        return mats["ic"]
    if ref.startswith("R") or "shunt" in p:
        return mats["res"]
    if ref.startswith("C") or "cap-smd" in p:
        return mats["cap"]
    if ref.startswith("J") or "conn" in p or "header" in p or "hdr-" in p:
        return mats["connector"]
    if ref.startswith("TP") or "test-point" in p or "testpoint" in p:
        return mats["gold"]
    if "fiducial" in p:
        return mats["gold"]
    return mats["generic"]


def add_pins_for_chip(ref, x, y, angle, dims, z, side, mats):
    w, h, _ = dims
    p = ref.upper()
    if not (p.startswith("U") or "IC" in p):
        return
    if w >= 6.5:
        count = 12
    elif w <= 3.1:
        count = 4
    else:
        count = 4
    metal = mats["metal"]
    sign = 1 if side == "top" else -1
    pin_z = z + sign * 0.05
    pin_h = 0.18
    pin_l = 0.9
    for i in range(count):
        t = (i + 0.5) / count
        yy = -h / 2 + h * t
        px, py = offset_xy(x, y, -w / 2 - pin_l / 2, yy, angle)
        add_cube(f"{ref}_pin_L_{i}", (px, py, pin_z), (pin_l, pin_h, 0.16), metal, rotation=angle)
        px, py = offset_xy(x, y, w / 2 + pin_l / 2, yy, angle)
        add_cube(f"{ref}_pin_R_{i}", (px, py, pin_z), (pin_l, pin_h, 0.16), metal, rotation=angle)
    if w >= 6.5:
        for i in range(count):
            t = (i + 0.5) / count
            xx = -w / 2 + w * t
            px, py = offset_xy(x, y, xx, -h / 2 - pin_l / 2, angle)
            add_cube(f"{ref}_pin_B_{i}", (px, py, pin_z), (pin_h, pin_l, 0.16), metal, rotation=angle)
            px, py = offset_xy(x, y, xx, h / 2 + pin_l / 2, angle)
            add_cube(f"{ref}_pin_T_{i}", (px, py, pin_z), (pin_h, pin_l, 0.16), metal, rotation=angle)


def add_component(component, mats, board_top):
    ref = component["ref"]
    package = component["package"]
    x = component["x"]
    y = component["y"]
    angle = math.radians(-component["angle"])
    side = "bottom" if component["side"].startswith("bottom") else "top"
    w, h, height = package_dimensions(package)
    material = component_material(ref, package, mats)
    if "fiducial" in package.lower():
        z = board_top + 0.10 if side == "top" else -0.10
        add_cylinder(ref + "_fiducial", (x, y, z), 0.5, 0.18, mats["gold"])
        return
    if "test-point" in package.lower() or "testpoint" in package.lower():
        z = board_top + 0.30 if side == "top" else -0.30
        add_cylinder(ref + "_pad", (x, y, z), 0.75, 0.35, mats["gold"])
        add_cylinder(ref + "_post", (x, y, z + (0.7 if side == "top" else -0.7)), 0.22, 1.4, mats["metal"])
        return
    sign = 1 if side == "top" else -1
    z = board_top + height / 2 if side == "top" else -height / 2
    if "cap-smd" in package.lower():
        # Aluminium electrolytic can, with a small polarity stripe.
        add_cylinder(ref + "_can", (x, y, z), min(w, h) * 0.44, height, mats["cap_dark"], vertices=48)
        stripe_x, stripe_y = offset_xy(x, y, -w * 0.26, 0, angle)
        add_cube(ref + "_stripe", (stripe_x, stripe_y, z), (0.28, h * 0.78, height * 0.86), mats["stripe"], rotation=angle)
    elif "conn" in package.lower() or "header" in package.lower() or "hdr-" in package.lower():
        add_cube(ref + "_body", (x, y, z), (w, h, height), mats["connector"], rotation=angle, bevel=0.35)
        pitch = 2.54 if "2.54" in package or "hdr-" in package else 3.5
        n = 5 if "5p" in package.lower() or "1x05" in package.lower() else 3
        for i in range(n):
            dx = (i - (n - 1) / 2) * pitch
            px, py = offset_xy(x, y, dx, 0, angle)
            add_cylinder(ref + f"_pin_{i+1}", (px, py, z + sign * (height / 2 + 0.8)), 0.32, 2.0, mats["metal"], vertices=20)
    elif "smb" in package.lower():
        add_cube(ref + "_body", (x, y, z), (w * 0.62, h, height), mats["diode"], rotation=angle, bevel=0.18)
        for dx in (-w * 0.42, w * 0.42):
            px, py = offset_xy(x, y, dx, 0, angle)
            add_cube(ref + "_end", (px, py, z), (w * 0.18, h * 0.75, height * 0.7), mats["metal"], rotation=angle)
    else:
        add_cube(ref + "_body", (x, y, z), (w, h, height), material, rotation=angle, bevel=min(0.18, height / 5))
        if ref.startswith("R") or ref.startswith("C") or ref.startswith("L"):
            # Exposed end terminations on passives.
            for dx in (-w * 0.42, w * 0.42):
                px, py = offset_xy(x, y, dx, 0, angle)
                add_cube(ref + "_term", (px, py, z + sign * height * 0.03), (w * 0.18, h * 0.85, height * 0.7), mats["metal"], rotation=angle)
        add_pins_for_chip(ref, x, y, angle, (w, h, height), z, side, mats)


def setup_camera_and_lights(scene, target):
    def point_at(obj, point):
        obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()

    bpy.ops.object.camera_add(location=(164, -158, 175))
    camera = bpy.context.object
    camera.name = "Camera_Isometric"
    camera.data.lens = 53
    camera.data.sensor_width = 36
    camera.data.clip_end = 1000
    point_at(camera, target)
    scene.camera = camera

    light_specs = [
        ("Key", (20, -55, 220), (130, 120), (1.0, 0.89, 0.72), 130000),
        ("Fill", (-145, -10, 100), (90, 90), (0.46, 0.68, 1.0), 85000),
        ("Rim", (120, 130, 170), (100, 80), (0.52, 0.74, 1.0), 100000),
    ]
    for name, loc, size, color, power in light_specs:
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = name
        light.data.energy = power
        light.data.shape = "DISK"
        light.data.size = size[0]
        light.data.color = color
        point_at(light, target)


def build_scene():
    clear_scene()
    pcb_text = read_text(PCB_PATH)
    min_x, max_x, min_y, max_y = parse_board_bounds(pcb_text)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    board_w = max_x - min_x
    board_h = max_y - min_y
    segments = parse_copper_segments(pcb_text)
    components = read_components(CPL_PATH)

    mats = {
        "board": make_material("PCB green", (0.035, 0.30, 0.12), metallic=0.0, roughness=0.32),
        "board_edge": make_material("PCB edge", (0.018, 0.08, 0.045), roughness=0.55),
        "copper": make_material("Copper", (1.0, 0.34, 0.035), metallic=0.72, roughness=0.24),
        "silk": make_material("Silkscreen", (1.0, 0.96, 0.52), roughness=0.32),
        "metal": make_material("Lead metal", (0.53, 0.57, 0.60), metallic=0.86, roughness=0.22),
        "gold": make_material("Testpoint gold", (0.95, 0.52, 0.08), metallic=0.86, roughness=0.22),
        "ic": make_material("IC black", (0.012, 0.014, 0.018), roughness=0.28),
        "res": make_material("Resistor body", (0.26, 0.17, 0.10), roughness=0.34),
        "cap": make_material("Ceramic capacitor", (0.68, 0.52, 0.30), roughness=0.45),
        "cap_dark": make_material("Electrolytic sleeve", (0.045, 0.09, 0.14), roughness=0.3),
        "stripe": make_material("Polarity stripe", (0.78, 0.78, 0.70), roughness=0.38),
        "connector": make_material("Connector blue", (0.02, 0.18, 0.38), roughness=0.30),
        "diode": make_material("Diode black", (0.015, 0.018, 0.02), roughness=0.28),
        "generic": make_material("Generic component", (0.20, 0.22, 0.22), roughness=0.4),
        "ground": make_material("Ground", (0.006, 0.008, 0.012), roughness=0.58),
    }

    board = rounded_prism("PCB_V8", board_w, board_h, BOARD_THICKNESS, BOARD_CORNER_RADIUS, 0.0, mats["board"], segments=10)
    board.location = (0.0, 0.0, 0.0)

    # Keep all PCB geometry in a local coordinate system centred on the board.
    trace_segments = []
    for x1, y1, x2, y2, width in segments:
        trace_segments.append((x1 - center_x, y1 - center_y, x2 - center_x, y2 - center_y, width))
    add_trace_mesh("F_Cu_segments", trace_segments, mats["copper"])

    # A thin solder-mask highlight makes the board edge readable without
    # hiding the actual copper lines extracted from the board file.
    mask = rounded_prism("Solder_mask_surface", board_w - 1.4, board_h - 1.4, 0.025, BOARD_CORNER_RADIUS - 0.7, BOARD_THICKNESS, mats["board"], segments=10)

    # Components are placed from the CPL, whose X coordinate is direct and Y
    # is mirrored relative to the PCB coordinate system.
    for component in components:
        component["x"] -= center_x
        component["y"] -= center_y
        add_component(component, mats, BOARD_THICKNESS)

    # Human-readable reference labels for the critical bring-up points.
    by_ref = {c["ref"]: c for c in components}
    key_refs = ["J1", "J2", "J3", "J4", "J5", "J7", "U1", "U4", "U5", "R5", "R10", "R12", "TP7", "TP8", "TP9", "TP14", "TP16", "TP17"]
    for ref in key_refs:
        c = by_ref.get(ref)
        if not c or c["side"] != "top":
            continue
        pkg_dims = package_dimensions(c["package"])
        dy = pkg_dims[1] / 2 + 1.35
        label_x, label_y = c["x"], c["y"] + dy
        size = 1.25 if ref.startswith("TP") else 1.55
        add_text("Silk_" + ref, ref, (label_x, label_y, SILK_Z), size, mats["silk"], rotation=0.0, extrude=0.025)

    add_text("BoardTitle", "C11_35  /  V8 PCB", (-31, -48, SILK_Z), 3.0, mats["silk"], extrude=0.035)
    add_text("BoardSubTitle", "ACTIVE ACOUSTIC IMPEDANCE CONTROLLER", (-31, -43, SILK_Z), 1.2, mats["silk"], extrude=0.025, align="LEFT")
    add_text("AnalogLabel", "ANALOG", -47 * Vector((1, 0, 0)) + Vector((0, -22, SILK_Z)), 1.4, mats["silk"], extrude=0.025)

    # Ground plane and a subtle presentation frame.
    add_cube("GroundPlane", (0, 0, -8.0), (board_w + 125, board_h + 115, 2.0), mats["ground"], bevel=5.0)
    add_text("RenderCaption", "V8 PCB / procedural Blender model from KiCad", (-board_w / 2 - 44, -board_h / 2 - 38, -6.8), 2.4, mats["silk"], extrude=0.02, align="LEFT")

    scene = bpy.context.scene
    # Blender 5.2 exposes the Eevee engine as BLENDER_EEVEE (the enum name
    # changed between development snapshots even though it is Eevee Next).
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1350
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(OUT_DIR / "c11_35_v8_pcb_isometric.png")
    scene.render.resolution_percentage = 100
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 1.15
    scene.world.color = (0.003, 0.004, 0.008)

    # World nodes give a small amount of fill in the dark presentation scene.
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.004, 0.006, 0.012, 1.0)
        bg.inputs["Strength"].default_value = 0.42

    setup_camera_and_lights(scene, (0, 0, 0))
    iso_camera = scene.camera

    # A second camera is kept in the .blend for inspection and produces a
    # true top view suitable for checking placement and silkscreen labels.
    bpy.ops.object.camera_add(location=(0, 0, 280))
    top_camera = bpy.context.object
    top_camera.name = "Camera_Top"
    top_camera.data.type = "ORTHO"
    # ortho_scale is the frame width; account for the 4:3 render aspect so
    # the full board height is also inside the top-view image.
    aspect = scene.render.resolution_x / scene.render.resolution_y
    top_camera.data.ortho_scale = max(board_w, board_h * aspect) * 1.10
    top_camera.data.clip_end = 1000
    top_camera.rotation_euler = (0.0, 0.0, 0.0)
    top_camera.rotation_euler[0] = 0.0
    # A camera points down -Z by default; rotating 180° around X makes its
    # local -Z axis point at the board from above.
    top_camera.rotation_euler[0] = 0.0
    top_camera.rotation_euler[2] = 0.0
    top_camera.rotation_euler[1] = 0.0
    top_camera.rotation_euler = (0.0, 0.0, 0.0)
    scene.camera = top_camera
    scene.render.filepath = str(OUT_DIR / "c11_35_v8_pcb_top.png")
    bpy.ops.render.render(write_still=True)

    scene.camera = iso_camera
    scene.render.filepath = str(OUT_DIR / "c11_35_v8_pcb_isometric.png")
    scene["source_pcb"] = str(PCB_PATH.relative_to(PROJECT_ROOT))
    scene["source_cpl"] = str(CPL_PATH.relative_to(PROJECT_ROOT))
    scene["board_bounds_mm"] = f"{min_x},{max_x},{min_y},{max_y}"
    scene["component_count"] = len(components)
    scene["trace_count"] = len(segments)
    scene["model_note"] = "Engineering approximation: component 3D bodies are procedural; coordinates derive from current KiCad V8 PCB/CPL."

    blend_path = OUT_DIR / "c11_35_v8_pcb_model.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)
    print(f"Saved Blender scene: {blend_path}")
    print(f"Saved render: {scene.render.filepath}")
    print(f"Board: {board_w:.3f} x {board_h:.3f} mm; components={len(components)}; F.Cu segments={len(segments)}")


if __name__ == "__main__":
    build_scene()
