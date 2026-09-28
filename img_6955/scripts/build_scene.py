"""Build a coherent metric scene for future walkable-map development.
Blender 5.2; no add-ons. Photo projection restores the calibrated view; structural geometry remains editable.
"""
import bpy,bmesh,math,random,json,time
from pathlib import Path
from mathutils import Vector
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from project import ROOT, REPORTS as OUT, ensure_directories, write_report
ensure_directories()
(OUT/'verification.json').unlink(missing_ok=True)
(OUT/'appearance.json').unlink(missing_ok=True)
T=time.monotonic();random.seed(6955)
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
collections={}
def collection(name):
 c=bpy.data.collections.new(name);s.collection.children.link(c);collections[name]=c;return c
GROUND=collection('01 Terrain and quay');STAIRS=collection('02 Continuous stairs');SHELTER=collection('03 Connected shelters and benches');BUILDING=collection('04 Pavilion');RAIL=collection('05 Boundary guards');FERRY=collection('06 Sakurajima type ferry');HARBOR=collection('07 Harbor and terrain');NATURE=collection('08 Sea and planting');CAM=collection('09 Cameras and lighting');COLL=collection('10 Collision proxies');NAV=collection('11 Walk start and extension anchors');REFERENCE=collection('12 Photo reference — non geometry')
FRAME=None;contacts=[];stairs=[];shelters=[];collision_sources=[]
def root(name,pos,col,yaw=0):
 o=bpy.data.objects.new(name,None);col.objects.link(o);o.location=pos;o.rotation_euler.z=math.radians(yaw);o.empty_display_size=.3;o['asset_root']=True;return o

def lin(rgb):return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb)
def material(name,rgb,rough=.7,metal=0,grain=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*lin(rgb),1);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF');b.inputs['Base Color'].default_value=m.diffuse_color;b.inputs['Roughness'].default_value=rough;b.inputs['Metallic'].default_value=metal
 if grain:
  tc=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=70;noise.inputs['Detail'].default_value=2;l.new(tc.outputs['Object'],noise.inputs['Vector']);bu=n.new('ShaderNodeBump');bu.inputs['Strength'].default_value=.22;bu.inputs['Distance'].default_value=grain;l.new(noise.outputs['Fac'],bu.inputs['Height']);l.new(bu.outputs[0],b.inputs['Normal'])
 return m
concrete=material('Weathered concrete',(.48,.49,.47),.86,grain=.004)
wallmat=material('Quay concrete and salt marks',(.35,.36,.33),.92,grain=.012)
steel=material('Shelter silver coated metal',(.69,.71,.72),.36,.35,grain=.0005)
roofmat=material('Pale metal roof',(.68,.70,.72),.4,.45)
blue=material('Marine blue painted rail',(.12,.32,.48),.35,.3)
white=material('Ferry and railing ivory white',(.89,.90,.88),.4,.12)
red=material('Ferry red orange trim',(.73,.16,.10),.4,.25)
green=material('Ferry funnel green',(.06,.31,.23),.4,.3)
black=material('Rubber and dark hardware',(.065,.075,.08),.75)
wood=material('Bench weathered timber',(.34,.29,.22),.7,grain=.003)
glass=material('Dark marine glass',(.085,.17,.22),.16,.3);glass.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value=.18;glass.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value=1.45
watermat=material('Sea base material',(.11,.25,.34),.18,.25);wn=watermat.node_tree.nodes;wl=watermat.node_tree.links;wbs=wn.get('Principled BSDF');wbs.inputs['IOR'].default_value=1.333
coord=wn.new('ShaderNodeTexCoord');noise=wn.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=2.4;noise.inputs['Detail'].default_value=3;wl.new(coord.outputs['Object'],noise.inputs['Vector']);bump=wn.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.35;bump.inputs['Distance'].default_value=.07;wl.new(noise.outputs['Fac'],bump.inputs['Height']);wl.new(bump.outputs[0],wbs.inputs['Normal'])
grassmat=material('Coastal grass',(.30,.35,.15),.95)
soil=material('Planter soil',(.23,.20,.14),.96)
landmat=material('Distant hazy land',(.36,.47,.48),1)
tilemat=material('Pavilion ceramic tile',(.60,.60,.56),.65,grain=.001)
# World-space materials stay attached to the environment from every camera.
paving=material('Metric checker paving — world anchored',(.35,.32,.30),.9,grain=.005)
n=paving.node_tree.nodes;l=paving.node_tree.links;b=n.get('Principled BSDF');tc=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeVectorRotate');mapping.rotation_type='AXIS_ANGLE';mapping.inputs['Axis'].default_value=(0,0,1);mapping.inputs['Angle'].default_value=math.radians(17);l.new(tc.outputs['Object'],mapping.inputs['Vector']);checker=n.new('ShaderNodeTexChecker');checker.inputs['Scale'].default_value=1/2.7;checker.inputs['Color1'].default_value=(*lin((.30,.28,.27)),1);checker.inputs['Color2'].default_value=(*lin((.59,.55,.51)),1);l.new(mapping.outputs[0],checker.inputs[0]);l.new(checker.outputs['Color'],b.inputs['Base Color'])
# Choose XY / XZ / YZ coordinates by face normal for square tile joints.
n=tilemat.node_tree.nodes;l=tilemat.node_tree.links;b=n.get('Principled BSDF');geo=n.new('ShaderNodeTexCoord');brick=n.new('ShaderNodeTexBrick');brick.inputs['Color1'].default_value=(*lin((.66,.65,.61)),1);brick.inputs['Color2'].default_value=(*lin((.56,.57,.54)),1);brick.inputs['Mortar'].default_value=(*lin((.22,.24,.24)),1);brick.inputs['Scale'].default_value=3.3;brick.inputs['Mortar Size'].default_value=.012;brick.offset=0;brick.inputs['Brick Width'].default_value=.5;brick.inputs['Row Height'].default_value=.5;l.new(brick.outputs['Color'],b.inputs['Base Color'])
xyz=n.new('ShaderNodeSeparateXYZ');l.new(geo.outputs['Object'],xyz.inputs[0]);normal=n.new('ShaderNodeNewGeometry');ns=n.new('ShaderNodeSeparateXYZ');l.new(normal.outputs['Normal'],ns.inputs[0])
xz=n.new('ShaderNodeCombineXYZ');yz=n.new('ShaderNodeCombineXYZ');l.new(xyz.outputs['X'],xz.inputs['X']);l.new(xyz.outputs['Z'],xz.inputs['Y']);l.new(xyz.outputs['Y'],yz.inputs['X']);l.new(xyz.outputs['Z'],yz.inputs['Y'])
def face_weight(axis):
 ab=n.new('ShaderNodeMath');ab.operation='ABSOLUTE';l.new(ns.outputs[axis],ab.inputs[0]);gt=n.new('ShaderNodeMath');gt.operation='GREATER_THAN';gt.inputs[1].default_value=.5;l.new(ab.outputs[0],gt.inputs[0]);return gt.outputs[0]
mix=n.new('ShaderNodeMixRGB');l.new(face_weight('X'),mix.inputs[0]);l.new(xz.outputs[0],mix.inputs[1]);l.new(yz.outputs[0],mix.inputs[2]);top=n.new('ShaderNodeMixRGB');l.new(face_weight('Z'),top.inputs[0]);l.new(mix.outputs[0],top.inputs[1]);l.new(geo.outputs['Object'],top.inputs[2]);l.new(top.outputs[0],brick.inputs['Vector'])

def mesh(name,verts,faces,mat,col,kind='solid',collision=False):
 d=bpy.data.meshes.new(name);d.from_pydata(verts,[],faces);d.update()
 if kind=='solid':
  bm=bmesh.new();bm.from_mesh(d);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(d);bm.free()
 o=bpy.data.objects.new(name,d);col.objects.link(o)
 if FRAME:o.parent=FRAME
 if mat:d.materials.append(mat)
 o['geometry_kind']=kind;o['collision']=collision
 if collision:collision_sources.append(o)
 return o

def box(name,lo,hi,mat,col,collision=False):
 x,y,z=lo;X,Y,Z=hi;assert X>x and Y>y and Z>z,(name,lo,hi)
 return mesh(name,[(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,col,collision=collision)
def prism(name,poly,z0,z1,mat,col,collision=False):
 k=len(poly);verts=[(x,y,z) for z in [z0,z1] for x,y in poly];faces=[tuple(reversed(range(k))),tuple(range(k,2*k))]+[(i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k)]
 return mesh(name,verts,faces,mat,col,collision=collision)
def rod(name,a,b,r,mat,col,n=8,collision=False):
 a,b=Vector(a),Vector(b);delta=b-a;assert delta.length>1e-6;rot=delta.to_track_quat('Z','Y');verts=[a+rot@Vector((r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),z)) for z in [0,delta.length] for i in range(n)];faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)];return mesh(name,verts,faces,mat,col,collision=collision)
def beam(name,a,b,width,height,mat,col,collision=False):
 a,b=Vector(a),Vector(b);q=(b-a).to_track_quat('X','Z');L=(b-a).length;c=(a+b)/2
 pts=[c+q@Vector((x*L/2,y*width/2,z*height/2)) for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
 return mesh(name,pts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,col,collision=collision)
def contact(a,b,point,label):contacts.append({'a':a.name,'b':b.name,'point':list(point),'frame':FRAME.name if FRAME else None,'label':label})
def stairmesh(name,x0,x1,y0,count,rise,tread,zbase,col):
 profile=[(y0,zbase)]
 for i in range(count):profile.extend([(y0+i*tread,zbase+(i+1)*rise),(y0+(i+1)*tread,zbase+(i+1)*rise)])
 profile.append((y0+count*tread,zbase));k=len(profile);v=[(x,y,z) for x in [x0,x1] for y,z in profile];f=[tuple(range(k)),tuple(reversed(range(k,2*k)))]+[(i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k)]
 o=mesh(name,v,f,concrete,col,collision=True);o['step_count']=count;o['riser_m']=rise;o['tread_m']=tread;stairs.append({'name':name,'x_center':(x0+x1)/2,'y_start':y0,'count':count,'rise':rise,'tread':tread,'base':zbase,'frame':FRAME.name if FRAME else None});return o

# Closed landmass: plaza, structural fill, vertical quay walls and an open inland extension.
outline=[(-9,-12),(19,-12),(19,25),(15,32),(-14,79),(-35,97),(-24,48),(-10,5)]
terrain=prism('Plaza and solid quay foundation',outline,-8,0,paving,GROUND,True);terrain.data.materials.append(wallmat)
for p in terrain.data.polygons:
 if p.normal.z<.5:p.material_index=1
terrain['walkable_top_z']=0.;terrain['inferred_footprint']=True
seabed=box('Seabed beneath harbor',(-2500,-1200,-18),(2500,5000,-15),soil,HARBOR)
# Entry connects to the base map with no height seam.
entry=box('Inland extension connector',(-3,-30,-8),(8,-11.98,0),paving,GROUND,True)
contact(terrain,entry,(2,-12,0),'level entry to plaza')
SEA_LEVEL=-1.8
sea=mesh('Sea surface at -1.8m',[(-12000,-12000,SEA_LEVEL),(12000,-12000,SEA_LEVEL),(12000,16000,SEA_LEVEL),(-12000,16000,SEA_LEVEL)],[(0,1,2,3)],watermat,NATURE,'surface');sea['water_level_m']=SEA_LEVEL

# Edge guards rooted on the actual plaza boundary; no levitating posts.
def fence(name,a,b,wallheight=.20):
 a,b=Vector((*a,0)),Vector((*b,0));length=(b-a).length;direction=(b-a).normalized();normal=Vector((-direction.y,direction.x,0));inset=normal*.12;a+=inset;b+=inset
 base=beam(name+' curb',a+Vector((0,0,wallheight/2)),b+Vector((0,0,wallheight/2)),.24,wallheight,wallmat,RAIL,True)
 count=math.ceil(length/1.8)
 for i in range(count+1):
  p=a.lerp(b,i/count);o=rod(name+' post %02d'%i,p+Vector((0,0,wallheight)),p+Vector((0,0,1.12)),.035,blue,RAIL,8,True)
  contact(base,o,p+Vector((0,0,wallheight)),'guard post to curb')
 for h in [.48,.80,1.12]:rod(name+' rail %.2f'%h,a+Vector((0,0,h)),b+Vector((0,0,h)),.026,white,RAIL,8,True)
# Counter-clockwise polygon keeps the inward normal on its left.
for i in range(1,len(outline)):
 fence('Quay edge %02d'%i,outline[i],outline[(i+1)%len(outline)],.22 if i<5 else .38)
# Close the inland-facing edges except an 11m extension opening.
fence('South west guard',outline[0],(-3,-12),.2);fence('South east guard',(8,-12),outline[1],.2)

# Left viewpoint: fixed width, equal rise/run, attached landing and continuous guards.
FRAME=root('Viewpoint stair assembly',(-16.2,55,0),STAIRS)
st=stairmesh('Viewpoint — ten equal steps',-3.6,3.6,0,10,.18,.32,0,STAIRS)
landing=box('Viewpoint upper landing',(-3.6,3.2,-.03),(3.6,6.3,1.8),concrete,STAIRS,True);contact(st,landing,(0,3.2,1.8),'top tread to landing')
for side in [-1,1]:
 x=side*3.48
 for i in range(0,10,3):
  y=i*.32+.15;z=(i+1)*.18;rod('Viewpoint stair guard post %s %s'%(side,i),(x,y,z),(x,y,1.23+(y-.15)*1.62/3.05),.035,steel,STAIRS,8,True)
 rod('Viewpoint continuous handrail %s'%side,(x,.15,1.23),(x,3.2,2.85),.035,steel,STAIRS,12,True)
 for j in range(3):rod('Viewpoint landing guard %s %s'%(side,j),(x,3.2+j*1.5,1.8),(x,3.2+j*1.5,2.85),.035,steel,STAIRS,8,True)
 rod('Viewpoint landing top rail %s'%side,(x,3.2,2.85),(x,6.3,2.85),.035,steel,STAIRS,12,True)
box('Viewpoint rear parapet',(-3.6,6.1,1.8),(3.6,6.3,2.9),concrete,STAIRS,True)
box('Viewpoint left masonry parapet',(-3.6,3.2,1.8),(-3.38,6.3,3.4),concrete,STAIRS,True)
FRAME=None

# Complete bench with connected supports, not a photograph-sized plinth.
def bench_asset(prefix,col,offset=(0,0,0)):
 x,y,z=offset;legs=[]
 for u in [-.84,.84]:
  for v in [-.21,.21]:
   leg=box(prefix+' leg %.2f %.2f'%(u,v),(x+u-.055,y+v-.055,z),(x+u+.055,y+v+.055,z+.42),steel,col,True);legs.append(leg)
   support=bpy.data.objects.get('Ferry Sky deck') if FRAME and FRAME.name.startswith('Sakurajima') else terrain
   contact(support,leg,(x+u,y+v,z),'bench foot to supporting deck')
 bearers=[]
 for u in [-.84,.84]:
  bearer=box(prefix+' seat bearer %.2f'%u,(x+u-.075,y-.30,z+.36),(x+u+.075,y+.30,z+.42),steel,col);bearers.append(bearer)
  for v in [-.21,.21]:contact(legs[(0 if u<0 else 2)+(0 if v<0 else 1)],bearer,(x+u,y+v,z+.42),'bench leg to bearer')
 seats=[]
 for i in range(4):seats.append(box(prefix+' seat slat %d'%i,(x-1.12,y-.29+i*.15,z+.42),(x+1.12,y-.155+i*.15,z+.47),wood,col,True))
 for j,bearer in enumerate(bearers):
  for seat in seats:
   q=seat.data.vertices[4].co.copy();q.x=x+(-.84 if j==0 else .84);q.y+=.0675;q.z=z+.42;contact(bearer,seat,q,'seat slat to bearer')
 for u in [-.84,.84]:
  post=box(prefix+' back upright %.2f'%u,(x+u-.045,y+.22,z+.05),(x+u+.045,y+.30,z+1.02),steel,col,True)
  contact(legs[1 if u<0 else 3],post,(x+u,y+.245,z+.2),'back upright to rear leg')
 for i in range(3):box(prefix+' back slat %d'%i,(x-1.12,y+.215,z+.64+i*.125),(x+1.12,y+.265,z+.74+i*.125),wood,col,True)
 return legs

def roof_height(y,width):return 2.68+.52*math.sin(math.pi*(y/width+.5))
def shell(name,length,width,thick,mat,col,zoffset=0):
 steps=32;v=[]
 for layer in [0,1]:
  for x in [-length/2,length/2]:
   for i in range(steps+1):
    y=-width/2+i*width/steps;v.append((x,y,roof_height(y,width)+zoffset+layer*thick))
 k=steps+1;faces=[]
 for i in range(steps):
  faces.extend([(i,i+1,k+i+1,k+i),(2*k+i,3*k+i,3*k+i+1,2*k+i+1),(i,2*k+i,2*k+i+1,i+1),(k+i,k+i+1,3*k+i+1,3*k+i)])
 faces.extend([(0,k,3*k,2*k),(k-1,2*k-1,4*k-1,3*k-1)])
 return mesh(name,v,faces,mat,col)
def shelter_asset(name,pos,length=5.4,width=3.2,yaw=0):
 global FRAME
 FRAME=root(name,pos,SHELTER,yaw);frame=FRAME;roof=shell(name+' continuous barrel roof',length,width,.075,roofmat,SHELTER);roof['collision']=True;collision_sources.append(roof)
 py=width/2-.32;px=length/2-.45;z_top=roof_height(py,width);z_beam=z_top-.22;column_names=[]
 beams=[]
 for y in [-py,py]:beams.append(box(name+' longitudinal beam %.2f'%y,(-length/2+.12,y-.09,z_beam),(length/2-.12,y+.09,z_top),steel,SHELTER,True));contact(beams[-1],roof,(0,y,z_top),'longitudinal beam to roof')
 for x in [-px,px]:
  for y in [-py,py]:
   footing=box(name+' footing %.2f %.2f'%(x,y),(x-.22,y-.22,0),(x+.22,y+.22,.12),concrete,SHELTER,True)
   post=box(name+' column %.2f %.2f'%(x,y),(x-.105,y-.105,.12),(x+.105,y+.105,z_beam),concrete,SHELTER,True);column_names.append(post.name)
   contact(footing,post,(x,y,.12),'column foot to foundation');contact(post,beams[0 if y<0 else 1],(x,y,z_beam),'column head to beam')
   contact(terrain,footing,(x,y,0),'shelter footing to plaza')
   for dx in [-.15,.15]:
    for dy in [-.15,.15]:rod(name+' anchor bolt %.2f %.2f %.2f %.2f'%(x,y,dx,dy),(x+dx,y+dy,.105),(x+dx,y+dy,.14),.013,steel,SHELTER,6)
 # Curved transverse ribs run just under the sheet and bridge both longitudinal beams.
 for j,x in enumerate([-px,0,px]):
  rib=shell(name+' transverse arched rib %d'%j,.085,width-.01,.11,steel,SHELTER,-.10)
  for v in rib.data.vertices:v.co.x+=x
  for y in [-py,py]:contact(rib,beams[0 if y<0 else 1],(x,y,z_top-.055),'arched rib to edge beam')
 # Diagonal knee braces provide lateral support, reaching the columns and edge beams.
 for x in [-px,px]:
  for y in [-py,py]:
   sign=-1 if x>0 else 1;beam(name+' knee brace %.2f %.2f'%(x,y),(x,y,z_beam-.45),(x+sign*.55,y,z_beam+.02),.065,.065,steel,SHELTER)
 bench_asset(name+' bench',SHELTER,(0,0,0))
 shelters.append({'root':name,'roof':roof.name,'columns':column_names,'beam_top':z_top,'beam_bottom':z_beam,'post_xy':[px,py],'length':length,'width':width})
 FRAME=None
shelter_asset('Main shelter',(3.25,43,0),4.8,3.2)
shelter_asset('Rear shelter',(1.0,49.7,0),4.6,3.2)
shelter_asset('Far shelter',(-15.8,76.5,0),4.4,3.2)

# Right pavilion: fixed landing, uniform stairs, four walls, door and bearing roof.
FRAME=root('Pavilion assembly',(11.0,18.23,0),BUILDING,-14)
# Five equal-height terraces wrap the front and left of the raised pavilion.
# Union the nested blocks so the landing and steps form one closed solid.
st=None
for i in range(5):
 outset=(5-i)*.35
 part=box('Pavilion terrace temporary %d'%i,(-3.85-outset,-outset,0),(3,6.1,(i+1)*.15),concrete,BUILDING)
 if st is None:st=part;st.name='Pavilion — five equal steps'
 else:
  mod=st.modifiers.new('Merge terrace','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=part;bpy.context.view_layer.update()
  new=bpy.data.meshes.new_from_object(st.evaluated_get(bpy.context.evaluated_depsgraph_get()));old=st.data;st.modifiers.clear();st.data=new;bpy.data.objects.remove(part,do_unlink=True)
  if old.users==0:bpy.data.meshes.remove(old)
st['collision']=True;collision_sources.append(st);st['step_count']=5;st['riser_m']=.15;st['tread_m']=.35
stairs.append({'name':st.name,'x_center':-1.3,'y_start':-1.75,'count':5,'rise':.15,'tread':.35,'base':0,'frame':FRAME.name})
platform=st
# Clear front doorway is 1.2m wide, 2.25m high, with a lintel supported on both jambs.
wallbase=.75;roofz=3.64;walls=[]
walls.append(box('Pavilion west wall',(-1.75,1.0,wallbase),(-1.53,4.2,roofz),tilemat,BUILDING,True))
walls.append(box('Pavilion east wall',(1.88,1.0,wallbase),(2.1,4.2,roofz),tilemat,BUILDING,True))
walls.append(box('Pavilion rear wall',(-1.53,3.98,wallbase),(1.88,4.2,roofz),tilemat,BUILDING,True))
walls.append(box('Pavilion front left jamb',(-1.53,1.0,wallbase),(-.6,1.22,roofz),tilemat,BUILDING,True))
walls.append(box('Pavilion front right jamb',(.6,1.0,wallbase),(1.88,1.22,roofz),tilemat,BUILDING,True))
lintel=box('Pavilion supported door lintel',(-.6,1.0,3.0),(.6,1.22,roofz),tilemat,BUILDING,True)
roof=box('Pavilion complete supported roof',(-2.8,.3,roofz),(2.8,4.36,roofz+.44),concrete,BUILDING,True)
for wall in walls:
 lo=Vector(wall.bound_box[0]);hi=Vector(wall.bound_box[6]);p=(lo+hi)/2;p.z=wallbase;contact(platform,wall,p,'pavilion wall to platform');p.z=roofz;contact(wall,roof,p,'pavilion wall bearing roof')
contact(walls[3],lintel,(-.6,1.1,3.4),'door lintel left bearing');contact(walls[4],lintel,(.6,1.1,3.4),'door lintel right bearing')
# Monument seated on the west part of the landing, as visible in the photograph.
monument=box('Pavilion monument body',(-4.18,-.15,.75),(-3.28,.6,1.65),concrete,BUILDING,True);contact(platform,monument,(-3.73,.2,.75),'monument seated on platform')
box('Pavilion monument inset plaque',(-4.12,-.167,.86),(-3.34,-.15,1.57),black,BUILDING)
for side in [1]:
 x=-6.17 if side<0 else 2.87
 for i in range(0,5,2):
  y=-1.75+(i+.5)*.35;z=(i+1)*.15;px=(-7.92+(y+1.575)*1.75/1.575) if side<0 else x
  rod('Pavilion stair guard %d %d'%(side,i),(px,y,z),(px,y,1.15+(y+1.575)*.75/1.575),.032,steel,BUILDING,8,True)
 rod('Pavilion stair handrail %d'%side,(-7.92 if side<0 else x,-1.575,1.15),(x,0,1.9),.035,steel,BUILDING,12,True)
 for j in range(5):
  y=j*1.48;rod('Pavilion landing guard %d %d'%(side,j),(x,y,.75),(x,y,1.9),.032,steel,BUILDING,8,True)
 for h in [1.15,1.52,1.9]:rod('Pavilion landing rail %d %.2f'%(side,h),(x,0,h),(x,5.92,h),.03,steel,BUILDING,8,True)

FRAME=None

# Planters and rooted three-dimensional grass, replacing camera-facing grass silhouettes.
for i,(x,y) in enumerate([(-9.5,12),(-14.2,33),(-21.6,50)]):
 planter=box('Grounded planter %d'%i,(x-.65,y-1.4,0),(x+.65,y+1.4,.2),soil,NATURE,True)
 verts=[];faces=[]
 for k in range(200):
  X=x+random.uniform(-.62,.62);Y=y+random.uniform(-1.35,1.35);h=random.uniform(.10,.4);w=random.uniform(.006,.018);j=len(verts);verts.extend([(X-w,Y,.2),(X+w,Y,.2),(X+.05,Y+.02,.2+h),(X,Y-w,.2),(X,Y+w,.2),(X+.02,Y-.03,.2+h)]);faces.extend([(j,j+1,j+2),(j+3,j+4,j+5)])
 mesh('Rooted grass blades %d'%i,verts,faces,grassmat,NATURE,'detail')

# Volumetric breakwaters rise from the seabed, with beacons on their top surface.
for name,cx,cy,L in [('Inner',-60,600,170),('Outer',180,1100,360)]:
 pier=box(name+' breakwater foundation',(cx-L/2,cy-5,-15),(cx+L/2,cy+5,.05),wallmat,HARBOR)
 cap=box(name+' breakwater cap',(cx-L/2,cy-5,.05),(cx+L/2,cy+5,.55),concrete,HARBOR)
 xx=cx+L/2-4;rod(name+' beacon tower',(xx,cy,.55),(xx,cy,7.0),.6,red,HARBOR,16);rod(name+' beacon lantern',(xx,cy,7),(xx,cy,7.7),.85,white,HARBOR,16)
# Far bank is a genuine height field with a closed underside, not a hanging silhouette.
def terrain_patch(name,cx,cy,width,depth,nx,ny,height):
 verts=[]
 for j in range(ny+1):
  for i in range(nx+1):
   x=cx-width/2+width*i/nx;y=cy-depth/2+depth*j/ny;h=height*(.3+.7*math.sin(math.pi*i/nx)**2)*math.sin(math.pi*j/ny)**2;verts.append((x,y,-2+h))
 faces=[]
 for j in range(ny):
  for i in range(nx):a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
 edge=list(range(nx+1))+[j*(nx+1)+nx for j in range(1,ny+1)]+[ny*(nx+1)+i for i in range(nx-1,-1,-1)]+[j*(nx+1) for j in range(ny-1,0,-1)]
 bottom=[]
 for idx in edge:bottom.append(len(verts));verts.append((verts[idx][0],verts[idx][1],-15))
 for i in range(len(edge)):faces.append((edge[i],edge[(i+1)%len(edge)],bottom[(i+1)%len(edge)],bottom[i]))
 faces.append(tuple(reversed(bottom)));return mesh(name,verts,faces,landmat,HARBOR)
terrain_patch('Distant land volume — inferred',700,3500,3200,1400,48,16,100)
for i in range(10):
 x=700+i*38;box('Distant harbor warehouse %02d'%i,(x,1900,-15),(x+28,1940,random.uniform(5,14)),concrete,HARBOR)

# Sakurajima-ferry family: official 56.10 x 13.50m envelope; vessel identity unconfirmed.
FRAME=root('Sakurajima type ferry — independent asset',(-227,810,SEA_LEVEL),FERRY,-3)
ferryroot=FRAME;ferryroot['reference']='https://www.city.kagoshima.lg.jp/sakurajima-ferry/gaiyo/shokai-ship.html';ferryroot['identity']='Family reconstruction informed by Princess Marine; the vessel in IMG_6955 is not positively identified';ferryroot['nominal_length_m']=56.1;ferryroot['beam_m']=13.5;ferryroot['draft_m']=2.6
hulloutline=[(-28.05,-4.8),(-25,-6.4),(-19,-6.75),(19,-6.75),(25,-6.4),(28.05,-4.8),(28.05,4.8),(25,6.4),(19,6.75),(-19,6.75),(-25,6.4),(-28.05,4.8)]
def hull_loft():
 k=len(hulloutline);layers=[(-2.6,.86,.60),(-1.7,.97,.9),(0,1,1),(1.02,1,1)];v=[(x*sx,y*sy,z) for z,sx,sy in layers for x,y in hulloutline];f=[tuple(reversed(range(k)))]
 for j in range(len(layers)-1):
  for i in range(k):f.append((j*k+i,j*k+(i+1)%k,(j+1)*k+(i+1)%k,(j+1)*k+i))
 f.append(tuple(range((len(layers)-1)*k,len(layers)*k)))
 return mesh('Ferry watertight submerged hull',v,f,blue,FERRY)
hull=hull_loft();hull['waterline_local_z']=0.;hull['keel_local_z']=-2.6
# Decks bear on side pillars and central core. Two open vehicle ends have raised travel ramps.
decks=[]
for name,z,shrink in [('Vehicle',1.2,0),('Passenger lower',5.4,0),('Passenger upper',8.1,0),('Sky',10.6,0)]:
 poly=[(x*(1-shrink/28),y*(1-shrink/6.75)) for x,y in hulloutline];decks.append(prism('Ferry '+name+' deck',poly,z-.18,z,white,FERRY));decks[-1]['deck_top_z']=z
for end in [-1,1]:
 x=end*27.5;ramp=box('Ferry raised vehicle ramp %d'%end,(x-.14,-4.1,1.2),(x+.14,4.1,4.6),white,FERRY)
 for y in [-4.1,4.1]:rod('Ferry ramp hinge %d %.1f'%(end,y),(x-.3,y,1.23),(x+.3,y,1.23),.12,black,FERRY,12)
 # Diagonal tension/support arms, fixed to deck framing and ramp top.
 for y in [-4.0,4.0]:
  stay=rod('Ferry ramp travel stay %d %.1f'%(end,y),(x-end*2,y,1.2),(x,y,4.5),.055,steel,FERRY,10)
  contact(decks[0],stay,(x-end*2,y,1.2),'ramp stay to vehicle deck');contact(stay,ramp,(x,y,4.5),'ramp stay to raised ramp')
for side in [-1,1]:
 y=side*6.15
 for i in range(21):
  x=-24+i*2.4
  for level_index,(level,z0,z1) in enumerate([('vehicle',1.2,5.22),('lower',5.4,7.92),('upper',8.1,10.42)]):
   pier=box('Ferry %s side pier %d %02d'%(level,side,i),(x-.14,y-.14,z0),(x+.14,y+.14,z1),white,FERRY)
   contact(decks[level_index],pier,(x,y,z0),'ferry pier foot to deck');contact(pier,decks[level_index+1],(x,y,z1),'ferry pier head to deck')
 # Sills retain vehicles; open bays are true holes, not painted windows.
 box('Ferry vehicle bulwark %d'%side,(-25,y-.14,1.2),(25,y+.14,1.75),white,FERRY)
 for z in [5.4,8.1]:
  box('Ferry saloon sill %d %.1f'%(side,z),(-21,y-.16,z),(21,y+.16,z+.6),white,FERRY)
  for i in range(18):
   x=-20.5+i*2.35;box('Ferry saloon window %d %.1f %02d'%(side,z,i),(x,y-.05,z+.60),(x+1.94,y+.05,z+(2.52 if z==5.4 else 2.32)),glass,FERRY)
 for z in [1.33,5.30,10.50]:box('Ferry red stripe %d %.2f'%(side,z),(-25,y-.18,z),(25,y+.18,z+.11),red,FERRY)
# Central service core and saloon end partitions support the decks above.
box('Ferry internal service core',(-4,-2.1,1.2),(4,2.1,10.42),white,FERRY)
for x in [-21,21]:
 for z in [5.4,8.1]:box('Ferry saloon end bulkhead %.0f %.1f'%(x,z),(x-.1,-6.0,z),(x+.1,6.0,z+(2.52 if z==5.4 else 2.32)),white,FERRY)
# Both bridge ends, tapered corner footprint and wraparound dark windows.
for end in [-1,1]:
 cx=end*18.5;poly=[(cx-5.5,-5.2),(cx+5.5,-5.2),(cx+6.2,-4.3),(cx+6.2,4.3),(cx+5.5,5.2),(cx-5.5,5.2),(cx-6.2,4.3),(cx-6.2,-4.3)]
 prism('Ferry bridge lower coaming %d'%end,poly,10.6,11.3,white,FERRY)
 prism('Ferry bridge glazing %d'%end,[(cx+(x-cx)*.97,y*.98) for x,y in poly],11.3,12.5,glass,FERRY)
 prism('Ferry bridge roof %d'%end,[(cx+(x-cx)*1.04,y*1.04) for x,y in poly],12.5,12.72,white,FERRY)
 for x in [cx-5,cx-2.5,cx,cx+2.5,cx+5]:
  for y in [-5.1,5.1]:box('Ferry bridge mullion %d %.1f %.1f'%(end,x,y),(x-.055,y-.065,11.3),(x+.055,y+.065,12.55),white,FERRY)
 # Mast anchored through roof to bridge deck; rigging to real deck anchors.
 mastx=cx;rod('Ferry mast %d'%end,(mastx,0,12.65),(mastx-end*1.5,0,24),.14,white,FERRY,12)
 for z in [15,18,21]:rod('Ferry mast cross tree %d %d'%(end,z),(mastx-end*(z-12.65)/7.6,-1.2,z),(mastx-end*(z-12.65)/7.6,1.2,z),.05,white,FERRY,8)
 for side in [-1,1]:rod('Ferry mast tension cable %d %d'%(end,side),(mastx-end*1.5,0,23.8),(mastx-end*5,side*4.5,12.72),.016,steel,FERRY,6)
 # Raised side trim arch observed on the Princess Marine family.
 for side in [-1,1]:beam('Ferry curved-style side brace %d %d'%(end,side),(cx+end*6,side*5.85,8.15),(cx-end*3,side*5.3,12.5),.20,.30,red,FERRY)
# Funnel sits on the service core rather than floating above the open deck.
box('Ferry green funnel',(-1.6,-1.7,10.6),(1.6,1.7,14.0),green,FERRY)
box('Ferry funnel black cap',(-1.85,-1.9,13.9),(1.85,1.9,14.3),black,FERRY)
for x in [-.8,.8]:rod('Ferry exhaust pipe %.1f'%x,(x,0,13.8),(x,0,14.7),.32,black,FERRY,16)
# Guard perimeter follows the tapered deck footprint, inset inside every edge.
railpoly=[Vector((x*.975,y*.96,0)) for x,y in hulloutline]
for deck,z in zip(decks[1:],[5.4,8.1,10.6]):
 for edge,(a,b) in enumerate(zip(railpoly,railpoly[1:]+railpoly[:1])):
  count=math.ceil((b-a).length/1.95)
  for j in range(count):
   q=a.lerp(b,j/count);q.z=z
   post=rod('Ferry deck guard %.1f %02d %02d'%(z,edge,j),q,q+Vector((0,0,1.05)),.023,white,FERRY,6)
   contact(deck,post,q,'ferry guard foot to tapered deck')
  for h in [.4,.75,1.05]:rod('Ferry perimeter rail %.1f %02d %.2f'%(z,edge,h),(a.x,a.y,z+h),(b.x,b.y,z+h),.021,white,FERRY,6)
# Cut actual stair wells through the upper floor slabs before installing flights.
for side in [-1,1]:
 for deck_name,deck_z,start_x in [('Ferry Passenger upper deck',8.1,-10),('Ferry Sky deck',10.6,4)]:
  deck=bpy.data.objects[deck_name];y=side*4.7
  cutter=box('Temporary stair well cutter',(start_x-.08,y-.65,deck_z-.5),(start_x+4.2,y+.65,deck_z+.5),None,FERRY)
  mod=deck.modifiers.new('Open stairwell','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;bpy.context.view_layer.update()
  evaluated=deck.evaluated_get(bpy.context.evaluated_depsgraph_get());newmesh=bpy.data.meshes.new_from_object(evaluated);old=deck.data;deck.modifiers.clear();deck.data=newmesh;bpy.data.objects.remove(cutter,do_unlink=True)
  if old.users==0:bpy.data.meshes.remove(old)
  for sy in [-1,1]:
   yy=y+sy*.72
   for xx in [start_x-.13,start_x+2.0,start_x+4.16]:rod('Ferry stairwell post %.1f %d %.2f %.2f'%(deck_z,side,xx,yy),(xx,yy,deck_z),(xx,yy,deck_z+1.05),.023,white,FERRY,6)
   rod('Ferry stairwell rail %.1f %d %d'%(deck_z,side,sy),(start_x-.13,yy,deck_z+1.05),(start_x+4.16,yy,deck_z+1.05),.023,white,FERRY,6)
  rod('Ferry stairwell rear guard %.1f %d'%(deck_z,side),(start_x-.13,y-.72,deck_z+1.05),(start_x-.13,y+.72,deck_z+1.05),.023,white,FERRY,6)
# Actual connecting stair flights on both sides, with step geometry and handrails.
for side in [-1,1]:
 for base,height,x0 in [(5.4,2.7,-10),(8.1,2.5,4)]:
  # Profile staircase built in a child frame so the staircase helper remains reusable.
  previous=FRAME;FRAME=root('Ferry companionway frame %d %.1f'%(side,base),(0,0,0),FERRY);FRAME.parent=previous;FRAME.location=(x0,side*4.7,base);FRAME.rotation_euler.z=-math.pi/2
  nstep=15;flight=stairmesh('Ferry companionway %d %.1f'%(side,base),-.55,.55,0,nstep,height/nstep,.28,0,FERRY);flight['collision']=False;collision_sources.remove(flight)
  for side2 in [-1,1]:
   rail=rod('Ferry companionway handrail %d %.1f %d'%(side,base,side2),(side2*.54,.14,1+height/nstep),(side2*.54,nstep*.28,height+1),.023,white,FERRY,8)
   for j in range(0,nstep,3):
    yy=(j+.5)*.28;zz=(j+1)*height/nstep;top=1+height/nstep+(yy-.14)*(height-height/nstep)/(nstep*.28-.14)
    post=rod('Ferry companionway support %d %.1f %d %d'%(side,base,side2,j),(side2*.54,yy,zz),(side2*.54,yy,top),.023,white,FERRY,8)
    contact(flight,post,(side2*.54,yy,zz),'companionway guard to tread');contact(post,rail,(side2*.54,yy,top),'companionway guard to rail')
  FRAME=previous
# Upper open-deck benches with physical legs.
for x in [-9,-6,6,9]:
 for y in [-3,3]:bench_asset('Ferry open-deck bench %.0f %.0f'%(x,y),FERRY,(x,y,10.6))
# Liferaft canisters, lifebuoys, bollards and fenders are independent 3D details.
for x in [-9,-5,5,9]:
 for y in [-3.7,3.7]:
  cradle=box('Ferry liferaft cradle %.0f %.1f'%(x,y),(x-.6,y-.24,10.6),(x+.6,y+.24,10.74),steel,FERRY)
  canister=rod('Ferry liferaft canister %.0f %.1f'%(x,y),(x-.7,y,10.95),(x+.7,y,10.95),.33,white,FERRY,12)
  contact(decks[3],cradle,(x,y,10.6),'liferaft cradle on solid deck');contact(cradle,canister,(x,y,10.74),'liferaft on cradle')
for x in [-24,-12,0,12,24]:
 for y in [-6.5,6.5]:rod('Ferry rubber fender %.0f %.1f'%(x,y),(x,y,-.05),(x,y,1.15),.23,black,FERRY,12)
for x in [-24,24]:
 for y in [-4.8,4.8]:rod('Ferry mooring bollard %.0f %.1f'%(x,y),(x,y,1.2),(x,y,1.65),.16,steel,FERRY,12)
FRAME=None

# Dedicated static collision geometry: exact terrain and simplified visible solids.
# Kept out of rendering and hidden in viewport; exporters can select this collection.
bpy.context.view_layer.update()
for src in collision_sources:
 if src.name.startswith('Ferry'):continue
 o=bpy.data.objects.new('COLLIDER::'+src.name,src.data.copy());COLL.objects.link(o);o.matrix_world=src.matrix_world.copy();o.display_type='WIRE';o.hide_render=True;o.hide_set(True);o['collision_source']=src.name;o['geometry_kind']='collision';o['engine_role']='static concave mesh for terrain/stairs; convex primitives for props'
COLL.hide_render=True
# Player markers and future extension interface; no invented game engine dependency.
spawn=root('Player spawn — feet at plaza level',(0,0,0),NAV);spawn['eye_height_m']=1.65;spawn['capsule_radius_m']=.30;spawn['capsule_height_m']=1.8;spawn['suggested_step_height_m']=.20
extension=root('Map extension — inland connector',(2.5,-30,0),NAV);extension['clear_width_m']=11
# Navigable routes deliberately avoid benches, posts and the monument.
routes={'entry_to_main':[(0,-18),(0,0),(0,25),(3.1,40.8),(3.1,42.1)],'entry_to_viewpoint':[(0,0),(-10,35),(-16.2,53.5),(-16.2,54.9),(-16.2,58.4),(-16.2,60)],'entry_to_pavilion':[(0,0),(8,13),(11,15),(10.54,16.385),(10.976,18.133),(11.169,18.909),(11.532,20.365)],'main_to_rear':[(3.1,42.1),(3.1,40.8),(6.5,40.8),(6.5,44.7),(4.5,47),(1,47.5),(1,48.8)]}

# Cameras for real multi-view inspection, not screenshot-only matching.
def camera(name,pos,target,lens=40):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);CAM.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.lens=lens;d.clip_end=20000;return o
cam=camera('Photo camera',(0,0,1.65),(0,55,.22),35.7);s.camera=cam
camera('Walk camera',(0,0,1.65),(0,55,.22),35.7)
camera('Overview camera',(68,-52,70),(-5,38,0),42)
camera('Shelter inspection camera',(11,34,5.2),(2.2,44.5,1.5),44)
camera('Reverse inspection camera',(-5,61,3.4),(5,34,1.5),30)
camera('Pavilion inspection camera',(22,8,7),(11,20,1.8),42)
ferrypos=ferryroot.location.copy();camera('Ferry inspection camera',ferrypos+Vector((54,-68,35)),ferrypos+Vector((0,0,7)),45)
# 360 degree world, replacing a view-dependent sky rectangle.
world=bpy.data.worlds.new('Maritime daylight world');world.use_nodes=True;n=world.node_tree.nodes;l=world.node_tree.links;n.clear();out=n.new('ShaderNodeOutputWorld');bg=n.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.65;l.new(bg.outputs[0],out.inputs[0]);tc=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tc.outputs['Normal'],sep.inputs[0]);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=0;ramp.color_ramp.elements[0].color=(*lin((.74,.79,.83)),1);ramp.color_ramp.elements[1].position=.8;ramp.color_ramp.elements[1].color=(*lin((.34,.51,.71)),1);l.new(sep.outputs['Z'],ramp.inputs[0]);l.new(ramp.outputs[0],bg.inputs['Color']);s.world=world
ld=bpy.data.lights.new('Broad daylight sun','SUN');lo=bpy.data.objects.new(ld.name,ld);CAM.objects.link(lo);lo.rotation_euler=(math.radians(28),math.radians(-23),math.radians(-35));ld.energy=2.0;ld.angle=math.radians(8)
# Keep original photo solely as a packed image-editor/reference resource.
ref=bpy.data.images.load(str(ROOT/'assets/reference_srgb.png'));ref.name='Source photograph — calibrated projection';ref.pack();ref.filepath='//assets/reference_srgb.png'
s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=128;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.01;s.cycles.adaptive_min_samples=16;s.cycles.use_denoising=True;s.cycles.denoiser='OPENIMAGEDENOISE';s.cycles.max_bounces=4;s.cycles.transmission_bounces=3;s.render.threads_mode='FIXED';s.render.threads=16;s.render.resolution_x=3024;s.render.resolution_y=3024;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.filepath='//renders/hamamachi_breakwater.png';s.view_settings.view_transform='Standard';s.view_settings.look='None';s.render.film_transparent=False
s['project']='Hamamachi breakwater — structural revision 2';s['model_revision']=2;s['metric_basis']='Meters; plausible inferred dimensions except ferry envelope referenced from Kagoshima City. Not a site survey or structural engineering certification.';s['purpose']='Coherent multi-view editable geometry for future walkable-map expansion';s['water_level_m']=SEA_LEVEL;s['photo_projection_enabled']=True
from restore_appearance import restore_appearance
restore_appearance(s,cam,ref,collections)
s['contact_manifest']=json.dumps(contacts);s['stair_manifest']=json.dumps(stairs);s['shelter_manifest']=json.dumps(shelters);s['walk_routes']=json.dumps(routes)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_extras=False;area.spaces.active.clip_end=20000
bpy.context.preferences.filepaths.save_version=0
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'hamamachi_breakwater.blend'))
report={'build_seconds':time.monotonic()-T,'revision':2,'objects':len(s.objects),'meshes':sum(o.type=='MESH' for o in s.objects),'vertices':sum(len(o.data.vertices) for o in s.objects if o.type=='MESH'),'contacts':len(contacts),'static_colliders':len(COLL.objects),'ferry_parts':len(FERRY.objects),'units':'meters'}
write_report('build',report);print('BUILD_REPORT',json.dumps(report),flush=True)
