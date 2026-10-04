"""Verify current-scene provenance, image integrity and nonblank render outputs."""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont,ImageStat

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'scripts/project.json').read_text())
REPORTS = ROOT/'review/reports'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review_images(final_render=False):
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
    ref = Image.open(ROOT/'photos'/CONFIG['reference']).convert('RGB').resize((1024,1024))
    final = Image.open(ROOT/('renders/final.png' if final_render else 'review/images/main.png')).convert('RGB').resize((1024,1024))
    comparison = Image.new('RGB',(2048,1072),(245,245,245))
    comparison.paste(ref,(0,48))
    comparison.paste(final,(1024,48))
    draw = ImageDraw.Draw(comparison)
    draw.text((24,12),'REFERENCE',fill=(25,25,25),font=font)
    draw.text((1048,12),'BLENDER / '+CONFIG['kind'].upper(),fill=(25,25,25),font=font)
    comparison.save(ROOT/('review/images/comparison.png' if final_render else 'review/images/preview_comparison.png'))
    views = CONFIG['views']
    contact = Image.new('RGB',(1024,548*((len(views)+1)//2)),(245,245,245))
    draw = ImageDraw.Draw(contact)
    for i,name in enumerate(views):
        x,y=(i%2)*512,(i//2)*548
        view = Image.open(ROOT/'review/images'/f'{name}.png').convert('RGB').resize((512,512))
        contact.paste(view,(x,y+36))
        draw.text((x+12,y+5),name,fill=(25,25,25),font=font)
    contact.save(ROOT/'review/images/views.png')


def main():
    scene_hash = sha(ROOT/CONFIG['scene'])
    checks = []
    for stage in ['build','validation']:
        data = json.loads((REPORTS/(stage+'.json')).read_text())
        assert data['status']=='PASS' and data['scene_sha256']==scene_hash
        checks.append(stage)
    for stage in ['preview','final']:
        data = json.loads((REPORTS/(stage+'.json')).read_text())
        for name in (CONFIG['views'] if stage=='preview' else ['main']):
            rec = data['views'][name]
            assert rec['scene_sha256']==scene_hash
            path = ROOT/rec['image']
            assert sha(path)==rec['image_sha256']
            with Image.open(path) as image:
                image.load()
                assert image.format=='PNG' and list(image.size)==rec['size']
                assert image.size==((2048,2048) if stage=='final' else (1024,1024))
                assert max(ImageStat.Stat(image.resize((256,256))).stddev)>8,'Blank or flat render'
            assert rec['samples']==(512 if stage=='final' else 64)
            assert rec['engine']=='CYCLES' and rec['device']=='CPU'
            checks.append(stage+':'+name)
    for name in CONFIG['references']:
        path=ROOT/'photos'/name
        assert sha(path)==CONFIG['reference_hashes'][name]
        checks.append('reference:'+name)
    review_images(final_render=True)
    result = {'status':'PASS','scene_sha256':scene_hash,'checks':checks,
              'final_image':'renders/final.png','comparison':'review/images/comparison.png',
              'views':'review/images/views.png'}
    (REPORTS/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    if '--preview-comparison' in sys.argv:
        scene_hash = sha(ROOT/CONFIG['scene'])
        preview = json.loads((REPORTS/'preview.json').read_text())
        current = all(name in preview['views'] and preview['views'][name]['scene_sha256']==scene_hash
                      for name in CONFIG['views'])
        if current:
            for record in preview['views'].values():
                assert sha(ROOT/record['image'])==record['image_sha256']
            review_images()
            print('Preview comparison and view sheet created.')
        else:
            print('Comparison postponed until all current preview views exist.')
    else:
        main()
