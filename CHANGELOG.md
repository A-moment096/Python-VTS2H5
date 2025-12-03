# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-04

### Added
- Initial release of vts2h5 converter
- Convert VTS files from folders to HDF5 with XDMF2 descriptors
- Support for time series with automatic step number extraction
- Three output modes: silent (`-s`), normal (default), and verbose (`-v`)
- Flexible output location options:
  - Default: current directory with folder name
  - `-i`: output in input folder
  - `-o`: custom output folder
- Progress bar for conversion tracking (using tqdm)
- Compression options: gzip (default), lzf, none
- XDMF format using 3DRectMesh topology with ORIGIN_DXDYDZ geometry
- Numerical sorting of time steps for correct temporal ordering
- Info mode (`--info`) to inspect VTS files without conversion
- Grid information display in verbose mode
- Cross-platform support (Windows, Linux, macOS)

### Features
- Efficient storage using origin/spacing instead of explicit coordinates
- 70-80% file size reduction with default compression
- VTK 9.5+ API compatibility
- Preserves all point data and cell data arrays
- Automatic dimension detection and grid type handling

### Dependencies
- Python >= 3.9
- VTK >= 9.3.0
- h5py >= 3.10.0
- numpy >= 1.24.0
- lxml >= 5.0.0
- tqdm >= 4.66.0

[0.1.0]: https://github.com/yourusername/Python-VTS2H5/releases/tag/v0.1.0
