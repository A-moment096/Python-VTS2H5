"""Geometry storage preserves actual coordinates and rejects changed meshes."""

import copy

import h5py
import numpy as np
import pytest

from tests.vtk_fixtures import make_dataset
from vtk2h5.mesh import normalize_dataset
from vtk2h5.writer import HDF5Writer


@pytest.mark.parametrize(
    "kind,family",
    [
        ("structured", "uniform"),
        ("curved", "structured"),
        ("image", "uniform"),
        ("rotated_image", "structured"),
        ("rectilinear", "rectilinear"),
        ("unstructured", "unstructured"),
        ("polydata", "unstructured"),
    ],
)
def test_geometry_families(tmp_path, kind, family):
    data = normalize_dataset(make_dataset(kind), "fixture")
    path = tmp_path / "grid.h5"
    with HDF5Writer(str(path)) as writer:
        writer.write(data, time_step=0)
        writer.write(data, time_step=10)
    with h5py.File(path) as h5:
        assert h5.attrs["geometry_type"] == family
        assert h5.attrs["layout_version"] == 2
        if family in ("structured", "unstructured"):
            np.testing.assert_array_equal(
                h5["points"][:].reshape(-1, 3), data["points"]
            )
            assert h5["points"].dtype == np.float64
        if family == "rectilinear":
            for axis, name in enumerate(("x", "y", "z")):
                np.testing.assert_array_equal(h5[name][:], data["axes"][axis])
        if family == "unstructured":
            np.testing.assert_array_equal(h5["topology"][:], data["topology"])
            assert h5["step_0/point_data/scalar"].shape == (data["num_points"],)
        else:
            assert h5["step_0/point_data/scalar"].shape == tuple(
                reversed(data["dimensions"])
            )


@pytest.mark.parametrize(
    "kind", ["structured", "curved", "rectilinear", "unstructured"]
)
def test_changed_mesh(tmp_path, kind):
    data = normalize_dataset(make_dataset(kind), "fixture")
    changed = copy.deepcopy(data)
    if kind == "rectilinear":
        changed["axes"][0][1] += 0.5
        # Keep explicit coordinates consistent with changed axes.
        changed["points"][1 :: data["dimensions"][0], 0] += 0.5
    elif kind == "unstructured":
        changed["topology"][1] = 2
    else:
        changed["points"][:, 0] += 1
    with HDF5Writer(str(tmp_path / "grid.h5")) as writer:
        writer.write(data, time_step=0)
        with pytest.raises(RuntimeError, match="geometry"):
            writer.write(changed, time_step=1)


@pytest.mark.parametrize(
    "dims",
    [(4, 3, 1), (4, 1, 3), (1, 4, 3), (4, 1, 1), (1, 4, 1), (1, 1, 4), (1, 1, 1)],
)
@pytest.mark.parametrize("kind", ["structured", "curved", "rectilinear", "image"])
def test_degenerate_axes(tmp_path, dims, kind):
    data = normalize_dataset(make_dataset(kind, dims=dims), "fixture")
    with HDF5Writer(str(tmp_path / "grid.h5")) as writer:
        writer.write(data)
    with h5py.File(tmp_path / "grid.h5") as h5:
        assert h5["point_data/scalar"].size == data["num_points"]
        assert h5["cell_data/cell_ids"].size == data["num_cells"]


def test_geometry_only_frames(tmp_path):
    data = normalize_dataset(make_dataset("structured"), "fixture")
    data["point_data"], data["cell_data"] = {}, {}
    with HDF5Writer(str(tmp_path / "grid.h5"), group="timeseries") as writer:
        writer.write(data, time_step=0)
        assert "timeseries/step_0" in writer.file
        with pytest.raises(RuntimeError, match="already exists"):
            writer.write(data, time_step=0)
