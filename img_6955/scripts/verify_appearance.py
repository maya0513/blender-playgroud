"""Check render provenance and image health; similarity is a human review.

No source-photo pixel-error threshold: independently constructed geometry and
procedural clouds cannot be required to reproduce photographic pixels.
"""
import argparse
import json
import sys
sys.dont_write_bytecode = True
from PIL import Image, ImageStat
from project import ROOT, SCENE, REPORTS, sha256, write_report


def check(stage):
    record = json.loads((REPORTS / (stage + '.json')).read_text())['views']['photo']
    path = ROOT / record['image']
    assert record['scene_sha256'] == sha256(SCENE), 'Stale scene: regenerate photo preview'
    assert record['image_sha256'] == sha256(path), 'Image hash mismatch'
    assert record['camera'] == 'Photo camera' and record['view_transform'] == 'AgX'
    assert record['photo_projection'] is False and record['scene_audit']['status'] == 'PASS'
    expected = (3024,3024) if stage == 'final' else (1512,1512)
    with Image.open(path) as im:
        assert im.size == expected
        stat = ImageStat.Stat(im.convert('RGB'))
        assert max(stat.stddev) > 5, 'Blank or nearly uniform render'
        assert 5 < sum(stat.mean)/3 < 250, 'Severely clipped render'
    return {'status': 'PASS', 'scene_sha256': record['scene_sha256'],
            'image': record['image'], 'image_sha256': record['image_sha256'],
            'mean_rgb': stat.mean, 'stddev_rgb': stat.stddev,
            'scope': 'Automated provenance and image-health checks only. Composition, materials and likeness require visual review.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['preview','final'], default='preview')
    a = p.parse_args()
    (REPORTS / 'appearance.json').unlink(missing_ok=True)
    (REPORTS / 'verification.json').unlink(missing_ok=True)
    result = check(a.stage)
    write_report('appearance', {a.stage: result})
    print(json.dumps(result, indent=2))
