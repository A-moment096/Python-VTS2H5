# Tests for VTK2H5

This directory contains comprehensive tests for the vtk2h5 package.

## Test Structure

- `conftest.py` - Pytest fixtures for creating sample VTS files and test data
- `test_reader.py` - Tests for VTSReader (reading VTS files, validation)
- `test_writer.py` - Tests for HDF5Writer (writing HDF5 files, compression)
- `test_xdmf.py` - Tests for XDMFGenerator (XDMF descriptor generation)
- `test_converter.py` - Tests for conversion functions (parallel processing)
- `test_cli.py` - Tests for command-line interface

## Running Tests

The XDMF3 regression tests validate geometry ordering, dataset metadata, precision conversion, and invalid inputs. Optional round-trip tests open generated files with ParaView in separate processes and compare their coordinates and point/cell arrays with the source VTS data. To enable them on Windows:

```powershell
$env:VTK2H5_PVPYTHON = 'C:\Program Files\ParaView 6.1.0\bin\pvpython.exe'
pytest tests/test_paraview_roundtrip.py
```

Without this environment variable the ParaView tests are skipped; the remaining tests require only the normal project dependencies.

### Run all tests
```bash
pytest
```

### Run with coverage report
```bash
pytest --cov=vtk2h5 --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_reader.py
```

### Run specific test class
```bash
pytest tests/test_reader.py::TestVTSReader
```

### Run specific test function
```bash
pytest tests/test_reader.py::TestVTSReader::test_init_with_valid_file
```

### Run tests in parallel (requires pytest-xdist)
```bash
pytest -n auto
```

### Run tests with verbose output
```bash
pytest -v
```

### Run tests and show print statements
```bash
pytest -s
```

## Coverage

After running tests with coverage, you can view the HTML report:
```bash
# Generate coverage report
pytest --cov=vtk2h5 --cov-report=html

# Open the report (the exact command depends on your OS)
# Linux/Mac:
open htmlcov/index.html

# Windows:
start htmlcov/index.html
```

## Test Dependencies

All test dependencies are included in the `dev` dependency group:
- pytest - Testing framework
- pytest-cov - Coverage plugin
- black - Code formatter (also used for checking in CI)
- ruff - Linter (also used for checking in CI)

Install with:
```bash
uv pip install -e ".[dev]"
```

## CI/CD

Tests are automatically run on every push and pull request through GitHub Actions:
- **Test job**: Runs tests on Ubuntu, Windows, and macOS with Python 3.9-3.12
- **Lint job**: Checks code formatting with black and linting with ruff
- **Build job**: Builds the package distribution

See `.github/workflows/ci.yml` for the complete CI configuration.


## v1.2.0 generated data

From a source checkout, run `python scripts/generate_test_data.py data/examples`.
The generator refuses to overwrite files and creates two deterministic frames
per geometry family, plus legacy and comprehensive mixed-cell examples. Fields
include float scalars/vectors/tensors, integer point IDs, and cell fields.
The automated suite generates fixtures in pytest temporary directories; the
ignored local `data` folder is not required by CI.

For actual ParaView tests on Windows, set
`$env:VTK2H5_PVPYTHON="C:/Program Files/ParaView 6.2.0/bin/pvpython.exe"`
and run `python -m pytest tests/test_paraview_roundtrip.py tests/test_vtk_paraview.py`.
Tests compare every coordinate and field tuple and normalized cell connectivity.
