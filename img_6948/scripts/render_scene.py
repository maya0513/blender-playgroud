"""Render the saved scene, without rebuilding it or changing the blend file."""
import bpy,argparse,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--width',type=int,default=3024);p.add_argument('--samples',type=int,default=128);p.add_argument('--output',default='photo_match.png')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if a.width<1 or a.samples<1:raise ValueError('width and samples must be positive')
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=a.samples;s.cycles.use_denoising=True;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.035;s.cycles.adaptive_min_samples=16;s.render.resolution_x=a.width;s.render.resolution_y=a.width;s.render.resolution_percentage=100
s.render.filepath=str(Path(__file__).resolve().parents[1]/'renders'/a.output)
bpy.ops.render.render(write_still=True)
