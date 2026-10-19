"""Maya-only adapters. No external Python dependencies; requires Maya Python 3."""
import contextlib
import hashlib
import json
import os
import tempfile
import traceback
from collections import OrderedDict

import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om

from . import ply_io


def _plugin(name):
    try:
        if not cmds.pluginInfo(name, query=True, loaded=True):
            cmds.loadPlugin(name, quiet=True)
    except RuntimeError as exc:
        raise RuntimeError('Maya plugin {} is required: {}'.format(name, exc))


def _shapes(nodes=None, node_type='nurbsCurve'):
    found = set()
    for node in nodes if nodes is not None else (cmds.ls(selection=True, long=True) or []):
        node = node.split('.')[0]
        if cmds.nodeType(node) == node_type:
            found.add((cmds.ls(node, long=True) or [node])[0])
        for child in cmds.listRelatives(node, allDescendents=True, fullPath=True, type=node_type) or []:
            found.add(child)
    return [s for s in sorted(found) if not cmds.attributeQuery('intermediateObject', node=s, exists=True)
            or not cmds.getAttr(s + '.intermediateObject')]


def _dag(node):
    selection = om.MSelectionList()
    selection.add(node)
    return selection.getDagPath(0)


@contextlib.contextmanager
def _edit(label):
    cmds.undoInfo(openChunk=True, chunkName=label)
    try:
        yield
    finally:
        cmds.undoInfo(closeChunk=True)


def _points(shape, count):
    fn = om.MFnNurbsCurve(_dag(shape))
    if fn.form != om.MFnNurbsCurve.kOpen:
        raise ValueError('Hair strands must be open curves: {}'.format(shape))
    length = fn.length()
    if length <= 1e-8:
        raise ValueError('Zero-length curve: {}'.format(shape))
    points = []
    for i in range(count):
        parameter = fn.findParamFromLength(length * i / float(count - 1))
        p = fn.getPointAtParam(parameter, om.MSpace.kWorld)
        points.append((p.x, p.y, p.z))  # Maya API positions are internal centimeters.
    return points


def collect_curves(samples=32):
    if samples < 2 or samples > 255:
        raise ValueError('Use 2 to 255 points per strand; check your Unreal platform limits.')
    shapes = _shapes()
    if not shapes:
        raise ValueError('Select curves or a group containing curves. Convert XGen first if needed.')
    up_axis = cmds.upAxis(query=True, axis=True)
    strands = []
    for index, shape in enumerate(shapes):
        parent = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        layer = cmds.getAttr(parent + '.furBrushLayerId') if cmds.attributeQuery('furBrushLayerId', node=parent, exists=True) else 0
        world = _points(shape, samples)
        strands.append({'shape': shape, 'curve_id': index, 'layer_id': int(layer),
                        'points_world_cm': world,
                        'points': [ply_io.maya_to_yup(p, up_axis) for p in world]})
    return strands


def import_ply(path, fallback_unit='cm'):
    data = ply_io.read_ply(path, fallback_unit)
    if not data['strands']:
        raise ValueError('The PLY contains no strands.')
    scene_factor = ply_io.unit_scale(cmds.currentUnit(query=True, linear=True))
    up = cmds.upAxis(query=True, axis=True)
    root = None
    with _edit('Import FurBrush guides'):
        try:
            root = cmds.group(empty=True, name='FurBrush_Guides#')
            cmds.addAttr(root, longName='furBrushSource', dataType='string')
            cmds.setAttr(root + '.furBrushSource', os.path.abspath(path), type='string')
            groups = {}
            for strand in data['strands']:
                lid = strand['layer_id']
                if lid not in groups:
                    # Keep arbitrary user layer labels as metadata, not Maya node names.
                    groups[lid] = cmds.group(empty=True, name='FurBrush_Layer_{}#'.format(abs(lid)), parent=root)
                    cmds.addAttr(groups[lid], longName='furBrushLayerName', dataType='string')
                    cmds.setAttr(groups[lid] + '.furBrushLayerName', data['layers'].get(lid, 'Layer {}'.format(lid)), type='string')
                positions = [tuple(v / scene_factor for v in ply_io.yup_to_maya(p, up)) for p in strand['points']]
                curve = cmds.curve(degree=1, point=positions, name='FurBrush_Guide#')
                curve = cmds.parent(curve, groups[lid])[0]
                cmds.addAttr(curve, longName='furBrushLayerId', attributeType='long')
                cmds.setAttr(curve + '.furBrushLayerId', lid)
            cmds.select(root, replace=True)
        except Exception:
            if root and cmds.objExists(root):
                cmds.delete(root)
            raise
    return root, data


def export_ply(path, samples=32):
    strands = collect_curves(samples)
    # Match file snapshots atomically; never leave a partially written target.
    fd, temporary = tempfile.mkstemp(suffix='.ply', dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    try:
        ply_io.write_ply(temporary, strands)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(strands)


def interactive_groom_to_curves():
    """Use Maya's own installed XGen conversion; preserve the description graph."""
    _plugin('xgenToolkit')
    descriptions = _shapes(node_type='xgmSplineDescription')
    if len(descriptions) != 1:
        raise ValueError('Select exactly one Interactive Groom description transform/shape.')
    description = descriptions[0]
    before = set(cmds.ls(type='nurbsCurve', long=True) or [])
    with _edit('XGen groom to FurBrush curves'):
        try:
            cmds.xgmSplineToCurves(splineDescription=description)
        except (RuntimeError, AttributeError) as exc:
            raise RuntimeError('This Maya XGen conversion command was not supported. Use the Interactive Groom editor: select the description and use its built-in Convert to Curves operation. Original error: {}'.format(exc))
    after = set(cmds.ls(type='nurbsCurve', long=True) or [])
    created = sorted(after - before)
    if not created:
        raise RuntimeError('Maya created no curve shapes. Check groom visibility/density and XGen evaluation.')
    transforms = sorted({cmds.listRelatives(s, parent=True, fullPath=True)[0] for s in created})
    cmds.select(transforms, replace=True)
    return len(created)


def create_interactive_from_curves():
    """Experimental curve-driven description, not a recreated bound groom graph."""
    _plugin('xgenToolkit')
    shapes = _shapes()
    if not shapes:
        raise ValueError('Select the imported guide curves/group first.')
    types = set(cmds.allNodeTypes())
    if not {'xgmCurveToSpline', 'xgmSplineDescription'}.issubset(types):
        raise RuntimeError('This Maya build does not expose the required curve-to-spline nodes. Keep the imported NURBS curves and use Maya\'s native XGen guide conversion tools.')
    created = []
    with _edit('FurBrush curves to Interactive Groom'):
        try:
            converter = cmds.createNode('xgmCurveToSpline', name='FurBrush_CurveInput#')
            created.append(converter)
            shape = cmds.createNode('xgmSplineDescription', name='FurBrush_DescriptionShape#')
            parent = cmds.listRelatives(shape, parent=True, fullPath=True)
            created.append(parent[0] if parent else shape)
            required = [(converter, 'inputCurves'), (converter, 'outputSplineData'), (shape, 'inSplineData')]
            if not all(cmds.attributeQuery(attr, node=node, exists=True) for node, attr in required):
                raise RuntimeError('Installed XGen node schema differs; automatic conversion was cancelled. Imported curves were retained.')
            for index, source in enumerate(shapes):
                cmds.connectAttr(source + '.worldSpace[0]', converter + '.inputCurves[{}]'.format(index))
            cmds.connectAttr(converter + '.outputSplineData', shape + '.inSplineData')
            cmds.select(parent or [shape], replace=True)
            return parent[0] if parent else shape
        except Exception:
            for node in reversed(created):
                if cmds.objExists(node):
                    cmds.delete(node)
            raise


def _string_attr(node, name, value):
    cmds.addAttr(node, longName=name, dataType='string')
    cmds.setAttr(node + '.' + name, value, type='string')


def _array_attr(node, name, kind, values, scope='uni', abc_type=None):
    cmds.addAttr(node, longName=name, dataType=kind)
    selection = om.MSelectionList()
    selection.add(node + '.' + name)
    plug = selection.getPlug(0)
    if kind == 'Int32Array':
        data = om.MFnIntArrayData().create(om.MIntArray(values))
    elif kind == 'vectorArray':
        data = om.MFnVectorArrayData().create(om.MVectorArray([om.MVector(*v) for v in values]))
    else:
        raise ValueError('Unsupported groom array type: ' + kind)
    plug.setMObject(data)
    _string_attr(node, name + '_AbcGeomScope', scope)
    if abc_type:
        _string_attr(node, name + '_AbcType', abc_type)


def _dag_curve_order(root):
    iterator = om.MItDag(om.MItDag.kDepthFirst, om.MFn.kNurbsCurve)
    iterator.reset(_dag(root), om.MItDag.kDepthFirst, om.MFn.kNurbsCurve)
    shapes = []
    while not iterator.isDone():
        dag = iterator.getPath()
        if not om.MFnDagNode(dag).isIntermediateObject:
            shapes.append(dag.fullPathName())
        iterator.next()
    return shapes


def _scalp_mesh(node):
    if cmds.nodeType(node) == 'mesh':
        shapes = [node]
    else:
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True, type='mesh') or []
    shapes = [s for s in shapes if not cmds.getAttr(s + '.intermediateObject')]
    if len(shapes) != 1:
        raise ValueError('Root UV target must resolve to exactly one non-intermediate mesh shape.')
    fn = om.MFnMesh(_dag(shapes[0]))
    uv_set = fn.currentUVSetName()
    if not uv_set or fn.numUVs(uv_set) == 0:
        raise ValueError('The scalp mesh has no UVs in its active UV set.')
    return fn, uv_set


def export_unreal(path, samples=32, scalp=None, width_cm=0.01, base_group_id=0):
    """Static curves snapshot with standard widths, group/guide IDs and optional UVs."""
    if width_cm <= 0 or base_group_id < 0:
        raise ValueError('Width must be positive and group ID nonnegative.')
    _plugin('AbcExport')
    strands = collect_curves(samples)
    scalp_info = _scalp_mesh(scalp) if scalp else None
    old_selection = cmds.ls(selection=True, long=True) or []
    scene_factor = ply_io.unit_scale(cmds.currentUnit(query=True, linear=True))
    stage = None
    fd, temporary = tempfile.mkstemp(suffix='.abc', dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    try:
        with _edit('Export FurBrush Unreal groom'):
            try:
                stage = cmds.group(empty=True, name='FurBrush_ExportStage#')
                staged = {}
                for strand in strands:
                    converted = [tuple(v / scene_factor for v in ply_io.unreal_point(p)) for p in strand['points']]
                    curve = cmds.curve(degree=1, point=converted, name='FurBrush_ExportStrand#')
                    curve = cmds.parent(curve, stage)[0]
                    shape = cmds.listRelatives(curve, shapes=True, fullPath=True, type='nurbsCurve')[0]
                    staged[shape] = strand
                ordered = [staged[s] for s in _dag_curve_order(stage)]
                if len(ordered) != len(strands):
                    raise RuntimeError('Staged Alembic curve order/count mismatch.')
                # Official Alembic Maya exporter groups matching curve shapes when riCurves is set.
                cmds.addAttr(stage, longName='riCurves', attributeType='bool')
                cmds.setAttr(stage + '.riCurves', True)
                cmds.addAttr(stage, longName='width', attributeType='float')
                cmds.setAttr(stage + '.width', width_cm)
                ids = [base_group_id + s['layer_id'] for s in ordered]
                if min(ids) < 0:
                    raise ValueError('Computed groom group IDs must be nonnegative.')
                _array_attr(stage, 'groom_group_id', 'Int32Array', ids)
                # Selected curves are render strands; no new dense hair is synthesized.
                _array_attr(stage, 'groom_guide', 'Int32Array', [0] * len(ordered))
                if scalp_info:
                    mesh, uv_set = scalp_info
                    uv = []
                    for strand in ordered:
                        closest, _ = mesh.getClosestPoint(om.MPoint(*strand['points_world_cm'][0]), om.MSpace.kWorld)
                        u, v = mesh.getUVAtPoint(closest, om.MSpace.kWorld, uv_set)
                        uv.append((u, v, 0.0))
                    _array_attr(stage, 'groom_root_uv', 'vectorArray', uv, abc_type='vector2')
                frame = cmds.currentTime(query=True)
                root_path = (cmds.ls(stage, long=True) or [stage])[0]
                job = '-frameRange {0} {0} -dataFormat ogawa -worldSpace -attr groom_group_id -attr groom_guide -attr groom_root_uv -root {1} -file {2}'.format(frame, ply_io.quote_abc(root_path), ply_io.quote_abc(temporary))
                cmds.AbcExport(j=job)
            finally:
                if stage and cmds.objExists(stage):
                    cmds.delete(stage)
                valid = [n for n in old_selection if cmds.objExists(n)]
                if valid:
                    cmds.select(valid, replace=True)
                else:
                    cmds.select(clear=True)
        with open(temporary, 'rb') as handle:
            if handle.read(5) != b'Ogawa':
                raise RuntimeError('Alembic export did not produce an Ogawa archive.')
        os.replace(temporary, path)
        report = {'format': 'Unreal Alembic Groom', 'static_frame': frame,
                  'strand_count': len(strands), 'points_per_strand': samples,
                  'width_cm': width_cm, 'coordinate_space': 'Unreal Z-up; Y/Z swapped from Maya Y-up',
                  'import_conversion': {'rotation': [0, 0, 0], 'scale': [1, 1, 1]},
                  'root_uv_exported': bool(scalp_info), 'group_ids': sorted(set(ids)),
                  'note': 'Selected curves exported as render strands. No interpolation/density generation or rig binding was performed.'}
        with open(path, 'rb') as handle:
            report['sha256'] = hashlib.sha256(handle.read()).hexdigest()
        with open(path + '.furbrush.json', 'w', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        return report
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _run(action):
    try:
        value = action()
        if value is not None:
            cmds.inViewMessage(amg='FurBrush operation completed. See Script Editor for details.', pos='topCenter', fade=True)
            print(value)
    except Exception as exc:
        traceback.print_exc()
        cmds.confirmDialog(title='FurBrush bridge', message=str(exc), button=['OK'])


def show():
    window = 'FurBrushMayaBridge'
    if cmds.window(window, exists=True):
        cmds.deleteUI(window)
    cmds.window(window, title='FurBrush - Maya / XGen / Unreal', widthHeight=(470,650), sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=('both',12))
    cmds.text(label='FurBrush guide and groom interchange', align='left', height=28)
    samples = cmds.intSliderGrp(label='Samples per curve', field=True, minValue=2, maxValue=128, fieldMaxValue=255, value=32)
    units = cmds.optionMenuGrp(label='PLY fallback unit')
    for unit in ['cm','mm','m','in','ft']:
        cmds.menuItem(label=unit)
    cmds.text(label='Fallback is used only if the PLY has no unit tag.', align='left')
    def choose(mode, ext):
        result = cmds.fileDialog2(fileMode=mode, fileFilter='{} files (*.{})'.format(ext.upper(),ext), dialogStyle=2)
        if not result:
            return None
        return result[0] if result[0].lower().endswith('.'+ext) else result[0]+'.'+ext
    def load_ply():
        path = choose(1,'ply')
        if path:
            root, data = import_ply(path,cmds.optionMenuGrp(units,query=True,value=True))
            return 'Imported {} curves into {} (source unit: {}{}).'.format(len(data['strands']),root,data['source_unit'],'; assumed' if data['assumed_unit'] else '')
    def save_ply():
        path = choose(0,'ply')
        if path:
            return export_ply(path,cmds.intSliderGrp(samples,query=True,value=True))
    cmds.button(label='Import FurBrush PLY as Maya curves', command=lambda *_:_run(load_ply))
    cmds.button(label='Export selected Maya curves to FurBrush PLY', command=lambda *_:_run(save_ply))
    cmds.separator(height=14)
    cmds.text(label='XGen Interactive Groom', align='left')
    cmds.button(label='Convert selected Interactive Groom to curves', command=lambda *_:_run(interactive_groom_to_curves))
    cmds.button(label='Create curve-driven Interactive Groom (experimental)', command=lambda *_:_run(create_interactive_from_curves))
    cmds.text(label='Classic XGen: use Utilities > Curves To Guides on imported curves.\nCurve-driven conversion does not rebuild scalp binding or modifiers.', align='left')
    cmds.separator(height=14)
    cmds.text(label='Unreal Engine - static Alembic Groom', align='left')
    scalp = cmds.textFieldButtonGrp(label='Scalp mesh (optional)', buttonLabel='Use selected')
    def set_scalp(*_):
        selection = cmds.ls(selection=True,long=True) or []
        if len(selection)!=1:
            cmds.warning('Select one scalp mesh, then click Use selected. Afterwards select the hair curves.')
            return
        cmds.textFieldButtonGrp(scalp,edit=True,text=selection[0])
    cmds.textFieldButtonGrp(scalp,edit=True,buttonCommand=set_scalp)
    width = cmds.floatFieldGrp(label='Strand width (cm)',numberOfFields=1,value1=0.01,precision=4)
    group = cmds.intFieldGrp(label='Base groom group ID',numberOfFields=1,value1=0)
    def save_abc():
        path = choose(0,'abc')
        if path:
            return export_unreal(path,cmds.intSliderGrp(samples,query=True,value=True),cmds.textFieldButtonGrp(scalp,query=True,text=True).strip() or None,cmds.floatFieldGrp(width,query=True,value1=True),cmds.intFieldGrp(group,query=True,value1=True))
    cmds.button(label='Export selected curves as Unreal Groom .abc', height=34, command=lambda *_:_run(save_abc))
    cmds.text(label='Exports the current frame and selected strands only.\nFor dense hair, convert/generate the full XGen groom first.\nIn Unreal enable Groom + Alembic Groom Importer, then import .abc.\nThis export already bakes orientation: use identity import conversion.',align='left')
    def smoke():
        from . import smoke_check
        return smoke_check.run()
    cmds.separator(height=12)
    cmds.button(label='Run Maya bridge smoke check', command=lambda *_:_run(smoke))
    cmds.showWindow(window)
    return window
