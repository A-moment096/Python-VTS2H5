"""End-to-end generic conversion, mesh validation, and output preservation."""

import copy

import h5py
import numpy as np
import pytest
from lxml import etree

from tests.vtk_fixtures import KINDS, make_dataset, write_dataset
from vtk2h5.converter import convert_vtk_to_hdf5


@pytest.mark.parametrize("kind", [*KINDS, "legacy"])
@pytest.mark.parametrize("jobs", [1, 2])
def test_series(tmp_path, kind, jobs):
    paths = [
        write_dataset(
            make_dataset("structured" if kind == "legacy" else kind, step),
            tmp_path / f"step_{step}.{'vtk' if kind == 'legacy' else KINDS[kind]}",
        )
        for step in (0, 10)
    ]
    h5, xmf = tmp_path / "output.h5", tmp_path / "output.xdmf"
    stats = convert_vtk_to_hdf5(paths, h5, xmf, jobs=jobs, silent=True)
    assert stats["num_files"] == 2
    with h5py.File(h5) as file:
        for step in (0, 10):
            values = file[f"timeseries/step_{step}/point_data/scalar"][:].ravel()
            np.testing.assert_array_equal(values, np.arange(len(values)) + step * 0.25)
    assert all(
        item.text.startswith("output.h5:")
        for item in etree.parse(str(xmf)).findall(".//DataItem")
    )


@pytest.mark.parametrize("jobs", [1, 2])
def test_changed_mesh_preserves_output(tmp_path, jobs):
    grid = make_dataset("unstructured")
    paths = [write_dataset(grid, tmp_path / "step0.vtu")]
    grid.GetPoints().SetPoint(0, 7, 8, 9)
    paths.append(write_dataset(grid, tmp_path / "step10.vtu"))
    h5, xmf = tmp_path / "output.h5", tmp_path / "output.xdmf"
    h5.write_bytes(b"old h5")
    xmf.write_bytes(b"old xdmf")
    with pytest.raises(SystemExit):
        convert_vtk_to_hdf5(paths, h5, xmf, jobs=jobs, silent=True)
    assert h5.read_bytes() == b"old h5"
    assert xmf.read_bytes() == b"old xdmf"
    assert not list(tmp_path.glob(".*.tmp*"))


@pytest.mark.parametrize("steps", [[], [0, 0], [10, 0]])
def test_invalid_steps(tmp_path, steps):
    paths = [
        write_dataset(make_dataset("image"), tmp_path / f"file{i}_step{step}.vti")
        for i, step in enumerate(steps)
    ]
    with pytest.raises(SystemExit):
        convert_vtk_to_hdf5(
            paths, tmp_path / "out.h5", tmp_path / "out.xdmf", silent=True
        )
    assert not (tmp_path / "out.h5").exists()


def test_mixed_extensions_same_mesh(tmp_path):
    grid = make_dataset("structured")
    paths = [
        write_dataset(grid, tmp_path / "step0.vts"),
        write_dataset(grid, tmp_path / "step10.vtk", "binary"),
    ]
    convert_vtk_to_hdf5(
        paths, tmp_path / "out.h5", tmp_path / "out.xdmf", jobs=1, silent=True
    )


@pytest.mark.parametrize(
    "kind", ["curved", "rectilinear", "unstructured", "mixed_cells"]
)
@pytest.mark.parametrize("compression", ["gzip", "lzf", "none"])
@pytest.mark.parametrize("precision", ["preserve", "float32", "float64"])
def test_storage_options(tmp_path, kind, compression, precision):
    path = write_dataset(
        make_dataset(kind),
        (
            tmp_path / "step0.vtu"
            if kind in ("unstructured", "mixed_cells")
            else tmp_path / f"step0.{KINDS[kind]}"
        ),
    )
    h5, xmf = tmp_path / "out.h5", tmp_path / "out.xdmf"
    convert_vtk_to_hdf5(
        [path],
        h5,
        xmf,
        jobs=1,
        silent=True,
        compression=compression,
        float_dtype=precision,
        first_fields=["scalar"],
    )
    with h5py.File(h5) as file:
        ds = file["timeseries/step_0/point_data/scalar"]
        assert ds.dtype == np.dtype("float64" if precision == "preserve" else precision)
        assert ds.compression == (None if compression == "none" else compression)
        assert file["timeseries/step_0/point_data/ids"].dtype == np.int32
    assert etree.parse(str(xmf)).find(".//Attribute").get("Name") == "scalar"


@pytest.mark.parametrize("change", ["schema", "connectivity", "reader"])
@pytest.mark.parametrize("jobs", [1, 2])
def test_failed_frame_preserves_outputs(tmp_path, change, jobs):
    dataset = make_dataset("unstructured")
    paths = [write_dataset(dataset, tmp_path / "step0.vtu")]
    if change == "schema":
        dataset.GetPointData().RemoveArray("scalar")
    elif change == "connectivity":
        dataset.ReplaceCell(0, 4, [1, 2, 3, 4])
    paths.append(write_dataset(dataset, tmp_path / "step10.vtu"))
    if change == "reader":
        paths[-1].write_text("broken XML")
    h5, xmf = tmp_path / "out.h5", tmp_path / "out.xdmf"
    h5.write_bytes(b"oldh5")
    xmf.write_bytes(b"oldxmf")
    with pytest.raises(SystemExit):
        convert_vtk_to_hdf5(paths, h5, xmf, jobs=jobs, silent=True)
    assert h5.read_bytes() == b"oldh5"
    assert xmf.read_bytes() == b"oldxmf"
