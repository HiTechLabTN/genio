import trimesh, numpy as np
from PIL import Image, ImageEnhance
import rembg

GLB = "/data/ai_tools/genio/assets-pipeline/mesh-v2/v2_clean.glb"
OUT = "/data/ai_tools/genio/assets-pipeline/mesh-v2/v2_fallback_baked.glb"
VIEW_DIR = "/data/ai_tools/genio/assets-pipeline/reference-views-v2"
VIEWS = ['view_front', 'view_34R', 'view_profile', 'view_back', 'view_34L']
# Y-up trimesh coords, front = -Z. az rotates around +Y from front.
AZ = [0, 45, 90, 180, 315]
EL = [8, 5, 8, 8, 5]
RADIUS, FOV = 4.0, 30.0
focal = 0.5/np.tan(np.radians(FOV)/2)
GRID = 512
GAIN, CONTRAST, SAT = 1.42, 1.10, 1.12

mesh = trimesh.load(GLB, force='mesh')
verts = np.asarray(mesh.vertices)
faces = np.asarray(mesh.faces)
print(f"verts {len(verts)} faces {len(faces)}", flush=True)
print(f"bounds {mesh.bounds}", flush=True)
mesh.vertex_normals
normals = np.asarray(mesh.vertex_normals)
# target = mesh center (Y-up)
target = np.array([(mesh.bounds[0]+mesh.bounds[1])/2]).flatten()
print("target", target, flush=True)

def cam_matrix_yup(az_deg, el_deg, r):
    az_r, el_r = np.radians(az_deg), np.radians(el_deg)
    # front (0,0,-1) rotated about Y
    d = np.array([-np.sin(az_r)*np.cos(el_r), np.sin(el_r), -np.cos(az_r)*np.cos(el_r)])
    cam_pos = target + d*r
    z_axis = d  # from target to camera, normalized
    up = np.array([0,1.0,0])
    x_axis = np.cross(up, z_axis); x_axis/=np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    return cam_pos, np.stack([x_axis, y_axis, z_axis], axis=0)

sess = rembg.new_session()
imgs = []
for v in VIEWS:
    img = Image.open(f"{VIEW_DIR}/{v}.png").convert("RGB")
    fg = rembg.remove(img, session=sess)
    bg = Image.new('RGBA', img.size, (255,255,255,255))
    base = Image.alpha_composite(bg, fg).convert("RGB")
    base = ImageEnhance.Brightness(base).enhance(GAIN)
    base = ImageEnhance.Contrast(base).enhance(CONTRAST)
    base = ImageEnhance.Color(base).enhance(SAT)
    imgs.append(np.asarray(base, dtype=np.float32))
    print(f"{v}: mean {np.asarray(base).mean((0,1)).astype(int)}", flush=True)

N = len(verts)
view_data = []
for k in range(len(VIEWS)):
    cam_pos, R = cam_matrix_yup(AZ[k], EL[k], RADIUS)
    d = verts - cam_pos
    xc = d@R[0]; yc = d@R[1]; zc = d@R[2]
    depth = -zc
    ix = focal*xc/depth + 0.5
    iy = 0.5 - focal*yc/depth
    valid = (depth > 0.01) & (ix >= 0) & (ix < 1) & (iy >= 0) & (iy < 1)
    cellx = np.clip((ix*GRID).astype(int), 0, GRID-1)
    celly = np.clip((iy*GRID).astype(int), 0, GRID-1)
    cellid = np.where(valid, celly*GRID + cellx, -1)
    best = np.full(GRID*GRID, np.inf)
    np.minimum.at(best, cellid[valid], depth[valid])
    visible = valid & (depth <= best[cellid] + 5e-4)
    view_dir = (target - cam_pos); view_dir/=np.linalg.norm(view_dir)
    # facing: normal vs view direction (direction from surface to camera = -view travel = cam-vert)
    view_data.append((ix, iy, visible, -view_dir, cam_pos))
    print(f"{VIEWS[k]}: {visible.sum()} visibles", flush=True)

best_view = np.full(N, -1, dtype=int)
best_score = np.full(N, -1e9)
for k in range(len(VIEWS)):
    ix, iy, visible, vdir, cam_pos = view_data[k]
    # per-vertex direction to camera
    tocam = np.stack([view_data[k][4]-verts[:,0:1]*0], axis=0)  # placeholder
    tocam = view_data[k][4][None,:] - verts
    tocam /= (np.linalg.norm(tocam,axis=1,keepdims=True)+1e-9)
    score = (normals*tocam).sum(1)
    upd = visible & (score > best_score)
    best_view[upd] = k
    best_score[upd] = score[upd]

unassigned = best_view < 0
print(f"sans vue (1er passage): {unassigned.sum()}", flush=True)
if unassigned.any():
    idx = np.where(unassigned)[0]
    sc = np.stack([(normals[idx]*((view_data[k][4][None,:]-verts[idx])/(np.linalg.norm(view_data[k][4][None,:]-verts[idx],axis=1,keepdims=True)+1e-9))).sum(1) for k in range(len(VIEWS))], axis=1)
    bv = sc.argmax(axis=1); bs = sc.max(axis=1)
    ok = bs > -0.2
    best_view[idx[ok]] = bv[ok]
    print(f"second passage: {ok.sum()} assignés", flush=True)

new_colors = np.full((N,3), 128, np.float32)
for k in range(len(VIEWS)):
    sel = best_view == k
    if sel.sum() == 0: continue
    ix, iy, _, _, _ = view_data[k]
    img = imgs[k]; H, W = img.shape[:2]
    px = np.clip(ix[sel]*W, 0, W-1.001); py = np.clip(iy[sel]*H, 0, H-1.001)
    x0 = px.astype(int); y0 = py.astype(int)
    fx = px-x0; fy = py-y0
    x1 = np.minimum(x0+1, W-1); y1 = np.minimum(y0+1, H-1)
    w = np.stack([(1-fx)*(1-fy), fx*(1-fy), (1-fx)*fy, fx*fy], axis=1)
    c = img[y0,x0]*w[:,0:1]+img[y0,x1]*w[:,1:2]+img[y1,x0]*w[:,2:3]+img[y1,x1]*w[:,3:4]
    new_colors[sel] = c
    print(f"{VIEWS[k]}: {sel.sum()} colorés", flush=True)

print(f"sans vue final: {(best_view<0).sum()}", flush=True)
out = trimesh.Trimesh(vertices=verts, faces=faces, vertex_colors=new_colors.astype(np.uint8))
out.export(OUT)
print("Saved", OUT)
