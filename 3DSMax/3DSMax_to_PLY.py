"""Sisir guide exporter for 3ds Max Python.

Run this inside 3ds Max's Python environment. Select one or more Editable
Spline (or other spline shape) objects and run this script to export them as
a Sisir ASCII PLY guide file.
"""

import os
import time

try:
    import pymxs
except ImportError as exc:
    raise RuntimeError("This script must be run from 3ds Max's Python environment") from exc


rt = pymxs.runtime


def _format_ply_float(value):
    return f"{value:.6f}"


def _transform_point(point):
    x_coord, y_coord, z_coord = point
    # Inverse of the importer's Y-up -> Z-up remap: Max is Z-up, Sisir is Y-up.
    return (x_coord, z_coord, -y_coord)


def _current_unit_label():
    try:
        if rt.units.DisplayType == rt.name("Metric"):
            return str(rt.units.MetricType).lower()
        if rt.units.DisplayType == rt.name("US"):
            return "inches"
    except Exception:
        pass
    return "generic"


def _layer_info(node):
    try:
        layer = node.layer
        name = layer.name or "0"
        visible = not layer.isHidden
    except Exception:
        name = "0"
        visible = True
    return name, visible


def _layer_color(node):
    try:
        color = node.wirecolor
        return (color.r / 255.0, color.g / 255.0, color.b / 255.0)
    except Exception:
        return (1.0, 1.0, 1.0)


def _iter_spline_objects(nodes):
    valid = []
    skipped = []
    for node in nodes:
        try:
            spline_count = rt.numSplines(node)
        except Exception:
            skipped.append(node)
            continue
        if spline_count and spline_count > 0:
            valid.append(node)
        else:
            skipped.append(node)
    return valid, skipped


def _node_strands(node):
    strands = []
    skipped_closed = 0
    spline_count = rt.numSplines(node)
    for spline_index in range(1, spline_count + 1):
        if rt.isClosed(node, spline_index):
            skipped_closed += 1
            continue
        knot_count = rt.numKnots(node, spline_index)
        if knot_count < 2:
            continue
        points = []
        for knot_index in range(1, knot_count + 1):
            local_point = rt.getKnotPoint(node, spline_index, knot_index)
            world_point = local_point * node.transform
            points.append(_transform_point((world_point.x, world_point.y, world_point.z)))
        strands.append(points)
    return strands, skipped_closed


def export_sisir_guides(path=None):
    selection = list(rt.selection)
    if not selection:
        raise RuntimeError("Select at least one Editable Spline object to export")

    nodes, skipped_nodes = _iter_spline_objects(selection)
    if not nodes:
        raise RuntimeError("No selected objects contain spline data (Editable Spline expected)")

    if not path:
        path = rt.getSaveFileName(
            caption="Export Sisir Guides",
            types="Sisir Guides (*.ply)|*.ply|All Files (*.*)|*.*|",
        )
        if not path:
            return None

    start_time = time.time()

    layers_by_name = {}
    layer_order = []
    strands = []
    skipped_closed = 0

    for node in nodes:
        layer_name, layer_visible = _layer_info(node)
        if layer_name not in layers_by_name:
            layers_by_name[layer_name] = {
                "id": len(layer_order),
                "name": layer_name,
                "color": _layer_color(node),
                "visible": layer_visible,
            }
            layer_order.append(layer_name)
        layer_id = layers_by_name[layer_name]["id"]

        node_strands, node_skipped_closed = _node_strands(node)
        skipped_closed += node_skipped_closed
        for points in node_strands:
            strands.append({"layer_id": layer_id, "points": points})

    if not strands:
        raise RuntimeError("No valid open guide strands with at least two points were found")

    unit_label = _current_unit_label()
    vertex_count = sum(len(strand["points"]) for strand in strands)

    with open(path, "w", encoding="ascii", newline="\n") as handle:
        handle.write("ply\n")
        handle.write("format ascii 1.0\n")
        handle.write(f"comment sisir_unit {unit_label}\n")
        for layer_name in layer_order:
            layer = layers_by_name[layer_name]
            red, green, blue = layer["color"]
            handle.write(
                f'comment layer {layer["id"]} "{layer["name"]}" '
                f"{_format_ply_float(red)} {_format_ply_float(green)} "
                f"{_format_ply_float(blue)} {1 if layer['visible'] else 0}\n"
            )
        handle.write(f"element vertex {vertex_count}\n")
        handle.write("property float x\n")
        handle.write("property float y\n")
        handle.write("property float z\n")
        handle.write("property uchar anchor\n")
        handle.write("property int layer_id\n")
        handle.write("property int curve_id\n")
        handle.write("end_header\n")
        for curve_id, strand in enumerate(strands):
            for point_index, point in enumerate(strand["points"]):
                handle.write(
                    f"{_format_ply_float(point[0])} {_format_ply_float(point[1])} "
                    f"{_format_ply_float(point[2])} {1 if point_index == 0 else 0} "
                    f"{strand['layer_id']} {curve_id}\n"
                )

    elapsed = time.time() - start_time
    message = f"Exported {len(strands)} Sisir guides ({vertex_count} points) from 3ds Max in {elapsed:.2f}s"
    if skipped_nodes:
        message += f" ({len(skipped_nodes)} non-spline objects skipped)"
    if skipped_closed:
        message += f" ({skipped_closed} closed splines skipped)"
    print(message)
    try:
        rt.messageBox(message, title="Sisir Export")
    except Exception:
        pass
    return path


if __name__ == "__main__":
    export_sisir_guides()
