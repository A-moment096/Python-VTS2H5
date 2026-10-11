# VTS2H5 - VTK Structured Grid to HDF5 Converter

A simple Python tool to convert your VTS files into H5 format data file with XDMF file to describe the data structure. 

## Installation

You can use your favourite package manager to install this package. For example, using `pip`:

```bash
pip install vts2h5-xxx-py3-none-any.whl
```

Or you want to use `uv` to install this package as a tool:

```bash
uv tool install vts2h5-xxx-py3-none-any.whl
```

Or you'd like to create a virtual environment to hold this tool, for example using `conda`:

```bash
conda create -n vts2h5 python=3.9 # or any name you like, the lowest python version required is 3.9
conda activate vts2h5
pip install vts2h5-xxx-py3-none-any.whl
```

## Usage

### Command Line Interface

Convert all VTS files in a folder (outputs to current directory with folder name):
```bash
vts2h5 data/test1
# Creates: test1.h5 and test1.xdmf
```

Convert all VTS files in the current directory (outputs use the current directory name):
```bash
vts2h5 .
# Creates: <current-directory-name>.h5 and <current-directory-name>.xdmf
```

Output files in the input folder:
```bash
vts2h5 data/test1 -i
# Creates: data/test1/test1.h5 and data/test1/test1.xdmf
```

Output to a specific folder:
```bash
vts2h5 data/test1 -o results/
# Creates: results/test1.h5 and results/test1.xdmf
```

Custom output name:
```bash
vts2h5 data/test1 --output-name simulation
# Creates: simulation.h5 and simulation.xdmf
```

Silent mode (minimal output):
```bash
vts2h5 data/test1 -s
```

Verbose mode (show grid info and detailed statistics):
```bash
vts2h5 data/test1 -v
```

Show folder information without conversion:
```bash
vts2h5 data/test1 --info
```

Compression options:
```bash
vts2h5 data/test1 --compression gzip --compression-level 9
vts2h5 data/test1 --compression lzf  # Faster, lower ratio
vts2h5 data/test1 --compression none  # No compression
```

Floating-point field storage:
```bash
vts2h5 data/test1 --float-dtype float32
vts2h5 data/test1 --float-dtype float64
vts2h5 data/test1 --float-dtype preserve  # Default: keep each field's input dtype
```

`float32` reduces storage for double-precision fields, with rounding and possible underflow. Finite values that overflow the selected type cause an error. Integer fields retain their types, and grid geometry remains float64. `float16` is unsupported by ParaView's XDMF3 reader and is not offered. The Python APIs `convert_vts_to_hdf5`, `convert_folder`, and `HDF5Writer` accept the same `float_dtype` option.

## File Format

The tool converts VTK Structured Grid files to HDF5 with the following structure:

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

Only axis-aligned, uniformly spaced grids are supported. The exporter checks actual point coordinates and rejects nonuniform or curved grids. A singleton axis uses spacing 1, which does not add thickness or move any points. Time-series frames must share geometry, field names, component counts, and stored types. Scalars, three-component vectors, six-component symmetric tensors, and nine-component tensors are supported for both point and cell data.

Open the generated descriptor with **Xdmf3 Reader T** in ParaView. Its uniform-grid output may default to the **Slice** representation; select **Surface** when comparing with the earlier XDMF2 rectilinear-grid rendering. HDF5 references are relative to the descriptor's location, including when the descriptor is in a different folder.

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
