"""Regression tests for the ParaView XDMF3 export contract."""

import copy
import sys

import h5py
import numpy as np
import pytest
from lxml import etree

from vts2h5.cli import main, parse_args
from vts2h5.writer import HDF5Writer, uniform_geometry
from vts2h5.xdmf import XDMFGenerator


def uniform_grid(dims=(4, 3, 1)):
    origin = np.array([3.0, 7.0, 11.0])
    spacing = np.array([2.0, 3.0, 4.0])
    z, y, x = np.indices(tuple(reversed(dims)))
    points = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1) * spacing + origin
    n = len(points)
    nc = int(np.prod([max(1, d - 1) for d in dims]))
    return {
        "dimensions": list(dims),
        "points": points,
        "num_points": n,
        "num_cells": nc,
        "bounds": [
            points[:, i].min() if j == 0 else points[:, i].max()
            for i in range(3)
            for j in range(2)
        ],
        "point_data": {
            "scalar": np.linspace(0, 1, n, dtype=np.float64),
            "ids": np.arange(n, dtype=np.int32),
            "velocity": np.arange(n * 3, dtype=np.float32).reshape(n, 3),
        },
        "cell_data": {"flux": np.arange(nc * 3, dtype=np.float64).reshape(nc, 3)},
    }


def test_geometry_order_and_singleton_spacing(tmp_path):
    grid = uniform_grid()
    h5 = tmp_path / "grid.h5"
    with HDF5Writer(str(h5)) as writer:
        writer.write(grid)
    with h5py.File(h5) as f:
        np.testing.assert_array_equal(f["origin"][:], [11, 7, 3])
        np.testing.assert_array_equal(f["spacing"][:], [1, 3, 2])
        assert f.attrs["coordinate_order"] == "ZYX"


@pytest.mark.parametrize("dtype", ["preserve", "float32", "float64"])
def test_field_storage_and_descriptor_match(tmp_path, dtype):
    grid = uniform_grid((4, 3, 2))
    h5, xmf = tmp_path / "grid.h5", tmp_path / "grid.xdmf"
    with HDF5Writer(str(h5), float_dtype=dtype) as writer:
        writer.write(grid)
    XDMFGenerator(str(h5), grid).generate(str(xmf))
    tree = etree.parse(str(xmf))
    assert tree.find(".//Topology").get("TopologyType") == "3DCoRectMesh"
    with h5py.File(h5) as f:
        for attr in tree.findall(".//Attribute"):
            item = attr.find("DataItem")
            path = item.text.split(":", 1)[1]
            ds = f[path]
            assert item.get("Dimensions") == " ".join(map(str, ds.shape))
            assert int(item.get("Precision")) == ds.dtype.itemsize
            assert item.get("NumberType") == (
                "Int" if ds.dtype.kind == "i" else "Float"
            )
            assert attr.get("AttributeType") == ("Vector" if ds.ndim == 4 else "Scalar")
        assert f["point_data/ids"].dtype == np.int32
        expected = np.float64 if dtype == "preserve" else np.dtype(dtype)
        assert f["point_data/scalar"].dtype == expected
        expected_vector = np.float32 if dtype == "preserve" else np.dtype(dtype)
        assert f["point_data/velocity"].dtype == expected_vector
        np.testing.assert_array_equal(
            f["point_data/velocity"][:].reshape(-1, 3),
            grid["point_data"]["velocity"].astype(expected_vector),
        )


def test_fractional_time_and_relative_hdf_path(tmp_path):
    grid = uniform_grid()
    h5 = tmp_path / "data" / "grid.h5"
    xmf = tmp_path / "descriptors" / "grid.xdmf"
    h5.parent.mkdir()
    xmf.parent.mkdir()
    with HDF5Writer(str(h5)) as writer:
        writer.write(grid, time_step=5)
    XDMFGenerator(str(h5), grid).generate(str(xmf), time_steps=[5], time_values=[0.125])
    tree = etree.parse(str(xmf))
    assert float(tree.find(".//Time").get("Value")) == 0.125
    for item in tree.findall(".//DataItem"):
        assert item.text.startswith("../data/grid.h5:")


@pytest.mark.parametrize("change", ["warp", "spacing", "schema"])
def test_invalid_or_changing_grid_is_rejected(tmp_path, change):
    grid = uniform_grid()
    with HDF5Writer(str(tmp_path / "grid.h5")) as writer:
        writer.write(grid, time_step=0)
        changed = copy.deepcopy(grid)
        if change == "warp":
            changed["points"][5, 0] += 0.2
        elif change == "spacing":
            changed["points"][:, 0] *= 2
        else:
            changed["point_data"].pop("ids")
        with pytest.raises(RuntimeError):
            writer.write(changed, time_step=1)


def test_float32_overflow_does_not_silently_corrupt_data(tmp_path):
    grid = uniform_grid()
    grid["point_data"]["scalar"][0] = 1e100
    with HDF5Writer(str(tmp_path / "grid.h5"), float_dtype="float32") as writer:
        with pytest.raises(RuntimeError, match="overflow"):
            writer.write(grid)


def test_float16_is_rejected_before_creating_output(tmp_path):
    path = tmp_path / "grid.h5"
    with pytest.raises(ValueError, match="float16"):
        HDF5Writer(str(path), float_dtype="float16")
    assert not path.exists()


def test_cli_precision_option(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["vts2h5", "data", "--float-dtype", "float32"])
    assert parse_args().float_dtype == "float32"


def test_cli_writes_selected_precision_and_lzf(sample_vts_file, tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vts2h5",
            str(sample_vts_file.parent),
            "-o",
            str(tmp_path),
            "--output-name",
            "cli",
            "--float-dtype",
            "float32",
            "--compression",
            "lzf",
            "-j",
            "1",
            "-s",
        ],
    )
    main()
    with h5py.File(tmp_path / "cli.h5") as h5:
        field = h5["timeseries/step_0/point_data/temperature"]
        assert field.dtype == np.float32
        assert field.compression == "lzf"
    tree = etree.parse(str(tmp_path / "cli.xdmf"))
    item = tree.find(".//Attribute[@Name='temperature']/DataItem")
    assert item.get("NumberType") == "Float"
    assert item.get("Precision") == "4"


@pytest.mark.parametrize("times", [[0.1], [0.1, float("nan")]])
def test_invalid_time_values(tmp_path, times):
    grid = uniform_grid()
    path = tmp_path / "grid.h5"
    with HDF5Writer(str(path)) as writer:
        for step in [0, 1]:
            writer.write(grid, time_step=step)
    with pytest.raises(ValueError):
        XDMFGenerator(str(path), grid).generate(
            str(tmp_path / "grid.xdmf"), time_steps=[0, 1], time_values=times
        )


@pytest.mark.parametrize("case", ["large_offset", "small_units"])
def test_geometry_tolerance_does_not_hide_nonuniform_coordinates(case):
    grid = uniform_grid()
    points = grid["points"].astype(np.float32)
    if case == "large_offset":
        points[:, 0] = 1e8 + (points[:, 0] - 3) * 8
        points[5, 1] += 0.5
    else:
        points *= 1e-8
        points[1, 0] += 1e-8
    grid["points"] = points
    with pytest.raises(ValueError, match="uniformly spaced"):
        uniform_geometry(grid)


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_singleton_axis_tolerance_does_not_flatten_tiny_warp(axis):
    dims = [4, 3, 2]
    dims[axis] = 1
    grid = uniform_grid(tuple(dims))
    points = grid["points"].astype(np.float32) * 1e-8
    points[:, axis] = 0
    points[1, axis] = 5e-8
    grid["points"] = points
    with pytest.raises(ValueError, match="uniformly spaced"):
        uniform_geometry(grid)
