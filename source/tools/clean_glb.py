# Cleans a .glb of a door (for example a roll-up garage door with a drum, a chain, a track and 40 slats) so MLO Creator can use it: removes the extra parts, joins the rest into ONE mesh,
# sets a real-world size, puts the origin at the bottom centre, applies every transform, and exports a new .glb next to the original (which is never touched). The author and licence of
# the original (asset.extras, which Blender drops) are copied into the new file, so the credit still goes into the README of the export. It can also render a picture before and after.
#
#   blender --background --python tools\clean_glb.py -- --in door.glb [--out door_clean.glb] [--drop "drum|chain|track"] [--keep "slat|panel"] [--width 2.4] [--height 2.1] [--depth 0.05]
#                                                       [--rotate-z 90] [--straighten] [--preview-before before.png] [--preview after.png] [--list]
#
# --preview-only   only render the --preview-before pictures of the file as it is, change nothing
# --list      only print the objects (name, size) of the file, so you can decide what to drop
# --drop      objects whose name matches this regular expression (case does not matter) are deleted
# --keep      only objects whose name matches are kept (everything else is deleted)
# --width / --height / --depth   the size in metres of what is left (width = x, depth = y, height = z); with only one given, everything is scaled alike
# --straighten   turn what is left about the vertical so its long horizontal side lies along x (a door leaf saved swung open becomes a closed door)
# --rotate-z  turn what is left about the vertical (degrees) before sizing, to bring the door's width onto x
import bpy, sys, os, re, json, struct, math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def opt(name, default=None, cast=str):
    if name in argv:
        i = argv.index(name); return cast(argv[i + 1]) if i + 1 < len(argv) else default
    return default
src = opt('--in'); assert src and os.path.isfile(src), 'give --in file.glb'
out = opt('--out') or os.path.join(os.path.dirname(os.path.abspath(src)), os.path.splitext(os.path.basename(src))[0] + '_clean.glb')
assert os.path.abspath(out).lower() != os.path.abspath(src).lower(), 'the output must not be the original'
drop, keep = opt('--drop'), opt('--keep'); W, H, D = opt('--width', None, float), opt('--height', None, float), opt('--depth', None, float); rotz = opt('--rotate-z', 0.0, float)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
for o in bpy.context.scene.objects: o.animation_data_clear()          # (animations are not used: the parts stay in the pose they are imported in, and nothing moves them back when the transforms are applied)
for a in list(bpy.data.actions): bpy.data.actions.remove(a)
meshes = lambda: [o for o in bpy.context.scene.objects if o.type == 'MESH']
def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))

if '--list' in argv:
    bpy.context.view_layer.update()
    for o in meshes():
        lo, hi = bbox([o]); print('OBJECT %-40s size %.3f x %.3f x %.3f   at z %.3f..%.3f   %d tris' % (o.name, hi.x - lo.x, hi.y - lo.y, hi.z - lo.z, lo.z, hi.z, sum(len(p.vertices) - 2 for p in o.data.polygons)))
    lo, hi = bbox(meshes()); print('WHOLE FILE size %.3f x %.3f x %.3f' % (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)); sys.exit(0)

# a picture of the scene (the front and a three-quarter view, flat shaded) to check by eye
def render(path):
    if not path: return
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = 900; sc.render.resolution_y = 600
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'TEXTURE' if bpy.data.images else 'MATERIAL'; sh.show_object_outline = True
    bpy.context.view_layer.update(); lo, hi = bbox(meshes()); ctr = (lo + hi) / 2; size = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = 'ORTHO'; cam.data.ortho_scale = size * 1.9; cam.data.clip_start = size * 0.01; cam.data.clip_end = size * 20
    base, ext = os.path.splitext(path)
    for tag, d in (('front', Vector((0, -1, 0))), ('side', Vector((-0.8, -0.6, 0.45)))):
        d = d.normalized(); cam.location = ctr - d * size * 3; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = base + '_' + tag + ext; bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
render(opt('--preview-before'))
if '--preview-only' in argv: sys.exit(0)

# bake every transform first (the parents carry the file's rotation and scale), then delete what is not wanted
ms = meshes(); assert ms, 'the file has no meshes'
bpy.ops.object.select_all(action='DESELECT')
for o in ms: o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
bpy.ops.object.make_single_user(object=True, obdata=True)
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM'); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(meshes()):
    if (drop and re.search(drop, o.name, re.I)) or (keep and not re.search(keep, o.name, re.I)): bpy.data.objects.remove(o, do_unlink=True)
for o in [o for o in bpy.context.scene.objects if o.type != 'MESH']: bpy.data.objects.remove(o, do_unlink=True)
ms = meshes(); assert ms, 'nothing is left after --drop / --keep'
bpy.ops.object.select_all(action='DESELECT')
for o in ms: o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
bpy.ops.object.join(); door = bpy.context.active_object; door.name = os.path.splitext(os.path.basename(out))[0]; door.rotation_mode = 'XYZ'; print('JOINED dims', tuple(round(v, 3) for v in door.dimensions))
if rotz: door.rotation_euler.z = math.radians(rotz); bpy.ops.object.transform_apply(rotation=True)
if '--straighten' in argv:
    # a door leaf saved in an open pose: turn it about the vertical so its long horizontal side lies along x (the way a closed door lies in its frame)
    import numpy as np
    xy = np.array([[v.co.x, v.co.y] for v in door.data.vertices]); xy -= xy.mean(axis=0); cov = np.cov(xy.T); ang = 0.5 * math.atan2(2 * cov[0, 1], cov[0, 0] - cov[1, 1])
    door.rotation_euler.z = -ang; bpy.ops.object.transform_apply(rotation=True); print('STRAIGHTENED by %.1f degrees' % math.degrees(-ang))
bpy.context.view_layer.update(); lo, hi = bbox([door]); dims = hi - lo
sx = (W / dims.x) if W else None; sz = (H / dims.z) if H else None; sy = (D / dims.y) if D else None
base = sx or sz or sy or 1.0; door.scale = Vector((sx or base, sy or base, sz or base)); bpy.ops.object.transform_apply(scale=True)
bpy.context.view_layer.update(); lo, hi = bbox([door]); door.location = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)); bpy.ops.object.transform_apply(location=True)   # origin at the bottom centre
bpy.context.view_layer.update(); lo, hi = bbox([door]); print('RESULT size %.3f x %.3f x %.3f (width x depth x height), origin at the bottom centre, %d triangles' % (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z, sum(len(p.vertices) - 2 for p in door.data.polygons)))
render(opt('--preview'))
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True, use_selection=False)

# the author and licence of the original go into the new file
def glb_json(path):
    b = open(path, 'rb').read(); l, t = struct.unpack_from('<II', b, 12); return b, l, t, json.loads(b[20:20 + l])
_, _, _, j0 = glb_json(src); extras = (j0.get('asset') or {}).get('extras')
b, l, t, j = glb_json(out)
if extras is not None: j.setdefault('asset', {})['extras'] = dict(extras, changes='cleaned copy for MLO Creator: extra parts removed, joined into one mesh, resized, origin at the bottom centre')
js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4); rest = b[20 + l:]
open(out, 'wb').write(b[:8] + struct.pack('<I', 12 + 8 + len(js) + len(rest)) + struct.pack('<II', len(js), t) + js + rest)
print('WRITTEN', out, '(credit kept: %s)' % bool(extras))
