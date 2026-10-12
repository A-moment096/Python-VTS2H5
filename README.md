# VTK2H5

VTK2H5 converts VTK datasets (`.vtk`, `.vts`, `.vti`, `.vtr`, `.vtu`, `.vtp`) into compressed HDF5 data and XDMF3 descriptors for visualization in ParaView.

## Features

- Convert one or more folders, with a separate time series for each folder.
- Preserve point and cell scalars, vectors, and tensors.
- Choose floating-point storage: original precision, float32, or float64.
- Prioritize visualization fields by case-insensitive name or prefix.
- Select output location and compression, and read files in parallel.
- Select input extensions with repeatable `--format`; read legacy ASCII/binary and XML encodings.
- Preserve existing output pairs if conversion fails.

Supports uniform, rectilinear, curved structured, unstructured, and polygonal meshes with fixed geometry and field schema across time steps. Common linear cells are supported; higher-order and polyhedron cells are rejected. Triangle strips and Polyvertex groups are expanded with their cell fields retained.

Version 1.2.0 uses the `vtk2h5` package and command name. Update earlier `vts2h5` imports and commands when upgrading.

## Installation

Download the wheel from [GitHub Releases](https://github.com/A-moment096/Python-VTS2H5/releases), then install it:

```bash
pip install ./vtk2h5-1.2.0-py3-none-any.whl
```

Alternatively, use `uv tool install ./vtk2h5-1.2.0-py3-none-any.whl`. To install from a local source checkout, run `pip install .`.

## Usage

```bash
vtk2h5 data/trial
vtk2h5 data/trial1 data/trial2 -n -f con --float-dtype float32
vtk2h5 data/trial --format vtk --format vtu
vtk2h5 --help
```

Outputs default to the working directory. Use `-i` to write inside each input folder, `-n` to write beside it, or `-o DIRECTORY` for a shared output directory. `-f con` prioritizes fields such as `Con_Nb_1` without omitting other fields. Open the generated `.xdmf` with ParaView's **Xdmf3 Reader T**.

Generate reproducible sample meshes with `python scripts/generate_test_data.py data/examples` from a source checkout. Compression and read-speed gains vary by dataset and compression settings.

See the [detailed guide](docs/usage.md) for all options, file layout, and ParaView display defaults. Regenerate older XYZ-layout HDF5/XDMF pairs from VTS before using the new exporter.

## Requirements

Python **3.9+**. Installation automatically provides VTK **9.3+**, h5py **3.10+**, NumPy **1.24+**, lxml **5.0+**, and tqdm **4.66+**. ParaView is only needed to visualize the output.

## License

[MIT](LICENSE).
