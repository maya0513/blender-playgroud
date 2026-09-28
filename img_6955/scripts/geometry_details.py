"""Small real geometry for near-field silhouettes; deterministic, no billboards."""
import math
import random
import bpy


def add_details(scene, api):
    rod, mesh = api['rod'], api['mesh']
    steel, roofmat = api['steel'], api['roofmat']
    shelter_collection = api['SHELTER']
    # Rim sections follow exactly the same barrel profile as the structural roof.
    for sh in api['shelters']:
        frame = bpy.data.objects[sh['root']]
        length, width = sh['length'], sh['width']
        for end in (-1,1):
            points = [(end*length/2, -width/2+i*width/32,
                       api['roof_height'](-width/2+i*width/32,width)+.04) for i in range(33)]
            for i,(a,b) in enumerate(zip(points,points[1:])):
                o=rod(sh['root']+' rolled roof rim %d %02d'%(end,i),a,b,.043,steel,shelter_collection,8)
                o.parent=frame
        for i in range(1,8):
            y=-width/2+i*width/8
            z=api['roof_height'](y,width)+.078
            o=rod(sh['root']+' standing roof seam %02d'%i,(-length/2,y,z),(length/2,y,z),.009,roofmat,shelter_collection,6)
            o.parent=frame

    # Sub-centimeter edge highlights, keeping stair riser/tread dimensions intact.
    for o in list(scene.objects):
        if o.type != 'MESH' or o.get('geometry_kind') != 'solid' or o.name.startswith('Ferry'):
            continue
        if any(word in o.name.lower() for word in ('pavilion','viewpoint','footing','column','bench','longitudinal beam')):
            bevel=o.modifiers.new('Small real edge radius','BEVEL')
            bevel.width=.009 if 'step' in o.name.lower() else .012
            bevel.segments=2
            bevel.limit_method='ANGLE'
        if any(word in o.name for word in (' rail ', ' post ', 'rim ', 'seam ')):
            for polygon in o.data.polygons:
                if len(polygon.vertices)==4:
                    polygon.use_smooth=True

    # Sparse bent tufts rooted in the concrete/curb joint, with no soil patches.
    rng=random.Random(695504)
    vertices=[];faces=[];roots=[];joints=[]
    outline=api['outline']
    # Traverse the left boundary south -> north; right side is plaza interior.
    segments=[(outline[0],outline[-1]),(outline[-1],outline[-2]),(outline[-2],outline[-3])]
    for segment,((ax,ay),(bx,by)) in enumerate(segments):
        length=math.hypot(bx-ax,by-ay);dx=(bx-ax)/length;dy=(by-ay)/length
        nx,ny=dy,-dx
        # Inner curb edge is 0.24m from the boundary; roots occupy its narrow seam.
        joint_a=(ax+nx*.25,ay+ny*.25);joint_b=(bx+nx*.25,by+ny*.25)
        joints.append([joint_a,joint_b])
        api['beam']('Concrete joint %02d'%segment,(*joint_a,-.001),(*joint_b,-.001),.018,.008,api['black'],api['NATURE'])
        positions=[(rng.uniform(.05,.95)*length,False) for _ in range(int(length*.4))]
        # Taller groups match the sparse near, middle and far patches in the photo.
        for target_y in [12.,32.,50.]:
            if min(ay,by)<target_y<max(ay,by):
                center=(target_y-ay)/dy
                positions.extend((center+rng.uniform(-.9,.9),True) for _ in range(24))
        for along,tall in positions:
            for blade in range(rng.randint(18,32) if tall else rng.randint(6,12)):
                a=along+rng.uniform(-.11,.11);offset=.25+rng.uniform(-.005,.005)
                x=ax+dx*a+nx*offset;y=ay+dy*a+ny*offset
                z=-.003;height=rng.uniform(.28,.78) if tall else rng.uniform(.08,.3);width=rng.uniform(.004,.012)
                lean=height*rng.uniform(.65,1.5);drift=rng.uniform(-.25,.25)*height
                vx=nx*lean+dx*drift;vy=ny*lean+dy*drift
                root=(x,y,z);roots.append(root)
                # Four sections make a curved tapered ribbon; mixed planes give volume.
                angle=rng.uniform(0,math.tau);wx=math.cos(angle)*width;wy=math.sin(angle)*width
                k=len(vertices)
                for j in range(4):
                    q=j/3;w=(1-q)*.94+.06
                    cx=x+vx*(.5*q+.5*q*q);cy=y+vy*(.5*q+.5*q*q);cz=z+height*q
                    vertices.extend([(cx-wx*w,cy-wy*w,cz),(cx+wx*w,cy+wy*w,cz)])
                for j in range(3):faces.append((k+2*j,k+2*j+1,k+2*j+3,k+2*j+2))
    mesh('Concrete seam bent grass tufts',vertices,faces,api['grassmat'],api['NATURE'],'detail')
    scene['grass_manifest']=__import__('json').dumps({'roots':roots,'joints':joints,'root_tolerance_m':.012})
    # Surface scale follows the object, never the inspection camera.
    scene['surface_method']='Procedural world/object coordinates; real near-field edges; no image textures'
