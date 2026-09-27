"""Photo comparison refinements, also applied by build_scene.py before saving."""
import bpy, math, random
from mathutils import Matrix, Vector

REVISION='photo-review-6'
def refine():
    s=bpy.context.scene
    if s.get('photo_review_revision')==REVISION:return
    if s.get('photo_review_revision'):raise RuntimeError('Rebuild from build_scene.py before applying a different refinement revision')
    bpy.context.view_layer.update()
    # Auxiliary lamps provide fill on structures, but must not draw a source-plane
    # intersection across the river. Sun/world continue to illuminate the water.
    receivers=bpy.data.collections.new('Fill receivers excluding water')
    for c in s.collection.children:
        if not c.name.startswith('06 '):receivers.children.link(c)
    for o in s.objects:
        if o.type=='LIGHT' and o.data.type=='AREA':o.light_linking.receiver_collection=receivers

    # Match the near path edges without changing the camera's vanishing direction.
    path=bpy.data.objects['Continuous walkway'];path.location.x-=.12;path.scale.x=1.10
    for o in bpy.data.collections['02 · Seaward handrail and green net'].objects:o.location+=Vector((-.24,.4,-.03))
    for name in ['Retaining wall','Rounded coping']:
        bpy.data.objects[name].location.x-=.38
    for o in bpy.data.collections['03 · White boundary fence'].objects:
        # Lower the fence above its mounting line and follow the wall sideways.
        T=Matrix.Translation((-.38,0,1.87)) @ Matrix.Diagonal((1,1,.86,1)) @ Matrix.Translation((0,0,-1.87))
        o.matrix_world=T @ o.matrix_world
    debris=bpy.data.objects['Fallen leaves along edge']
    for v in debris.data.vertices:
        v.co.x-=.38
    # Smaller, irregular debris is subordinate to the asphalt surface.
    for poly in debris.data.polygons:
        centre=sum((debris.data.vertices[i].co for i in poly.vertices),Vector())/len(poly.vertices)
        for i in poly.vertices:debris.data.vertices[i].co=centre+(debris.data.vertices[i].co-centre)*.55

    # The bridge silhouette rises slightly at the left edge in the photograph.
    shear=Matrix.Identity(4);shear[2][0]=-.032
    for prefix in ['04 · Bridge plate girders and bracing','05 · Bridge services and maintenance rails']:
        for o in bpy.data.collections[prefix].objects:
            # Bake the affine transform into geometry. Object decomposition loses shear
            # and separates pipes from their couplings.
            local=o.matrix_world.inverted() @ shear @ o.matrix_world
            if o.type=='MESH':
                for v in o.data.vertices:v.co=local @ v.co
            elif o.type=='CURVE':
                for sp in o.data.splines:
                    for p in sp.points:p.co=(* (local @ Vector(p.co[:3])),1)

    for o in bpy.data.collections['08 · Foreground pine and broadleaf canopy'].objects:
        pine=o.name.startswith(('Pine','Individual pine'))
        if pine:o.hide_render=True;o.hide_viewport=True
        else:o.location+=Vector((-.8,0,-.3))
    make_photo_pine()

    # Blue atmospheric mountain, with its summit hidden behind the bridge.
    for m in bpy.data.materials:
        if m.name.startswith('Hazy mountain layer'):
            ramp=m.node_tree.nodes.get('Color Ramp')
            for e in ramp.color_ramp.elements:
                c=e.color;e.color=(c[0]*.47,c[1]*.58,c[2]*.78,1)
    # Far vegetation receives a warmer, brighter leaf treatment than shaded foreground.
    copies={}
    for o in bpy.data.collections['09 · Opposite planting and palms'].objects:
        if o.type!='MESH':continue
        for slot in o.material_slots:
            m=slot.material
            if m and m.name.startswith('Broadleaf green'):
                if m.name not in copies:
                    mm=m.copy();mm.name='Sunlit opposite '+m.name
                    b=mm.node_tree.nodes.get('Principled BSDF');c=b.inputs['Base Color'].default_value
                    b.inputs['Base Color'].default_value=(c[0]*1.7,c[1]*1.55,c[2]*1.3,1);copies[m.name]=mm
                slot.material=copies[m.name]
    # Soften the overly clean white enamel and thin its welded wires.
    m=bpy.data.materials['White fence · worn enamel'];b=m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value=(.47,.49,.45,1);b.inputs['Roughness'].default_value=.66
    for o in bpy.data.collections['03 · White boundary fence'].objects:
        if o.type=='CURVE':o.data.bevel_depth*=.37
    # Net has unequal sag, instead of a taut, perfectly periodic grid.
    for o in bpy.data.collections['02 · Seaward handrail and green net'].objects:
        if not o.name.startswith('Net mesh panel'):continue
        for spline in o.data.splines:
            for p in spline.points:
                y=p.co.y
                p.co.x+=.018*math.sin(y*1.9)+.012*math.sin(y*5.3)
                p.co.z+=.012*math.sin(y*3.1)
    # Neutral warm grey bridge under shade, rather than pale blue steel.
    for name in ['Bridge · warm grey weathered paint','Bridge · pale coated edges']:
        ramp=bpy.data.materials[name].node_tree.nodes.get('Color Ramp')
        for e in ramp.color_ramp.elements:
            c=e.color;e.color=(c[0]*.74,c[1]*.70,c[2]*.67,1)
    ramp=bpy.data.materials['Walkway · weathered asphalt aggregate'].node_tree.nodes.get('Color Ramp')
    for e in ramp.color_ramp.elements:
        c=e.color;e.color=(c[0],c[1]*1.04,c[2]*1.18,1)
    # Match water colour without the former large artificial fill reflection.
    water=bpy.data.materials['Blue green rippled water']
    water.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.39,.45,.49,1)
    for node in s.world.node_tree.nodes:
        if node.bl_idname=='ShaderNodeMath' and node.operation=='MULTIPLY_ADD':node.inputs[1].default_value=1.2
    q=bpy.data.materials['Opposite quay · curved weathered concrete'].node_tree.nodes.get('Color Ramp')
    for e in q.color_ramp.elements:
        c=e.color;e.color=(c[0]*.77,c[1]*.76,c[2]*.73,1)
    refine_left_bank()
    make_near_bank_sediment()
    s['photo_review_revision']=REVISION
    bpy.context.view_layer.update()

def make_photo_pine():
    """Curved branches and individual needles fitted to the photographed silhouette."""
    c=bpy.data.collections['08 · Foreground pine and broadleaf canopy']
    rng=random.Random(16948)
    cam=bpy.context.scene.camera
    def point(u,v,depth):
        ray=cam.rotation_euler.to_quaternion() @ Vector(((u-.5)*36/26,(.5-v)*36/26,-1))
        return cam.location+ray*((depth-cam.location.y)/ray.y)
    def mesh(name,vs,fs,mat):
        d=bpy.data.meshes.new(name);d.from_pydata(vs,[],fs);d.update()
        o=bpy.data.objects.new(name,d);c.objects.link(o);d.materials.append(mat);return o
    def branch(name,pts,radius):
        vs=[];fs=[]
        for j,p in enumerate(pts):
            direction=(pts[min(j+1,len(pts)-1)]-pts[max(j-1,0)]).normalized()
            u=direction.cross(Vector((0,1,0))).normalized();v=direction.cross(u).normalized()
            r=max(.002,radius*(1-j/(len(pts)-1))**.8)
            vs.extend(p+r*(u*math.cos(k*math.tau/7)+v*math.sin(k*math.tau/7)) for k in range(7))
            if j:
                for k in range(7):fs.append(((j-1)*7+k,(j-1)*7+(k+1)%7,j*7+(k+1)%7,j*7+k))
        ob=mesh(name,vs,fs,bpy.data.materials['Tree bark · fissures'])
        for f in ob.data.polygons:f.use_smooth=True
    needle_vs=[];needle_fs=[];needle_mi=[]
    def spray(center,direction):
        d=direction.normalized();u=d.cross(Vector((0,1,0))).normalized();v=d.cross(u)
        for k in range(60):
            angle=rng.random()*math.tau
            root=center+d*rng.uniform(-.10,.09)
            outward=u*math.cos(angle)+v*math.sin(angle)
            end=root+(outward*.8+d*.55)*rng.uniform(.12,.26)
            side=(end-root).cross(Vector((0,1,0))).normalized()*.006
            i=len(needle_vs);needle_vs.extend([root-side,root+side,end]);needle_fs.append((i,i+1,i+2));needle_mi.append(rng.randrange(3))
    # Asymmetric fans reach left and droop towards the channel.
    ends=[(.43,.351),(.49,.374),(.56,.394),(.62,.420),(.68,.450),(.71,.484),(.77,.498),(.81,.452),(.58,.361)]
    ends += [(u+rng.uniform(-.025,.025),v+rng.uniform(-.012,.020)) for u,v in list(ends)]
    for j,(u,v) in enumerate(ends):
        start=point(.92,.315+(j%9)*.009,23+j*.17);end=point(u,v,22+rng.uniform(-2,2))
        pts=[]
        for k in range(13):
            t=k/12;p=start.lerp(end,t);p.z-=math.sin(t*math.pi)*rng.uniform(.13,.28);p.y+=math.sin(t*math.pi)*.4;pts.append(p)
        branch('Photo pine curved bough',pts,.065 if j<5 else .042)
        for k in range(4,29):
            t=(k+rng.uniform(-.45,.45))/30;centre=pts[min(11,int(t*12))].lerp(pts[min(12,int(t*12)+1)],(t*12)%1)
            d=Vector((rng.uniform(-.8,.2),rng.uniform(-.8,.8),rng.uniform(-.25,.55)))
            tip=centre+d*1.35
            branch('Photo pine fine twig',[centre,centre.lerp(tip,.5)+Vector((0,0,.08)),tip],.009)
            for q in range(9):
                out=Vector((rng.uniform(-.3,.3),rng.uniform(-.3,.3),rng.uniform(.08,.3)))
                spray(centre.lerp(tip,rng.uniform(.2,1.1))+out*.8,out)
    ob=mesh('Photo pine individual needle fans',needle_vs,needle_fs,bpy.data.materials['Pine needles 00'])
    for i in [1,2]:ob.data.materials.append(bpy.data.materials['Pine needles %02d'%i])
    for f,idx in zip(ob.data.polygons,needle_mi):f.material_index=idx

def refine_left_bank():
    """Layer irregular mineral wear, runoff and algae; fit the visible facade."""
    mat=bpy.data.materials['Opposite quay · curved weathered concrete']
    n=mat.node_tree.nodes;l=mat.node_tree.links;b=n.get('Principled BSDF')
    source=b.inputs['Base Color'].links[0].from_socket
    geo=n.new('ShaderNodeNewGeometry')
    def noise(name,stretch,scale):
        vec=n.new('ShaderNodeVectorMath');vec.operation='MULTIPLY';vec.inputs[1].default_value=stretch;l.new(geo.outputs['Position'],vec.inputs[0])
        no=n.new('ShaderNodeTexNoise');no.name=name;no.inputs['Scale'].default_value=scale;no.inputs['Detail'].default_value=4;no.inputs['Roughness'].default_value=.72;l.new(vec.outputs[0],no.inputs['Vector']);return no.outputs['Fac']
    def ramp(name,socket,stops):
        r=n.new('ShaderNodeValToRGB');r.name=name
        for e in list(r.color_ramp.elements)[1:]:r.color_ramp.elements.remove(e)
        for i,(p,c) in enumerate(stops):
            e=r.color_ramp.elements[0] if not i else r.color_ramp.elements.new(p);e.position=p;e.color=(*c,1)
        l.new(socket,r.inputs[0]);return r.outputs[0]
    def blend(name,base,factor,color):
        m=n.new('ShaderNodeMixRGB');m.name=name;l.new(base,m.inputs[1]);l.new(factor,m.inputs[0]);m.inputs[2].default_value=(*color,1);return m.outputs[0]
    patch=noise('Quay irregular algae colonies',(1,.32,.65),1)
    mask=ramp('Quay algae coverage',patch,[(.35,(0,0,0)),(.49,(.24,.24,.24)),(.65,(.78,.78,.78))])
    source=blend('Quay green grey algae',source,mask,(.065,.085,.057))
    streak=noise('Quay vertical runoff',(1,1.2,.045),1)
    mask=ramp('Quay runoff coverage',streak,[(.35,(0,0,0)),(.51,(.28,.28,.28)),(.65,(.84,.84,.84))])
    source=blend('Quay dark runoff',source,mask,(.038,.045,.039))
    wear=noise('Quay irregular mineral wear',(1,.42,1.8),.8)
    mask=ramp('Quay pale wear coverage',wear,[(.42,(0,0,0)),(.65,(.27,.27,.27)),(.8,(.48,.48,.48))])
    source=blend('Quay pale mineral scuffs',source,mask,(.40,.40,.36));l.new(source,b.inputs['Base Color'])
    # Replace the generic roof block with the small visible orange/white facade.
    for name in ['Partially hidden distant building','Low terracotta roof']:
        ob=bpy.data.objects.get(name)
        if ob:bpy.data.objects.remove(ob,do_unlink=True)
    c=bpy.data.collections['09 · Opposite planting and palms'];cam=bpy.context.scene.camera
    def material(name,color):
        m=bpy.data.materials.new(name);m.use_nodes=True
        bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.83;return m
    # A small dip in the crown reveals the facade, as in the photograph.
    # Smoothly deform only the foliage/branches in front of this narrow opening.
    from bpy_extras.object_utils import world_to_camera_view
    bpy.context.view_layer.update()
    for ob in c.objects:
        if ob.type!='MESH':continue
        inv=ob.matrix_world.inverted()
        # Leaf-cloud leaves each use five vertices. Translate each leaf rigidly
        # to preserve its silhouette and normal instead of stretching its surface.
        leaf_cloud=('individual leaves' in ob.name or 'understory' in ob.name)
        step=5 if leaf_cloud else 1
        for first in range(0,len(ob.data.vertices),step):
            verts=list(ob.data.vertices[first:first+step])
            center=sum((v.co for v in verts),Vector())/len(verts)
            world=ob.matrix_world @ center
            uv=world_to_camera_view(bpy.context.scene,cam,world)
            u=uv.x;v=1-uv.y
            if .09<u<.19 and .32<v<.435:
                weight=math.exp(-((u-.141)/.029)**4)
                fade=max(0,min(1,(.435-v)/.045))
                target_v=v+.031*weight*fade
                ray=cam.rotation_euler.to_quaternion() @ Vector(((u-.5)*36/26,(.5-target_v)*36/26,-1))
                target=inv @ (cam.location+ray*((world.x-cam.location.x)/ray.x))
                delta=target-center
                for vert in verts:vert.co+=delta
    orange=material('Distant facade muted orange',(.43,.19,.095))
    white=material('Distant facade warm white',(.73,.72,.66))
    def point(u,v,x):
        ray=cam.rotation_euler.to_quaternion() @ Vector(((u-.5)*36/26,(.5-v)*36/26,-1))
        return cam.location+ray*((x-cam.location.x)/ray.x)
    def panel(name,u0,u1,v0,v1,mat,x=-162):
        vs=[point(u,v,x) for u,v in [(u0,v0),(u1,v0),(u1,v1),(u0,v1)]]
        d=bpy.data.meshes.new(name);d.from_pydata(vs,[],[(0,1,2,3)]);d.materials.append(mat)
        o=bpy.data.objects.new(name,d);c.objects.link(o)
        solid=o.modifiers.new('Facade thickness','SOLIDIFY');solid.thickness=.35;return o
    panel('Orange facade behind left planting',.103,.147,.341,.397,orange)
    panel('White facade behind left planting',.147,.177,.341,.391,white)
    for j,u in enumerate([.112,.132,.148,.162,.175]):
        panel('White facade vertical trim %02d'%j,u,u+.0025,.341,.394,white,-161.5)
    panel('White facade horizontal trim',.103,.147,.367,.369,white,-161.5)

def make_near_bank_sediment():
    """Low, irregular sediment tongue fitted to the photographed near shoreline."""
    c=bpy.data.collections['01 · Walkway and retaining wall']
    cam=bpy.context.scene.camera
    def ground_point(u,v,z=0):
        ray=cam.rotation_euler.to_quaternion() @ Vector(((u-.5)*36/26,(.5-v)*36/26,-1))
        return cam.location+ray*((z-cam.location.z)/ray.z)
    # Measured visible WATERLINE, not the submerged outer edge of the mesh.
    image_edge=[(.612,.727),(.605,.710),(.590,.694),(.572,.680),
                (.557,.667),(.546,.653),(.520,.632),(.505,.615),
                (.515,.602),(.548,.587),(.580,.575),(.615,.562),
                (.650,.550),(.690,.536),(.725,.524),(.740,.519)]
    anchors=sorted((ground_point(u,v).y,ground_point(u,v).x) for u,v in image_edge)
    y_min=anchors[0][0];y_max=anchors[-1][0]
    def edge(y):
        for (a,x),(b,xx) in zip(anchors,anchors[1:]):
            if a<=y<=b:
                t=(y-a)/(b-a);t=t*t*(3-2*t)
                return x+(xx-x)*t+.045*math.sin(y*4.3)+.025*math.sin(y*10.1)
        return -.20
    vs=[];faces=[];ny=260;nx=48
    for j in range(ny+1):
        y=y_min+(y_max-y_min)*j/ny
        coast=min(-.24,edge(y));outside=coast-.35
        for i in range(nx+1):
            t=i/nx;x=outside+(.12-outside)*t
            # The zero-height contour follows the traced line exactly.
            d=x-coast;z=max(-.12,min(.105,d*.36))
            fade=max(0,min(1,d/.35))
            z+=(.014*math.sin(y*3.4+x*4.1)+.008*math.sin(y*8.1-x*11))*fade
            vs.append((x,y,z))
    for j in range(ny):
        for i in range(nx):
            k=j*(nx+1)+i;faces.append((k,k+1,k+nx+2,k+nx+1))
    d=bpy.data.meshes.new('Near-bank sediment terrain');d.from_pydata(vs,[],faces);d.update()
    o=bpy.data.objects.new('Near-bank exposed sediment',d);c.objects.link(o)
    for f in d.polygons:f.use_smooth=True
    m=bpy.data.materials.new('Sediment · mottled sand and wet mud');m.use_nodes=True;d.materials.append(m)
    n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF');b.inputs['Roughness'].default_value=.92
    geo=n.new('ShaderNodeNewGeometry');sep=n.new('ShaderNodeSeparateXYZ');l.new(geo.outputs['Position'],sep.inputs[0])
    noise=n.new('ShaderNodeTexNoise');noise.name='Sediment uneven mineral colour';noise.inputs['Scale'].default_value=12;noise.inputs['Detail'].default_value=5;l.new(geo.outputs['Position'],noise.inputs['Vector'])
    color=n.new('ShaderNodeValToRGB');color.color_ramp.elements[0].color=(.22,.16,.09,1);color.color_ramp.elements[1].color=(.46,.37,.23,1);l.new(noise.outputs['Fac'],color.inputs[0])
    wet=n.new('ShaderNodeMapRange');wet.name='Sediment wet shoreline';wet.inputs['From Min'].default_value=.005;wet.inputs['From Max'].default_value=.085;wet.inputs['To Min'].default_value=1;wet.inputs['To Max'].default_value=0;l.new(sep.outputs['Z'],wet.inputs['Value'])
    mix=n.new('ShaderNodeMixRGB');mix.name='Dark damp river margin';l.new(wet.outputs[0],mix.inputs[0]);l.new(color.outputs[0],mix.inputs[1]);mix.inputs[2].default_value=(.055,.051,.035,1);l.new(mix.outputs[0],b.inputs['Base Color'])
    grain=n.new('ShaderNodeTexNoise');grain.name='Sediment fine grains';grain.inputs['Scale'].default_value=180;grain.inputs['Detail'].default_value=2;l.new(geo.outputs['Position'],grain.inputs['Vector'])
    fleck=n.new('ShaderNodeValToRGB');fleck.color_ramp.elements[0].color=(.4,.38,.34,1);fleck.color_ramp.elements[1].color=(1.2,1.15,1.05,1);l.new(grain.outputs['Fac'],fleck.inputs[0])
    grain_color=n.new('ShaderNodeMixRGB');grain_color.blend_type='MULTIPLY';grain_color.inputs[0].default_value=.55;l.new(mix.outputs[0],grain_color.inputs[1]);l.new(fleck.outputs[0],grain_color.inputs[2]);l.new(grain_color.outputs[0],b.inputs['Base Color'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.38;bump.inputs['Distance'].default_value=.015;l.new(grain.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],b.inputs['Normal'])
    o['reference']='Exposed brown-grey sediment beside the mid-distance net fence'
    o['water_level']=0.0
    # Reproducible clustered leaf litter, with individual curled leaf geometry.
    from mathutils.bvhtree import BVHTree
    from bpy_extras.object_utils import world_to_camera_view
    terrain=BVHTree.FromPolygons([Vector(v) for v in vs],faces)
    rng=random.Random(694806)
    palette=[(.42,.28,.105),(.65,.48,.24),(.18,.11,.045),(.34,.20,.07),(.52,.38,.17)]
    mats=[]
    for j,col in enumerate(palette):
        mat=bpy.data.materials.new('Sediment dry leaf %02d'%j);mat.use_nodes=True
        bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*col,1);bs.inputs['Roughness'].default_value=.88;mats.append(mat)
    lv=[];lf=[];indices=[];placed=0
    # Discrete dense patches among lighter scatter; coordinates refer to the photo.
    clusters=[(.567,.610,.037,.020),(.626,.615,.027,.027),(.611,.673,.024,.023),(.681,.554,.025,.018)]
    for attempt in range(45000):
        if placed>=1700:break
        y=rng.uniform(y_min+.3,y_max-.3);coast=min(-.24,edge(y));x=rng.uniform(coast+.15,-.22)
        loc,normal,idx,dist=terrain.ray_cast(Vector((x,y,1)),Vector((0,0,-1)),2)
        if loc is None or loc.z<.04:continue
        uv=world_to_camera_view(bpy.context.scene,cam,loc);u=uv.x;v=1-uv.y
        weight=.055+sum(.70*math.exp(-((u-a)/su)**2-((v-b)/sv)**2) for a,b,su,sv in clusters)
        if rng.random()>min(.95,weight):continue
        angle=rng.random()*math.tau;length=rng.uniform(.075,.19);width=length*rng.uniform(.30,.53)
        axis=Vector((math.cos(angle),math.sin(angle),0));side=Vector((-axis.y,axis.x,0))
        curl=rng.uniform(.003,.012);start=len(lv)
        # Tip, three cross-sections with a central vein, and opposite tip.
        profile=[(-.5,0),(-.25,-.36),(-.25,0),(-.25,.36),(0,-.5),(0,0),(0,.5),(.25,-.32),(.25,0),(.25,.32),(.5,0)]
        points=[]
        for along,across in profile:
            p=loc+axis*(along*length)+side*(across*width)
            hit,_,_,_=terrain.ray_cast(Vector((p.x,p.y,1)),Vector((0,0,-1)),2)
            if hit is None:break
            p.z=hit.z+.002+curl*(2*abs(along))**2+.004*abs(across);points.append(p)
        if len(points)!=11:continue
        lv.extend(points)
        faces_leaf=[(0,2,1),(0,3,2),(1,2,5,4),(2,3,6,5),(4,5,8,7),(5,6,9,8),(7,8,10),(8,9,10)]
        mat_index=rng.choices(range(5),[3,2,2,3,2])[0]
        for face in faces_leaf:lf.append(tuple(start+i for i in face));indices.append(mat_index)
        placed+=1
    ld=bpy.data.meshes.new('Individual curled dry leaves on sediment');ld.from_pydata(lv,[],lf);ld.update()
    leaves=bpy.data.objects.new('Dry leaves on sediment',ld);c.objects.link(leaves)
    for mat in mats:ld.materials.append(mat)
    for poly,mi in zip(ld.polygons,indices):poly.material_index=mi
    leaves['leaf_count']=placed;leaves['seed']=694806

if __name__=='__main__':
    refine()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
