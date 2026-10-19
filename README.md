# Sisir

Standalone interactive hair-guide authoring tool:
- Maya-like viewport navigation (Alt+LMB orbit, Alt+MMB pan, Alt+RMB dolly)
- Import head mesh (`.obj`)
- Click on mesh to spawn a guide curve (root bound to triangle via barycentric coords)
- Drag curve vertices
- Save/Load scene (`.json`)
- Export curves as `.ply` point cloud

## Tech
- C++20, CMake
- OpenGL 3.3+, GLFW + GLAD
- Dear ImGui (Docking)
- Assimp for OBJ import
- JsonCpp for scene serialization

This repo is structured to later plug in **YarnBall**-style GPU physics (CUDA/OpenGL interop). The initial MVP ships with a fast CPU XPBD solver so the app runs without CUDA.

## Build (Windows)

### 1) Install prerequisites
- Visual Studio 2022 (Desktop development with C++)
- CMake 3.24+
- Git
- (Recommended) vcpkg

### 2) vcpkg (manifest mode)
This project uses `vcpkg.json`. You can use vcpkg manifest mode:

```powershell
git clone https://github.com/microsoft/vcpkg.git C:\vcpkg
C:\vcpkg\bootstrap-vcpkg.bat
```

### 3) Configure + build
From the project root:

```powershell
cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake
cmake --build build --config Release
```

Run:
```powershell
.\build\Release\HairTool.exe
```

## DCC scripts

The Maya import/export helpers live in `Scripts/Maya` in the source tree:
- `Scripts/Maya/Maya_curves_to_PLY.py`
- `Scripts/Maya/PLY_to_Maya_Hair.py`

The Blender importers live in `Scripts/Blender`:
- `Scripts/Blender/SisirImporter/__init__.py` (the installable add-on with Sisir Guides PLY import/export and Sisir Hair Alembic import)
- `Scripts/Blender/PLY_to_Blender.py` (a convenience launcher for Blender's text editor)

To create a normal Blender-installable add-on zip, build the `SisirBlenderAddonZip` target. It outputs `build/SisirImporter-Blender.zip`.

The 3ds Max import/export scripts live in `Scripts/3DSMax`:
- `Scripts/3DSMax/PLY_to_3DSMax.py` (import Sisir PLY guides as Editable Spline shapes)
- `Scripts/3DSMax/3DSMax_to_PLY.py` (export selected Editable Spline objects as a Sisir PLY guide file)

The package/install step copies the Maya and 3ds Max Python scripts into `Scripts/Maya` and `Scripts/3DSMax`. For Blender, the distributable only includes `Scripts/Blender/SisirImporter-Blender.zip`.

## Controls
- **Alt + LMB**: Orbit
- **Alt + MMB**: Pan
- **Alt + RMB**: Dolly
- **LMB (no Alt)**: Interact (spawn/select/drag)

## Notes on YarnBall integration
YarnBall is CUDA/OpenGL-interp based and uses vcpkg deps similar to this project. Once you confirm:
- NVIDIA GPU
- CUDA Toolkit version (YarnBall mentions CUDA 12.8)

…we can add an optional `HAIRTOOL_ENABLE_YARNBALL` build flag and wire curves into a YarnBall-based solver module.
