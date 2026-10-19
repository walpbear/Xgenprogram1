"""Strict FurBrush ASCII PLY strand interchange; positions normalized to cm/Y-up."""
from collections import OrderedDict
import math
import shlex

UNIT_CM = {'mm': 0.1, 'cm': 1.0, 'm': 100.0, 'in': 2.54, 'inch': 2.54,
           'ft': 30.48, 'yd': 91.44}


def unit_scale(unit):
    try:
        return UNIT_CM[unit.lower()]
    except KeyError:
        raise ValueError('Unsupported linear unit: {}'.format(unit))


def read_ply(path, fallback_unit='cm'):
    with open(path, 'r', encoding='utf-8-sig') as handle:
        if handle.readline().strip() != 'ply':
            raise ValueError('Not a PLY file.')
        props, layers, unit, vertex_count, active, fixed = [], {}, None, None, False, None
        ascii_format = False
        for line in handle:
            fields = shlex.split(line)
            if not fields:
                continue
            if fields[0] == 'end_header':
                break
            if fields[:2] == ['format', 'ascii']:
                ascii_format = True
            elif fields[:2] == ['element', 'vertex']:
                vertex_count, active = int(fields[2]), True
            elif fields[0] == 'element':
                active = False
            elif fields[0] == 'property' and active:
                if fields[1] == 'list':
                    raise ValueError('List vertex properties are not supported.')
                props.append(fields[2])
            elif fields[:2] == ['comment', 'sisir_unit']:
                unit = fields[2]
            elif fields[:2] == ['comment', 'points_per_strand']:
                fixed = int(fields[2])
            elif fields[:2] == ['comment', 'layer'] and len(fields) >= 4:
                layers[int(fields[2])] = fields[3]
        else:
            raise ValueError('PLY header has no end_header.')
        if not ascii_format or vertex_count is None or vertex_count < 0:
            raise ValueError('An ASCII PLY with a valid vertex count is required.')
        if len(props) != len(set(props)) or not {'x', 'y', 'z'}.issubset(props):
            raise ValueError('Vertex properties must include unique x/y/z fields.')
        if 'curve_id' not in props and (fixed is None or fixed < 2):
            raise ValueError('PLY needs curve_id or points_per_strand metadata; cannot infer strands safely.')
        factor = unit_scale(unit or fallback_unit)
        grouped = OrderedDict()
        for index in range(vertex_count):
            values = handle.readline().split()
            if len(values) != len(props):
                raise ValueError('Invalid/truncated vertex row {}.'.format(index + 1))
            row = dict(zip(props, values))
            point = tuple(float(row[k]) * factor for k in ('x', 'y', 'z'))
            if not all(math.isfinite(v) for v in point):
                raise ValueError('Non-finite curve coordinates.')
            key = (int(row.get('layer_id', 0)), int(row['curve_id']) if 'curve_id' in row else index // fixed)
            grouped.setdefault(key, []).append((point, int(row.get('anchor', 0))))
        if 'curve_id' not in props and vertex_count % fixed:
            raise ValueError('Vertex count is not divisible by points_per_strand.')
        strands = []
        for (layer_id, curve_id), points in grouped.items():
            if len(points) < 2:
                raise ValueError('Curve {} has fewer than two vertices.'.format(curve_id))
            anchors = [i for i, (_, flag) in enumerate(points) if flag]
            if anchors not in ([], [0]):
                raise ValueError('Curve {} must be root-to-tip, with its anchor first.'.format(curve_id))
            strands.append({'layer_id': layer_id, 'curve_id': curve_id,
                            'points': [p for p, _ in points]})
        return {'unit': 'cm', 'source_unit': unit or fallback_unit,
                'assumed_unit': unit is None, 'layers': layers, 'strands': strands}


def write_ply(path, strands, layers=None):
    layers = layers or {}
    for strand in strands:
        if len(strand['points']) < 2 or any(not math.isfinite(v) for p in strand['points'] for v in p):
            raise ValueError('Every strand needs at least two finite points.')
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('ply\nformat ascii 1.0\ncomment sisir_unit cm\n')
        for layer_id, name in sorted(layers.items()):
            safe = str(name).replace('"', "'").replace('\n', ' ').replace('\r', ' ')
            handle.write('comment layer {} "{}" 0.5 0.7 1 1\n'.format(layer_id, safe))
        handle.write('element vertex {}\n'.format(sum(len(s['points']) for s in strands)))
        handle.write('property float x\nproperty float y\nproperty float z\nproperty uchar anchor\n'
                     'property int layer_id\nproperty int curve_id\nend_header\n')
        for cid, strand in enumerate(strands):
            for index, p in enumerate(strand['points']):
                handle.write('{:.12g} {:.12g} {:.12g} {} {} {}\n'.format(
                    p[0], p[1], p[2], int(index == 0), strand.get('layer_id', 0), cid))


def maya_to_yup(point, up_axis='y'):
    x, y, z = point
    return (x, z, -y) if up_axis == 'z' else (x, y, z)


def yup_to_maya(point, up_axis='y'):
    x, y, z = point
    return (x, -z, y) if up_axis == 'z' else (x, y, z)


def unreal_point(point):
    # Bake the same Y/Z swap described by the native export's Unreal option:
    # X rotation -90 followed by Z scale -1. Unreal import conversion stays identity.
    return (point[0], point[2], point[1])


def quote_abc(value):
    value = str(value).replace('\\', '/')
    if any(c in value for c in ('"', '\n', '\r')):
        raise ValueError('Unsupported quote/newline in Alembic path.')
    return '"{}"'.format(value)
