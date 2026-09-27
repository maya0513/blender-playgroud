"""Validate a saved photograph reconstruction without changing any data."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
s=bpy.context.scene
assert s.camera and s.camera.type=='CAMERA','Missing camera'
assert s.render.resolution_x==s.render.resolution_y,'Expected square render'
assert s.render.engine=='CYCLES','Expected Cycles'
assert len([c for c in bpy.data.collections if ' · ' in c.name])==11,'Missing scene collection'
missing=[i.filepath for i in bpy.data.images if i.source=='FILE' and not i.packed_file and not Path(bpy.path.abspath(i.filepath)).is_file()]
assert not missing,missing
assert not bpy.data.libraries,'Scene must not link other projects'
assert all(math.isfinite(v) for o in s.objects for row in o.matrix_world for v in row),'Non-finite transform'
assert all(len(o.data.vertices)>0 and len(o.data.materials)>0 for o in s.objects if o.type=='MESH'),'Empty or unshaded mesh'
hit,pos,normal,index,obj,matrix=s.ray_cast(bpy.context.evaluated_depsgraph_get(),s.camera.location,Vector((0,0,-1)),distance=5)
assert hit and obj.name.startswith(('Continuous walkway','Transverse paving joint')),(hit,obj.name if hit else None)
assert 1.4<s.camera.location.z-pos.z<1.9,'Camera height'
ref=[i for i in bpy.data.images if i.name.startswith('IMG_6948')]
assert ref and ref[0].packed_file,'Photo must be packed'
assert tuple(ref[0].size)==(3024,3024),tuple(ref[0].size)
# A curved cross section must remain actual editable geometry, not a flat wall.
quay=bpy.data.objects.get('Opposite seawall · curved cross section')
assert quay and quay.type=='MESH','Missing curved quay'
crest=quay['crest_z'];toe=quay['toe_projection'];front_x=max(v.co.x for v in quay.data.vertices)-toe
start_y=min(v.co.y for v in quay.data.vertices)
section=[v.co for v in quay.data.vertices if abs(v.co.y-start_y)<1e-4 and v.co.x>=front_x-1e-4 and v.co.z>=0]
assert len({round(v.x,3) for v in section})>=20,'Quay cross section is flat'
assert max(v.x for v in section)-min(v.x for v in section)>1,'Missing seaward curve'
assert sum(p.use_smooth for p in quay.data.polygons)>100,'Missing smooth curved face'
assert all(bpy.data.objects.get('Mountain ridge %d'%i) for i in range(3)),'Missing mountain layers'
assert not any(o.name.startswith(('Inset service cover','Drain slot','Transverse paving joint')) for o in s.objects),'Asphalt must have no invented grates or slab grid'
asphalt=bpy.data.objects['Continuous walkway'].data.materials[0]
assert asphalt.node_tree.nodes.get('Asphalt mineral grains'),'Missing asphalt aggregate'
assert asphalt.node_tree.nodes.get('Asphalt irregular worn patches'),'Missing asphalt weathering'
assert bpy.data.objects['Retaining wall'].data.materials[0].node_tree.nodes.get('Moss coverage'),'Missing wall moss'
# Auxiliary fill must not recreate the discontinuity across the river.
water=bpy.data.objects['Continuous wave surface']
for light in (o for o in s.objects if o.type=='LIGHT' and o.data.type=='AREA'):
    receivers=light.light_linking.receiver_collection
    assert receivers and water.name not in receivers.all_objects,'Auxiliary fill must not illuminate water'
assert s.get('photo_review_revision')=='photo-review-6','Missing photo comparison refinements'
assert bpy.data.objects.get('Photo pine individual needle fans'),'Missing rebuilt pine'

assert abs(crest-10.5)<1e-5,'Quay height correction missing'
assert quay.data.materials[0].node_tree.nodes.get('Quay algae coverage'),'Missing quay algae'
assert bpy.data.objects.get('Orange facade behind left planting'),'Missing orange facade'
assert abs(bpy.data.materials['Blue green rippled water'].node_tree.nodes['Fine river ripples'].inputs['Strength'].default_value-.9)<1e-5,'Ripple strength'
sediment=bpy.data.objects.get('Near-bank exposed sediment')
assert sediment and sediment.type=='MESH','Missing exposed sediment terrain'
assert min(v.co.z for v in sediment.data.vertices)<-.04 and max(v.co.z for v in sediment.data.vertices)>.07,'Sediment must cross water level'
assert sediment.data.materials[0].node_tree.nodes.get('Sediment wet shoreline'),'Missing damp sediment edge'
leaves=bpy.data.objects.get('Dry leaves on sediment')
assert leaves and leaves.get('leaf_count',0)>500,'Missing individual sediment leaves'
assert len(leaves.data.materials)>=3,'Missing dry leaf colour variation'
assert not s.render.use_border,'Saved scene must render the entire square'
print('IMG6948_AUDIT '+json.dumps({'blend':Path(bpy.data.filepath).name,'objects':len(s.objects),'camera_eye_height':round(s.camera.location.z-pos.z,3),'resolution':[s.render.resolution_x,s.render.resolution_y],'missing_images':missing,'external_libraries':len(bpy.data.libraries),'packed_reference':bool(ref[0].packed_file)},ensure_ascii=False),flush=True)
