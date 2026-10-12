# VTK2H5 - VTK to HDF5/XDMF3 Converter

A simple Python tool to convert your VTK datasets into H5 format data file with XDMF file to describe the data structure.

## Installation

You can use your favourite package manager to install this package. For example, using `pip`:

```bash
pip install vtk2h5-1.2.0-py3-none-any.whl
```

Or you want to use `uv` to install this package as a tool:

```bash
uv tool install vtk2h5-1.2.0-py3-none-any.whl
```

Or you'd like to create a virtual environment to hold this tool, for example using `conda`:

```bash
conda create -n vtk2h5 python=3.9 # or any name you like, the lowest python version required is 3.9
conda activate vtk2h5
pip install vtk2h5-1.2.0-py3-none-any.whl
```

## Usage

### Supported inputs and series selection

| Extension | Dataset |
| --- | --- |
| `.vtk` | Legacy structured points/image, structured grid, rectilinear grid, unstructured grid, or PolyData |
| `.vts` | StructuredGrid |
| `.vti` | ImageData |
| `.vtr` | RectilinearGrid |
| `.vtu` | UnstructuredGrid |
| `.vtp` | PolyData |

Extensions are case-insensitive. Legacy ASCII and binary and XML ASCII,
inline binary, appended base64, raw appended, and compressed data are read
by native VTK readers. Parallel manifests, multiblock files, `.pvd`
collections, and `.vtd` are outside v1.2.0 scope.

Discovery is nonrecursive and deterministic, ordered numerically by
`step_N` / `stepN`, then filename. Files without a step use their list
index. Steps must be unique and increasing; geometry, connectivity, field
names, shapes, and storage types must agree across frames.

```bash
vtk2h5 data/trial --format vtk
vtk2h5 data/trial --format .vtu --format vtp -j 2
```

`--format` is repeatable; by default all supported formats are included.
When multiple exports or independent series have the same step numbers,
select one format or put the series in separate folders. In the supplied
`data/testdata-1-vts` example, `scalar_variables` and `vec3_variables` must
be processed separately, even though both use `.vts`. The latter supplied
files contain geometry only, with empty PointData.

Conversion writes temporary sibling files and publishes the pair after
HDF5 writing and XDMF generation succeed. Ordinary conversion or replacement
failures preserve the existing pair. Two filesystem replacements are not
crash-atomic; backups are retained if rollback itself fails. Successful
conversion replaces existing targets.

### Python API

```python
from pathlib import Path
from vtk2h5 import VTKReader, convert_vtk_to_hdf5

inputs = [Path("data/step0.vtu"), Path("data/step10.vtu")]
info = VTKReader(str(inputs[0])).get_info()
stats = convert_vtk_to_hdf5(inputs, Path("result.h5"), Path("result.xdmf"), jobs=1)
```

The existing `VTSReader`, `convert_vts_to_hdf5`, HDF5Writer, and
XDMFGenerator APIs remain available. `VTSReader` accepts `.vts` only;
VTKReader handles all listed extensions. Direct dictionary-only writer
calls retain uniform-grid validation; records from readers carry the new
geometry-family information.

### Command Line Interface

Convert all supported VTK files in a folder (outputs to current directory with folder name):
```bash
vtk2h5 data/test1
# Creates: test1.h5 and test1.xdmf
```

Convert all supported VTK files in the current directory (outputs use the current directory name):
```bash
vtk2h5 .
# Creates: <current-directory-name>.h5 and <current-directory-name>.xdmf
```

Output files in the input folder:
```bash
vtk2h5 data/test1 -i
# Creates: data/test1/test1.h5 and data/test1/test1.xdmf
```

Output to a specific folder:
```bash
vtk2h5 data/test1 -o results/
# Creates: results/test1.h5 and results/test1.xdmf
```

Custom output name:
```bash
vtk2h5 data/test1 --output-name simulation
# Creates: simulation.h5 and simulation.xdmf
```

Silent mode (minimal output):
```bash
vtk2h5 data/test1 -s
```

Verbose mode (show grid info and detailed statistics):
```bash
vtk2h5 data/test1 -v
```

Show folder information without conversion:
```bash
vtk2h5 data/test1 --info
```

Convert several independent folders in one invocation:
```bash
vtk2h5 data/trial1 data/trial2 -n -f con --float-dtype float32
```

Each folder produces its own HDF5/XDMF pair. Folder conversions run sequentially; `-j` still controls parallel reading within each folder. Paths beginning with `~` are expanded. With no location flag, outputs go to the working directory. `-i` writes inside each input folder; `-n` / `--beside-input` writes in each input folder's parent; `-o` uses a shared output directory. These location flags are mutually exclusive. `--output-name` is available for a single input folder only. The tool rejects destination collisions across the batch before writing any output.

For `~/project1/simus/data/trial/step_0.vts`:

| Option | Output pair |
| --- | --- |
| Default | `<working-directory>/trial.{h5,xdmf}` |
| `-i` | `~/project1/simus/data/trial/trial.{h5,xdmf}` |
| `-n` | `~/project1/simus/data/trial.{h5,xdmf}` |

Use repeatable `-f` / `--first-field` to prioritize XDMF attributes:
```bash
vtk2h5 data/trial -n -f con
vtk2h5 data/trial -n -f Con_Nb_1 -f parameter
```

Matching ignores case. An exact match takes priority over prefix matches; otherwise every matching prefix field moves to the front in its existing order. For example, `-f con` matches `Con_Nb_1` and `Con_Nb_2`. Later `-f` values follow earlier priorities, and all other attributes remain present. An unmatched preference is an error, checked before opening the HDF5 output. The Python converter and XDMF generator accept a `first_fields` list. XML order influences the reader's active scalar; it cannot force every visualization application to select a particular field, especially across point/cell associations or nonscalar fields.

Compression options:
```bash
vtk2h5 data/test1 --compression gzip --compression-level 9
vtk2h5 data/test1 --compression lzf  # Faster, lower ratio
vtk2h5 data/test1 --compression none  # No compression
```

Floating-point field storage:
```bash
vtk2h5 data/test1 --float-dtype float32
vtk2h5 data/test1 --float-dtype float64
vtk2h5 data/test1 --float-dtype preserve  # Default: keep each field's input dtype
```

`float32` reduces storage for double-precision fields, with rounding and possible underflow. Finite values that overflow the selected type cause an error. Integer fields retain their types, and grid geometry remains float64. `float16` is unsupported by ParaView's XDMF3 reader and is not offered. The Python APIs `convert_vtk_to_hdf5`, `convert_vts_to_hdf5`, `convert_folder`, and `HDF5Writer` accept the same `float_dtype` option.

## File Format

Uniform grids keep the compact v1.1 HDF5 structure:

```
output.h5
├── origin              # Grid origin [z, y, x], float64
├── spacing             # Grid spacing [dz, dy, dx], float64
└── timeseries/
    ├── step_100000/
    │   └── point_data/
    │       ├── grains
    │       ├── energy_density
    │       └── ...
    ├── step_200000/
    │   └── point_data/
    │       └── ...
    └── ...
```

The XDMF3 file uses `3DCoRectMesh` topology with `ORIGIN_DXDYDZ` geometry. Topology dimensions, origin, and spacing use Z/Y/X order, as required by ParaView's XDMF3 uniform-grid reader. Spatial array shapes are `(nz, ny, nx)` for point scalars, and `(max(nz-1,1), max(ny-1,1), max(nx-1,1))` for cell scalars. Vector and tensor components are stored on a final axis; their component order remains unchanged. XDMF number types and precision are derived from the actual stored datasets.

The HDF5 root attribute `coordinate_order="ZYX"` identifies this layout; its `dimensions` attribute retains the Python/VTK `(nx, ny, nz)` convention. Older HDF5 files with XYZ geometry must be regenerated from VTS before using this exporter or appending frames. Do not change only their XDMF version number.

Uniform axis-aligned grids use compact origin/spacing. Rectilinear grids store separate `x`, `y`, `z` float64 coordinate axes and use `3DRectMesh` / `VXVYVZ`. Curved structured grids and rotated images store explicit XYZ `points` with shape `(nz, ny, nx, 3)` and use `3DSMesh` / `XYZ`. Nonzero image extents, direction matrices, and negative spacing are included in actual point coordinates.

Unstructured meshes and PolyData store `points` with shape `(N, 3)` and int64 `topology` as an XDMF Mixed stream, using `Mixed` / `XYZ`. Their fields have tuple-major shapes `(N,)` or `(N, components)` for point data and the corresponding cell count for cell data. All geometry families share root geometry and `/timeseries/step_N` fields. Geometry-only frames still have a frame group. New root attributes include `layout_version=2`, `geometry_type`, `num_points`, and `num_cells`; structured files retain `dimensions` and ZYX field ordering.

Supported cells: vertex, Polyvertex, line, Polyline, triangle, quad, polygon, tetrahedron, pyramid, wedge, and hexahedron. Pixels and voxels are reordered into quads and hexahedra. Triangle strips expand into triangles with alternating winding; multi-point Polyvertex groups expand into individual vertices for ParaView XDMF3 compatibility. Cell fields repeat for each expanded cell. A nonempty point cloud without cells gets one vertex per point and no invented cell fields. Higher-order and polyhedron cells fail explicitly; no resampling or silent cell dropping occurs. A singleton axis uses spacing 1, which does not add thickness or move any points. Time-series frames must share geometry, field names, component counts, and stored types. Scalars, three-component vectors, six-component symmetric tensors, and nine-component tensors are supported for both point and cell data.

Open the generated descriptor with **Xdmf3 Reader T** in ParaView. Its uniform-grid output may default to the **Slice** representation; select **Surface** when comparing with the earlier XDMF2 rectilinear-grid rendering. HDF5 references are relative to the descriptor's location, including when the descriptor is in a different folder.

### ParaView Surface default

Representation is a ParaView display preference, not standard XDMF metadata. ParaView 6.1 chooses Slice for planar uniform grids and Outline for 3D uniform grids. You can select Surface in the Display properties and save it as a custom default. Alternatively, close ParaView and merge this entry into its `ParaView-UserSettings.json` (usually `%APPDATA%/ParaView/ParaView-UserSettings.json` on Windows), preserving existing settings:

```json
{
  "representations": {
    "UniformGridRepresentation": {
      "Representation": "Surface"
    }
  }
}
```

This applies to uniform grids generally, including newly opened XDMF3 `3DCoRectMesh` data. It was verified with ParaView 6.1.0. See the [ParaView custom-default documentation](https://docs.paraview.org/en/latest/ReferenceManual/customizingParaView.html).

## Requirements

- Python >= 3.9
- VTK >= 9.3.0
- h5py >= 3.10.0
- numpy >= 1.24.0
- lxml >= 5.0.0
- tqdm >= 4.66.0

The development environment is using Python 3.11, but Python 3.9 version is tested and working well.

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit PR.
