"""A coloured-glass butterfly hovering above a swept, curling glass wave.

All ribbons, wing cells, veins, droplets and inclusions are actual geometry.
Control points are measured in the main reference's 1254-pixel image plane;
depth, elliptical sections and curved wing surfaces make a complete 3D model.
"""
import math
import random

import bpy
from mathutils import Matrix,Vector

from common import (ROOT,clear_scene,settings,group,mesh,weld_normals,
                    basic_material,glass_material,curve_tube,sphere,
                    camera,area,reference_guides,linear)

S=.30/1120
RNG=random.Random(5534)
GLASS={}
WING={}


def P(x,y,depth=0):
    return Vector(((x-627)*S,depth*S,(1155-y)*S))


def spline(values,t):
    """Clamped Catmull-Rom spline of arbitrary-dimensional control points."""
    u=max(0,min(1,t))*(len(values)-1)
    i=min(len(values)-2,int(u))
    f=u-i
    a,b,c,d=[values[max(0,min(len(values)-1,j))] for j in [i-1,i,i+1,i+2]]
    return [0.5*((2*b[k])+(-a[k]+c[k])*f+(2*a[k]-5*b[k]+4*c[k]-d[k])*f*f+(-a[k]+3*b[k]-3*c[k]+d[k])*f*f*f) for k in range(len(b))]


def sweep(name,controls,mat,depth=0,ratio=.28,twist=0,collection='Wave_Ribbons'):
    """Closed variable-section glass ribbon, with editable spine kept as a guide."""
    values=[]
    for point in controls:
        x,y,w=point[:3]
        dep=point[3] if len(point)>3 else depth
        r=point[4] if len(point)>4 else ratio
        rot=point[5] if len(point)>5 else twist
        values.append([x,y,w,dep,r,rot])
    n=max(60,(len(values)-1)*16)
    samples=[spline(values,i/(n-1)) for i in range(n)]
    centers=[P(v[0],v[1],v[3]) for v in samples]
    verts=[]
    section=24
    for i,(v,center) in enumerate(zip(samples,centers)):
        tangent=(centers[min(n-1,i+1)]-centers[max(0,i-1)]).normalized()
        normal=Vector((-tangent.z,0,tangent.x)).normalized()
        if normal.length<.1:normal=Vector((1,0,0))
        binormal=tangent.cross(normal).normalized()
        rot=v[5]+.12*math.sin(i/(n-1)*math.tau)
        a=normal*math.cos(rot)+binormal*math.sin(rot)
        b=-normal*math.sin(rot)+binormal*math.cos(rot)
        w=max(1.8,v[2])*S
        thick=max(.7,max(1.8,v[2])*v[4])*S
        for j in range(section):
            angle=j*math.tau/section
            # Broad polished convex faces, thin softly rounded lips.
            verts.append(center+a*(w*math.cos(angle))+b*(thick*math.sin(angle)))
    faces=[]
    for i in range(n-1):
        for j in range(section):
            faces.append((i*section+j,i*section+(j+1)%section,(i+1)*section+(j+1)%section,(i+1)*section+j))
    verts.extend([centers[0],centers[-1]])
    for j in range(section):
        faces.append((len(verts)-2,(j+1)%section,j))
        faces.append((len(verts)-1,(n-1)*section+j,(n-1)*section+(j+1)%section))
    obj=mesh(name,verts,faces,mat,collection)
    weld_normals(obj)
    obj['construction']='Variable elliptical cross sections along a Catmull-Rom spine'
    obj['control_points_pixels']=str(controls)
    guide=curve_tube('Spine · '+name,[P(v[0],v[1],v[3]) for v in values],.00015,mat,'Editable_Spines')
    guide.hide_render=guide.hide_viewport=True
    return obj


def ellipse_ring(name,center,rx,ry,tube,mat,phase=0):
    verts=[]
    a,b=128,20
    for i in range(a):
        theta=i*math.tau/a
        co=Vector((center[0]+rx*math.cos(theta),center[1]+ry*math.sin(theta),center[2]+.0008*math.sin(theta*2+phase)))
        radial=Vector((math.cos(theta),math.sin(theta),0))
        for j in range(b):
            phi=j*math.tau/b
            verts.append(co+radial*(tube*math.cos(phi))+Vector((0,0,tube*.72*math.sin(phi))))
    faces=[(i*b+j,i*b+(j+1)%b,((i+1)%a)*b+(j+1)%b,((i+1)%a)*b+j) for i in range(a) for j in range(b)]
    obj=mesh(name,verts,faces,mat,'Glass_Base')
    weld_normals(obj)
    return obj


def optical_tint(mat,color,length,gain=1):
    """Beer-Lambert dye concentration for a representative glass path length."""
    coefficients=[-math.log(max(.006,linear(v)))*gain/length for v in color]
    density=max(1e-8,max(coefficients))
    absorption=mat.node_tree.nodes['Coloured glass absorption']
    absorption.inputs['Density'].default_value=density
    absorption.inputs['Color'].default_value=(*[1-v/density for v in coefficients],1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(1,1,1,1)
    mat['representative_optical_path_m']=length
    mat['colour_srgb']=color


def make_materials():
    colors={
        'clear':(.94,.98,1),'ice':(.57,.91,.97),'aqua':(.20,.80,.88),
        'turquoise':(.13,.70,.78),'cobalt':(.08,.30,.87),'blue':(.12,.49,.95),
        'rose':(.96,.54,.70),'blush':(1,.70,.79),'coral':(1,.58,.60),
        'lavender':(.76,.67,.95),'pearl':(.95,.94,.94),'champagne':(1,.91,.68)
    }
    for name,col in colors.items():
        GLASS[name]=glass_material('Optical glass · '+name,col,.021 if name in ['clear','ice'] else .027,
                                   8 if name in ['cobalt','blue','turquoise'] else 3,glitter=name not in ['clear','pearl'])
        optical_tint(GLASS[name],col,.0065,.30 if name in ['clear','ice','pearl'] else .85)
        WING[name]=glass_material('Wing glass · '+name,col,.032,glitter=True)
        optical_tint(WING[name],col,.0018)
        wing_bsdf=WING[name].node_tree.nodes['Principled BSDF']
        wing_bsdf.inputs['Transmission Weight'].default_value=.88
        wing_bsdf.inputs['Base Color'].default_value=(*[linear(v) for v in col],1)
        wing_bsdf.inputs['Specular IOR Level'].default_value=.32
    GLASS['gold']=basic_material('Rose gold · butterfly veins',(.45,.22,.095),.17,.85)
    GLASS['dark']=glass_material('Deep sapphire · butterfly body',(.08,.10,.29),.025,5)
    optical_tint(GLASS['dark'],(.08,.10,.29),.0045)
    GLASS['spark']=basic_material('Minute crystal inclusions',(.93,.96,1),.14,.28)


def wing_map(root,arc,bulge,depth,t,r):
    # Every cell and vein uses exactly the same continuous wing surface.
    r=max(0,min(1,r+.046*math.sin(6*math.pi*t+.7)*math.sin(math.pi*r)))
    q=t+.014*math.sin(math.pi*r)*math.sin(6*math.pi*t)
    outer=spline(arc,max(0,min(1,q)))
    scallop=1+.012*math.sin(math.pi*t)**2*math.cos(18*math.pi*t)*r**4
    x=root[0]+r*(outer[0]-root[0])*scallop+bulge[0]*4*r*(1-r)*(1-t)**3
    y=root[1]+r*(outer[1]-root[1])*scallop+bulge[1]*4*r*(1-r)*(1-t)**3
    d=depth+17*r-14*math.sin(math.pi*r)*math.cos(math.pi*(t-.2))
    return P(x,y,d)


def wing_cell(name,mapper,t0,t1,r0,r1,mat):
    n=9
    verts=[]
    for side in [-1,1]:
        for j in range(n):
            v=j/(n-1)
            r=r0+(r1-r0)*(.012+.976*v)
            for i in range(n):
                u=i/(n-1)
                t=t0+(t1-t0)*(.012+.976*u)
                co=mapper(t,r)
                half=.00036+.00088*math.sin(math.pi*u)*math.sin(math.pi*v)
                verts.append(co+Vector((0,side*half,0)))
    faces=[]
    nn=n*n
    for j in range(n-1):
        for i in range(n-1):
            a=j*n+i
            faces.append((a,a+1,a+n+1,a+n))
            faces.append((nn+a+n,nn+a+n+1,nn+a+1,nn+a))
    border=list(range(n))+[j*n+n-1 for j in range(1,n)]+list(range(nn-2,nn-n-1,-1))+[j*n for j in range(n-2,0,-1)]
    for i,a in enumerate(border):
        b=border[(i+1)%len(border)]
        faces.append((a,nn+a,nn+b,b))
    obj=mesh(name,verts,faces,mat,'Butterfly_Wings')
    obj['butterfly_component']=True
    obj['wing_cell']=True
    obj['nominal_thickness_m']=.0024
    weld_normals(obj)
    return obj


def octa_cloud(name,positions,mat,collection):
    verts,faces=[],[]
    for center,radius in positions:
        k=len(verts)
        verts.extend([center+Vector(v)*radius for v in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]])
        faces.extend([tuple(k+j for j in tri) for tri in [(0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)]])
    obj=mesh(name,verts,faces,mat,collection,False)
    return obj


def butterfly():
    root=(685,597)
    specs=[
        ('left forewing',[(398,177),(412,237),(416,279),(408,325),(413,365),(425,404),(447,441),(484,475)],(102,-8),-63,10),
        ('left hindwing',[(316,560),(349,592),(381,622),(413,663),(455,710),(500,743),(551,748),(591,725),(623,682)],(-8,-92),-73,11),
        ('right forewing',[(948,427),(940,467),(910,502),(879,535),(841,568),(793,602),(748,620)],(15,-39),-57,9),
        ('right hindwing',[(758,634),(775,666),(769,699),(750,741),(724,778),(675,794),(660,770)],(4,-7),-47,8)
    ]
    sparkles=[]
    for label,arc,bulge,dep,count in specs:
        mapper=lambda t,r,arc=arc,bulge=bulge,dep=dep:wing_map(root,arc,bulge,dep,t,r)
        bands=[.018,.52,.81,1]
        for band in range(3):
            for i in range(count):
                if band==2:
                    color=['rose','blush','lavender','coral','blush'][i%5]
                elif band==1:
                    color=['champagne','pearl','blush','champagne','rose','pearl'][i%6]
                else:
                    color=['pearl','champagne','blush','pearl'][i%4]
                if 'forewing' in label and i==0 and band<2:color='blue'
                if label=='left hindwing' and i<2 and band==0:color='ice'
                wing_cell(f'Butterfly · {label} · cell {band}-{i:02d}',mapper,i/count,(i+1)/count,bands[band],bands[band+1],WING[color])
        for i in range(count+1):
            t=i/count
            points=[mapper(t,r)+Vector((0,-.00043,0)) for r in [0,.12,.27,.43,.60,.77,.9,1]]
            vein=curve_tube(f'Butterfly · {label} · radial vein {i:02d}',points,.00020,GLASS['gold'])
            vein['butterfly_component']=True
        for band in [.52,.81,1]:
            points=[mapper(i/48,band)+Vector((0,-.00043,0)) for i in range(49)]
            vein=curve_tube(f'Butterfly · {label} · curved vein {band}',points,.00022 if band<1 else .00030,GLASS['gold'])
            vein['butterfly_component']=True
        for i in range(140 if 'left' in label else 80):
            t=RNG.uniform(.03,.97)
            r=RNG.uniform(.24,.96)
            sparkles.append((mapper(t,r)+Vector((0,-.0002,0)),RNG.uniform(.000045,.00015)))
    inclusions=octa_cloud('Butterfly · minute glass inclusions',sparkles,GLASS['spark'],'Embellishments')
    inclusions['butterfly_component']=True
    tail,thorax=P(658,685,-66),P(711,564,-66)
    center=(tail+thorax)/2
    body=sphere('Butterfly · long sapphire abdomen',center,.010,GLASS['dark'],'Butterfly_Body',(.30,.36,(thorax-tail).length/.020))
    body.rotation_euler=(thorax-tail).to_track_quat('Z','Y').to_euler()
    body['butterfly_component']=True
    neck=curve_tube('Butterfly · gold thorax',[P(704,587,-66),P(716,554,-66),P(724,536,-66)],.0018,GLASS['gold'],'Butterfly_Body')
    neck['butterfly_component']=True
    head=sphere('Butterfly · crystal sapphire head',P(724,529,-69),.0047,GLASS['blue'],'Butterfly_Body')
    head['butterfly_component']=True
    for label,points in [
        ('left',[(719,516),(747,434),(731,355),(699,316),(682,318),(678,326),(689,329)]),
        ('right',[(729,517),(764,443),(801,383),(824,379),(834,387),(831,396)])]:
        obj=curve_tube('Butterfly · '+label+' gold antenna',[P(x,y,-65) for x,y in points],.00024,GLASS['gold'],'Butterfly_Body')
        obj['butterfly_component']=True
        cap=sphere('Butterfly · '+label+' antenna pearl',P(*points[-1],-65),.0014,GLASS['champagne'],'Butterfly_Body')
        cap['butterfly_component']=True
    # Linked geometry preserves the detailed cell structure in the small butterflies.
    originals=[o for o in bpy.context.scene.objects if o.get('butterfly_component')]
    pivot=P(*root,-65)
    scaled_materials={}
    for label,x,y,depth,scale,angle in [
        ('left satellite',236,491,-30,.185,.72),
        ('upper satellite',724,140,34,.195,.65),
        ('right satellite',1167,779,-16,.175,1.05)]:
        transform=Matrix.Translation(P(x,y,depth))@Matrix.Rotation(angle,4,'Y')@Matrix.Scale(scale,4)@Matrix.Translation(-pivot)
        for original in originals:
            copy=original.copy()
            copy.name=label+' · '+original.name.replace('Butterfly · ','')
            group('Satellite_Butterflies').objects.link(copy)
            copy.matrix_world=transform@original.matrix_world
            copy['satellite_butterfly']=label
            if original.get('glass'):
                for index,slot in enumerate(original.material_slots):
                    key=(slot.material.name,scale)
                    if key not in scaled_materials:
                        tint=slot.material.copy()
                        tint.name=f'Miniature {scale:g} · '+slot.material.name
                        node=tint.node_tree.nodes.get('Coloured glass absorption')
                        if node:node.inputs['Density'].default_value/=scale
                        scaled_materials[key]=tint
                    copy.material_slots[index].link='OBJECT'
                    copy.material_slots[index].material=scaled_materials[key]
                if copy.get('nominal_thickness_m'):
                    copy['nominal_thickness_m']=original['nominal_thickness_m']*scale
    bpy.context.scene['butterfly_count']=4


def wave():
    clear,ice,aqua,cobalt,blue,rose=[GLASS[k] for k in ['clear','ice','aqua','cobalt','blue','rose']]
    # Tall open spiral, right-hand ascending column and layered coloured ribbons.
    ribbons=[
        ('Wave · clear structural spiral',clear,20,.29,[(954,228,5),(967,250,19),(946,282,39),(899,289,43),(855,248,44),(838,184,48),(855,116,50),(909,73,43),(983,77,44),(1065,115,44),(1140,197,46),(1177,327,49),(1168,493,54),(1115,665,69),(1037,813,86),(902,931,99),(731,1022,95),(537,1072,59)]),
        ('Wave · cobalt inner crest',cobalt,-4,.22,[(955,225,5),(947,256,12),(918,264,16),(903,239,17),(917,200,22),(956,166,28),(1008,157,27),(1065,182,24),(1122,256,27),(1147,381,32),(1135,531,36),(1090,686,47),(1006,822,55),(872,940,61),(714,1008,59),(555,1052,42)]),
        ('Wave · turquoise outer sweep',aqua,46,.22,[(954,255,8),(930,292,22),(878,278,27),(850,224,31),(851,154,26),(895,99,30),(956,80,27),(1040,112,28),(1110,185,25),(1153,291,25),(1160,435,29),(1128,590,38),(1073,744,49),(955,896,58),(800,990,70),(624,1067,61),(482,1086,31)]),
        ('Wave · crystal outer crest',ice,67,.18,[(945,52,15),(999,56,20),(1062,85,25),(1121,147,27),(1169,231,24),(1190,339,27),(1187,462,30),(1154,610,36),(1097,753,37),(1009,853,43),(871,967,51),(734,1039,38)]),
        ('Wave · rising sapphire blade',blue,-42,.30,[(835,1014,17),(944,933,38),(1043,806,40),(1117,645,38),(1150,486,32),(1151,357,27),(1145,320,14)]),
        ('Wave · pink refracting ribbon',rose,84,.25,[(534,1100,22),(718,1053,31),(871,968,40),(1000,854,47),(1086,722,35),(1136,568,18),(1168,415,13)]),
        ('Wave · opal rim',clear,-69,.21,[(474,1091,16),(637,1101,46),(782,1065,50),(938,964,45),(1028,853,27),(1070,763,13)]),
        ('Wave · broad leftward clear sweep',clear,-67,.26,[(844,1056,38),(730,1026,50),(566,956,62),(410,874,65),(257,824,51),(140,824,35),(68,861,22),(54,894,9)]),
        ('Wave · azure left crest',cobalt,-88,.19,[(802,1038,21),(685,1010,29),(522,928,35),(363,853,36),(231,809,29),(128,820,24),(87,853,16)]),
        ('Wave · aqua left sheet',ice,-24,.24,[(883,1025,27),(783,1009,38),(642,955,48),(495,872,48),(361,824,35),(263,817,33),(232,839,14)]),
        ('Wave · upper clear left lip',clear,5,.24,[(826,1014,22),(686,971,30),(551,889,41),(427,829,40),(349,803,28),(297,814,12)]),
        ('Wave · low curled sapphire return',cobalt,-44,.26,[(746,1100,22),(611,1071,36),(457,1006,37),(332,965,32),(276,985,29),(255,1036,20),(264,1070,13),(289,1055,6)]),
        ('Wave · foreground crystal curl',clear,-103,.23,[(813,1082,28),(705,1053,47),(555,1006,48),(433,947,36),(325,931,30),(283,949,21),(272,985,14),(294,999,6)]),
        ('Wave · secondary left curl',ice,32,.24,[(726,1050,23),(579,1004,35),(423,931,36),(278,890,25),(196,903,20),(157,936,12),(145,942,5)])
    ]
    for name,mat,dep,ratio,controls in ribbons:
        sweep(name,controls,mat,dep,ratio)
    # Smaller upright scrolls around the lower basin.
    curls=[
        ('Wave · central pink scroll','lavender',35,[(672,979,22),(690,911,29),(722,849,32),(760,825,29),(790,841,21),(783,870,15),(760,881,8)]),
        ('Wave · inner aquamarine scroll','aqua',-3,[(792,1001,27),(854,899,32),(881,808,35),(874,733,31),(838,698,25),(861,684,11)]),
        ('Wave · low clear inward curl','clear',65,[(768,986,20),(831,908,24),(857,851,27),(859,799,26),(826,775,21),(804,787,12),(811,808,5)]),
        ('Wave · small blue hook','blue',-55,[(758,990,22),(799,951,28),(811,909,24),(795,884,21),(763,898,16),(767,921,7)]),
        ('Wave · pearl inner spiral','ice',94,[(848,1003,18),(935,900,22),(955,808,25),(932,751,21),(888,745,18),(877,767,10),(891,780,5)])
    ]
    for name,col,dep,controls in curls:sweep(name,controls,GLASS[col],dep,.40)
    # Clear elliptical contact base, seated on the floor.
    ellipse_ring('Base · outer crystal ring',(.004,0,.0071),.064,.032,.0055,clear)
    ellipse_ring('Base · lower blue ring',(.005,0,.0059),.053,.027,.0049,ice,.4)
    ellipse_ring('Base · upper opal ring',(.007,.002,.0118),.051,.026,.0046,clear,1)
    sphere('Base · solid polished lens',(.006,.002,.00585),.020,clear,'Glass_Base',(2.80,1.48,.30))


def droplets():
    stems=[
        ('front-left large pearl',[(401,933,11),(329,814,10),(238,683,8)],'clear',-5,31),
        ('left small pearl',[(325,882,7),(223,812,6),(120,729,3)],'clear',35,19),
        ('left sapphire pearl',[(414,937,8),(370,829,7),(335,722,4)],'blue',18,17),
        ('left oval pearl',[(486,976,12),(426,889,10),(387,785,8)],'ice',8,23),
        ('lower sky pearl',[(557,984,6),(518,897,7),(487,808,5)],'aqua',62,20),
        ('lower clear pearl',[(652,989,5),(607,902,5),(574,791,4)],'clear',69,17),
        ('inner sapphire pearl',[(852,946,8),(907,844,13),(937,745,13),(941,663,10),(925,587,5)],'blue',-61,27),
        ('middle crystal pearl',[(981,873,17),(1014,756,21),(1030,646,20),(1022,537,14),(1004,431,5)],'aqua',-70,26),
        ('upper clear pearl',[(1073,740,21),(1112,605,22),(1094,483,19),(1065,407,17),(1028,350,8)],'ice',-3,32),
        ('middle blue pearl',[(1023,851,15),(1067,735,16),(1090,624,13),(1083,533,4)],'blue',-20,22),
        ('low clear pearl',[(936,936,14),(945,838,14),(915,759,13),(863,716,5)],'ice',38,23),
        ('right highest pearl',[(1167,465,4),(1188,319,5),(1179,121,3)],'clear',62,17),
        ('right high pearl',[(1165,593,4),(1190,414,5),(1199,232,3)],'clear',69,13),
        ('right high sky pearl',[(1133,715,4),(1190,559,4),(1211,314,3)],'ice',82,12),
        ('right clear fine pearl',[(1122,794,4),(1197,579,4),(1227,366,3)],'clear',83,10),
        ('right lateral pearl',[(1042,852,6),(1140,688,7),(1211,610,4)],'clear',80,23),
        ('right low pearl',[(999,1019,6),(1065,963,7),(1136,892,4)],'ice',28,24)
    ]
    for label,controls,col,dep,radius in stems:
        obj=sweep('Droplet stem · '+label,controls,GLASS[col],dep,.62,collection='Embellishments')
        obj['droplet_stem']=True
        x,y=controls[-1][:2]
        bead=sphere('Droplet · '+label,P(x,y,dep),radius*S,GLASS[col])
        bead['droplet']=True
    for x,y,r,col,d in [(990,162,11,'aqua',27),(1058,209,12,'aqua',40),(926,405,13,'clear',36),(798,726,13,'clear',50),(1008,591,14,'clear',10),(911,642,9,'clear',38),(620,845,9,'clear',72),(548,900,11,'clear',49),(756,779,10,'clear',-25),(893,650,5,'clear',82)]:
        sphere('Suspended pearl',P(x,y,d),r*S,GLASS[col])


def studio():
    mat=basic_material('Silver-grey studio cyclorama',(.72,.73,.76),.25)
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Coat Weight'].default_value=.12
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    geometry=nodes.new('ShaderNodeNewGeometry')
    height=nodes.new('ShaderNodeSeparateXYZ')
    gradient=nodes.new('ShaderNodeMapRange')
    gradient.inputs['From Min'].default_value=0
    gradient.inputs['From Max'].default_value=.09
    gradient.clamp=True
    mix=nodes.new('ShaderNodeMixRGB')
    mix.inputs[1].default_value=(*[linear(v) for v in (.72,.73,.76)],1)
    mix.inputs[2].default_value=(*[linear(v) for v in (.47,.48,.50)],1)
    links.new(geometry.outputs['Position'],height.inputs[0])
    links.new(height.outputs['Z'],gradient.inputs['Value'])
    links.new(gradient.outputs['Result'],mix.inputs[0])
    links.new(mix.outputs[0],bsdf.inputs['Base Color'])
    profile=[(-3,0),(.32,0),(.40,.01),(.48,.04),(.55,.10),(.60,.18),(.63,.29),(.64,.5),(.64,2)]
    verts=[(x,y,z-.00015) for x in [-3,3] for y,z in profile]
    n=len(profile)
    floor=mesh('Studio · seamless curved floor',verts,[(i,n+i,n+i+1,i+1) for i in range(n-1)],mat,'Studio',False)
    floor.cycles.is_caustics_receiver=True
    area('Studio · warm left softbox',(-.30,-.35,.46),(0,0,.15),8,.21,(1,.90,.80),.52)
    area('Studio · cool right strip',(.31,-.11,.35),(.05,0,.16),12,.10,(.76,.87,1),.42)
    area('Studio · top white wash',(-.04,.12,.54),(0,0,.10),13,.30,(1,1,1),.24)
    area('Studio · transmitted caustic source',(.12,.22,.43),(.01,0,.11),7,.032,(1,.94,.84),caustics=True)
    black=basic_material('Black photographic reflection cards',(.008,.009,.012),.85)
    cards=[
        ('left',[(-.27,-.42,0),(-.27,.25,0),(-.27,.25,.50),(-.27,-.42,.50)]),
        ('right',[(.29,-.35,0),(.29,-.35,.50),(.29,.25,.50),(.29,.25,0)]),
        ('front',[(-.19,-.62,.02),(.19,-.62,.02),(.19,-.62,.46),(-.19,-.62,.46)])
    ]
    for name,verts in cards:
        card=mesh('Studio · '+name+' reflection card',verts,[(0,1,2,3)],black,'Studio',False)
        card.visible_camera=False
        card.visible_shadow=False
        card.visible_diffuse=False
        card.visible_transmission=False
    camera('Camera · main',(0,-1.05,.315),(0,0,.141),lens=113)
    camera('Camera · side',(.48,-.64,.29),(0,0,.15),ortho=.395)
    camera('Camera · rear',(-.38,.37,.33),(0,0,.15),ortho=.41)
    camera('Camera · top',(.015,-.47,.62),(0,0,.14),ortho=.405)
    scene=bpy.context.scene
    scene.camera=bpy.data.objects['Camera · main']
    scene.render.filepath='//renders/final.png'


def build():
    RNG.seed(5534)
    clear_scene()
    settings('sculpture')
    make_materials()
    wave()
    print('SCULPTURE_WAVE_COMPLETE',flush=True)
    droplets()
    butterfly()
    # Concentrate the caustic solver on the wave and droplets. Wing reflections
    # still use full path tracing; the floor receives the coloured wave caustics.
    for obj in bpy.context.scene.objects:
        if obj.get('glass') and obj.get('butterfly_component'):
            obj.cycles.is_caustics_caster=False
    print('SCULPTURE_BUTTERFLIES_COMPLETE',flush=True)
    studio()
    reference_guides(['glass_sculpture_target.png','glass_sculpture_angles.png'])
    scene=bpy.context.scene
    scene['artwork_height_m']=.30
    scene['description']='Four coloured-glass butterflies; swept blue/clear wave, spiral crest, droplets and a floor-contact glass base.'
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active=None
