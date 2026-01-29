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
# Creates: test1.h5 and test1.xdmf2
```

Output files in the input folder:
```bash
vts2h5 data/test1 -i
# Creates: data/test1/test1.h5 and data/test1/test1.xdmf2
```

Output to a specific folder:
```bash
vts2h5 data/test1 -o results/
# Creates: results/test1.h5 and results/test1.xdmf2
```

Custom output name:
```bash
vts2h5 data/test1 --output-name simulation
# Creates: simulation.h5 and simulation.xdmf2
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

## File Format

The tool converts VTK Structured Grid files to HDF5 with the following structure:

```
output.h5
├── origin              # Grid origin [x, y, z]
├── spacing             # Grid spacing [dx, dy, dz]
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

The XDMF2 file uses `3DRectMesh` topology with `ORIGIN_DXDYDZ` geometry, compatible with ParaView and other XDMF-aware visualization tools.

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
