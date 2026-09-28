"""Build IMG_6948 from new procedural geometry. Blender 5.2; no add-ons."""
import bpy, math, random, argparse, sys
from pathlib import Path
from mathutils import Vector, Matrix
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--render',action='store_true');p.add_argument('--width',type=int,default=3024);p.add_argument('--samples',type=int,default=128)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if a.width<1 or a.samples<1:raise ValueError('width and samples must be positive')
random.seed(6948)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for d in list(bpy.data.collections):
    if d.name!='Collection': bpy.data.collections.remove(d)
base=bpy.data.collections.get('Collection');base.name='00 · Cameras and illumination'
C=base
collections={}
def group(name):
    global C
    print('BUILD_GROUP',name,flush=True)
    C=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(C);collections[name]=C

def put(o,name,mat=None):
    o.name=name
    for c in list(o.users_collection):c.objects.unlink(o)
    C.objects.link(o)
    if mat:o.data.materials.append(mat)
    return o

def box(name,loc,scale,mat,bevel=0):
    x,y,z=[v/2 for v in scale]
    vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    o=mesh(name,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat);o.location=loc
    if bevel:
        m=o.modifiers.new('Soft manufactured edges','BEVEL');m.width=bevel;m.segments=2
        o.modifiers.new('Corner normals','WEIGHTED_NORMAL')
    return o

def mesh(name,verts,faces,mat):
    d=bpy.data.meshes.new(name);d.from_pydata(verts,[],faces);d.update();o=bpy.data.objects.new(name,d);C.objects.link(o)
    if mat:d.materials.append(mat)
    return o

def rod(name,start,end,r,mat,vertices=8,r2=None):
    start,end=Vector(start),Vector(end);delta=end-start;h=delta.length/2;r2=r if r2 is None else r2
    vs=[(rad*math.cos(j*math.tau/vertices),rad*math.sin(j*math.tau/vertices),z) for rad,z in [(r,-h),(r2,h)] for j in range(vertices)]
    fs=[tuple(reversed(range(vertices))),tuple(range(vertices,vertices*2))]+[(j,(j+1)%vertices,(j+1)%vertices+vertices,j+vertices) for j in range(vertices)]
    o=mesh(name,vs,fs,mat);o.location=(start+end)/2;o.rotation_euler=delta.to_track_quat('Z','Y').to_euler()
    for f in list(o.data.polygons)[2:]:f.use_smooth=True
    return o

def lines(name,paths,r,mat):
    d=bpy.data.curves.new(name,'CURVE');d.dimensions='3D';d.resolution_u=1;d.bevel_depth=r;d.bevel_resolution=0
    for points in paths:
        s=d.splines.new('POLY');s.points.add(len(points)-1)
        for q,co in zip(s.points,points):q.co=(*co,1)
    o=bpy.data.objects.new(name,d);C.objects.link(o);d.materials.append(mat);return o

def basic(name,color,rough=.6,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=rough;b.inputs['Metallic'].default_value=metal;return m

def textured(name,c1,c2,scale=3,rough=.7,bump=.04,stretch=(1,1,1),metal=0):
    m=basic(name,c1,rough,metal);n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF')
    tc=n.new('ShaderNodeTexCoord');vm=n.new('ShaderNodeVectorMath');vm.operation='MULTIPLY';vm.inputs[1].default_value=stretch;l.new(tc.outputs['Object'],vm.inputs[0])
    no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=scale;no.inputs['Detail'].default_value=4;no.inputs['Roughness'].default_value=.7;l.new(vm.outputs[0],no.inputs['Vector'])
    ra=n.new('ShaderNodeValToRGB');ra.color_ramp.elements[0].position=.22;ra.color_ramp.elements[0].color=(*c1,1);ra.color_ramp.elements[1].position=.78;ra.color_ramp.elements[1].color=(*c2,1);l.new(no.outputs['Fac'],ra.inputs[0]);l.new(ra.outputs[0],b.inputs['Base Color'])
    fine=n.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=140;fine.inputs['Detail'].default_value=2;l.new(tc.outputs['Object'],fine.inputs['Vector'])
    bu=n.new('ShaderNodeBump');bu.inputs['Strength'].default_value=.3;bu.inputs['Distance'].default_value=bump;l.new(fine.outputs['Fac'],bu.inputs['Height']);l.new(bu.outputs[0],b.inputs['Normal']);return m
steel=textured('Bridge · warm grey weathered paint',(.26,.275,.255),(.33,.35,.32),1.5,.38,.002,metal=.25)
edge=textured('Bridge · pale coated edges',(.34,.355,.33),(.44,.46,.425),3,.38,.002,metal=.2)
bolt=basic('Dull zinc bolt heads',(.20,.22,.20),.36,.62)
pipe=textured('Aged cream pipe coating',(.31,.30,.24),(.52,.50,.41),3,.6,.006)
concrete=textured('Walkway · weathered asphalt aggregate',(.24,.18,.11),(.335,.255,.17),2.2,.88,.012)
# Pavement colour varies with weathering along the shaded passage; lighting stays fixed.
n=concrete.node_tree.nodes;l=concrete.node_tree.links
geo=n.new('ShaderNodeNewGeometry');sep=n.new('ShaderNodeSeparateXYZ');norm=n.new('ShaderNodeMath');norm.operation='DIVIDE';norm.inputs[1].default_value=40
l.new(geo.outputs['Position'],sep.inputs[0]);l.new(sep.outputs['Y'],norm.inputs[0])
tone=n.new('ShaderNodeValToRGB');tone.label='Local pavement weathering, metres along path'
keys=[(0,(1.10,1.07,1.05,1)),(.075,(1.10,1.07,1.05,1)),(.11,(.78,.78,.86,1)),(.2,(.25,.31,.40,1)),(.3,(.5,.6,.74,1)),(.625,(.83,.89,.94,1)),(1,(1,1,1,1))]
tone.color_ramp.interpolation='EASE'
tone.color_ramp.elements.remove(tone.color_ramp.elements[1])
for i,(pos,col) in enumerate(keys):
    el=tone.color_ramp.elements[0] if i==0 else tone.color_ramp.elements.new(pos);el.position=pos;el.color=col
l.new(norm.outputs[0],tone.inputs[0]);multiply=n.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1
l.new(n.get('Color Ramp').outputs[0],multiply.inputs[1]);l.new(tone.outputs[0],multiply.inputs[2]);l.new(multiply.outputs[0],n.get('Principled BSDF').inputs['Base Color'])
# Broad faded patches, exposed aggregate and fine pits are independent scales.
asphalt_bs=n.get('Principled BSDF')
coord=n.new('ShaderNodeTexCoord')
patch=n.new('ShaderNodeTexNoise');patch.name='Asphalt irregular worn patches';patch.inputs['Scale'].default_value=3.7;patch.inputs['Detail'].default_value=5;patch.inputs['Roughness'].default_value=.8
l.new(coord.outputs['Object'],patch.inputs['Vector'])
patch_ramp=n.new('ShaderNodeValToRGB');patch_ramp.color_ramp.elements[0].position=.25;patch_ramp.color_ramp.elements[0].color=(.58,.60,.63,1);patch_ramp.color_ramp.elements[1].position=.75;patch_ramp.color_ramp.elements[1].color=(1.24,1.22,1.18,1)
l.new(patch.outputs['Fac'],patch_ramp.inputs[0])
patch_mix=n.new('ShaderNodeMixRGB');patch_mix.blend_type='MULTIPLY';patch_mix.inputs[0].default_value=.8;l.new(multiply.outputs[0],patch_mix.inputs[1]);l.new(patch_ramp.outputs[0],patch_mix.inputs[2])
aggregate=n.new('ShaderNodeTexNoise');aggregate.name='Asphalt mineral grains';aggregate.inputs['Scale'].default_value=190;aggregate.inputs['Detail'].default_value=2;aggregate.inputs['Roughness'].default_value=.8;l.new(coord.outputs['Object'],aggregate.inputs['Vector'])
grains=n.new('ShaderNodeValToRGB');grains.color_ramp.elements[0].position=.3;grains.color_ramp.elements[0].color=(.30,.32,.34,1);grains.color_ramp.elements[1].position=.7;grains.color_ramp.elements[1].color=(1.65,1.6,1.5,1);l.new(aggregate.outputs['Fac'],grains.inputs[0])
grain_mix=n.new('ShaderNodeMixRGB');grain_mix.blend_type='MULTIPLY';grain_mix.inputs[0].default_value=.55;l.new(patch_mix.outputs[0],grain_mix.inputs[1]);l.new(grains.outputs[0],grain_mix.inputs[2]);l.new(grain_mix.outputs[0],asphalt_bs.inputs['Base Color'])
asphalt_bump=n.get('Bump');asphalt_bump.inputs['Distance'].default_value=.007;asphalt_bump.inputs['Strength'].default_value=.65;l.new(aggregate.outputs['Fac'],asphalt_bump.inputs['Height'])
roughness=n.new('ShaderNodeMapRange');roughness.inputs['To Min'].default_value=.79;roughness.inputs['To Max'].default_value=.98;l.new(patch.outputs['Fac'],roughness.inputs['Value']);l.new(roughness.outputs[0],asphalt_bs.inputs['Roughness'])
wall=textured('Retaining wall · streaked concrete',(.16,.17,.12),(.35,.34,.26),3,.92,.022,(2,2,.14))
# Continuous moss colonies on the shaded wall, broken by vertical damp streaks.
wn=wall.node_tree.nodes;wl=wall.node_tree.links;wb=wn.get('Principled BSDF')
wcoord=wn.new('ShaderNodeTexCoord');wscale=wn.new('ShaderNodeVectorMath');wscale.operation='MULTIPLY';wscale.inputs[1].default_value=(1,1,.7);wl.new(wcoord.outputs['Object'],wscale.inputs[0])
wnoise=wn.new('ShaderNodeTexNoise');wnoise.name='Connected moss colonies';wnoise.inputs['Scale'].default_value=.9;wnoise.inputs['Detail'].default_value=5;wnoise.inputs['Roughness'].default_value=.75;wl.new(wscale.outputs[0],wnoise.inputs['Vector'])
wmask=wn.new('ShaderNodeValToRGB');wmask.name='Moss coverage';wmask.color_ramp.elements[0].position=.33;wmask.color_ramp.elements[0].color=(0,0,0,1);wmask.color_ramp.elements[1].position=.57;wmask.color_ramp.elements[1].color=(1,1,1,1);wl.new(wnoise.outputs['Fac'],wmask.inputs[0])
wgreen=wn.new('ShaderNodeValToRGB');wgreen.color_ramp.elements[0].color=(.026,.034,.010,1);wgreen.color_ramp.elements[1].color=(.095,.115,.036,1);wl.new(wn.get('Noise Texture').outputs['Fac'],wgreen.inputs[0])
wmix=wn.new('ShaderNodeMixRGB');wl.new(wmask.outputs[0],wmix.inputs[0]);wl.new(wn.get('Color Ramp').outputs[0],wmix.inputs[1]);wl.new(wgreen.outputs[0],wmix.inputs[2]);wl.new(wmix.outputs[0],wb.inputs['Base Color'])
sea_wall=textured('Opposite quay · washed concrete',(.20,.225,.21),(.43,.43,.39),2,.85,.025,(1,1,.22))
moss=textured('Moss and dark tide staining',(.033,.05,.017),(.15,.17,.074),4,.94,.013)
rail=textured('Handrail · grey painted tube',(.28,.30,.27),(.53,.55,.49),3,.43,.004,metal=.25)
fence=basic('White fence · worn enamel',(.64,.68,.64),.48,.25)
net=basic('Green polyethylene net',(.018,.28,.105),.58)
netdark=basic('Near net in shade',(.02,.085,.057),.68)
bark=textured('Tree bark · fissures',(.055,.045,.026),(.19,.16,.095),4,.93,.03,(2,2,.25))
leaves=[basic('Broadleaf green %02d'%i,c,.83) for i,c in enumerate([(.025,.08,.012),(.048,.125,.024),(.09,.18,.033),(.13,.21,.045),(.042,.105,.031)])]
needles=[basic('Pine needles %02d'%i,c,.83) for i,c in enumerate([(.025,.08,.044),(.055,.135,.065),(.09,.18,.09)])]
dry=basic('Dry leaves and twigs',(.15,.10,.045),.97)
# Ground and path: all positions in metres; photograph supplies relative proportions.
group('01 · Walkway and retaining wall')
box('Continuous walkway', (1.2,32,.82),(2.4,90,.36),concrete,.02)
box('Retaining wall', (2.66,38,1.17),(.55,103,1.1),wall,.028)
box('Rounded coping', (2.63,38,1.79),(.65,103,.16),wall,.025)
box('Soil behind fence',(7,40,1.9),(8,108,.6),moss)
# Asphalt has no drain grates or regularly spaced concrete slab joints.
# Keep the former lichen random sequence so existing vegetation stays identical.
patchv=[];patchf=[]
for i in range(900):
    y=random.uniform(-7,84);z=random.uniform(.72,1.71);h=random.uniform(.01,.16);w=random.uniform(.012,.075);k=len(patchv)
    for q in range(9):
        theta=q*math.tau/9;rr=random.uniform(.6,1.1);patchv.append((2.377,y+math.cos(theta)*w*rr,z+math.sin(theta)*h*rr))
    patchf.append(tuple(range(k,k+9)))
# Preserve random consumption for unchanged vegetation; moss now lives in the wall shader.
# small debris at wall foot
vv=[];ff=[]
for i in range(850):
    x=random.uniform(2.03,2.36) if random.random()<.8 else random.uniform(.1,2.35);y=random.uniform(-4,75);z=1.008;r=random.uniform(.009,.036);k=len(vv)
    vv.extend([(x-r,y,z),(x,y+r*2,z+.003),(x+r,y,z),(x,y-r,z)]);ff.append(tuple(range(k,k+4)))
mesh('Fallen leaves along edge',vv,ff,dry)

group('02 · Seaward handrail and green net')
for y in range(-9,79,3):
    rod('Tubular post',(0,y,.86),(0,y,2.13),.047,rail,12)
    rod('Post cap',(0,y,2.13),(0,y,2.17),.052,rail,12,r2=.036)
for z in [1.14,1.55,2.03]:rod('Continuous tubular rail',(0,-12,z),(0,82,z),.035,rail,12)
# Green net: actual open square mesh with slight sag and irregularity, batches per panel.
for panel,y0 in enumerate(range(-9,78,3)):
    paths=[]
    for j in range(121):
        y=y0+j*.025;paths.append([(-.047-.023*math.sin(t*math.pi),y,1.01+t*1.01) for t in [0,.25,.5,.75,1]])
    for k in range(44):
        z=1.01+k*.0235;paths.append([(-.047-.016*math.sin(j*math.pi/12),y0+j*.25,z-.035*math.sin(j*math.pi/12)) for j in range(13)])
    lines('Net mesh panel %02d'%panel,paths,.0011 if y0<12 else .0028,netdark if y0<12 else net)
    for z in [1.13,2.035]:
        for dy in [.08,1.5,2.9]:
            y=y0+dy;lines('Net tie',[[(.044*math.cos(t*math.tau/8),y+.008*math.sin(t*math.tau/8),z+.044*math.sin(t*math.tau/8)) for t in range(9)]],.003,netdark)

for ob in C.objects:ob.location.z+=.12;ob.location.y-=.8
group('03 · White boundary fence')
for y in range(-9,87,3):
    rod('Fence post',(2.59,y,2.37),(2.59,y,3.55),.029,fence,8)
    rod('Outward angled security arm',(2.59,y,3.55),(2.34,y,3.93),.023,fence,8)
for z in [2.47,3.49]:rod('Boundary horizontal rail',(2.59,-10,z),(2.59,86,z),.022,fence,8)
for z,x in [(3.63,2.54),(3.78,2.44),(3.92,2.34)]:rod('Security wire',(x,-10,z),(x,86,z),.004,bolt,6)
for y0 in range(-9,87,3):
    paths=[]
    for j in range(86):paths.append([(2.577,y0+j*.035,2.45),(2.577,y0+j*.035,3.52)])
    for j in range(25):paths.append([(2.577,y0,2.45+j*.044),(2.577,y0+3,2.45+j*.044)])
    lines('Welded boundary mesh',paths,.006,fence)
for ob in C.objects:ob.location.z-=.55
# Steel bridge: bridge axis crosses the path, angled slightly in plan.
group('04 · Bridge plate girders and bracing')
angle=-.13

def B(x,y,z):return (x, y+angle*x,z)
def bb(name,x,y,z,sx,sy,sz,mat=steel,bev=.008):
    o=box(name,B(x,y,z),(sx,sy,sz),mat,bev);o.rotation_euler.z=math.atan(angle);return o
# A wide flat bottom plate and the exposed parallel longitudinal girders.
bb('Broad lower steel box soffit',-22,11.2,5.52,100,4.7,.14,edge)
for y in [8.85,13.5]:
    bb('Box girder side web',-22,y,5.86,100,.12,.65)
    bb('Box girder lower flange',-22,y,5.55,100,.48,.12,edge)
# Open framing nearer the camera, high enough to reveal pipes and stiffeners.
for y in [-2.0,3.15,10.5]:
    bb('Main longitudinal web',-22,y,7.20,100,.10,2.04)
    bb('Main lower flange',-22,y,6.20,100,.66,.13,edge)
    bb('Main upper flange',-22,y,8.22,100,.57,.14,steel)
    for x in range(-70,28,3):
        bb('Vertical web stiffener',x,y-.12,7.2,.12,.28,1.94,edge)
        for z in [6.9,7.2,7.85]:rod('Stiffener bolt',B(x,y-.29,z),B(x,y-.34,z),.036,bolt,6)
for x in range(-70,28,7):
    bb('Transverse floor beam',x,3,8.37,.23,13.3,.72,steel)
    bb('Transverse beam flange',x,3,8.02,.46,13.4,.11,edge)
    # triangular gusset plates where webs meet cross members
    for y in [3.15,10.5]:
        verts=[B(x-.47,y-.20,6.36),B(x+.47,y-.20,6.36),B(x+.34,y-.20,7.54),B(x-.34,y-.20,7.54)]
        o=mesh('Bolted gusset plate',verts,[(0,1,2,3)],edge);so=o.modifiers.new('Steel plate thickness','SOLIDIFY');so.thickness=.035
        for dx in [-.30,-.13,.13,.30]:rod('Gusset hex bolt',B(x+dx,y-.22,6.54),B(x+dx,y-.28,6.54),.048,bolt,6)
# visible underside joints
for x in range(-70,28,9):
    bb('Soffit bolted joint',x,11.2,5.433,.27,4.55,.045,steel)
    for y in [9.05+j*.24 for j in range(19)]:
        for dx in [-.087,.087]:rod('Soffit joint bolt',B(x+dx,y,5.402),B(x+dx,y,5.435),.025,bolt,6)
bb('Road deck underside',-22,3.7,8.95,100,19,.25,steel)
group('05 · Bridge services and maintenance rails')
for y,z,r in [(-.3,8.25,.23),(1.1,8.25,.14),(4.8,8.33,.105),(7.8,8.25,.22),(8.4,8.27,.14)]:
    rod('Utility pipe',B(-73,y,z),B(28,y,z),r,pipe,16)
    for x in range(-70,28,6):
        rod('Pipe coupling sleeve',B(x-.075,y,z),B(x+.075,y,z),r*1.13,edge,16)
        rod('Pipe hanger',B(x,y,8.9),B(x,y,z),.023,bolt,8)
for y in [2.65,10.0]:
    for z in [7.07,7.65]:rod('Maintenance guardrail',B(-73,y,z),B(28,y,z),.027,edge,10)
    for x in range(-70,28,3):rod('Maintenance upright',B(x,y,6.15),B(x,y,7.85),.025,edge,8)
    for yy in [y-.48,y+.26]:bb('Inspection tray side',-22,yy,5.97,100,.075,.12,edge)
    for x in range(-70,28,2):bb('Inspection tray cross support',x,y-.12,5.95,.075,.8,.075,edge)
# Sea shader: crossing wind waves and fine ripples, actual subtly displaced mesh.
group('06 · Water')
# Reflection-dominant approximation keeps bridge shadows from reading as opaque paint.
water=basic('Blue green rippled water',(.25,.34,.42),.10,1.0)
n=water.node_tree.nodes;l=water.node_tree.links;bs=n.get('Principled BSDF');bs.inputs['IOR'].default_value=1.333;bs.inputs['Coat Weight'].default_value=.15;bs.inputs['Coat Roughness'].default_value=.05
tex=n.new('ShaderNodeTexCoord');vm=n.new('ShaderNodeVectorMath');vm.operation='MULTIPLY';vm.inputs[1].default_value=(.8,1.8,1);l.new(tex.outputs['Object'],vm.inputs[0])
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1.0;noise.inputs['Detail'].default_value=3;noise.inputs['Roughness'].default_value=.65;l.new(vm.outputs[0],noise.inputs['Vector'])
bu=n.new('ShaderNodeBump');bu.name='Fine river ripples';bu.inputs['Strength'].default_value=.90;bu.inputs['Distance'].default_value=.75;l.new(noise.outputs['Fac'],bu.inputs['Height']);l.new(bu.outputs[0],bs.inputs['Normal'])
slow=n.new('ShaderNodeTexNoise');slow.inputs['Scale'].default_value=.65;slow.inputs['Detail'].default_value=2;l.new(vm.outputs[0],slow.inputs['Vector'])
slow_bump=n.new('ShaderNodeBump');slow_bump.inputs['Strength'].default_value=.45;slow_bump.inputs['Distance'].default_value=.065;l.new(slow.outputs['Fac'],slow_bump.inputs['Height']);l.new(bu.outputs[0],slow_bump.inputs['Normal']);l.new(slow_bump.outputs[0],bs.inputs['Normal']);l.new(slow_bump.outputs[0],bs.inputs['Coat Normal'])
verts=[];faces=[];nx=260;ny=270
for j in range(ny+1):
    y=-30+j*1.7
    for i in range(nx+1):
        x=-420+i*1.75;z=.006*math.sin(x*.55+y*.8)+.003*math.sin(x*1.1-y*.65);verts.append((x,y,z))
for j in range(ny):
    for i in range(nx):k=j*(nx+1)+i;faces.append((k,k+1,k+nx+2,k+nx+1))
o=mesh('Continuous wave surface',verts,faces,water)
for f in o.data.polygons:f.use_smooth=True
# Shoreline across the channel.
group('07 · Opposite quay and wave breakers')
# Straight plan alignment, with a genuinely concave cross section facing the channel.
# Distances are chosen for the fixed photo camera, not as surveyed site dimensions.
QUAY_X=-120.0;QUAY_TOP=10.5;QUAY_TOE=4.8;QUAY_START=-180.0;QUAY_END=352.0

def quay_x(z):
    t=max(0,min(1,max(z,0)/QUAY_TOP))
    return QUAY_X+QUAY_TOE*(1-math.sqrt(max(0,1-(1-t)**2)))

quay_material=sea_wall.copy();quay_material.name='Opposite quay · curved weathered concrete'
quay_material.node_tree.nodes.get('Noise Texture').inputs['Scale'].default_value=.45
qn=quay_material.node_tree.nodes;ql=quay_material.node_tree.links
qgeo=qn.new('ShaderNodeNewGeometry');qsep=qn.new('ShaderNodeSeparateXYZ');qnorm=qn.new('ShaderNodeMath');qnorm.operation='DIVIDE';qnorm.inputs[1].default_value=QUAY_TOP
ql.new(qgeo.outputs['Position'],qsep.inputs[0]);ql.new(qsep.outputs['Z'],qnorm.inputs[0])
weather=qn.new('ShaderNodeValToRGB');weather.label='Horizontal damp and runoff bands on the curved face'
weather.color_ramp.elements.remove(weather.color_ramp.elements[1])
for i,(pos,value) in enumerate([(0,.60),(.06,.78),(.20,.95),(.60,.78),(.90,.58),(1,.70)]):
    el=weather.color_ramp.elements[0] if i==0 else weather.color_ramp.elements.new(pos);el.position=pos;el.color=(value,value,value,1)
ql.new(qnorm.outputs[0],weather.inputs[0]);qmix=qn.new('ShaderNodeMixRGB');qmix.blend_type='MULTIPLY';qmix.inputs[0].default_value=1
ql.new(qn.get('Color Ramp').outputs[0],qmix.inputs[1]);ql.new(weather.outputs[0],qmix.inputs[2]);ql.new(qmix.outputs[0],qn.get('Principled BSDF').inputs['Base Color'])
sections=[QUAY_START+(QUAY_END-QUAY_START)*j/80 for j in range(81)]
profile=[-.5]+[QUAY_TOP*(1-math.cos(j*math.pi/80)) for j in range(41)]
v=[(quay_x(z),y,z) for y in sections for z in profile];f=[];np=len(profile)
for j in range(len(sections)-1):
    for k in range(np-1):
        a0=j*np+k;f.append((a0,a0+np,a0+np+1,a0+1))
front_count=len(f)
# Close the rear, top, bottom and ends, leaving a solid editable mesh.
for j in range(len(sections)-1):
    ids=[]
    for y in [sections[j],sections[j+1]]:
        ids.append(len(v));v.extend([(QUAY_X-3,y,-.5),(QUAY_X-3,y,QUAY_TOP)])
    lo=j*np;hi=(j+1)*np;b0,b1=ids
    f.extend([(lo,b0,b1,hi),(lo+np-1,hi+np-1,b1+1,b0+1),(b0,b0+1,b1+1,b1)])
for j in [0,len(sections)-1]:
    ids=list(range(j*np,(j+1)*np));back=len(v);v.extend([(QUAY_X-3,sections[j],QUAY_TOP),(QUAY_X-3,sections[j],-.5)])
    face=ids+[back,back+1];f.append(tuple(face if j==0 else reversed(face)))
quay=mesh('Opposite seawall · curved cross section',v,f,quay_material)
for poly in list(quay.data.polygons)[:front_count]:poly.use_smooth=True
quay['cross_section']='Concave face; seaward toe, vertical crest';quay['crest_z']=QUAY_TOP;quay['toe_projection']=QUAY_TOE
box('Quay rounded top',(QUAY_X-.15,(QUAY_START+QUAY_END)/2,QUAY_TOP+.07),(.65,QUAY_END-QUAY_START,.16),quay_material,.055)
box('Opposite planted land',(QUAY_X-76,(QUAY_START+QUAY_END)/2,QUAY_TOP-1),(152,QUAY_END-QUAY_START,2),moss)
for y in range(-176,353,32):
    lines('Quay expansion joint',[[(quay_x(z)+.015,y,z) for z in profile if z>=0]],.018,moss)
# Narrow waterline staining follows the same curved surface.
tide=basic('Quay waterline · muted damp grey',(.12,.14,.12),.94)
v=[(quay_x(z)+.018,y,z) for y in sections for z in [.025,.48]]
f=[(2*j,2*j+2,2*j+3,2*j+1) for j in range(len(sections)-1)]
mesh('Tidal waterline · curved',v,f,tide)
rock=textured('Wave breakers · pale weathered concrete',(.29,.285,.24),(.54,.53,.46),3,.91,.035)
# Tetrapods are four tapered arms meeting at one centre; shared joined meshes.
for i in range(62):
    x=random.uniform(-28,-18);y=random.uniform(87,94);z=.35+random.random()*1.2
    centre=Vector((x,y,z));rot=__import__('mathutils').Euler((random.random()*3,random.random()*3,random.random()*6)).to_matrix()
    for d in [(1,1,1),(-1,-1,1),(-1,1,-1),(1,-1,-1)]:
        dr=rot@Vector(d).normalized();rod('Tetrapod arm',centre,centre+dr*random.uniform(.8,1.15),.38,rock,7,r2=.22)
# Move the existing randomised tetrapods with the far end of the relocated quay.
bpy.context.view_layer.update()
transform=Matrix.Translation((QUAY_X,QUAY_END,0)) @ Matrix.Diagonal((4,4,4,1)) @ Matrix.Translation((25,-88,0))
for ob in C.objects:
    if ob.name.startswith('Tetrapod arm'):ob.matrix_world=transform @ ob.matrix_world
# Vegetation is generated as branching wood and individual leaves/needle sprays.
def leaf_cloud(name,clusters,mats,count=55,size=.13):
    vs=[];fs=[];mi=[]
    for center,radius in clusters:
        center=Vector(center)
        for k in range(count):
            az=random.random()*math.tau;zz=random.uniform(-1,1);rr=random.random()**(1/3);s=math.sqrt(1-zz*zz)
            c=center+Vector((s*math.cos(az),s*math.sin(az),zz))*(radius*rr)
            u=Vector((random.uniform(-1,1),random.uniform(-1,1),random.uniform(-.6,.6))).normalized()*random.uniform(size*.6,size*1.35)
            v=u.cross(Vector((random.uniform(-.5,.5),random.uniform(-.5,.5),1))).normalized()*u.length*.42
            idx=len(vs);vs.extend([c-u,c+v,c+Vector((0,0,.022)),c-v,c+u]);fs.extend([(idx,idx+1,idx+2,idx+3),(idx+1,idx+4,idx+3,idx+2)]);mi.extend([random.randrange(len(mats))]*2)
    o=mesh(name,vs,fs,None)
    for m in mats:o.data.materials.append(m)
    for f,idx in zip(o.data.polygons,mi):f.material_index=idx
    return o

def broad_tree(name,x,y,z,h,spread):
    root=Vector((x,y,z));top=root+Vector((random.uniform(-.5,.5),random.uniform(-.4,.4),h*.72));rod(name+' trunk',root,top,h*.036,bark,9,r2=.045)
    clusters=[]
    for j in range(15):
        az=j*2.4+random.uniform(-.3,.3);level=random.uniform(.4,.9);start=root.lerp(top,level)
        tip=root+Vector((math.cos(az)*spread*random.uniform(.45,1),math.sin(az)*spread*random.uniform(.5,1),h*random.uniform(.62,1.0)))
        mid=start.lerp(tip,.63)+Vector((0,0,.2));rod(name+' limb',start,mid,h*.011,bark,7,r2=.025);rod(name+' branch',mid,tip,.027,bark,6,r2=.006)
        for k in range(5):
            end=tip+Vector((random.uniform(-.6,.6),random.uniform(-.6,.6),random.uniform(-.3,.6)))*spread*.6
            rod(name+' twig',tip,end,.009,bark,5,r2=.002);clusters.append((end,spread*.32))
    leaf_cloud(name+' individual leaves',clusters,leaves,count=210,size=.20 if h<9 else .23)

def pine_sprays(name,tips):
    vs=[];fs=[];indices=[]
    for tip,direction in tips:
        d=Vector(direction).normalized();tip=Vector(tip);ref=d.cross(Vector((0,0,1))).normalized()
        if ref.length<.01:ref=Vector((1,0,0))
        other=d.cross(ref).normalized()
        for t in range(90):
            az=random.random()*math.tau;along=random.uniform(-.18,.07);out=ref*math.cos(az)+other*math.sin(az);start=tip+d*along;end=start+(out*.7+d*.55)*random.uniform(.12,.24)
            side=(end-start).cross(Vector((.3,.2,1))).normalized()*.009;k=len(vs);vs.extend([start-side,start+side,end]);fs.append((k,k+1,k+2));indices.append(random.randrange(len(needles)))
    o=mesh(name,vs,fs,None)
    for m in needles:o.data.materials.append(m)
    for f,idx in zip(o.data.polygons,indices):f.material_index=idx

group('08 · Foreground pine and broadleaf canopy')
# Pine leaning over the channel, behind bridge edge.
root=Vector((5.8,22,2.2));t1=Vector((5.0,22,5.5));t2=Vector((3.8,23,9.2));rod('Pine continuous lower trunk',root,t1,.36,bark,12,r2=.24);rod('Pine upper trunk',t1,t2,.24,bark,10,r2=.09)
tips=[]
for j in range(22):
    z=random.uniform(4.4,9.5);start=Vector((5.8-(z-2.2)*.26,22,z));end=start+Vector((random.uniform(-9,-2),random.uniform(-4,5),random.uniform(-1.1,.9)));mid=start.lerp(end,.6)+Vector((0,0,-.4))
    rod('Pine sweeping bough',start,mid,.11,bark,9,r2=.06);rod('Pine secondary bough',mid,end,.06,bark,7,r2=.014)
    for k in range(14):
        a0=mid.lerp(end,random.random());az=random.random()*math.tau;out=Vector((math.cos(az)*random.uniform(.3,.8),math.sin(az)*random.uniform(.4,1),random.uniform(.1,.65)));e=a0+out
        rod('Pine leafy branch',a0,e,.013,bark,5,r2=.003)
        for q in range(7):
            d=Vector((random.uniform(-.5,.5),random.uniform(-.5,.5),random.uniform(.25,.8)));p0=a0.lerp(e,q/7);p1=p0+d*.38;tips.append((p1,d));rod('Pine terminal twig',p0,p1,.003,bark,4,r2=.001)
pine_sprays('Individual pine needle sprays',tips)
for idx,(x,y,h,s) in enumerate([(6,8,8,3),(7,16,9,3.7),(6,29,9,3.2),(6,39,10,3.4),(6,51,10,3.6),(7,64,11,4),(5,76,10,3.8)]):broad_tree('Right canopy %02d'%idx,x,y,2.2,h,s)
for i in range(18):
    leaf_cloud('Overhanging right understory %02d'%i,[((random.uniform(3.5,4.8),12+i*4.2,random.uniform(3.7,5.0)),1.8)],leaves,count=1250,size=.17)
group('09 · Opposite planting and palms')
for i in range(32):broad_tree('Opposite grove %02d'%i,random.uniform(-39,-30),-38+i*4.1,5.2,random.uniform(5.0,9),random.uniform(2.8,4.1))
for i in range(26):
    leaf_cloud('Dense opposite understory %02d'%i,[((random.uniform(-31,-29),-35+i*4.7,random.uniform(6,7.5)),2.0)],leaves,count=850,size=.23)
# Palm crowns with arching fronds and separate leaflets.
for i in range(14):
    x=random.uniform(-53,-34);y=random.uniform(-15,85);h=random.uniform(11,19);rod('Palm ringed trunk',(x,y,4),(x+.3,y,h),.18,bark,9,r2=.12)
    for j in range(10):
        az=j*math.tau/10;direction=Vector((math.cos(az),math.sin(az),0));start=Vector((x+.3,y,h));pts=[start+direction*(t*3.7)+Vector((0,0,math.sin(t*math.pi)*1.6-t*.65)) for t in [k/10 for k in range(11)]];lines('Arched palm frond',[pts],.023,leaves[2]);v=[];f=[]
        for k in range(1,10):
            pp=pts[k];side=Vector((-direction.y,direction.x,-.35));length=1.05*math.sin(k/11*math.pi)
            for sign in [-1,1]:
                end=pp+side*sign*length+direction*.35;idx=len(v);v += [pp-direction*.04,pp+direction*.055,end];f.append((idx,idx+1,idx+2))
        mesh('Palm slender leaflets',v,f,leaves[i%len(leaves)])
# Subtle distant buildings and power lines visible through planting.
roof=basic('Distant terracotta roof',(.36,.22,.12),.87)
box('Partially hidden distant building',(-46,38,8.3),(9,24,8),sea_wall)
box('Low terracotta roof',(-46,38,12.5),(11,27,.45),roof)
lines('Distant overhead wires',[[(-33,-50,z),(-33,30,z-.6),(-33,110,z)] for z in [12,13]],.022,bolt)
# Follow the new bank with its vegetation/buildings, preserving the near scene.
bpy.context.view_layer.update()
transform=Matrix.Translation((QUAY_X,0,QUAY_TOP)) @ Matrix.Diagonal((2.5,4,2.4,1)) @ Matrix.Translation((25,0,-5.2))
for ob in C.objects:ob.matrix_world=transform @ ob.matrix_world
group('10 · Mountain and small boats')
# Fit the ridge to reference-image coordinates while keeping the camera fixed.
# The summit lies behind the bridge; the visible slope falls towards image right.
cam_pos=Vector((.75,0,2.65));cam_rotation=Vector((-.39,1,-.035)).to_track_quat('-Z','Y')
def photo_point(u,v,depth):
    ray=cam_rotation @ Vector(((u-.5)*36/26,(.5-v)*36/26,-1))
    return cam_pos+ray*((depth-cam_pos.y)/ray.y)
ridge_anchors=[(-.45,.18),(0,.19),(.25,.20),(.4,.22),(.53,.26),(.62,.32),(.72,.40),(.85,.455),(1.1,.48)]
def ridge_v(u):
    for (u0,v0),(u1,v1) in zip(ridge_anchors,ridge_anchors[1:]):
        if u<=u1:
            t=max(0,min(1,(u-u0)/(u1-u0)));t=t*t*(3-2*t);return v0+(v1-v0)*t
    return ridge_anchors[-1][1]
for layer in range(3):
    depth=650+layer*80;vs=[];fs0=[]
    for i in range(101):
        u=-.45+i*1.55/100;v=ridge_v(u)+random.uniform(-5,5)/2400-layer*.0015
        top=photo_point(u,v,depth);vs.extend([(top.x,top.y,0),tuple(top)])
        if i:fs0.append((2*i-2,2*i,2*i+1,2*i-1))
    mat=textured('Hazy mountain layer %d'%layer,(.18+layer*.025,.28+layer*.022,.33+layer*.025),(.29+layer*.025,.38+layer*.022,.42+layer*.025),.045,.94,.02)
    mesh('Mountain ridge %d'%layer,vs,fs0,mat)
white=basic('Small boat off white',(.7,.72,.67),.5)
for x,y,size in [(-7,134,1),(-18,175,.7)]:
    box('Distant boat hull',(x,y,.6),(3.6*size,1.3*size,.75*size),white,.2)
    box('Boat wheelhouse',(x,y,1.35),(1.5*size,.95*size,.9*size),white,.08)
    rod('Boat mast',(x,y,1.5),(x,y,4),.025,bolt,6)
# World daylight; bridge provides real occlusion and reflected light.
C=base
world=bpy.data.worlds.new('Soft coastal daylight');bpy.context.scene.world=world;world.use_nodes=True
n=world.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputWorld');bg=n.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=2.0
tex=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');ramp=n.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position=0;ramp.color_ramp.elements[0].color=(.68,.76,.84,1)
ramp.color_ramp.elements[1].position=.8;ramp.color_ramp.elements[1].color=(.31,.46,.66,1)
world.node_tree.links.new(tex.outputs['Normal'],sep.inputs[0]);world.node_tree.links.new(sep.outputs['Z'],ramp.inputs[0]);cloud=n.new('ShaderNodeTexNoise');cloud.inputs['Scale'].default_value=3;cloud.inputs['Detail'].default_value=2;world.node_tree.links.new(tex.outputs['Normal'],cloud.inputs['Vector']);cr=n.new('ShaderNodeValToRGB');cr.color_ramp.elements[0].position=.32;cr.color_ramp.elements[0].color=(.28,.40,.57,1);cr.color_ramp.elements[1].position=.68;cr.color_ramp.elements[1].color=(1.5,1.5,1.5,1);world.node_tree.links.new(cloud.outputs['Fac'],cr.inputs[0]);mix=n.new('ShaderNodeMixRGB');mix.inputs[0].default_value=.7;world.node_tree.links.new(ramp.outputs[0],mix.inputs[1]);world.node_tree.links.new(cr.outputs[0],mix.inputs[2]);world.node_tree.links.new(mix.outputs[0],bg.inputs['Color']);world.node_tree.links.new(bg.outputs[0],out.inputs[0])
lp=n.new('ShaderNodeLightPath');gain=n.new('ShaderNodeMath');gain.operation='MULTIPLY_ADD';gain.inputs[1].default_value=2;gain.inputs[2].default_value=2;world.node_tree.links.new(lp.outputs['Is Glossy Ray'],gain.inputs[0]);world.node_tree.links.new(gain.outputs[0],bg.inputs['Strength'])
sun_data=bpy.data.lights.new('Soft daylight sun','SUN');sun_data.energy=2.0;sun_data.angle=.12;sun_data.color=(1,.95,.86)
sun=bpy.data.objects.new('Soft daylight sun',sun_data);C.objects.link(sun);sun.rotation_euler=Vector((.1,-1,-.5)).to_track_quat('-Z','Y').to_euler()
# Large diffuse sky source improves a soft overcast-like fill without emissive geometry.
def area(name,loc,power,size,color,target):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.specular_factor=0;d.shape='DISK';d.size=size;d.color=color;o=bpy.data.objects.new(name,d);C.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Open channel sky fill',(-18,25,22),1800,35,(.82,.89,1),(0,8,2))
area('Water reflected fill under bridge',(-7,1,1.5),1100,18,(.94,.96,1),(-4,9,7))
area('Open channel fill onto walkway',(-7,5,4.5),700,14,(1,.95,.85),(1,8,1))
bpy.ops.object.camera_add(location=(.75,0,2.65));cam=put(bpy.context.object,'IMG_6948 · matched square photograph')
cam.rotation_euler=Vector((-.39,1,-.035)).to_track_quat('-Z','Y').to_euler();cam.data.lens=26;cam.data.sensor_width=36;cam.data.clip_end=1800
ref=bpy.data.images.load(str(R/'photos/IMG_6948.jpeg'));ref.pack();ref.filepath='//photos/IMG_6948.jpeg';cam.data.show_background_images=True;im=cam.data.background_images.new();im.image=ref;im.alpha=.35;im.display_depth='BACK'
s=bpy.context.scene;s.camera=cam;s['reference']='photos/IMG_6948.jpeg';s['reference_pixel_size']='3024 x 3024; square source';s['creation']='New procedural geometry and materials; no other project assets';s['units_note']='Metres; dimensions inferred from a single photograph'
s.unit_settings.system='METRIC';s.render.engine='CYCLES';s.cycles.samples=a.samples;s.cycles.use_denoising=True;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.035;s.cycles.adaptive_min_samples=16;s.cycles.max_bounces=7;s.cycles.diffuse_bounces=3;s.cycles.glossy_bounces=4
s.render.resolution_x=a.width;s.render.resolution_y=a.width;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB'
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium Low Contrast';s.view_settings.exposure=.15
(R/'renders').mkdir(exist_ok=True)
s.render.filepath='//renders/photo_match.png';s.render.film_transparent=False
# Open in camera view and keep the photo overlay disabled by default.
cam.data.show_background_images=False
for screen in bpy.data.screens:
    for ar in screen.areas:
        if ar.type=='VIEW_3D':ar.spaces.active.region_3d.view_perspective='CAMERA';ar.spaces.active.clip_end=1800
# Apply the measured photo comparison refinements to every regenerated scene.
import importlib.util
spec=importlib.util.spec_from_file_location('img6948_refinements',R/'scripts/refine_scene.py')
refinement=importlib.util.module_from_spec(spec);spec.loader.exec_module(refinement);refinement.refine()
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(R/'under_bridge.blend'))
print('IMG6948_BUILD_COMPLETE',len(s.objects),flush=True)
if a.render:bpy.ops.render.render(write_still=True)
