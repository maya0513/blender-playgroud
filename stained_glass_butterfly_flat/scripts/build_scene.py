"""Build the complete flat design from traced panes and raised dark leading."""
import json
import random

import bmesh
import bpy

from common import ROOT, clear_scene, settings, group, basic_material, glass_material, weld_normals, mesh, camera, area, reference_guides

PIXEL = .30/740


def traced_part(part,name,material,collection,thickness,bevel,glass):
    data = bpy.data.curves.new(name,'CURVE')
    data.dimensions = '2D'
    data.resolution_u = 2
    data.fill_mode = 'BOTH'
    data.extrude = thickness/2
    data.bevel_depth = 0 if glass else bevel
    data.bevel_resolution = 1
    for contour in part['contours']:
        if glass and -160 < contour['area_pixels'] < 0:
            # Dark speckles are raised leading above continuous glass, not drilled holes.
            continue
        spline = data.splines.new('BEZIER')
        spline.bezier_points.add(len(contour['points'])-1)
        spline.use_cyclic_u = True
        for p,(x,y) in zip(spline.bezier_points,contour['points']):
            p.co = ((x-512)*PIXEL,(512-y)*PIXEL,0)
            p.handle_left_type = p.handle_right_type = 'VECTOR' if glass else 'AUTO'
    obj = bpy.data.objects.new(name,data)
    group(collection).objects.link(obj)
    data.materials.append(material)
    obj.location.z = .004 if glass else .00412
    obj['traced_region'] = part['id']
    obj['pixel_area'] = part['pixel_count']
    obj['editable_bezier_contours'] = len(part['contours'])
    # Keep the original editable paths in a hidden modelling collection.
    source = obj.copy()
    source.data = data.copy()
    group('Editable_Contours').objects.link(source)
    source.name = 'Path · '+name
    source.hide_render = source.hide_viewport = True
    if glass:
        obj['glass'] = True
        obj.cycles.is_caustics_caster = True
        obj['nominal_thickness_m'] = thickness
    return obj


def leading_part(part,name,mat):
    """A grid skin prevents self-touching outline loops filling entire panes."""
    cells={(x,y) for y,x0,x1 in part['pixel_runs'] for x in range(x0,x1)}
    verts,faces,lookup=[],[],{}
    def vertex(x,y,side):
        key=(x,y,side)
        if key not in lookup:
            lookup[key]=len(verts)
            verts.append(((x-512)*PIXEL,(512-y)*PIXEL,.00412+side*.00115))
        return lookup[key]
    for x,y in cells:
        corners=[(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
        top=[vertex(a,b,1) for a,b in corners]
        bottom=[vertex(a,b,-1) for a,b in corners]
        faces.append(tuple(reversed(top)))
        faces.append(tuple(bottom))
        for k,neighbor in enumerate([(x,y-1),(x+1,y),(x,y+1),(x-1,y)]):
            if neighbor not in cells:
                j=(k+1)%4
                faces.append((top[k],top[j],bottom[j],bottom[k]))
    obj=mesh(name,verts,faces,mat,'Leading',False)
    weld_normals(obj)
    for face in obj.data.polygons:face.use_smooth=False
    obj['traced_region']=part['id']
    obj['construction']='Closed extruded skin of the traced dark contour mask'
    curve=traced_part(part,name+' curve',mat,'Leading',.0023,.000032,False)
    data=curve.data
    bpy.data.objects.remove(curve,do_unlink=True)
    bpy.data.curves.remove(data)
    return obj


def build():
    clear_scene()
    settings('flat')
    bpy.context.scene.view_settings.view_transform='Standard'
    bpy.context.scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.15
    design = json.loads((ROOT/'scripts/traced_design.json').read_text())
    leading = basic_material('Dark plum · raised metal leading',(.105,.073,.115),.28,.32)
    for i,part in enumerate(design['panes']):
        color = part['color_srgb']
        mat = glass_material(f'Pane tint {i:03d}',color,.055,2,glitter=part['pixel_count']>180,flat=True)
        obj = traced_part(part,f'Glass pane {i:03d}',mat,'Glass_Panes',.002,.000075,True)
        obj['source_bounds_pixels'] = part['bounds']
    for i,part in enumerate(design['leading']):
        leading_part(part,f'Leading component {i:03d}',leading)
    # Convert in one batch; repeated scene evaluation for each pane is costly.
    parts=[o for o in bpy.context.scene.objects if o.type=='CURVE' and not o.hide_render]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.convert(target='MESH')
    for obj in parts:
        weld_normals(obj)
        for face in obj.data.polygons:face.use_smooth=True
        if obj.get('glass'):
            bm=bmesh.new()
            bm.from_mesh(obj.data)
            pinched=any(not e.is_manifold for e in bm.edges)
            bm.free()
            if pinched:
                # Pixel contours occasionally meet at a point. Resolve those
                # contacts into a closed glass volume at subpixel precision.
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active=obj
                repair=obj.modifiers.new('Resolve point contacts in traced contours','REMESH')
                repair.mode='VOXEL'
                repair.voxel_size=.00016
                repair.use_smooth_shade=True
                bpy.ops.object.modifier_apply(modifier=repair.name)
                weld_normals(obj)
                obj['subpixel_topology_repair_m']=.00016
            edge=obj.modifiers.new('Polished rounded pane edges','BEVEL')
            edge.width=.000075
            edge.segments=2
            edge.use_clamp_overlap=True
            obj.modifiers.new('Even pane normals','WEIGHTED_NORMAL')
    sparkle=basic_material('Fine pearl inclusions in the colour glass',(.99,.99,1),.12,.90)
    sp=sparkle.node_tree.nodes.get('Principled BSDF')
    sp.inputs['Coat Weight'].default_value=.4
    sp.inputs['Emission Color'].default_value=(1,1,1,1)
    sp.inputs['Emission Strength'].default_value=.10
    verts,faces=[],[]
    for pane in design['panes']:
        for x,y,r in pane.get('glints',[]):
            k=len(verts)
            center=((x-512)*PIXEL,(512-y)*PIXEL,.00505)
            radius=r*PIXEL
            for dx,dy,dz in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
                verts.append((center[0]+dx*radius,center[1]+dy*radius,center[2]+dz*radius*.30))
            faces.extend([tuple(k+j for j in f) for f in [(0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)]])
    if verts:
        specks=mesh('Minute pearl glints in the glass',verts,faces,sparkle,'Embellishments',False)
        specks['inclusion_count']=len(verts)//6
    white = basic_material('White studio paper',(.975,.978,.98),.8)
    paper=white.node_tree.nodes.get('Principled BSDF')
    paper.inputs['Emission Color'].default_value=(1,1,1,1)
    paper.inputs['Emission Strength'].default_value=.80
    floor = mesh('White background',[(-2,-2,-.006),(2,-2,-.006),(2,2,-.006),(-2,2,-.006)],[(0,1,2,3)],white,'Studio',False)
    floor.cycles.is_caustics_receiver = True
    # Gentle, broad lighting preserves the drawing's pale glass colours.
    area('Large white softbox',(-.12,-.08,.65),(0,0,0),.8,.70,caustics=True)
    area('Soft upper edge',(.2,.25,.40),(0,0,0),.3,.40)
    main = camera('Camera · main',(0,0,.85),(0,0,0),ortho=1024*PIXEL)
    camera('Camera · oblique',(.40,-.35,.52),(0,0,0),ortho=.48)
    scene = bpy.context.scene
    scene.camera = main
    scene['source_sha256'] = design['source_sha256']
    scene['pane_count'] = len(design['panes'])
    scene['leading_component_count'] = len(design['leading'])
    scene['inclusion_count']=len(verts)//6
    scene['artwork_height_m'] = .30
    scene['description'] = 'Complete traced butterfly, scroll, droplets and satellite butterflies; individually editable 2 mm glass panes.'
    scene.render.filepath = '//renders/final.png'
    reference_guides(['IMG_5534.JPG'])
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None
    print('FLAT_GEOMETRY',json.dumps({'panes':len(design['panes']),'leading':len(design['leading'])}),flush=True)
