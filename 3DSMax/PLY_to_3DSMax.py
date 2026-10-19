"""Sisir guide importer for 3ds Max Python.

Run this inside 3ds Max's Python environment. The script reads Sisir ASCII PLY
guide files and rebuilds them as editable spline shapes.
"""

import os
import re
import time

try:
    import pymxs
except ImportError as exc:
    raise RuntimeError("This script must be run from 3ds Max's Python environment") from exc


rt = pymxs.runtime

KNOT_TYPE = rt.name("corner")
LINE_TYPE = rt.name("line")


def _transform_point(point, import_scale):
    x_coord, y_coord, z_coord = point
    # Sisir data is in Y-up space. For 3ds Max, scale and remap into Z-up.
    return rt.Point3(
        x_coord * import_scale,
        -z_coord * import_scale,
        y_coord * import_scale,
    )


def _parse_ply_header(handle):
    meta = {
        "format": "ascii",
        "vertex_count": 0,
        "vertex_props": [],
        "points_per_strand": None,
        "layers": [],
        "sisir_unit": None,
        "header_end": 0,
    }
    in_vertex_element = False

    while True:
        line = handle.readline()
        if not line:
            break
        decoded = line.decode("ascii", "ignore") if hasattr(line, "decode") else line
        stripped = decoded.strip()

        if stripped == "end_header":
            meta["header_end"] = handle.tell()
            break
        if stripped.startswith("format"):
            meta["format"] = stripped.split()[1]
        elif stripped.startswith("comment sisir_unit"):
            parts = stripped.split()
            if len(parts) >= 3:
                meta["sisir_unit"] = parts[2].lower()
        elif stripped.startswith("comment") and "points_per_strand" in stripped:
            try:
                meta["points_per_strand"] = int(stripped.split()[-1])
            except Exception:
                pass
        elif stripped.startswith("comment layer "):
            try:
                rest = stripped[len("comment layer ") :].strip()
                parts = rest.split(None, 1)
                layer_id = int(parts[0])
                layer_name = ""
                color = None
                visible = True
                if len(parts) > 1:
                    tail = parts[1].strip()
                    if tail.startswith('"'):
                        end = tail.find('"', 1)
                        if end > 0:
                            layer_name = tail[1:end]
                            tail = tail[end + 1 :].strip()
                    if tail:
                        numbers = tail.split()
                        if len(numbers) >= 3:
                            color = (float(numbers[0]), float(numbers[1]), float(numbers[2]))
                        if len(numbers) >= 4:
                            visible = int(numbers[3]) != 0
                meta["layers"].append(
                    {
                        "id": layer_id,
                        "name": layer_name,
                        "color": color,
                        "visible": visible,
                    }
                )
            except Exception:
                pass
        elif stripped.startswith("element vertex"):
            meta["vertex_count"] = int(stripped.split()[-1])
            in_vertex_element = True
        elif stripped.startswith("element"):
            in_vertex_element = False
        elif stripped.startswith("property") and in_vertex_element:
            parts = stripped.split()
            meta["vertex_props"].append(parts[2])

    return meta


def _read_ascii_vertices(handle, meta):
    props = meta["vertex_props"]
    try:
        ix = props.index("x")
        iy = props.index("y")
        iz = props.index("z")
    except ValueError as exc:
        raise RuntimeError("PLY file missing x/y/z properties") from exc

    anchor_idx = props.index("anchor") if "anchor" in props else None
    curve_id_idx = props.index("curve_id") if "curve_id" in props else None
    layer_id_idx = props.index("layer_id") if "layer_id" in props else None

    vertices = []
    for _ in range(meta["vertex_count"]):
        parts = handle.readline().strip().split()
        if len(parts) < 3:
            continue
        x_coord = float(parts[ix])
        y_coord = float(parts[iy])
        z_coord = float(parts[iz])
        anchor = int(parts[anchor_idx]) if anchor_idx is not None else 0
        curve_id = int(parts[curve_id_idx]) if curve_id_idx is not None else 0
        layer_id = int(parts[layer_id_idx]) if layer_id_idx is not None else 0
        vertices.append((x_coord, y_coord, z_coord, anchor, curve_id, layer_id))

    return vertices


def _read_ply_vertices(path):
    with open(path, "rb") as handle:
        meta = _parse_ply_header(handle)
        if meta["format"] != "ascii":
            raise RuntimeError("Only ASCII PLY exported by Sisir is supported")
        handle.seek(meta["header_end"])
        vertices = _read_ascii_vertices(handle, meta)
    return meta, vertices


def _sanitize_name(name, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", name or "")
    cleaned = cleaned.strip("_")
    return cleaned or fallback


def _unique_node_name(base_name):
    if rt.getNodeByName(base_name) is None:
        return base_name

    suffix = 1
    while True:
        candidate = f"{base_name}_{suffix:02d}"
        if rt.getNodeByName(candidate) is None:
            return candidate
        suffix += 1


def _group_strands(meta, vertices):
    has_curve_id = "curve_id" in (meta.get("vertex_props") or [])
    has_layer_id = "layer_id" in (meta.get("vertex_props") or [])

    if has_curve_id:
        strands = {}
        order = []
        for vertex in vertices:
            curve_id = vertex[4]
            layer_id = vertex[5] if has_layer_id else 0
            if curve_id not in strands:
                strands[curve_id] = {"layer_id": layer_id, "points": []}
                order.append(curve_id)
            strands[curve_id]["points"].append(vertex[:3])

        grouped = []
        for curve_id in order:
            strand = strands[curve_id]
            if len(strand["points"]) >= 2:
                grouped.append(
                    {
                        "curve_id": curve_id,
                        "layer_id": strand["layer_id"],
                        "points": strand["points"],
                    }
                )
        return grouped

    points_per_strand = meta.get("points_per_strand") or 2
    if points_per_strand < 2:
        points_per_strand = 2

    grouped = []
    for index in range(0, len(vertices), points_per_strand):
        chunk = vertices[index : index + points_per_strand]
        if len(chunk) < 2:
            continue
        grouped.append(
            {
                "curve_id": len(grouped),
                "layer_id": chunk[0][5] if has_layer_id else 0,
                "points": [vertex[:3] for vertex in chunk],
            }
        )
    return grouped


def _create_spline_shape(name, strands, import_scale, color=None):
    shape = rt.splineShape(name=name)
    spline_index = 0

    for strand in strands:
        points = strand["points"]
        if len(points) < 2:
            continue
        rt.addNewSpline(shape)
        spline_index += 1
        for point in points:
            rt.addKnot(shape, spline_index, KNOT_TYPE, LINE_TYPE, _transform_point(point, import_scale))

    rt.updateShape(shape)

    if color:
        red = max(0, min(255, int(round(color[0] * 255.0))))
        green = max(0, min(255, int(round(color[1] * 255.0))))
        blue = max(0, min(255, int(round(color[2] * 255.0))))
        shape.wirecolor = rt.color(red, green, blue)

    return shape


def import_sisir_guides(path=None):
    if not path:
        path = rt.getOpenFileName(
            caption="Import Sisir Guides",
            types="Sisir Guides (*.ply)|*.ply|All Files (*.*)|*.*|",
        )
        if not path:
            return []

    start_time = time.time()
    meta, vertices = _read_ply_vertices(path)
    strands = _group_strands(meta, vertices)
    if not strands:
        raise RuntimeError("No valid guide strands found in the PLY file")

    # When sisir_unit is present the user already chose the export unit to match
    # their 3ds Max scene, so import positions as-is (scale 1.0).
    # Old files (no comment) were exported in Sisir-internal meters; apply the
    # legacy 100x to convert to 3ds Max's default cm scene.
    import_scale = 1.0 if meta.get("sisir_unit") is not None else 100.0

    layer_meta = meta.get("layers") or []
    layer_info = {
        layer.get("id", 0): {
            "name": layer.get("name") or f"Layer_{layer.get('id', 0)}",
            "color": layer.get("color"),
        }
        for layer in layer_meta
    }

    strands_by_layer = {}
    for strand in strands:
        strands_by_layer.setdefault(strand["layer_id"], []).append(strand)

    file_stem = os.path.splitext(os.path.basename(path))[0] or "SisirGuides"
    import_name = _sanitize_name(file_stem, "SisirGuides")

    created_nodes = []
    for layer_id in sorted(strands_by_layer.keys()):
        info = layer_info.get(layer_id, {})
        layer_name = _sanitize_name(info.get("name"), f"Layer_{layer_id}")
        node_name = _unique_node_name(f"{import_name}_{layer_name}_Guides")
        shape = _create_spline_shape(
            node_name,
            strands_by_layer[layer_id],
            import_scale,
            color=info.get("color"),
        )
        rt.setUserProp(shape, "sisir_source_path", path)
        rt.setUserProp(shape, "sisir_layer_id", layer_id)
        rt.setUserProp(shape, "sisir_strand_count", len(strands_by_layer[layer_id]))
        created_nodes.append(shape)

    rt.clearSelection()
    for node in created_nodes:
        rt.selectMore(node)
    rt.redrawViews()

    elapsed = time.time() - start_time
    message = f"Imported {len(strands)} Sisir guides into 3ds Max in {elapsed:.2f}s"
    print(message)
    try:
        rt.messageBox(message, title="Sisir Import")
    except Exception:
        pass
    return created_nodes


if __name__ == "__main__":
    import_sisir_guides()