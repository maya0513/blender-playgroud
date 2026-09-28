"""Check current outputs against the saved scene and the fixed directory layout."""
import json
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from PIL import Image
from project import ROOT, SCENE, REVIEW, IMAGES, REPORTS, LOGS, RENDERS, FINAL_IMAGE, CAMERAS, sha256, write_report

# Never leave a prior PASS visible if this verification fails.
(REPORTS / 'verification.json').unlink(missing_ok=True)
scene_hash = sha256(SCENE)
build = json.loads((REPORTS / 'build.json').read_text())
assert build['revision'] == 4 and build['scene_sha256'] == scene_hash
validation = json.loads((REPORTS / 'validation.json').read_text())
assert validation['status'] == 'PASS' and validation['scene_sha256'] == scene_hash
assert validation['visual_audit']['status'] == 'PASS'
records = {}
for stage in ['final', 'preview']:
    report = json.loads((REPORTS / (stage + '.json')).read_text())
    expected = {'photo'} if stage == 'final' else set(CAMERAS)
    assert set(report['views']) == expected, (stage, 'missing views')
    for name, record in report['views'].items():
        path = ROOT / record['image']
        expected_path = FINAL_IMAGE if stage == 'final' else IMAGES / (name + '.png')
        assert path == expected_path, (stage, name, 'wrong output path')
        assert record['camera'] == CAMERAS[name]
        assert record['engine'] == 'CYCLES' and record['device'] == 'CPU'
        assert record['view_transform'] == 'AgX' and record['display_device'] == 'sRGB'
        assert record['denoiser'] == 'OPENIMAGEDENOISE'
        assert record['photo_projection'] is False and record['scene_audit']['status'] == 'PASS'
        assert record['samples'] == (256 if stage == 'final' else (64 if name == 'photo' else 32))
        assert abs(record['adaptive_threshold'] - (.01 if stage == 'final' else .035)) < 1e-6
        assert record['scene_sha256'] == scene_hash, (path, 'stale scene')
        assert record['image_sha256'] == sha256(path), (path, 'changed image')
        expected_size = (3024, 3024) if stage == 'final' else ((1512,1512) if name=='photo' else ((756,756) if name=='clay' else (1280,850)))
        assert record['size'] == list(expected_size)
        with Image.open(path) as image:
            assert image.size == expected_size, (path, image.size)
            image.verify()
        records[f'{stage}/{name}'] = {'path': record['image'], 'size': list(expected_size), 'render_seconds': record['render_seconds']}
allowed = {
    REVIEW: {'README.md', 'images', 'reports', 'logs'},
    IMAGES: {name + '.png' for name in CAMERAS},
    REPORTS: {'build.json', 'validation.json', 'contacts.json', 'preview.json', 'final.json', 'verification.json', 'appearance.json'},
    LOGS: {'.pipeline.lock', 'build.log', 'validate.log', 'preview.log', 'final.log', 'verify.log'},
    RENDERS: {'hamamachi_breakwater.png'},
}
additional_unverified_files = []
for directory, names in allowed.items():
    unexpected = {p.name for p in directory.iterdir()} - names
    if directory == RENDERS:
        # Preserve user/other-process images; only manifest-backed paths are current outputs.
        additional_unverified_files.extend(str((directory / name).relative_to(ROOT)) for name in sorted(unexpected))
    else:
        assert not unexpected, (directory, 'unexpected outputs', unexpected)
from verify_appearance import check
appearance = {stage: check(stage) for stage in ['preview', 'final']}
write_report('appearance', appearance)
assert all(result['status'] == 'PASS' for result in appearance.values()), 'Appearance regression'
write_report('verification', {'status': 'PASS', 'scene_sha256': scene_hash, 'outputs': records, 'fixed_layout': True, 'additional_unverified_files': additional_unverified_files})
print('PASS: current scene, nine managed PNG files, dimensions, image hashes and fixed output paths')
if additional_unverified_files:
    print('Preserved additional files (not verified as current outputs):', additional_unverified_files)
