# FurBrush Maya / XGen / Unreal bridge — experimental

A separate Maya shelf tool for curve/guide interchange and static Unreal Groom Alembic export. It does not replace FurBrush.exe, change your existing Maya scripts, or recreate an entire XGen procedural graph.

## Install in Maya

Use Maya with Python 3 (target: Maya 2022+ in Python 3 mode). No pip packages are needed.

1. Extract the ZIP to a permanent folder.
2. Drag `FurBrushBridge/install_bridge.py` onto Maya's viewport. It adds a **FurBrush** button to your current shelf and opens the bridge. If drag-and-drop is unavailable, execute the installer in Maya's **Python** Script Editor; it can ask for the package folder.
3. Keep that folder in place; the shelf button loads the bridge from there.
4. Run **Run Maya bridge smoke check** before using it on a production groom. It creates/deletes only its own test objects, exports a tiny file, restores selection, and reports its result and Maya/XGen version/plugin details. It never opens a new scene. Save your scene beforehand as normal.

The smoke report is written to a temporary directory printed in Maya's Script Editor. It can be shared for troubleshooting. Passing it does not validate Unreal's importer.

## FurBrush → Maya

1. Export guide curves from FurBrush as ASCII PLY.
2. Click **Import FurBrush PLY as Maya curves**.
3. The bridge preserves strand boundaries and layer IDs, uses `sisir_unit`, converts to Maya's current scene unit/up-axis, and creates a new group. The original scene is retained and the import is undoable.

If a PLY has no unit comment, select the fallback unit yourself. Files without curve IDs or explicit points-per-strand metadata are rejected instead of guessing strand boundaries. Curves are linear polylines: they follow the file's point sequence and do not reconstruct an original spline basis.

## Maya → FurBrush

Select NURBS curves or a group containing curves and click **Export selected Maya curves to FurBrush PLY**. The bridge samples each open curve, writes world positions in centimeters/Y-up, marks roots, and preserves imported layer IDs. It supports nested groups and filters intermediate shapes. Adjust samples per curve to balance fidelity and size. Closed/zero-length curves are rejected.

## XGen workflows

### Classic XGen

Import the curves, then use the native XGen **Utilities → Curves To Guides** workflow for your chosen description/scalp. The bridge does not automate that description-specific binding step, paint maps, or modifiers. Converted guide curves are not automatically a dense final groom.

### Interactive Groom → curves

Select one Interactive Groom description/transform and click **Convert selected Interactive Groom to curves**. The adapter tries Maya's installed `xgmSplineToCurves(splineDescription=...)` command and selects newly created curves. If that command differs in your Maya version, the bridge reports the failure; use Maya's native Convert to Curves operation and then select its resulting curves instead. Check conversion density/strand counts: evaluated viewport hair may be sparser than final rendered hair.

### Curves → Interactive Groom (experimental)

**Create curve-driven Interactive Groom** checks for `xgmCurveToSpline`, `xgmSplineDescription`, their expected attributes and plug compatibility before wiring curves into a new description. It rolls back newly created nodes on failure, retaining source curves. Installed XGen schemas vary; this adapter has not been run in Maya here.

This creates a curve-driven description when supported, not a complete scalp-bound Interactive Groom with guides, density, sculpt layers and procedural modifiers. Add/validate native XGen binding and modifiers in Maya. Do not assume existing XGen settings, masks or expressions round-trip through PLY.

## Maya / XGen → Unreal Groom

1. Select the **final render-strand curves**, not only a sparse guide set. Convert/generate the full groom in XGen first when necessary. The exporter does not invent extra strands or interpolation.
2. Optional: select the scalp mesh and click **Use selected**, then reselect the hair curves. The scalp's active UV set is used for root UVs.
3. Choose samples per strand, strand width in **centimeters**, and base group ID.
4. Click **Export selected curves as Unreal Groom .abc**.

The exporter stages new linear curves, leaving sources unchanged. It uses the Maya Alembic exporter's `riCurves` grouping, checks DAG traversal order before assigning arrays, writes standard curve widths, per-strand `groom_group_id` and `groom_guide=0`, and optional uniform `groom_root_uv` vector2 data. Imported PLY layer IDs offset the base group ID. A scalp is required for authored root UVs; root UVs alone are not a skeletal binding asset.

Output is a **single current-frame snapshot**, not an animated Groom Cache. A sibling `.abc.furbrush.json` report records strand count, width, groups, coordinate conversion, root-UV presence and file hash. It does not prove Unreal imported the archive.

### Unreal import

- Enable **Groom** and **Alembic Groom Importer**, then restart Unreal if requested.
- Import the `.abc` as a **Groom**, rather than a mesh/Geometry Cache.
- This bridge already bakes the native FurBrush Unreal orientation mapping `(x,y,z) → (x,z,y)` from centimeter/Y-up coordinates. Use import rotation **0,0,0** and scale **1,1,1** to avoid converting twice. Validate against your character's orientation/origin before binding.
- Inspect imported strand/group counts. Choose a point limit/LOD appropriate to your engine version and target platform; 32 points per strand is only the bridge's starting default.
- To attach to a character, create a **Groom Binding Asset** for the intended skeletal mesh and assign the groom/binding on its Groom Component. Follow that Unreal version's rendering/skin-cache requirements and assign a compatible hair material. This step is not automated.

FurBrush's native **Export Hair (ABC)** already advertises Unreal orientation and root UV options, and remains an alternative for hair that does not need Maya edits. Avoid applying both its orientation bake and this bridge's bake to the same data.

## Validation and limits

**Executed here:** Python syntax compilation and 10 offline tests for variable/fixed PLY strands, unit/axis conversion, Unicode layer metadata, malformed-data rejection, quoted paths, exporter metadata order, original-world root UV inputs, and cleanup/file preservation after failed exports.

**Not executed here:** Maya, XGen, real Maya Alembic authoring, Alembic schema inspection of a Maya-produced archive, Unreal Groom import, skeletal binding, or animated export. Adapter tests mock Maya and write stub bytes; they do not certify real Alembic validity. The optional smoke check is supplied for running against your Maya installation. Both XGen adapters remain version-dependent/experimental until tested there.

A Maya or Unreal version was not supplied during development. Start with the smoke check and report the exact version/error before relying on these adapters for production.

## Offline tests

From the repository root:

```sh
PYTHONPATH=Maya python -m unittest discover -s Maya/FurBrushBridge/tests -v
```

## References checked

- Official Alembic Maya exporter grouping implementation: https://github.com/alembic/alembic/blob/master/maya/AbcExport/AbcWriteJob.cpp (`riCurves`).
- Official curve widths implementation: https://github.com/alembic/alembic/blob/master/maya/AbcExport/MayaNurbsCurveWriter.cpp.
- Official custom-array/scope/type implementation: https://github.com/alembic/alembic/blob/master/maya/AbcExport/AttributesWriter.cpp (`Int32Array`, `vector2`, `_AbcGeomScope`).
- Epic workflow reference for runtime verification: https://dev.epicgames.com/documentation/en-us/unreal-engine/xgen-guidelines-for-hair-creation-in-unreal-engine. The documentation host was inaccessible in this environment, so version-specific Maya/XGen and Unreal commands could not be checked there.
