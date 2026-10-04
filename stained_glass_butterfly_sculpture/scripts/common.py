"""Blender helpers: real geometry, physical glass and reproducible scene setup."""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = {}


def linear(v):
    return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj,do_unlink=True)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for blocks in (bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.cameras,bpy.data.lights,bpy.data.worlds,bpy.data.images):
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)
    COLLECTIONS.clear()
    for name in ['Glass_Panes','Leading','Embellishments','Studio','Reference_Guides']:
        group(name)


def group(name):
    if name not in COLLECTIONS:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
        COLLECTIONS[name] = col
    return COLLECTIONS[name]


def put(obj, name, collection, material=None):
    obj.name = name
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    group(collection).objects.link(obj)
    if material:
        obj.data.materials.append(material)
    return obj


def mesh(name,verts,faces,material,collection='Glass_Panes',glass=True):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces)
    data.update()
    obj = bpy.data.objects.new(name,data)
    group(collection).objects.link(obj)
    if material:
        data.materials.append(material)
    if glass:
        obj['glass'] = True
        obj.cycles.is_caustics_caster = True
    for face in data.polygons:
        face.use_smooth = True
    return obj


def weld_normals(obj, distance=1e-8):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=distance)
    wires=[e for e in bm.edges if not e.link_faces]
    if wires:
        bmesh.ops.delete(bm,geom=wires,context='EDGES')
    unused=[v for v in bm.verts if not v.link_faces]
    if unused:
        bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def basic_material(name,color,roughness=.25,metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*[linear(v) for v in color],1)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.name = 'Principled BSDF'
    output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    output.name = 'Material Output'
    mat.node_tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = mat.diffuse_color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    return mat


def glass_material(name,color,roughness=.035,density=3,glitter=False,flat=False):
    mat = basic_material(name,color,roughness)
    mat['physical_glass'] = True
    nodes,links = mat.node_tree.nodes,mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    # Two air/glass interfaces: compensate for the double transmission tint.
    tinted = [math.sqrt(linear(v)) if flat else linear(v)**.38 for v in color]
    bsdf.inputs['Base Color'].default_value = (*tinted,1)
    bsdf.inputs['Transmission Weight'].default_value = 1
    bsdf.inputs['IOR'].default_value = 1.50
    bsdf.inputs['Coat Weight'].default_value = .14
    bsdf.inputs['Coat Roughness'].default_value = .04
    if not flat:
        bsdf.inputs['Thin Film Thickness'].default_value = 120
        bsdf.inputs['Thin Film IOR'].default_value = 1.34
    absorption = nodes.new('ShaderNodeVolumeAbsorption')
    absorption.name = 'Coloured glass absorption'
    absorption.inputs['Color'].default_value = (*[linear(v) for v in color],1)
    absorption.inputs['Density'].default_value = density
    links.new(absorption.outputs['Volume'],nodes.get('Material Output').inputs['Volume'])
    if glitter:
        coord = nodes.new('ShaderNodeTexCoord')
        noise = nodes.new('ShaderNodeTexNoise')
        noise.name = 'Microscopic polished-glass grain'
        noise.inputs['Scale'].default_value = 11000 if flat else 6500
        noise.inputs['Detail'].default_value = 2
        links.new(coord.outputs['Object'],noise.inputs['Vector'])
        rough = nodes.new('ShaderNodeMapRange')
        rough.inputs['To Min'].default_value = roughness*.65
        rough.inputs['To Max'].default_value = roughness*1.65
        links.new(noise.outputs['Fac'],rough.inputs['Value'])
        links.new(rough.outputs['Result'],bsdf.inputs['Roughness'])
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .16
        bump.inputs['Distance'].default_value = .000012 if flat else .000018
        links.new(noise.outputs['Fac'],bump.inputs['Height'])
        links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
    return mat


def curve_tube(name,points,radius,material,collection='Leading',cyclic=False,radii=None):
    data = bpy.data.curves.new(name,'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 8
    data.bevel_depth = radius
    data.bevel_resolution = 3
    data.use_fill_caps = True
    spline = data.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    spline.use_cyclic_u = cyclic
    for i,(p,co) in enumerate(zip(spline.bezier_points,points)):
        p.co = co
        p.handle_left_type = p.handle_right_type = 'AUTO'
        if radii:
            p.radius = radii[i]
    obj = bpy.data.objects.new(name,data)
    group(collection).objects.link(obj)
    data.materials.append(material)
    return obj


def sphere(name,location,radius,material,collection='Embellishments',scale=(1,1,1),glass=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=radius,location=location)
    obj = put(bpy.context.object,name,collection,material)
    obj.scale = scale
    for face in obj.data.polygons:
        face.use_smooth = True
    if glass:
        obj['glass'] = True
        obj.cycles.is_caustics_caster = True
    return obj


def camera(name,location,target,ortho=None,lens=60):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name,data)
    group('Studio').objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    if ortho is not None:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    data.lens = lens
    data.clip_start = .001
    data.clip_end = 100
    return obj


def area(name,location,target,power,size,color=(1,1,1),size_y=None,caustics=False):
    data = bpy.data.lights.new(name,'AREA')
    data.energy = power
    data.color = color
    if size_y:
        data.shape = 'RECTANGLE'
        data.size_y = size_y
    data.size = size
    data.cycles.is_caustics_light = caustics
    obj = bpy.data.objects.new(name,data)
    group('Studio').objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    return obj


def reference_guides(names):
    for i,name in enumerate(names):
        image = bpy.data.images.load(str(ROOT/'photos'/name),check_existing=True)
        image.pack()
        image.filepath = '//photos/'+name
        obj = bpy.data.objects.new('Reference · '+name,None)
        obj.empty_display_type = 'IMAGE'
        obj.data = image
        obj.empty_display_size = .3
        obj.location = (2+i,0,0)
        obj.hide_render = True
        obj.hide_viewport = True
        group('Reference_Guides').objects.link(obj)


def settings(kind):
    scene = bpy.context.scene
    scene['project_kind'] = kind
    scene['model_revision'] = 1
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'CENTIMETERS'
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 512
    scene.cycles.max_bounces = 16
    scene.cycles.transmission_bounces = 12
    scene.cycles.glossy_bounces = 8
    scene.cycles.diffuse_bounces = 4
    scene.cycles.volume_bounces = 2
    scene.cycles.caustics_reflective = True
    scene.cycles.caustics_refractive = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .01
    scene.cycles.adaptive_min_samples = 32
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 16
    scene.render.resolution_x = scene.render.resolution_y = 2048
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'None'
    scene.display_settings.display_device = 'sRGB'
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new('Neutral studio environment')
    scene.world.use_nodes = True
    wn=scene.world.node_tree.nodes
    wn.clear()
    background=wn.new('ShaderNodeBackground')
    world_output=wn.new('ShaderNodeOutputWorld')
    scene.world.node_tree.links.new(background.outputs['Background'],world_output.inputs['Surface'])
    background.inputs['Color'].default_value = (.80,.83,.87,1)
    background.inputs['Strength'].default_value = .45 if kind == 'flat' else .28
    bpy.context.preferences.filepaths.save_version = 0
    preview_property=bpy.context.preferences.filepaths.bl_rna.properties.get('file_preview_type')
    if preview_property and 'NONE' in preview_property.enum_items:
        bpy.context.preferences.filepaths.file_preview_type='NONE'
    for screen in bpy.data.screens:
        for space in (a.spaces.active for a in screen.areas if a.type == 'VIEW_3D'):
            space.clip_start = .001
            space.clip_end = 100
            space.region_3d.view_distance = .65
            space.region_3d.view_perspective = 'CAMERA'
