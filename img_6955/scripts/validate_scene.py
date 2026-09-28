"""Validate metric solids, support contacts, ferry waterline and walk routes."""
import bpy,bmesh,json,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from project import ROOT, REPORTS as out, ensure_directories, write_report, sha256
ensure_directories();s=bpy.context.scene
assert s.get('model_revision')==4
assert s.unit_settings.system=='METRIC' and s.unit_settings.scale_length==1
bpy.context.view_layer.update();solids=[o for o in s.objects if o.type=='MESH' and o.get('geometry_kind')=='solid']
errors=[];topology=[];cache={}
def bvh(o):
 if o.name not in cache:cache[o.name]=BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons])
 return cache[o.name]
for o in solids:
 bm=bmesh.new();bm.from_mesh(o.data);bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-10 for f in bm.faces);vol=bm.calc_volume(signed=True);bm.free()
 if bad or deg or vol<=1e-10:errors.append({'kind':'topology','object':o.name,'nonmanifold_edges':bad,'degenerate_faces':deg,'signed_volume':vol})
 if not all(math.isfinite(v) for row in o.matrix_world for v in row):errors.append({'kind':'nonfinite','object':o.name})
 topology.append({'object':o.name,'closed':bad==0,'volume_m3':vol})
# AABB labels alone are insufficient: test actual triangle contact/proximity.
contact_report=[]
for c in json.loads(s['contact_manifest']):
 a=bpy.data.objects[c['a']];b=bpy.data.objects[c['b']];p=Vector(c['point'])
 if c['frame']:p=bpy.data.objects[c['frame']].matrix_world@p
 av=bvh(a);bv=bvh(b);da=av.find_nearest(p)[3];db=bv.find_nearest(p)[3]
 overlap=bool(av.overlap(bv));passed=overlap or (da is not None and db is not None and max(da,db)<=.015)
 item={**c,'distance_to_a_m':da,'distance_to_b_m':db,'triangles_intersect':overlap,'pass':passed};contact_report.append(item)
 if not passed:errors.append({'kind':'disconnected_support',**item})
# Both posts and sheet use the same root and derived cross-section.
for sh in json.loads(s['shelter_manifest']):
 for name in sh['columns']:
  o=bpy.data.objects[name];zmin=min(v.co.z for v in o.data.vertices);zmax=max(v.co.z for v in o.data.vertices)
  if abs(zmin-.12)>1e-5 or abs(zmax-sh['beam_bottom'])>1e-5:errors.append({'kind':'column_height','object':name})
from scene_audit import audit_scene
visual_audit = audit_scene(s)
errors.extend(visual_audit['errors'])
# Collision copies must preserve visible-source transforms and closed shape.
coll=bpy.data.collections['10 Collision proxies']
for o in coll.objects:
 src=bpy.data.objects.get(o.get('collision_source',''))
 if not src or any(abs(a-b)>1e-6 for r1,r2 in zip(o.matrix_world,src.matrix_world) for a,b in zip(r1,r2)):errors.append({'kind':'collision_transform','object':o.name})
# Build world BVH for the collision source geometry, excluding decorative/sea/ferry assets.
verts=[];faces=[]
for o in coll.objects:
 k=len(verts);verts.extend(o.matrix_world@v.co for v in o.data.vertices);faces.extend(tuple(k+i for i in p.vertices) for p in o.data.polygons)
static=BVHTree.FromPolygons(verts,faces)
route_reports=[]
for name,waypoints in json.loads(s['walk_routes']).items():
 samples=[]
 for a,b in zip(waypoints,waypoints[1:]):
  a,b=Vector(a),Vector(b);count=max(1,math.ceil((b-a).length/.1))
  samples.extend(a.lerp(b,j/count) for j in range(count))
 samples.append(Vector(waypoints[-1]));last_z=0.;issues=[];maxstep=0
 for i,p in enumerate(samples):
  # Find floor below the maximum permitted step-up, not a roof above the player.
  hit,normal,idx,d=static.ray_cast(Vector((p.x,p.y,last_z+.205)),Vector((0,0,-1)),3.0)
  if hit is None:issues.append({'sample':i,'xy':list(p),'reason':'no floor'});continue
  dz=hit.z-last_z;maxstep=max(maxstep,abs(dz))
  if abs(dz)>.205:issues.append({'sample':i,'xy':list(p),'reason':'step too large','delta_z':dz})
  last_z=hit.z
  if normal.z<.7:issues.append({'sample':i,'xy':list(p),'reason':'floor slope too steep'})
  # Head clearance and a 0.30m-radius cylinder sampled at three body heights.
  head=static.ray_cast(Vector((p.x,p.y,hit.z+.025)),Vector((0,0,1)),1.775)[0]
  if head is not None:issues.append({'sample':i,'xy':list(p),'reason':'head obstruction','z':head.z})
  blocked=False
  for h in [.22,.95,1.72]:
   if blocked:break
   for j in range(12):
    theta=j*math.tau/12
    if static.ray_cast(Vector((p.x,p.y,hit.z+h)),Vector((math.cos(theta),math.sin(theta),0)),.30)[0] is not None:
     issues.append({'sample':i,'xy':list(p),'reason':'body clearance','height':h});blocked=True;break
 route_reports.append({'route':name,'samples':len(samples),'max_step_m':maxstep,'issues':issues,'pass':not issues})
 if issues:errors.append({'kind':'walk_route','route':name,'issue_count':len(issues),'examples':issues[:5]})
# Ferry must straddle water, with a full 3D hull and connected floors.
hull=bpy.data.objects['Ferry watertight submerged hull'];pts=[hull.matrix_world@v.co for v in hull.data.vertices];zmin=min(p.z for p in pts);zmax=max(p.z for p in pts);water=s['water_level_m']
if not zmin<water<zmax or abs((water-zmin)-2.6)>1e-4:errors.append({'kind':'ferry_waterline','min_z':zmin,'water_z':water,'max_z':zmax})
# Stair flights have equal dimensions and physically open stairwells on ferry decks.
stair_report=[]
for d in json.loads(s['stair_manifest']):
 obj=bpy.data.objects[d['name']];width=max(v.co.x for v in obj.data.vertices)-min(v.co.x for v in obj.data.vertices)
 stair_report.append({'name':d['name'],'riser_m':d['rise'],'tread_m':d['tread'],'width_m':width})
 if width<1.0:errors.append({'kind':'stair_width','object':obj.name,'width':width})
 if not (.12<=d['rise']<=.20 and d['tread']>=.28):errors.append({'kind':'stair_dimensions','stair':d})
 if d['name'].startswith('Ferry'):
  frame=bpy.data.objects[d['frame']];local=Vector((0,d['count']*d['tread']*.5,d['base']+d['count']*d['rise']*.5+.05));p=frame.matrix_world@local
  # Upward ray must not hit the target deck halfway along the staircase.
  target=bpy.data.objects['Ferry Passenger upper deck' if '5.4' in d['name'] else 'Ferry Sky deck']
  if bvh(target).ray_cast(p,Vector((0,0,1)),2.0)[0] is not None:errors.append({'kind':'closed_ferry_stairwell','stair':d['name']})
# Revision 4 acceptance: actual mesh opening, common quay line, backless benches,
# and grass roots confined to physical joints.
toilet=json.loads(s['toilet_manifest']);frame=bpy.data.objects[toilet['frame']]
a,b=[Vector((*p,0)) for p in toilet['quay_line']];direction=(b-a).normalized()
rear=bpy.data.objects['Pavilion east rear wall']
for vertex in rear.data.vertices:
 if abs(vertex.co.x-toilet['rear_x'])<1e-5:
  p=rear.matrix_world@vertex.co;p.z=0
  if (p-a).cross(direction).length>1e-5:errors.append({'kind':'toilet_quay_alignment'})
# Sample the opening through its full width and height, not only its center.
for y in [2.01,2.6,3.19]:
 for z in [.77,1.8,2.99]:
  origin=frame.matrix_world@Vector((-2.,y,z));direction=frame.matrix_world.to_3x3()@Vector((1,0,0))
  for wall in bpy.data.collections['04 Pavilion'].objects:
   if wall.type=='MESH' and wall.name!='Pavilion complete supported roof' and bvh(wall).ray_cast(origin,direction,.6)[0] is not None:
    errors.append({'kind':'toilet_entrance_obstructed','object':wall.name,'y':y,'z':z})
for o in s.objects:
 if o.name.endswith('bench assembly'):
  if any('back ' in child.name for child in o.children):errors.append({'kind':'plaza_bench_backrest','object':o.name})
  a,b=[Vector((*p,0)) for p in json.loads(o['shore_segment'])]
  axis=o.matrix_world.to_3x3()@Vector((1,0,0))
  if abs(axis.normalized().dot((b-a).normalized()))<.99999:errors.append({'kind':'bench_shore_direction','object':o.name})
grass=json.loads(s['grass_manifest'])
for x,y,z in grass['roots']:
 p=Vector((x,y))
 distance=min((p-(Vector(a)+(Vector(b)-Vector(a))*max(0,min(1,(p-Vector(a)).dot(Vector(b)-Vector(a))/(Vector(b)-Vector(a)).length_squared)))).length for a,b in grass['joints'])
 if distance>grass['root_tolerance_m'] or not -.006<=z<=0:errors.append({'kind':'grass_root_outside_joint','point':[x,y,z]});break
if any(o.name.startswith('Grounded planter') for o in s.objects):errors.append({'kind':'remaining_soil_planter'})
# Packed reference and render/camera settings remain independently inspectable.
for img in bpy.data.images:
 if img.source=='FILE' and not img.packed_file:errors.append({'kind':'unpacked_image','image':img.name})
if s.camera is None or (s.render.resolution_x,s.render.resolution_y) not in [(1280,850),(3024,3024)]:errors.append({'kind':'review_output_settings'})
report={'status':'PASS' if not errors else 'FAIL','revision':4,'scene_sha256':sha256(bpy.data.filepath),'visual_audit':visual_audit,'solid_mesh_count':len(solids),'contact_count':len(contact_report),'contact_passed':sum(c['pass'] for c in contact_report),'collision_count':len(coll.objects),'walk_routes':route_reports,'ferry':{'keel_z':zmin,'waterline_z':water,'hull_top_z':zmax,'draft_m':water-zmin,'parts':len(bpy.data.collections['06 Sakurajima type ferry'].objects)},'stairs':stair_report,'errors':errors,'limits':'Geometric support and sampled clearance checks. Not FEM, buoyancy simulation, regulatory verification or an engine character-controller test.'}
write_report('validation',report);write_report('contacts',contact_report);print(json.dumps({k:v for k,v in report.items() if k not in ['walk_routes','stairs']},indent=2),flush=True)
assert not errors,'Structural validation failed; see review/reports/validation.json'
