"""Restore camera-projected photograph detail on editable structural geometry.
Projection is fixed in world space. The scene also retains ordinary PBR shaders
for geometric inspection and secondary rays; the photograph is never composited
over the render. Sky uses a distant hemisphere, not a full-frame image plane.
"""
import math
import bpy
from mathutils import Vector

GROUP = 'Calibrated photo projection'

def set_photo_mode(enabled):
    bpy.data.node_groups[GROUP].nodes['Enabled'].outputs[0].default_value = float(enabled)

def restore_appearance(scene, camera, image, collections):
    projector = camera.copy()
    projector.data = camera.data.copy()
    projector.name = 'Fixed photograph projector'
    collections['09 Cameras and lighting'].objects.link(projector)
    projector.hide_set(True)
    projector['purpose'] = 'Immutable reference pose for world-space photo projection'
    group = bpy.data.node_groups.new(GROUP, 'ShaderNodeTree')
    group.interface.new_socket(name='UV', in_out='OUTPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name='Weight', in_out='OUTPUT', socket_type='NodeSocketFloat')
    nodes, links = group.nodes, group.links
    output = nodes.new('NodeGroupOutput')
    coordinates = nodes.new('ShaderNodeTexCoord')
    coordinates.object = projector
    xyz = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coordinates.outputs['Object'], xyz.inputs[0])
    def math_node(operation, first, second):
        node = nodes.new('ShaderNodeMath');node.operation = operation
        for socket, value in zip(node.inputs, (first, second)):
            if isinstance(value, (int, float)):socket.default_value = value
            else:links.new(value, socket)
        return node.outputs[0]
    depth = math_node('MULTIPLY', xyz.outputs['Z'], -1)
    divisor = math_node('MAXIMUM', depth, .00001)
    uv = nodes.new('ShaderNodeCombineXYZ')
    factor = camera.data.lens / camera.data.sensor_width
    for axis in ['X', 'Y']:
        value = math_node('ADD', math_node('MULTIPLY', math_node('DIVIDE', xyz.outputs[axis], divisor), factor), .5)
        links.new(value, uv.inputs[axis])
    links.new(uv.outputs[0], output.inputs['UV'])
    enabled = nodes.new('ShaderNodeValue');enabled.name = 'Enabled';enabled.label = 'Photo view: 1 / structural inspection: 0';enabled.outputs[0].default_value = 1
    path = nodes.new('ShaderNodeLightPath')
    weight = math_node('MULTIPLY', enabled.outputs[0], path.outputs['Is Camera Ray'])
    weight = math_node('MULTIPLY', weight, math_node('GREATER_THAN', depth, 0))
    for axis in ['X','Y']:
        value = uv.inputs[axis].links[0].from_socket
        weight = math_node('MULTIPLY', weight, math_node('GREATER_THAN', value, 0))
        weight = math_node('MULTIPLY', weight, math_node('LESS_THAN', value, 1))
    links.new(weight, output.inputs['Weight'])
    # Extend each actual surface material; preserve its previous shader branch.
    for material in list(bpy.data.materials):
        if not material.use_nodes:continue
        n, l = material.node_tree.nodes, material.node_tree.links
        out = next((x for x in n if x.type == 'OUTPUT_MATERIAL'), None)
        if not out or not out.inputs['Surface'].links:continue
        original = out.inputs['Surface'].links[0].from_socket
        projection = n.new('ShaderNodeGroup');projection.node_tree = group
        texture = n.new('ShaderNodeTexImage');texture.image = image;texture.extension = 'CLIP';texture.interpolation = 'Linear';texture.label = 'Original sRGB color at fixed-camera projection'
        l.new(projection.outputs['UV'], texture.inputs['Vector'])
        emission = n.new('ShaderNodeEmission');emission.inputs['Strength'].default_value = 1
        l.new(texture.outputs['Color'], emission.inputs['Color'])
        geometry = n.new('ShaderNodeNewGeometry')
        front = n.new('ShaderNodeMath');front.operation = 'SUBTRACT';front.inputs[0].default_value = 1;l.new(geometry.outputs['Backfacing'], front.inputs[1])
        mask = n.new('ShaderNodeMath');mask.operation = 'MULTIPLY';l.new(front.outputs[0], mask.inputs[0]);l.new(projection.outputs['Weight'], mask.inputs[1])
        mix = n.new('ShaderNodeMixShader');l.new(mask.outputs[0],mix.inputs[0]);l.new(original,mix.inputs[1]);l.new(emission.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],out.inputs['Surface'])
        material['photo_projection'] = True
    # A distant upper hemisphere carries the recovered cloud texture. Its lower
    # edge is the horizon; it cannot fill the foreground with photograph pixels.
    radius = 10000.;segments = 64;rings = 24
    vertices = [(0,0,radius)]
    for j in range(1,rings+1):
        theta = (math.pi/2)*j/rings
        for i in range(segments):
            angle = math.tau*i/segments
            vertices.append((radius*math.sin(theta)*math.cos(angle),radius*math.sin(theta)*math.sin(angle),radius*math.cos(theta)))
    faces = [(0,1+(i+1)%segments,1+i) for i in range(segments)]
    for j in range(rings-1):
        for i in range(segments):
            a=1+j*segments+i;b=1+j*segments+(i+1)%segments
            faces.append((a,b,b+segments,a+segments))
    data = bpy.data.meshes.new('Cloud hemisphere mesh');data.from_pydata(vertices,[],faces);data.update()
    dome = bpy.data.objects.new('Photographic cloud hemisphere',data)
    collections['08 Sea and planting'].objects.link(dome)
    dome['geometry_kind'] = 'sky_surface';dome['collision'] = False
    for attribute in ['visible_shadow','visible_diffuse','visible_glossy','visible_transmission','visible_volume_scatter']:
        setattr(dome,attribute,False)
    mat=bpy.data.materials.new('Recovered cloud color');mat.use_nodes=True;dome.data.materials.append(mat)
    n,l=mat.node_tree.nodes,mat.node_tree.links;n.clear()
    projection=n.new('ShaderNodeGroup');projection.node_tree=group
    split=n.new('ShaderNodeSeparateXYZ');l.new(projection.outputs['UV'],split.inputs[0])
    # Remove photographed foreground structures from the sky sampling area:
    # use a clear neighboring sky column below the roof line and at the right edge.
    def op(kind,a,b):
        q=n.new('ShaderNodeMath');q.operation=kind
        for sock,value in zip(q.inputs,(a,b)):
            if isinstance(value,(int,float)):sock.default_value=value
            else:l.new(value,sock)
        return q.outputs[0]
    x,y=split.outputs['X'],split.outputs['Y']
    def rectangle(x0,x1,y0,y1):
        result=op('MULTIPLY',op('GREATER_THAN',x,x0),op('LESS_THAN',x,x1))
        result=op('MULTIPLY',result,op('GREATER_THAN',y,1-y1))
        return op('MULTIPLY',result,op('LESS_THAN',y,1-y0))
    # Local occluder areas only: preserve the original sky and mountain texture
    # everywhere else instead of replacing an entire horizontal band.
    roofs=rectangle(.474,.641,.435,.478)
    roof_right=rectangle(.898,1.001,.347,.395)
    wall_right=rectangle(.948,1.001,.395,.479)
    middle=roofs;right=op('MAXIMUM',roof_right,wall_right)
    u=op('ADD',op('MULTIPLY',x,op('SUBTRACT',1,middle)),op('MULTIPLY',middle,.68))
    u=op('ADD',op('MULTIPLY',u,op('SUBTRACT',1,right)),op('MULTIPLY',right,.88))
    skyuv=n.new('ShaderNodeCombineXYZ');l.new(u,skyuv.inputs['X']);l.new(split.outputs['Y'],skyuv.inputs['Y'])
    tex=n.new('ShaderNodeTexImage');tex.image=image;tex.extension='EXTEND';l.new(skyuv.outputs[0],tex.inputs[0])
    original=n.new('ShaderNodeTexImage');original.image=image;original.extension='EXTEND';l.new(projection.outputs['UV'],original.inputs[0])
    channels=n.new('ShaderNodeSeparateColor');channels.mode='RGB';l.new(original.outputs['Color'],channels.inputs[0])
    blue_difference=op('SUBTRACT',channels.outputs['Blue'],channels.outputs['Red'])
    neutral=op('MINIMUM',op('MAXIMUM',op('DIVIDE',op('SUBTRACT',.08,blue_difference),.06),0),1)
    neutral=op('MULTIPLY',neutral,op('MAXIMUM',middle,right))
    heal=n.new('ShaderNodeMixRGB');l.new(neutral,heal.inputs[0]);l.new(original.outputs['Color'],heal.inputs[1]);l.new(tex.outputs['Color'],heal.inputs[2])
    emission=n.new('ShaderNodeEmission');l.new(heal.outputs[0],emission.inputs['Color'])
    fallback=n.new('ShaderNodeEmission');fallback.inputs['Color'].default_value=(.35,.46,.62,1);fallback.inputs['Strength'].default_value=.7
    mix=n.new('ShaderNodeMixShader');l.new(projection.outputs['Weight'],mix.inputs[0]);l.new(fallback.outputs[0],mix.inputs[1]);l.new(emission.outputs[0],mix.inputs[2])
    out=n.new('ShaderNodeOutputMaterial');l.new(mix.outputs[0],out.inputs['Surface'])
    scene['photo_projection_enabled']=True
    scene['photo_camera']='Photo camera'
    scene['photo_projection_note']='Fixed camera projection on geometry, with an upper sky hemisphere; not an independently recovered texture or all-view photo match.'
