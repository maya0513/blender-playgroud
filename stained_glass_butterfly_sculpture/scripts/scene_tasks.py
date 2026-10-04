"""Blender subprocess tasks, with current-scene reports and atomic outputs."""
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
CONFIG = json.loads((ROOT/'scripts/project.json').read_text())
SCENE = ROOT/CONFIG['scene']
REPORTS = ROOT/'review/reports'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report(name,data):
    path = REPORTS/(name+'.json')
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(path)


def audit():
    scene = bpy.context.scene
    errors = []
    if scene.get('project_kind') != CONFIG['kind'] or scene.get('model_revision') != CONFIG['revision']:
        errors.append('Unexpected scene identity or revision')
    if scene.render.engine != 'CYCLES' or not scene.camera:
        errors.append('Missing Cycles setup or main camera')
    if bpy.data.libraries:
        errors.append('External linked libraries')
    if any(node.type == 'TEX_IMAGE' for mat in bpy.data.materials if mat.use_nodes for node in mat.node_tree.nodes):
        errors.append('Artwork must use geometry and procedural materials')
    for name in ['Glass_Panes','Leading','Embellishments','Studio','Reference_Guides']:
        if not bpy.data.collections.get(name):
            errors.append('Missing collection '+name)
    for name in CONFIG['views']:
        if not bpy.data.objects.get('Camera · '+name):
            errors.append('Missing camera '+name)
    guides = [o for o in bpy.data.collections['Reference_Guides'].objects]
    if len(guides) != len(CONFIG['references']) or any(not o.hide_render or not o.data.packed_file for o in guides):
        errors.append('Reference guides must be packed and hidden from rendering')
    glass = [o for o in scene.objects if o.get('glass')]
    if not glass:
        errors.append('No glass objects')
    nonmanifold = []
    thickness = []
    for obj in scene.objects:
        if not all(math.isfinite(v) for row in obj.matrix_world for v in row):
            errors.append('Non-finite transform '+obj.name)
        if obj.type != 'MESH':
            continue
        if not obj.data.vertices or not obj.data.materials:
            errors.append('Empty or unshaded mesh '+obj.name)
        if not obj.get('glass'):
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bad = sum(not e.is_manifold for e in bm.edges)
        volume = bm.calc_volume(signed=True)
        inconsistent = sum(not e.is_contiguous for e in bm.edges if e.is_manifold)
        bm.free()
        if bad or inconsistent or volume < 1e-15:
            nonmanifold.append({'object':obj.name,'bad_edges':bad,
                                'inconsistent_normals':inconsistent,'signed_volume':volume})
        nominal = obj.get('nominal_thickness_m')
        if nominal:
            if CONFIG['kind'] == 'flat':
                z = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
                lo = hi = max(z)-min(z)
                valid = .80*nominal <= lo <= 1.20*nominal
            elif obj.get('wing_cell'):
                vertices = obj.data.vertices
                half = len(vertices)//2
                matrix = obj.matrix_world.to_3x3()
                distances = [(matrix @ (vertices[i+half].co-vertices[i].co)).length
                             for i in range(half)]
                lo,hi = min(distances),max(distances)
                valid = .24*nominal <= lo and hi <= 1.15*nominal
            else:
                continue
            thickness.append({'object':obj.name,'minimum_m':lo,'maximum_m':hi,
                              'nominal_m':nominal})
            if not valid:
                errors.append('Glass thickness mismatch '+obj.name)
    if nonmanifold:
        errors.append({'glass_geometry_errors':nonmanifold})
    expected = CONFIG['reference_hashes']
    for name in CONFIG['references']:
        if sha(ROOT/'photos'/name) != expected[name]:
            errors.append('Reference integrity mismatch '+name)
    return {'status':'PASS' if not errors else 'FAIL','errors':errors,
            'kind':CONFIG['kind'],'objects':len(scene.objects),'glass_objects':len(glass),
            'mesh_vertices':sum(len(o.data.vertices) for o in scene.objects if o.type=='MESH'),
            'packed_references':len(guides),'glass_normals':'Consistent outward normals and positive signed volumes',
            'thickness_checked_objects':len(thickness),'glass_thickness':thickness,'geometry_policy':'Closed glass volumes; no image-texture artwork or external linked libraries.'}


def build():
    from build_scene import build as build_model
    start = time.monotonic()
    build_model()
    result = audit()
    assert result['status'] == 'PASS',result
    tmp = SCENE.with_name('.'+SCENE.stem+'.building.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp))
    tmp.replace(SCENE)
    result.update(scene_sha256=sha(SCENE),build_seconds=time.monotonic()-start)
    report('build',result)
    print('BUILD_REPORT',json.dumps(result),flush=True)


def validate():
    result = audit()
    result['scene_sha256'] = sha(SCENE)
    report('validation',result)
    assert result['status'] == 'PASS',result
    print('VALIDATION_REPORT',json.dumps(result),flush=True)


def render(action,threads,views):
    result = audit()
    assert result['status'] == 'PASS',result
    scene_hash = sha(SCENE)
    validation = json.loads((REPORTS/'validation.json').read_text())
    assert validation['status']=='PASS' and validation['scene_sha256']==scene_hash,'Validate current scene first'
    final = action == 'final'
    if final:
        preview = json.loads((REPORTS/'preview.json').read_text())
        for name in CONFIG['views']:
            record = preview['views'][name]
            assert record['scene_sha256']==scene_hash and sha(ROOT/record['image'])==record['image_sha256'],'Preview current scene first'
    scene = bpy.context.scene
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = threads
    scene.cycles.samples = 512 if final else 64
    scene.cycles.adaptive_threshold = .01 if final else .035
    scene.cycles.adaptive_min_samples = 32 if final else 12
    scene.render.resolution_x = scene.render.resolution_y = 2048 if final else 1024
    scene.render.resolution_percentage = 100
    scene.render.use_border = scene.render.use_crop_to_border = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    manifest = {'stage':action,'views':{}}
    if not final and (REPORTS/'preview.json').exists():
        old = json.loads((REPORTS/'preview.json').read_text())
        manifest['views'] = {k:v for k,v in old['views'].items() if v['scene_sha256']==scene_hash}
    for name in (['main'] if final else (views or CONFIG['views'])):
        scene.camera = bpy.data.objects['Camera · '+name]
        output = ROOT/('renders/final.png' if final else 'review/images/'+name+'.png')
        tmp = output.with_name('.'+output.stem+'.rendering.png')
        scene.render.filepath = str(tmp)
        start = time.monotonic()
        last_progress = 0
        def progress(stats,*_):
            nonlocal last_progress
            now = time.monotonic()
            if now-last_progress >= 30 or 'Finished' in str(stats):
                print('RENDER_PROGRESS',json.dumps({'view':name,'elapsed_seconds':round(now-start,1),
                                                   'stats':str(stats)}),flush=True)
                last_progress = now
        bpy.app.handlers.render_stats.append(progress)
        try:
            bpy.ops.render.render(write_still=True)
            assert tmp.exists() and tmp.stat().st_size>100
            tmp.replace(output)
        finally:
            bpy.app.handlers.render_stats.remove(progress)
            tmp.unlink(missing_ok=True)
        record = {'image':str(output.relative_to(ROOT)),'size':[scene.render.resolution_x,scene.render.resolution_y],
                  'scene_sha256':scene_hash,'image_sha256':sha(output),'seconds':time.monotonic()-start,
                  'samples':scene.cycles.samples,'engine':'CYCLES','device':'CPU','threads':threads,
                  'max_bounces':scene.cycles.max_bounces,'transmission_bounces':scene.cycles.transmission_bounces,
                  'view_transform':scene.view_settings.view_transform,'camera':scene.camera.name,
                  'adaptive_sampling':scene.cycles.use_adaptive_sampling,
                  'adaptive_threshold':scene.cycles.adaptive_threshold,
                  'adaptive_min_samples':scene.cycles.adaptive_min_samples,
                  'denoising':scene.cycles.use_denoising,'denoiser':scene.cycles.denoiser}
        manifest['views'][name] = record
        report(action,manifest)
        print('RENDER_REPORT',json.dumps(record),flush=True)
    assert sha(SCENE)==scene_hash,'Rendering must not change saved scene'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','validate','preview','final'])
    p.add_argument('--threads',type=int,default=16)
    p.add_argument('--views',nargs='+',choices=CONFIG['views'])
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.action == 'build':
        build()
    elif args.action == 'validate':
        validate()
    else:
        render(args.action,args.threads,args.views)


if __name__ == '__main__':
    main()
