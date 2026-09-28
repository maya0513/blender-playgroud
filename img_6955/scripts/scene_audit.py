"""Inspect all shader/compositor trees, including nested and unused groups.

This project deliberately uses no image textures, camera-driven coordinates,
image planes or external linked libraries. A photograph may only live outside
of the scene as a human comparison reference.
"""
import bpy


def audit_scene(scene):
    errors = []
    seen = set()
    node_count = 0

    def inspect(tree):
        nonlocal node_count
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            node_count += 1
            if getattr(node, 'image', None) is not None or node.bl_idname in {
                'ShaderNodeTexImage', 'ShaderNodeTexEnvironment', 'CompositorNodeImage',
                'CompositorNodeMovieClip', 'ShaderNodeCameraData', 'ShaderNodeLightPath',
            }:
                errors.append({'kind': 'forbidden_image_or_view_dependency', 'tree': tree.name, 'node': node.name})
            if node.bl_idname == 'ShaderNodeTexCoord':
                for name in ('Camera', 'Window', 'Reflection'):
                    if node.outputs[name].is_linked:
                        errors.append({'kind': 'view_dependent_coordinates', 'tree': tree.name, 'socket': name})
                if node.object and node.object.type == 'CAMERA':
                    errors.append({'kind': 'camera_coordinate_anchor', 'tree': tree.name})
            inspect(getattr(node, 'node_tree', None))
        if tree.animation_data and tree.animation_data.drivers:
            errors.append({'kind': 'shader_drivers', 'tree': tree.name})

    for block in list(bpy.data.materials) + list(bpy.data.worlds) + list(bpy.data.scenes):
        inspect(getattr(block, 'node_tree', None))
        inspect(getattr(block, 'compositing_node_group', None))
    for tree in bpy.data.node_groups:
        inspect(tree)
    for obj in scene.objects:
        if obj.get('photo_projection') or 'projector' in obj.name.lower() or 'photographic' in obj.name.lower():
            errors.append({'kind': 'projection_object', 'object': obj.name})
        if obj.type == 'EMPTY' and obj.empty_display_type == 'IMAGE':
            errors.append({'kind': 'image_object', 'object': obj.name})
        for modifier in obj.modifiers:
            if modifier.type == 'UV_PROJECT':
                errors.append({'kind': 'uv_projection', 'object': obj.name})
    if scene.get('photo_projection_enabled') is not False:
        errors.append({'kind': 'projection_flag'})
    if any(image.source in {'FILE', 'MOVIE', 'SEQUENCE'} for image in bpy.data.images):
        errors.append({'kind': 'external_image_in_scene'})
    if bpy.data.libraries:
        errors.append({'kind': 'external_library'})
    return {'status': 'PASS' if not errors else 'FAIL', 'node_trees_checked': len(seen),
            'nodes_checked': node_count, 'errors': errors,
            'policy': 'No image textures, photographic background, image composite, projection or camera-dependent shader branches.'}
