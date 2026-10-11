"""Optional integration against an installed ParaView, in an isolated process."""

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from vts2h5.converter import convert_vts_to_hdf5
from vts2h5.reader import VTSReader
from vts2h5.xdmf import XDMFGenerator

PVPYTHON = os.environ.get("VTS2H5_PVPYTHON")
pytestmark = pytest.mark.skipif(
    not PVPYTHON, reason="Set VTS2H5_PVPYTHON to test an installed ParaView"
)


@pytest.mark.parametrize(
    "dims", [(4, 3, 2), (4, 3, 1), (4, 1, 3), (1, 4, 3), (4, 1, 1)]
)
@pytest.mark.parametrize("dtype", ["preserve", "float32", "float64"])
def test_vts_to_xdmf3_roundtrip(tmp_path, dims, dtype):
    inputs = []
    expected = []
    for step in [0, 10]:
        z, y, x = np.indices(tuple(reversed(dims)))
        points = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1).astype(np.float64)
        points = points * [2, 3, 4] + [3, 7, 11]
        grid = vtk.vtkStructuredGrid()
        grid.SetDimensions(*dims)
        coordinates = vtk.vtkPoints()
        coordinates.SetData(numpy_to_vtk(points, deep=True))
        grid.SetPoints(coordinates)
        n, nc = grid.GetNumberOfPoints(), grid.GetNumberOfCells()
        arrays = {
            "scalar": np.linspace(0, 1, n) + step + 1e-8,
            "velocity": np.arange(n * 3, dtype=np.float32).reshape(n, 3),
            "ids": np.arange(n, dtype=np.int32),
            "unsigned": np.arange(n, dtype=np.uint64) + 2**63,
            "tensor": np.arange(n * 9, dtype=np.float64).reshape(n, 9),
        }
        for name, values in arrays.items():
            array = numpy_to_vtk(values, deep=True)
            array.SetName(name)
            grid.GetPointData().AddArray(array)
        array = numpy_to_vtk(
            np.arange(nc * 3, dtype=np.float64).reshape(nc, 3), deep=True
        )
        array.SetName("flux")
        grid.GetCellData().AddArray(array)
        path = tmp_path / f"source_step{step}.vts"
        writer = vtk.vtkXMLStructuredGridWriter()
        writer.SetFileName(str(path))
        writer.SetInputData(grid)
        assert writer.Write()
        inputs.append(path)
        source = VTSReader(str(path)).read()
        expected.append(
            dict(
                time=step / 40 + 0.125,
                dimensions=source["dimensions"],
                points=source["points"].tolist(),
                **{
                    center: {
                        name: {"values": values.tolist(), "dtype": str(values.dtype)}
                        for name, values in source[center].items()
                    }
                    for center in ["point_data", "cell_data"]
                },
            )
        )
    h5 = tmp_path / "converted.h5"
    descriptors = tmp_path / "descriptors"
    descriptors.mkdir()
    xmf = descriptors / "converted.xdmf"
    convert_vts_to_hdf5(inputs, h5, xmf, jobs=1, silent=True, float_dtype=dtype)
    XDMFGenerator.generate_temporal_collection(
        str(h5), str(xmf), [0, 10], time_values=[0.125, 0.375], hdf5_group="timeseries"
    )
    expected_file = tmp_path / "expected.json"
    expected_file.write_text(json.dumps(expected))
    probe = Path(__file__).with_name("paraview_probe.py")
    result = subprocess.run(
        [
            PVPYTHON,
            "--no-mpi",
            "--disable-registry",
            str(probe),
            str(xmf),
            str(expected_file),
            dtype,
        ],
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS:" in result.stdout
