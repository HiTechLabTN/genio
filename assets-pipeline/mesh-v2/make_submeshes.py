#!/usr/bin/env python3
"""Generate modular accessory submeshes for the approved v2_fallback_baked.glb.

Each submesh is centered at its own origin; the socket anchor (world position)
is applied in RiggedMascot.tsx. Vertex colors only (no UV, no materials) so the
GLB stays tiny and consistent with the baked base mesh.

Outputs (in this directory):
  gland_submesh.glb        — black fez tassel (knot + strands)
  headphones_submesh.glb   — DJ headphones resting around the neck
  g_pendant_submesh.glb    — gold letter "G" pendant (chest chain)
"""
import numpy as np
import trimesh

OUT = "/data/ai_tools/genio/assets-pipeline/mesh-v2"


def _torus_arc(major: float, minor: float, u0_deg: float, u1_deg: float,
               plane: str = "xy", sections: int = 48, minor_sections: int = 12):
    """Parametric torus arc. plane='xy' → ring in x-y (normal +z);
    plane='xz' → ring in x-z (normal +y)."""
    u = np.linspace(np.radians(u0_deg), np.radians(u1_deg), sections)
    v = np.linspace(0, 2 * np.pi, minor_sections, endpoint=False)
    U, V = np.meshgrid(u, v, indexing="ij")
    cx = (major + minor * np.cos(V)) * np.cos(U)
    cy = (major + minor * np.cos(V)) * np.sin(U)
    cz = minor * np.sin(V)
    if plane == "xy":
        pts = np.stack([cx, cy, cz], axis=-1)
    else:  # xz
        pts = np.stack([cx, cz, cy], axis=-1)
    pts = pts.reshape(-1, 3)
    faces = []
    for i in range(sections - 1):
        for j in range(minor_sections):
            a = i * minor_sections + j
            b = i * minor_sections + (j + 1) % minor_sections
            c = (i + 1) * minor_sections + j
            d = (i + 1) * minor_sections + (j + 1) % minor_sections
            faces.append([a, b, d])
            faces.append([a, d, c])
    return trimesh.Trimesh(vertices=pts, faces=np.array(faces), process=False)


def _colored(mesh: trimesh.Trimesh, rgb: tuple) -> trimesh.Trimesh:
    colors = np.tile(np.array([*rgb, 255], dtype=np.uint8), (len(mesh.vertices), 1))
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=colors)
    return mesh


def _export(name: str, parts: list):
    scene = trimesh.Scene()
    for i, m in enumerate(parts):
        scene.add_geometry(m, node_name=f"{name}_{i}")
    path = f"{OUT}/{name}.glb"
    scene.export(path)
    print(f"wrote {path} ({len(parts)} parts)")


# ---------------------------------------------------------------- gland (fez tassel)
# Knot at the fez top + 5 splayed strands hanging down.
gland_parts = []
knot = trimesh.creation.icosphere(subdivisions=2, radius=0.042)
gland_parts.append(_colored(knot, (18, 18, 20)))
for k in range(5):
    ang = k / 5 * 2 * np.pi
    splay = 0.012
    x0, z0 = splay * np.cos(ang), splay * np.sin(ang)
    strand = trimesh.creation.cylinder(radius=0.0055, height=0.11, sections=8)
    # cylinder is along z; translate so it hangs from y=0 down to y=-0.11
    strand.apply_translation([x0, -0.055, z0])
    gland_parts.append(_colored(strand, (18, 18, 20)))
_export("gland_submesh", gland_parts)

# ---------------------------------------------------------------- headphones (neck)
# Ear cups: cylinders along x at (±0.30, 0, -0.02) in local frame (anchor at neck).
# Headband: torus arc in x-z plane behind the neck.
hp_parts = []
cup = trimesh.creation.cylinder(radius=0.058, height=0.075, sections=24)
cup.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))  # axis → x
for sx in (-1, 1):
    c = cup.copy()
    c.apply_translation([sx * 0.30, 0.0, -0.02])
    hp_parts.append(_colored(c, (24, 24, 28)))
    # red accent ring on the outer face
    ring = trimesh.creation.cylinder(radius=0.058, height=0.012, sections=24)
    ring.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    ring.apply_translation([sx * 0.30 + sx * 0.038, 0.0, -0.02])
    hp_parts.append(_colored(ring, (176, 42, 38)))
band = _torus_arc(0.26, 0.02, 0, 180, plane="xz", sections=56)
band.apply_translation([0, 0.03, 0.06])
hp_parts.append(_colored(band, (24, 24, 28)))
_export("headphones_submesh", hp_parts)

# ---------------------------------------------------------------- letter G pendant
# Ring arc (270°, gap on the right) + horizontal bar, gold. Ring in x-y plane.
g_parts = []
arc = _torus_arc(0.052, 0.013, 90, 360, plane="xy", sections=64)
g_parts.append(_colored(arc, (212, 175, 55)))
bar = trimesh.creation.box(extents=(0.052, 0.015, 0.015))
bar.apply_translation([0.026, 0.0, 0.0])
g_parts.append(_colored(bar, (212, 175, 55)))
_export("g_pendant_submesh", g_parts)

print("done")