# Changelog

## [1.2.0] - 2026-10-12

### Changed
- Rename the project, Python package, CLI command, and distribution artifacts from `vts2h5` to `vtk2h5`. Update imports and commands when upgrading.

### Added
- Native readers for legacy `.vtk`, `.vti`, `.vtr`, `.vtu`, and `.vtp`, alongside `.vts`.
- Nonuniform rectilinear, curved structured, rotated image, unstructured, and PolyData geometry in HDF5/XDMF3.
- XDMF Mixed topology for common linear cells; pixel/voxel reordering and triangle-strip/Polyvertex expansion with repeated cell fields.
- Generic `VTKReader` and `convert_vtk_to_hdf5` APIs; repeatable CLI `--format` selection and dataset-aware `--info`.
- Reproducible fixture generator and ParaView tests comparing coordinates, connectivity, fields, precision, and time values.

### Fixed
- Read raw-appended XML without mandatory general-purpose XML parsing.
- Read all legacy numeric arrays instead of only the first array in each category.
- Preserve existing output pairs on read, validation, write, descriptor, or publication failure, with rollback backups.
- Validate fixed geometry/connectivity and schema in both sequential and parallel conversion; cap workers by input count.
- Keep geometry-only frame groups and reject duplicate/nonincreasing steps before output creation.

### Compatibility
- Retain the command name, existing VTS Python entry points, and compact uniform-grid geometry/ZYX field layout.
- Higher-order/polyhedron cells, changing meshes, parallel manifests, multiblock, and collection manifests remain unsupported.
- Compression and reading-performance benefits depend on data and reader settings.

## [1.1.0] - 2026-10-11

### Added
- Multiple input folders, with batch output collision checks.
- `-n` / `--beside-input` writes each output pair beside its input folder.
- Repeatable `-f` / `--first-field` prioritizes fields by case-insensitive exact name or prefix.
- `--float-dtype preserve|float32|float64`; integer field types and float64 geometry are retained.
- Coordinate and time-series schema validation, plus optional ParaView round-trip tests.

### Fixed
- Generate XDMF3 `3DCoRectMesh` with ZYX dimensions, origin, and spacing.
- Derive point/cell scalar, vector, and tensor metadata from actual HDF5 datasets.
- Preserve fractional times and one-frame temporal collections; validate duplicate steps.
- Resolve HDF5 references relative to the descriptor; fix LZF options and current-directory output naming.
- Reject unmatched field preferences before opening output files.
- Fix optional XML-attribute access reported by Pylance/Pyright.

### Changed
- Make `-i`, `-n`, and `-o` mutually exclusive; restrict `--output-name` to one input folder.
- Shorten the README and move detailed usage and ParaView settings to `docs/usage.md`.
- Geometry uses ZYX order, and temporal fields live under `/timeseries`. Regenerate older output from VTS rather than relabeling descriptors or appending new frames.

## [0.2.0] - 2025-12-04

### Added
- **Multiprocessing support** for parallel VTS file reading
  - New `-j/--jobs N` flag to specify number of parallel workers
  - Use `-j 0` for automatic CPU core detection
  - Up to **4.7x speedup** on large datasets (125+ files)
- Two-phase processing: parallel reading, sequential HDF5 writing
- Separate progress bars for reading and writing phases in multiprocessing mode

### Performance
- Sequential (baseline): 159.88s for 125 files
- 4 workers (`-j 4`): 58.91s - **2.7x speedup**
- Auto cores (`-j 0`): 33.80s - **4.7x speedup**

### Notes
- Small datasets (< 10 files) may not benefit from parallelization due to overhead
- Output files are byte-identical to sequential processing (verified via SHA256)

## [0.1.0] - 2025-12-04

### Added
- Initial release of vtk2h5 converter
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
