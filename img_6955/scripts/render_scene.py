"""Render current-scene previews or the 3024px deliverable into fixed locations."""
import argparse
import json
import runpy
import sys
sys.dont_write_bytecode = True
import time
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project import ROOT, SCENE, IMAGES, REPORTS, FINAL_IMAGE, CAMERAS, ensure_directories, sha256, write_report

p = argparse.ArgumentParser()
p.add_argument('--mode', choices=['preview', 'final'], default='preview')
p.add_argument('--views', nargs='+', choices=list(CAMERAS))
p.add_argument('--threads', type=int, default=16)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
if a.mode == 'final' and a.views:
    p.error('--views is only available for preview; final uses Photo camera')
if a.threads < 1:
    p.error('--threads must be positive')
ensure_directories()
(REPORTS / 'verification.json').unlink(missing_ok=True)
s = bpy.context.scene
assert s.get('model_revision') == 2
assert Path(bpy.data.filepath).resolve() == SCENE.resolve(), 'Load the current project scene'
s.render.engine = 'CYCLES'
s.cycles.device = 'CPU'
s.render.threads_mode = 'FIXED'
s.render.threads = a.threads
s.render.resolution_percentage = 100
s.render.pixel_aspect_x = s.render.pixel_aspect_y = 1
s.render.use_border = False
s.render.use_crop_to_border = False
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGB'
s.render.image_settings.color_depth = '8'
s.render.film_transparent = False
s.view_settings.view_transform = 'Standard'
s.display_settings.display_device = 'sRGB'
s.cycles.use_adaptive_sampling = True
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPENIMAGEDENOISE'
final = a.mode == 'final'
s.cycles.samples = 128 if final else 32
s.cycles.adaptive_threshold = .01 if final else .035
s.cycles.adaptive_min_samples = 16 if final else 12
s.render.resolution_x, s.render.resolution_y = (3024, 3024) if final else (1280, 850)
from restore_appearance import set_photo_mode
if final:
    set_photo_mode(True)
    bpy.data.objects['Photographic cloud hemisphere'].hide_render = False
    bpy.context.view_layer.material_override = None
    s.camera = bpy.data.objects[CAMERAS['photo']]
    s.render.filepath = '//renders/hamamachi_breakwater.png'
    # Persist exactly the final settings, without accumulating .blend1 files.
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SCENE))
    runpy.run_path(str(ROOT / 'scripts/validate_scene.py'), run_name='__main__')
scene_hash = sha256(SCENE)
manifest_path = REPORTS / (a.mode + '.json')
manifest = {'mode': a.mode, 'views': {}}
if not final and manifest_path.exists():
    manifest = json.loads(manifest_path.read_text())
for name in (['photo'] if final else (a.views or list(CAMERAS))):
    is_photo = final or name == 'photo'
    s.cycles.samples = 128 if final else (64 if name == 'photo' else 32)
    set_photo_mode(is_photo)
    s.view_settings.view_transform = 'Standard' if is_photo else 'AgX'
    s.render.resolution_x, s.render.resolution_y = (3024,3024) if final else ((1512,1512) if name=='photo' else ((756,756) if name=='clay' else (1280,850)))
    dome=bpy.data.objects['Photographic cloud hemisphere'];dome.hide_render=not is_photo
    if name == 'clay':
        clay=bpy.data.materials.get('Geometry inspection clay') or bpy.data.materials.new('Geometry inspection clay');clay.diffuse_color=(.55,.55,.55,1);clay.use_nodes=True;clay.node_tree.nodes.clear();bsdf=clay.node_tree.nodes.new('ShaderNodeBsdfPrincipled');bsdf.inputs['Base Color'].default_value=(.55,.55,.55,1);out=clay.node_tree.nodes.new('ShaderNodeOutputMaterial');clay.node_tree.links.new(bsdf.outputs[0],out.inputs['Surface'])
        bpy.context.view_layer.material_override=clay
    else:bpy.context.view_layer.material_override=None
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
    record = {
        'image': str(output.relative_to(ROOT)), 'camera': CAMERAS[name],
        'scene_sha256': scene_hash, 'image_sha256': sha256(output),
        'render_seconds': time.monotonic() - started,
        'size': [s.render.resolution_x, s.render.resolution_y],
        'engine': 'CYCLES', 'device': 'CPU', 'threads': a.threads,
        'samples': s.cycles.samples, 'adaptive_threshold': s.cycles.adaptive_threshold,
        'denoiser': s.cycles.denoiser, 'view_transform': s.view_settings.view_transform,
        'display_device': s.display_settings.display_device,
    }
    manifest['views'][name] = record
    write_report(a.mode, manifest)
    print('RENDER_REPORT', json.dumps(record), flush=True)
