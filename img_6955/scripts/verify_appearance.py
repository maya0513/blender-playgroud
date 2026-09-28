"""Detect loss of calibrated photographic appearance, independently of mesh checks.
This is a fixed-camera color regression check, not evidence of 3D accuracy.
"""
import argparse
import json
import sys
sys.dont_write_bytecode = True
from PIL import Image, ImageChops, ImageStat
from project import ROOT, SCENE, REPORTS, sha256, write_report

REGIONS = {
    'sky': ((0, 0, 890, 425), 6.0),
    'floor': ((0, 550, 1008, 1008), 6.0),
    'structures': ((100, 440, 1008, 550), 15.0),
}

def check(stage):
    record = json.loads((REPORTS / (stage + '.json')).read_text())['views']['photo']
    path = ROOT / record['image']
    assert record['scene_sha256'] == sha256(SCENE), 'Photo view belongs to an older scene; render preview again'
    assert record['image_sha256'] == sha256(path), 'Photo output changed after rendering'
    assert record['camera'] == 'Photo camera' and record['view_transform'] == 'Standard'
    source = ROOT / 'assets/reference_srgb.png'
    expected = (3024, 3024) if stage == 'final' else (1512, 1512)
    with Image.open(path) as im:
        assert im.size == expected, (stage, im.size)
        rendered = im.convert('RGB').resize((1008, 1008), Image.Resampling.LANCZOS)
    with Image.open(source) as im:
        reference = im.convert('RGB').resize((1008, 1008), Image.Resampling.LANCZOS)
    metrics = {}
    for name, (box, limit) in REGIONS.items():
        difference = ImageChops.difference(rendered.crop(box), reference.crop(box))
        error = sum(ImageStat.Stat(difference).mean) / 3
        metrics[name] = {'mean_absolute_srgb_error_0_255': error, 'limit': limit, 'pass': error <= limit}
    return {'status': 'PASS' if all(v['pass'] for v in metrics.values()) else 'FAIL',
            'scene_sha256': record['scene_sha256'], 'image': record['image'],
            'image_sha256': record['image_sha256'], 'reference_sha256': sha256(source),
            'regions': metrics,
            'scope': 'Detect major fixed-camera appearance regressions. Photo-projected color agreement does not validate geometry or unobserved views.'}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['preview', 'final'], default='preview')
    a = p.parse_args()
    (REPORTS / 'appearance.json').unlink(missing_ok=True)
    (REPORTS / 'verification.json').unlink(missing_ok=True)
    result = check(a.stage)
    write_report('appearance', {a.stage: result})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['status'] == 'PASS' else 1)
