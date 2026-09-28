"""World/object-anchored weathering, seawater and a fully procedural sky.

Small surface relief uses bump; silhouette details are actual geometry.
No photograph, environment image, camera-ray switch or compositing plate.
"""
import math
import bpy


def linear(rgb):
    return tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb)


class Nodes:
    def __init__(self, tree):
        self.n, self.l = tree.nodes, tree.links

    def node(self, kind, name):
        n = self.n.new(kind)
        n.label = n.name = name
        return n

    def link(self, a, b):
        self.l.new(a, b)

    def noise(self, vector, scale, detail, name):
        n = self.node('ShaderNodeTexNoise', name)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = .7
        self.link(vector, n.inputs['Vector'])
        return n.outputs['Fac']

    def ramp(self, value, stops, name):
        n = self.node('ShaderNodeValToRGB', name)
        r = n.color_ramp
        for i, (position, color) in enumerate(stops):
            e = r.elements[i] if i < 2 else r.elements.new(position)
            e.position = position
            e.color = (*color, 1)
        self.link(value, n.inputs[0])
        return n.outputs['Color']

    def math(self, operation, a, b, name):
        n = self.node('ShaderNodeMath', name)
        n.operation = operation
        for value, socket in zip((a, b), n.inputs):
            if isinstance(value, (int, float)):
                socket.default_value = value
            else:
                self.link(value, socket)
        return n.outputs[0]

    def mix(self, a, b, factor, name, blend='MIX'):
        n = self.node('ShaderNodeMixRGB', name)
        n.blend_type = blend
        if isinstance(factor, (int, float)):
            n.inputs[0].default_value = factor
        else:
            self.link(factor, n.inputs[0])
        for value, socket in ((a, n.inputs[1]), (b, n.inputs[2])):
            if isinstance(value, tuple):
                socket.default_value = (*value, 1)
            else:
                self.link(value, socket)
        return n.outputs[0]


def weather(material, dark=.65, grain=.003):
    g = Nodes(material.node_tree)
    bs = material.node_tree.nodes.get('Principled BSDF')
    tc = g.node('ShaderNodeTexCoord', 'Metric object coordinates')
    v = tc.outputs['Object']
    base = bs.inputs['Base Color']
    original = base.links[0].from_socket if base.is_linked else tuple(base.default_value[:3])
    broad = g.noise(v, .38, 3, 'Salt and wear — meters')
    fine = g.noise(v, 65, 2, 'Mineral grain — millimeters')
    stain = g.ramp(broad, [(.22,(dark,dark,dark)),(.78,(1,1,1))], 'Uneven surface aging')
    color = g.mix(original, stain, 1, 'Pigment multiplied by weathering', 'MULTIPLY')
    g.link(color, base)
    rough = g.ramp(fine, [(.15,(.56,)*3),(.85,(.91,)*3)], 'Roughness variation')
    g.link(rough, bs.inputs['Roughness'])
    bump = g.node('ShaderNodeBump', 'Fine relief, not displaced geometry')
    bump.inputs['Distance'].default_value = grain
    bump.inputs['Strength'].default_value = .4
    g.link(fine, bump.inputs['Height'])
    g.link(bump.outputs[0], bs.inputs['Normal'])
    return g, bs, v, bump


def paving():
    m = bpy.data.materials['Metric checker paving — world anchored']
    checker = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeTexChecker')
    checker.inputs['Color1'].default_value = (*linear((.27,.25,.26)),1)
    checker.inputs['Color2'].default_value = (*linear((.65,.60,.58)),1)
    g, bs, v, bump = weather(m, .32, .005)
    vector = checker.inputs['Vector'].links[0].from_socket
    brick = g.node('ShaderNodeTexBrick', 'Small rectangular paving joints')
    brick.offset = .5
    brick.offset_frequency = 2
    brick.inputs['Scale'].default_value = 1
    brick.inputs['Brick Width'].default_value = .27
    brick.inputs['Row Height'].default_value = .18
    brick.inputs['Mortar Size'].default_value = .003
    brick.inputs['Mortar Smooth'].default_value = .001
    brick.inputs['Color1'].default_value = (.65,.65,.65,1)
    brick.inputs['Color2'].default_value = (1,1,1,1)
    brick.inputs['Mortar'].default_value = (.18,.18,.18,1)
    g.link(vector, brick.inputs['Vector'])
    current = bs.inputs['Base Color'].links[0].from_socket
    # Joints show strongly on light pavers and only faintly on dark infill.
    amount = g.math('ADD', g.math('MULTIPLY',g.math('SUBTRACT',1,checker.outputs['Fac'],'Light paver mask'),.8,'Light pavers'), .12, 'Joint visibility')
    # Dark areas keep mostly asphalt grain.
    joint_color = g.mix((1,1,1), brick.outputs['Color'], amount, 'Paver joints mask')
    g.link(g.mix(current,joint_color,1,'Paver tint','MULTIPLY'), bs.inputs['Base Color'])
    joint = g.node('ShaderNodeBump', 'Recessed paving joints')
    joint.invert = True
    joint.inputs['Distance'].default_value = .0025
    joint.inputs['Strength'].default_value = .65
    g.link(brick.outputs['Fac'], joint.inputs['Height'])
    g.link(bump.outputs[0], joint.inputs['Normal'])
    g.link(joint.outputs[0], bs.inputs['Normal'])


def sea():
    m = bpy.data.materials['Sea base material']
    m.node_tree.nodes.clear()
    g = Nodes(m.node_tree)
    bs = g.node('ShaderNodeBsdfPrincipled','Water surface')
    out = g.node('ShaderNodeOutputMaterial','Water output')
    g.link(bs.outputs[0],out.inputs['Surface'])
    bs.inputs['Base Color'].default_value = (*linear((.18,.29,.34)),1)
    bs.inputs['Metallic'].default_value = 0
    bs.inputs['Roughness'].default_value = .26
    bs.inputs['IOR'].default_value = 1.333
    bs.inputs['Transmission Weight'].default_value = .12
    tc = g.node('ShaderNodeTexCoord','World anchored sea ripples')
    stretch = g.node('ShaderNodeVectorMath','Wind stretched wave pattern')
    stretch.operation = 'MULTIPLY'
    stretch.inputs[1].default_value = (.65,2.8,1)
    g.link(tc.outputs['Object'],stretch.inputs[0])
    macro = g.noise(stretch.outputs[0], .55, 2, 'Low harbor swell')
    micro = g.noise(stretch.outputs[0], 7, 2, 'Small wind ripples')
    b1 = g.node('ShaderNodeBump','Harbor swell normal')
    b1.inputs['Distance'].default_value = .26
    b1.inputs['Strength'].default_value = .6
    g.link(macro,b1.inputs['Height'])
    b2 = g.node('ShaderNodeBump','Wind ripples normal')
    b2.inputs['Distance'].default_value = .018
    b2.inputs['Strength'].default_value = .45
    g.link(micro,b2.inputs['Height'])
    g.link(b1.outputs[0],b2.inputs['Normal'])
    g.link(b2.outputs[0],bs.inputs['Normal'])


def sky(scene):
    world = scene.world
    world.name = 'Procedural overcast maritime sky'
    world.node_tree.nodes.clear()
    g = Nodes(world.node_tree)
    tc = g.node('ShaderNodeTexCoord','Fixed world direction')
    separate = g.node('ShaderNodeSeparateXYZ','Elevation above horizon')
    g.link(tc.outputs['Normal'],separate.inputs[0])
    # World Normal points into the world surface, opposite the outgoing ray.
    z = g.math('MULTIPLY',separate.outputs['Z'],-1,'Outgoing sky elevation')
    clear = g.ramp(z, [
        (0,linear((.98,.94,.82))),
        (.10,linear((.65,.79,.99))),
        (.5,linear((.54,.68,.91))),
        (1,linear((.45,.61,.86))),
    ], 'Warm horizon to blue zenith')
    # Intersect the fixed world direction with a horizontal cloud layer.
    # Perspective compression forms thin cloud bands toward the horizon.
    # This is analytic procedural sky shading, with no image or camera input.
    height = g.math('MAXIMUM',z,.025,'Cloud horizon denominator')
    distance = g.math('DIVIDE',1,height,'Distance to flat cloud layer')
    mapping = g.node('ShaderNodeVectorMath','World cloud layer coordinates')
    mapping.operation = 'SCALE'
    g.link(tc.outputs['Normal'],mapping.inputs[0])
    g.link(distance,mapping.inputs['Scale'])
    broad = g.noise(mapping.outputs[0], .85, 3, 'Large overcast cloud banks')
    fine = g.noise(mapping.outputs[0], 6, 3, 'Cloud edge detail')
    density = g.math('ADD',g.math('MULTIPLY',broad,.82,'Cloud banks weight'),g.math('MULTIPLY',fine,.18,'Cloud detail weight'),'Layered cloud density')
    cover = g.ramp(density,[(.38,(0,)*3),(.50,(.95,)*3),(.60,(1,)*3)],'Soft broken cloud cover')
    horizon = g.ramp(z,[(0,(0,)*3),(.035,(0,)*3),(.085,(1,)*3)],'Clear bright band near horizon')
    mask = g.mix(cover,horizon,1,'Cloud cover fades at horizon','MULTIPLY')
    cloud_color = g.ramp(density,[(.33,linear((.44,.52,.69))),(.62,linear((.27,.34,.49)))],'Blue gray cloud underside')
    color = g.mix(clear,cloud_color,mask,'Atmosphere and clouds')
    bg = g.node('ShaderNodeBackground','Diffuse sky illumination')
    bg.inputs['Strength'].default_value = .8
    g.link(color,bg.inputs['Color'])
    out = g.node('ShaderNodeOutputWorld','World output')
    g.link(bg.outputs[0],out.inputs['Surface'])
    sun = bpy.data.lights['Broad daylight sun']
    sun.energy = .16
    sun.angle = math.radians(20)
    sun.color = (1,.95,.9)
    # Broad warm skylight from the open sky behind the observer.
    # A real light affects all surfaces and cameras consistently.
    fill_data=bpy.data.lights.new('Open sky soft fill','AREA')
    fill_data.energy=2200
    fill_data.shape='DISK'
    fill_data.size=45
    fill_data.color=(1,.86,.77)
    fill=bpy.data.objects.new(fill_data.name,fill_data)
    bpy.data.collections['09 Cameras and lighting'].objects.link(fill)
    fill.location=(0,15,28)
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = .8


def apply_surfaces(scene):
    paving()
    for name,dark,grain in [
        ('Weathered concrete',.58,.004),
        ('Quay concrete and salt marks',.45,.007),
        ('Pavilion ceramic tile',.72,.0008),
        ('Bench weathered timber',.48,.002),
    ]:
        weather(bpy.data.materials[name],dark,grain)
    # Metal stays relatively smooth; oxide and paint are not bare metal.
    for name in ('Marine blue painted rail','Ferry and railing ivory white','Ferry red orange trim'):
        bs = bpy.data.materials[name].node_tree.nodes.get('Principled BSDF')
        bs.inputs['Metallic'].default_value = 0
    # Atmospheric scattering approximation on distant terrain only.
    land = bpy.data.materials['Distant hazy land'].node_tree.nodes.get('Principled BSDF')
    land.inputs['Base Color'].default_value = (*linear((.42,.53,.67)),1)
    land.inputs['Emission Color'].default_value = (*linear((.40,.52,.69)),1)
    land.inputs['Emission Strength'].default_value = .55
    sea()
    sky(scene)
