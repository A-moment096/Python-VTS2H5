# v1.2.0 VTK Formats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, if selected by the user, superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Convert common serial VTK datasets into faithful compressed HDF5/XDMF3 pairs and release v1.2.0.

**Architecture:** VTK readers normalize datasets into uniform, rectilinear, explicit structured, or unstructured geometry records. HDF5Writer stores shared fixed geometry and per-frame fields; XDMFGenerator describes those stored datasets. Converter and CLI handle discovery, series validation, and safe publication.

**Tech Stack:** Existing Python 3.9+, VTK 9.3+, NumPy 1.24+, h5py 3.10+, lxml 5.0+, tqdm 4.66+, pytest; optional installed ParaView.

**Spec:** [Approved design](../../v1.2.0-design.md).

## Global Constraints

- No new runtime dependency. Preserve `vtk2h5`, VTSReader, and convert_vts_to_hdf5 entry points.
- Support `.vtk`, `.vts`, `.vti`, `.vtr`, `.vtu`, `.vtp`, case-insensitively; reject unspecified `.vtd` and deferred manifests.
- Preserve the v1.1 compact uniform layout and ZYX structured fields; explicit coordinates use XYZ components.
- Geometry stays float64; float storage conversion affects floating fields only. Preserve compression and field priority behavior.
- Require fixed geometry/connectivity and field schema across a time series.
- Unsupported cells/arrays and malformed inputs fail explicitly; preserve existing output pairs on conversion failure.
- Keep supplied data and the user's `.gitignore` change untouched.
- Product version changes to 1.2.0 only when implementation and verification are complete.

## Review Focus

1. Raw appended XML must pass the VTK reader without generic XML parsing (Task 1).
2. Image extents/directions and structured singleton axes must preserve actual coordinates and cell associations (Tasks 2 and 4).
3. Pixel, voxel, and triangle-strip normalization must preserve cell ordering and values (Task 3).
4. Same-size meshes with changed coordinates/connectivity must fail in both processing modes (Task 5).
5. Failures during descriptor generation or the second output replacement must preserve a previous pair (Task 5).

## Task 1: Generic readers and reproducible fixtures

**Files:** Create `tests/vtk_fixtures.py`, `scripts/generate_test_data.py`, `tests/test_vtk_reader.py`, `src/vtk2h5/mesh.py`; modify `src/vtk2h5/reader.py`, `tests/README.md`.

**Interfaces:**
- Fixture factory: `make_dataset(kind: str, step: int = 0) -> vtk.vtkDataSet` for uniform/curved structured, image, rectilinear, unstructured, polydata.
- Fixture writer: `write_dataset(dataset, path: Path, encoding: str = "appended") -> Path`; use VTK XML writers and legacy ASCII/binary writers.
- `VTKReader(filepath: str).read() -> dict[str, Any]`, `.get_info() -> dict[str, Any]`.
- Mesh records retain existing `points`, `point_data`, `cell_data`, `bounds`, `metadata`, `num_points`, `num_cells`; add `dataset_type`, `geometry_type`. Structured records include `dimensions`; rectilinear records include `axes`; unstructured records include `topology` (int64 Mixed stream), `cell_sources` (original cell index per output cell).
- `normalize_dataset(dataset, source: str) -> dict[str, Any]` in `mesh.py`; Task 3 supplies the complete cell encoder.

- [x] Write parametrized reader tests for the six extensions, supported encodings, legacy multiple scalar/vector/tensor arrays, numeric dtype preservation, uppercase extensions, missing files, wrong declared XML dataset, failed VTK reads, empty geometry, duplicate/unnamed/nonnumeric fields, and invalid tuple counts. Assert exact counts and deterministic arrays.
- [x] Run `.venv/Scripts/python.exe -m pytest tests/test_vtk_reader.py --no-cov -q`; verify failures exercise missing generic support.
- [x] Implement reader dispatch, legacy ReadAll flags, ErrorEvent capture/error codes, output-type validation, and normalization. Keep `VTSReader.validate_xml()` for existing callers, but remove whole-file XML parsing from conversion paths. VTSReader remains restricted to structured `.vts` input.
- [x] Implement fixture factory and generator CLI `python scripts/generate_test_data.py OUTPUT_DIRECTORY`, generating two frames per dataset kind in separate folders. Emit scalar float64, vector float32, tensor float64, point IDs int32, and cell IDs int32. Report paths and types; never overwrite supplied data implicitly.
- [x] Run reader tests plus `tests/test_reader.py`; verify all assertions pass. Document generator use.

## Task 2: Structured geometry storage

**Files:** Modify `src/vtk2h5/mesh.py`, `src/vtk2h5/writer.py`; create `tests/test_structured_geometry.py`.

**Interfaces:**
- `prepare_geometry(grid_data: dict[str, Any]) -> tuple[str, dict[str, np.ndarray]]` validates and returns geometry family/payload.
- Uniform payload: `origin`, `spacing` in ZYX. Rectilinear payload: `x`, `y`, `z` axes. Structured payload: `points` XYZ with VTK point ordering.
- New HDF5 metadata: `layout_version=2`, `geometry_type`, counts and optional XYZ `dimensions`; retain uniform `coordinate_order="ZYX"` and existing dataset paths.
- `HDF5Writer.write()` retains its public signature and validates geometry/schema before appending a frame.

- [x] Write tests asserting unchanged uniform datasets and field shapes, nonuniform rectilinear axes, curved points, nonzero image extents, negative spacing, rotated image directions, all singleton-axis positions, 1D/2D grids, and invalid finite coordinates. Assert geometry changes between frames fail, including a change only in a rectilinear interior axis value.
- [x] Run the new tests and confirm missing geometry-family support causes failures.
- [x] Implement geometry-family selection: compact uniform when valid, explicit structured for curved/rotated structured geometry, separate rectilinear axes otherwise. Derive image coordinates from actual extent/origin/spacing/direction. Validate axis lengths and finite values. Reuse field dtype/component validation while separating tuple validation from reshaping.
- [x] Store shared geometry once and compare every geometry dataset on subsequent frames. Read legacy uniform metadata compatibly; do not reinterpret arbitrary existing HDF5 files.
- [x] Run structured tests plus `tests/test_writer.py` and existing regression tests; compare uniform layout directly with v1.1 expectations.

## Task 3: Unstructured and polydata connectivity

**Files:** Modify `src/vtk2h5/mesh.py`, `src/vtk2h5/writer.py`, `tests/vtk_fixtures.py`; create `tests/test_connectivity.py`.

**Interfaces:**
- `encode_cells(dataset, source: str) -> tuple[np.ndarray, np.ndarray]` produces int64 XDMF Mixed connectivity and original-cell indices.
- XDMF codes: Polyvertex=1, Polyline=2, Polygon=3, Triangle=4, Quadrilateral=5, Tetrahedron=6, Pyramid=7, Wedge=8, Hexahedron=9. Codes 1/2/3 include a node-count prefix.
- Pixel order becomes `[0,1,3,2]`; voxel order becomes `[0,1,3,2,4,5,7,6]` relative to source cell IDs. Triangle strips alternate winding and repeat source cell IDs for cell field selection.
- Unstructured geometry datasets: root `points` `(N,3)` float64, `topology` `(K,)` int64. Point/cell fields retain tuple-major shapes.

- [x] Write tests for every supported cell type, mixed cells, multiple polydata cell categories, disconnected vertices, invalid node IDs, unsupported quadratic/polyhedron cells, and geometry with no cells. Assert exact encoded streams for pixel/voxel and strip winding; assert cell fields duplicate correctly after strip expansion.
- [x] Run connectivity tests and confirm failures before implementing the encoder.
- [x] Implement encoder and remap cell fields using `cell_sources`. Fail unsupported cells with filename, index, and VTK cell type. Preserve source point ordering and unused points. Reject empty geometry; support nonempty point-only datasets by explicit vertex topology with a documented cell-data policy.
- [x] Extend writer validation/storage to tuple-major unstructured fields and fixed connectivity comparisons. Keep stored output cell count separate from original source count when strips expand.
- [x] Run connectivity, reader, and writer tests; verify compressed/uncompressed topology retains integer values.

## Task 4: Geometry-aware XDMF and round trips

**Files:** Modify `src/vtk2h5/xdmf.py`, `tests/paraview_probe.py`, `tests/test_paraview_roundtrip.py`; create `tests/test_vtk_xdmf.py`.

**Interfaces:**
- XDMFGenerator public signatures stay compatible; optional dimensions for unstructured records must not be indexed unconditionally.
- Add `_geometry(grid, h5, reference)` helper that emits topology and geometry from stored metadata.
- Add optional `hdf5_reference` argument to generator entry points so temporary HDF5 input can be described using its final path.
- Uniform uses existing `3DCoRectMesh`/`ORIGIN_DXDYDZ`; rectilinear uses `3DRectMesh`/`VXVYVZ`; explicit structured uses `3DSMesh`/`XYZ`; unstructured uses `Mixed`/`XYZ` with `NumberOfElements`. Verify lower-dimensional variants with ParaView before choosing them.

- [x] Write tests parsing descriptors and checking each HDF reference, dataset shape, precision, topology, element count, and Node/Cell association. Parametrize geometry families, precision options, compression, preferred fields, descriptor location, and singleton axes. Check new generation also handles legacy uniform metadata.
- [x] Run tests and confirm failures on new geometry families.
- [x] Implement family-specific geometry and expected attribute shapes, retaining scalar/vector/tensor components 1/3/6/9 and dataset-derived numeric types. Preserve relative references and deterministic attribute priority.
- [x] Extend optional ParaView probe to compare points, cell type/point IDs, all field tuples/types, and time values across structured and unstructured outputs. Account for intentional strip/pixel/voxel normalization in expected records.
- [x] Run descriptor/regression tests and ParaView tests when `VTK2H5_PVPYTHON` is available. Record missing ParaView as a verification gap, not a round-trip pass.

## Task 5: Generic conversion, CLI, and safe publication

**Files:** Modify `src/vtk2h5/converter.py`, `src/vtk2h5/cli.py`, `src/vtk2h5/__init__.py`; create `src/vtk2h5/output.py`, `tests/test_vtk_converter.py`, `tests/test_output_safety.py`; modify CLI tests.

**Interfaces:**
- `convert_vtk_to_hdf5()` has the current converter's parameters/return keys; `convert_vts_to_hdf5()` remains a compatibility wrapper.
- `read_vtk_file_worker(filepath: str) -> tuple[dict, int]`; retain old worker compatibility if used externally.
- `find_vtk_files(folder: Path, formats=None) -> list[Path]`; `find_vts_files()` retains VTS-only compatibility.
- Repeatable `--format EXT` accepts supported extensions with or without leading dot, normalized case-insensitively.
- `publish_pair(temporary_h5: Path, temporary_xdmf: Path, output_h5: Path, output_xdmf: Path) -> None` in `output.py` backs up existing targets, replaces both, and restores on replacement failure.

- [x] Write converter tests for all geometry families with jobs=1 and jobs=2, mixed extensions with identical normalized meshes, duplicate/nonincreasing steps, changed coordinates/connectivity with unchanged counts, changed schema, invalid preferred fields, empty input, and precision overflow.
- [x] Write publication tests with preexisting sentinel outputs. Inject reader, writer, descriptor, and second-replacement failures; assert both original files survive and temporary files/handles are cleaned up. Assert descriptor references final output filename.
- [x] Write CLI tests for case-insensitive deterministic discovery, format filters, no matches, ambiguous duplicate steps, --info with unstructured input, multi-folder behavior, and original options.
- [x] Run new tests and verify missing generic support/failure safety produces failures.
- [x] Implement generic conversion using temporary sibling files and one shared validation path for sequential/parallel reads. Validate steps before starting output. Always close writer in finally; cap workers by number of inputs. Generate and validate descriptor before publication. Preserve existing SystemExit failure behavior for CLI-compatible callers.
- [x] Integrate generic CLI and public exports. Dimension reporting is conditional; show source type, points, and cells. Preserve unsupported/duplicate diagnostics rather than silently picking one export.
- [x] Run converter/CLI/output tests and all previous tests. Smoke-test supplied legacy series and VTS scalar/vector series separately; verify duplicate rejection for the combined VTS folder without changing supplied files.

## Task 6: Release documentation and final verification

**Files:** Modify `README.md`, `docs/usage.md`, `CHANGELOG.md`, `tests/README.md`, `pyproject.toml`, `src/vtk2h5/__init__.py`, and `uv.lock` if package metadata requires it.

- [x] Document formats, cell types, geometry layout, fixed-mesh requirement, generated sample command, format selection, deferred manifests, and supplied VTS duplicate-step caveat. Include compression/read-speed qualifications.
- [x] Run `.venv/Scripts/python.exe -m pytest tests --cov=vtk2h5 --cov-report=term-missing` and report actual results, including skipped integration cases.
- [x] Run `.venv/Scripts/python.exe -m black --check src` and `.venv/Scripts/python.exe -m ruff check src`; fix findings, then rerun affected tests.
- [x] Set package and exported versions to `1.2.0`; update wheel examples and changelog to final shipped scope.
- [x] Build with `uv build` or the available build frontend; inspect wheel metadata and CLI --version. Run a generated dataset conversion from the built wheel in an isolated environment if dependencies are available.
- [x] Review final diff against acceptance criteria; record ParaView availability, actual local sample results, and any remaining limitations. Leave release publishing to a separate explicit request.

## Execution choice

Recommended: implement inline in this chat. Reader normalization, HDF5
layout, and XDMF shape handling share interfaces, so sequential ownership
reduces integration churn. Subagent-driven implementation is an alternative
if the user prefers independent task reviews.

## Plan self-review

All approved format/geometry families, compatibility entry points, CLI
selection, output safety, generated/local samples, and release criteria map
to tasks above. Each Review Focus item has explicit tests. Implementation and independent review are complete. Final verification
results are recorded in `docs/v1.2.0-verification.md`.
