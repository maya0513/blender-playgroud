"""Render without modifying the saved scene. Commit each PNG atomically."""
import argparse
import json
import sys
import time
from pathlib import Path
import bpy

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project import SCENE, IMAGES, REPORTS, FINAL_IMAGE, CAMERAS, ROOT, ensure_directories, sha256, write_report
from scene_audit import audit_scene

p = argparse.ArgumentParser()
p.add_argument('--mode', choices=['preview', 'final'], default='preview')
p.add_argument('--views', nargs='+', choices=list(CAMERAS))
p.add_argument('--threads', type=int, default=16)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
if a.threads < 1 or (a.mode == 'final' and a.views):
    p.error('Positive threads required; --views only applies to preview')
ensure_directories()
(REPORTS / 'verification.json').unlink(missing_ok=True)
s = bpy.context.scene
assert s.get('model_revision') == 4
assert Path(bpy.data.filepath).resolve() == SCENE.resolve()
audit = audit_scene(s)
assert audit['status'] == 'PASS', audit
scene_hash = sha256(SCENE)
s.render.engine = 'CYCLES'
s.cycles.device = 'CPU'
s.render.threads_mode = 'FIXED'
s.render.threads = a.threads
s.render.resolution_percentage = 100
s.render.pixel_aspect_x = s.render.pixel_aspect_y = 1
s.render.use_border = s.render.use_crop_to_border = False
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGB'
s.render.image_settings.color_depth = '8'
s.render.film_transparent = False
s.view_settings.view_transform = 'AgX'
s.display_settings.display_device = 'sRGB'
s.cycles.use_adaptive_sampling = True
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPENIMAGEDENOISE'
s.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
final = a.mode == 'final'
s.cycles.adaptive_threshold = .01 if final else .035
s.cycles.adaptive_min_samples = 16 if final else 12
manifest_path = REPORTS / (a.mode + '.json')
manifest = {'mode': a.mode, 'views': {}}
if not final and manifest_path.exists():
    old = json.loads(manifest_path.read_text())
    manifest['views'] = {k:v for k,v in old['views'].items() if v['scene_sha256'] == scene_hash}
for name in (['photo'] if final else (a.views or list(CAMERAS))):
    s.cycles.samples = 256 if final else (64 if name == 'photo' else 32)
    size = (3024,3024) if final else ((1512,1512) if name == 'photo' else ((756,756) if name == 'clay' else (1280,850)))
    s.render.resolution_x, s.render.resolution_y = size
    if name == 'clay':
        clay = bpy.data.materials.new('Geometry inspection clay')
        clay.use_nodes = True
        clay.node_tree.nodes.clear()
        bsdf = clay.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        out = clay.node_tree.nodes.new('ShaderNodeOutputMaterial')
        clay.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
        bsdf.inputs['Base Color'].default_value = (.32,.32,.32,1)
        bsdf.inputs['Roughness'].default_value = .8
        bpy.context.view_layer.material_override = clay
    else:
        bpy.context.view_layer.material_override = None
    output = FINAL_IMAGE if final else IMAGES / (name + '.png')
    temporary = output.with_name('.' + output.stem + '.rendering.png')
    s.camera = bpy.data.objects[CAMERAS[name]]
    s.render.filepath = str(temporary)
    started = time.monotonic()
    try:
        bpy.ops.render.render(write_still=True)
        assert temporary.is_file() and temporary.stat().st_size > 0
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    assert sha256(SCENE) == scene_hash, 'Rendering must not alter the saved scene'
    record = {
        'image': str(output.relative_to(ROOT)), 'camera': s.camera.name,
        'scene_sha256': scene_hash, 'image_sha256': sha256(output),
        'render_seconds': time.monotonic() - started, 'size': list(size),
        'engine': s.render.engine, 'device': s.cycles.device, 'threads': a.threads,
        'samples': s.cycles.samples, 'adaptive_threshold': s.cycles.adaptive_threshold,
        'denoiser': s.cycles.denoiser, 'view_transform': s.view_settings.view_transform,
        'display_device': s.display_settings.display_device, 'photo_projection': False,
        'scene_audit': audit,
    }
    manifest['views'][name] = record
    write_report(a.mode, manifest)
    print('RENDER_REPORT', json.dumps(record), flush=True)
