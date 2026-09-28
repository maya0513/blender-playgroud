"""Check current outputs against the saved scene and the fixed directory layout."""
import json
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from PIL import Image
from project import ROOT, SCENE, REVIEW, IMAGES, REPORTS, LOGS, RENDERS, CAMERAS, sha256, write_report

# Never leave a prior PASS visible if this verification fails.
(REPORTS / 'verification.json').unlink(missing_ok=True)
scene_hash = sha256(SCENE)
validation = json.loads((REPORTS / 'validation.json').read_text())
assert validation['status'] == 'PASS' and validation['scene_sha256'] == scene_hash
records = {}
for stage in ['final', 'preview']:
    report = json.loads((REPORTS / (stage + '.json')).read_text())
    expected = {'photo'} if stage == 'final' else set(CAMERAS)
    assert set(report['views']) == expected, (stage, 'missing views')
    for name, record in report['views'].items():
        path = ROOT / record['image']
        assert record['scene_sha256'] == scene_hash, (path, 'stale scene')
        assert record['image_sha256'] == sha256(path), (path, 'changed image')
        expected_size = (3024, 3024) if stage == 'final' else ((1512,1512) if name=='photo' else ((756,756) if name=='clay' else (1280,850)))
        with Image.open(path) as image:
            assert image.size == expected_size, (path, image.size)
            image.verify()
        records[f'{stage}/{name}'] = {'path': record['image'], 'size': list(expected_size), 'render_seconds': record['render_seconds']}
allowed = {
    REVIEW: {'README.md', 'images', 'reports', 'logs'},
    IMAGES: {name + '.png' for name in CAMERAS},
    REPORTS: {'build.json', 'validation.json', 'contacts.json', 'preview.json', 'final.json', 'verification.json', 'appearance.json'},
    LOGS: {'.pipeline.lock', 'build.log', 'validate.log', 'preview.log', 'final.log'},
    RENDERS: {'hamamachi_breakwater.png'},
}
for directory, names in allowed.items():
    unexpected = {p.name for p in directory.iterdir()} - names
    assert not unexpected, (directory, 'unexpected outputs', unexpected)
from verify_appearance import check
appearance = {stage: check(stage) for stage in ['preview', 'final']}
write_report('appearance', appearance)
assert all(result['status'] == 'PASS' for result in appearance.values()), 'Appearance regression'
write_report('verification', {'status': 'PASS', 'scene_sha256': scene_hash, 'outputs': records, 'fixed_layout': True})
print('PASS: current scene, nine PNG files, dimensions, image hashes and fixed output layout')
