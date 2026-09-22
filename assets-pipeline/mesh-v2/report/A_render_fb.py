import bpy, sys, math, os, mathutils
SRC="/data/ai_tools/genio/assets-pipeline/mesh-v2/v2_fallback_baked_v2.glb"
OUT="/tmp/partA_fbv2"
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
S=bpy.context.scene
S.render.engine='BLENDER_EEVEE'; S.render.resolution_x=S.render.resolution_y=1024
S.world=bpy.data.worlds.new('W'); S.world.use_nodes=True
bg=S.world.node_tree.nodes['Background']; bg.inputs[0].default_value=(0.45,0.45,0.5,1); bg.inputs[1].default_value=1.0
for name,loc,rot,e in [('Key',(4,-6,6),(0.9,0,0.6),300),('Fill',(-5,-3,3),(0.8,0,-2.2),120),('Rim',(0,5,4),(0.9,0,3.14),150)]:
    l=bpy.data.lights.new(name,type='AREA'); l.energy=e; l.size=5
    o=bpy.data.objects.new(name,l); o.location=loc; o.rotation_euler=rot; S.collection.objects.link(o)
mat=bpy.data.materials.new('VCOL'); mat.use_nodes=True; nt=mat.node_tree
bsdf=nt.nodes['Principled BSDF']
vc=nt.nodes.new('ShaderNodeVertexColor')
try: vc.layer_name='Col'
except: pass
nt.links.new(vc.outputs['Color'], bsdf.inputs['Base Color'])
for o in [x for x in bpy.data.objects if x.type=='MESH']:
    o.data.materials.clear(); o.data.materials.append(mat)
meshes=[o for o in bpy.data.objects if o.type=='MESH']
mn=[1e9]*3; mx=[-1e9]*3
for o in meshes:
    for c in o.bound_box:
        w=o.matrix_world@mathutils.Vector(c)
        for i in range(3): mn[i]=min(mn[i],w[i]); mx[i]=max(mx[i],w[i])
cx,cy,cz=[(a+b)/2 for a,b in zip(mn,mx)]; size=max(mx[i]-mn[i] for i in range(3))
print(f"bbox c=({cx:.3f},{cy:.3f},{cz:.3f}) size={size:.3f}")
cam=bpy.data.cameras.new('V'); cam.type='PERSP'; cam.lens=50
co=bpy.data.objects.new('V',cam); S.collection.objects.link(co); S.camera=co
dist=size*2.0
# front = Blender +Y (north) = yaw180 in old convention
for name,deg in [('front',180),('threequarter',135),('profile',90),('back',0)]:
    a=math.radians(deg)
    co.location=(cx+math.sin(a)*dist, cy-math.cos(a)*dist, cz+size*0.1)
    d=mathutils.Vector((cx,cy,cz))-co.location
    co.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    S.render.filepath=os.path.join(OUT,f'fb_{name}.png'); bpy.ops.render.render(write_still=True); print('wrote',name)
