# VTS2H5

VTS2H5 converts VTK Structured Grid (`.vts`) files into compressed HDF5 data and XDMF3 descriptors for visualization in ParaView.

## Features

- Convert one or more folders, with a separate time series for each folder.
- Preserve point and cell scalars, vectors, and tensors.
- Choose floating-point storage: original precision, float32, or float64.
- Prioritize visualization fields by case-insensitive name or prefix.
- Select output location and compression, and read files in parallel.

Supports axis-aligned, uniformly spaced grids with fixed geometry and field schema across time steps. Nonuniform and curved grids are rejected.

## Installation

Download the wheel from [GitHub Releases](https://github.com/A-moment096/Python-VTS2H5/releases), then install it:

```bash
pip install ./vts2h5-1.1.0-py3-none-any.whl
```

Alternatively, use `uv tool install ./vts2h5-1.1.0-py3-none-any.whl`. To install from a local source checkout, run `pip install .`.

## Usage

```bash
vts2h5 data/trial
vts2h5 data/trial1 data/trial2 -n -f con --float-dtype float32
vts2h5 --help
```

Outputs default to the working directory. Use `-i` to write inside each input folder, `-n` to write beside it, or `-o DIRECTORY` for a shared output directory. `-f con` prioritizes fields such as `Con_Nb_1` without omitting other fields. Open the generated `.xdmf` with ParaView's **Xdmf3 Reader T**.

See the [detailed guide](docs/usage.md) for all options, file layout, and ParaView display defaults. Regenerate older XYZ-layout HDF5/XDMF pairs from VTS before using the new exporter.

## Requirements

Python **3.9+**. Installation automatically provides VTK **9.3+**, h5py **3.10+**, NumPy **1.24+**, lxml **5.0+**, and tqdm **4.66+**. ParaView is only needed to visualize the output.

## License

[MIT](LICENSE).
