"""Trace the supplied drawing into editable closed Bezier contours, not textures.

The dark seams separate glass panes. Flood fill extracts the panes; pixel-edge
loops are simplified to subpixel tolerance. Blender uses these as Bezier paths.
Only averaged pane colours and outlines are retained in the modelling data.
"""
import hashlib
import json
import random
from array import array
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'photos/IMG_5534.JPG'


def simplify(points, tolerance=.48):
    """Iterative Ramer-Douglas-Peucker; rotate a loop at its leftmost point."""
    if len(points) < 5:
        return points
    start = min(range(len(points)), key=lambda i: (points[i][0], points[i][1]))
    points = points[start:] + points[:start]
    far = max(range(len(points)), key=lambda i: (points[i][0]-points[0][0])**2 + (points[i][1]-points[0][1])**2)

    def section(seq):
        keep = {0, len(seq)-1}
        todo = [(0, len(seq)-1)]
        while todo:
            a, b = todo.pop()
            if b-a < 2:
                continue
            ax, ay = seq[a]
            bx, by = seq[b]
            dx, dy = bx-ax, by-ay
            length = dx*dx+dy*dy
            best, index = -1, -1
            for i in range(a+1, b):
                px, py = seq[i]
                t = max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/length)) if length else 0
                d = (px-ax-t*dx)**2+(py-ay-t*dy)**2
                if d > best:
                    best, index = d, i
            if best > tolerance*tolerance:
                keep.add(index)
                todo.extend([(a, index), (index, b)])
        return [seq[i] for i in sorted(keep)]

    return section(points[:far+1])[:-1] + section(points[far:]+[points[0]])[:-1]


def contours(pixels, labels, label, width, height):
    """Directed cell edges, including oppositely wound interior holes."""
    edges = defaultdict(list)
    for index in pixels:
        y, x = divmod(index, width)
        if y == 0 or labels[index-width] != label:
            edges[(x, y)].append((x+1, y))
        if x == width-1 or labels[index+1] != label:
            edges[(x+1, y)].append((x+1, y+1))
        if y == height-1 or labels[index+width] != label:
            edges[(x+1, y+1)].append((x, y+1))
        if x == 0 or labels[index-1] != label:
            edges[(x, y+1)].append((x, y))
    result = []
    while edges:
        start = next(iter(edges))
        point, loop = start, []
        while True:
            loop.append(point)
            options = edges[point]
            nxt = options.pop()
            if not options:
                del edges[point]
            point = nxt
            if point == start:
                break
        area = sum(loop[i][0]*loop[(i+1) % len(loop)][1]-loop[(i+1) % len(loop)][0]*loop[i][1] for i in range(len(loop)))/2
        if abs(area) >= 2:
            simple = simplify(loop)
            if len(simple) >= 3:
                result.append({'points': simple, 'area_pixels': area})
    return result


def main():
    image = Image.open(SOURCE).convert('RGB')
    width, height = image.size
    rgb = list(image.getdata())
    size = width*height
    # Neutral charcoal contours, rather than saturated dark-blue glass.
    luminance=[.2126*p[0]+.7152*p[1]+.0722*p[2] for p in rgb]
    seam=bytearray(size)
    for y in range(4,height-4):
        for x in range(4,width-4):
            i=y*width+x
            p=rgb[i]
            core=max(p)<140 and max(p)-min(p)<85 and luminance[i]<75
            ridge=False
            if max(p)<232 and max(p)-min(p)<105:
                for dx,dy in [(4,0),(0,4),(3,3),(3,-3)]:
                    a=luminance[i+dy*width+dx]-luminance[i]
                    b=luminance[i-dy*width-dx]-luminance[i]
                    if min(a,b)>10 and a+b>62:
                        ridge=True
                        break
            seam[i]=core or ridge
    # Preserve the cropped left/right edge of the artwork.
    for y in range(height):
        for x in list(range(4))+list(range(width-4,width)):
            i=y*width+x
            p=rgb[i]
            seam[i]=int(max(p)<150 and max(p)-min(p)<90)
    # Close single-pixel interruptions in the JPEG outline, without broad dilation.
    repaired = seam[:]
    for y in range(1, height-1):
        for x in range(1, width-1):
            i = y*width+x
            if not seam[i] and ((seam[i-1] and seam[i+1]) or (seam[i-width] and seam[i+width])):
                repaired[i] = 1
    # A 3x3 closing also joins diagonal and copper-coloured rim interruptions.
    dilated = bytearray(size)
    for y in range(1,height-1):
        for x in range(1,width-1):
            i=y*width+x
            dilated[i]=any(repaired[i+dy*width+dx] for dy in (-1,0,1) for dx in (-1,0,1))
    seam = repaired[:]
    for y in range(2,height-2):
        for x in range(2,width-2):
            i=y*width+x
            seam[i]=all(dilated[i+dy*width+dx] for dy in (-1,0,1) for dx in (-1,0,1))
    labels = array('i', [-1])*size
    groups = []
    for seed in range(size):
        if labels[seed] != -1:
            continue
        value = seam[seed]
        label = len(groups)
        labels[seed] = label
        todo, pixels = [seed], []
        total = [0, 0, 0]
        xmin, ymin, xmax, ymax = width, height, 0, 0
        while todo:
            i = todo.pop()
            pixels.append(i)
            y, x = divmod(i, width)
            xmin, ymin, xmax, ymax = min(xmin,x), min(ymin,y), max(xmax,x), max(ymax,y)
            for c in range(3):
                total[c] += rgb[i][c]
            for j in ([i-1] if x else []) + ([i+1] if x+1<width else []) + ([i-width] if y else []) + ([i+width] if y+1<height else []):
                if labels[j] == -1 and seam[j] == value:
                    labels[j] = label
                    todo.append(j)
        groups.append({'label':label,'seam':bool(value),'pixels':pixels,
                       'color':[v/len(pixels)/255 for v in total],
                       'bounds':[xmin,ymin,xmax,ymax]})
    outside = max((g for g in groups if not g['seam']), key=lambda g:len(g['pixels']))['label']
    # Some outer copper rims in the drawing are intentionally very pale. Extract
    # their coloured fill separately from the outside flood, instead of adding a
    # heavy black outline or losing the entire pane through an open rim.
    foreground = bytearray(int(labels[i]==outside and min(p)<237 and max(p)-min(p)>16) for i,p in enumerate(rgb))
    expanded = bytearray(size)
    for y in range(1,height-1):
        for x in range(1,width-1):
            i=y*width+x
            expanded[i]=any(foreground[i+dy*width+dx] for dy in (-1,0,1) for dx in (-1,0,1))
    for y in range(2,height-2):
        for x in range(2,width-2):
            i=y*width+x
            if labels[i]==outside and all(expanded[i+dy*width+dx] for dy in (-1,0,1) for dx in (-1,0,1)):
                foreground[i]=1
    for seed in range(size):
        if not foreground[seed] or labels[seed]!=outside:
            continue
        label=len(groups)
        todo,pixels=[seed],[]
        labels[seed]=label
        total=[0,0,0]
        xmin,ymin,xmax,ymax=width,height,0,0
        while todo:
            i=todo.pop()
            pixels.append(i)
            y,x=divmod(i,width)
            xmin,ymin,xmax,ymax=min(xmin,x),min(ymin,y),max(xmax,x),max(ymax,y)
            for c in range(3):total[c]+=rgb[i][c]
            for j in ([i-1] if x else [])+([i+1] if x+1<width else [])+([i-width] if y else [])+([i+width] if y+1<height else []):
                if labels[j]==outside and foreground[j]:
                    labels[j]=label
                    todo.append(j)
        groups.append({'label':label,'seam':False,'pixels':pixels,'color':[v/len(pixels)/255 for v in total],'bounds':[xmin,ymin,xmax,ymax]})
    panes, leading = [], []
    diagnostic = Image.new('RGB', image.size, 'white')
    paint = ImageDraw.Draw(diagnostic)
    for g in groups:
        count, col = len(g['pixels']), g['color']
        if count < (6 if g['seam'] else 16) or g['label'] == outside:
            continue
        saturation = (max(col)-min(col))/max(col) if max(col) else 0
        # Large white openings inside the scroll remain open, not filled glass.
        if not g['seam'] and count > 900 and min(col) > .91 and saturation < .065:
            continue
        loops = contours(g['pixels'], labels, g['label'], width, height)
        if not loops:
            continue
        item = {'id':g['label'],'pixel_count':count,'color_srgb':col,
                'bounds':g['bounds'],'contours':loops}
        if not g['seam'] and count>450 and saturation>.10:
            mean_light=sum(w*c*255 for w,c in zip((.2126,.7152,.0722),col))
            candidates=[i for i in g['pixels'] if luminance[i]>mean_light+42]
            rng=random.Random(5534+g['label'])
            amount=min(len(candidates),int(count*.010))
            item['glints']=[[i%width,i//width,rng.uniform(.14,.56)] for i in rng.sample(candidates,amount)]
        if g['seam']:
            runs=[]
            for index in sorted(g['pixels']):
                y,x=divmod(index,width)
                if runs and runs[-1][0]==y and runs[-1][2]==x:
                    runs[-1][2]=x+1
                else:
                    runs.append([y,x,x+1])
            item['pixel_runs']=runs
        (leading if g['seam'] else panes).append(item)
        fill = (30,23,37) if g['seam'] else tuple(round(v*255) for v in col)
        for contour in sorted(loops,key=lambda c:-abs(c['area_pixels'])):
            paint.polygon([tuple(p) for p in contour['points']],fill=fill if contour['area_pixels']>0 else 'white')
    out = ROOT / 'scripts/traced_design.json'
    out.write_text(json.dumps({'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                               'size':list(image.size),'panes':panes,'leading':leading},separators=(',',':'))+'\n')
    diagnostic.save(ROOT/'review/images/traced_design.png')
    report = {'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'panes':len(panes),'leading_components':len(leading),
              'bezier_control_points':sum(len(c['points']) for g in panes+leading for c in g['contours'])}
    (ROOT/'review/reports/tracing.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
