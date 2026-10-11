"""Run in pvpython, separately from the converter's VTK installation."""

import ctypes
import json
import os
import sys
from pathlib import Path

if os.name == "nt":
    ctypes.windll.kernel32.SetErrorMode(0x8003)

import numpy as np
from paraview.simple import Delete, Xdmf3ReaderT
from vtkmodules.util.numpy_support import vtk_to_numpy

descriptor, expected_file, float_dtype = sys.argv[1:]
expected = json.loads(Path(expected_file).read_text())
reader = Xdmf3ReaderT(FileName=[descriptor])
for frame in expected:
    reader.UpdatePipeline(frame["time"])
    data = reader.GetClientSideObject().GetOutputDataObject(0)
    assert data.GetNumberOfPoints() == len(frame["points"])
    assert data.GetDimensions() == tuple(frame["dimensions"])
    assert data.GetPointData().GetScalars().GetName() == frame["first_field"]
    actual_points = np.array(
        [data.GetPoint(i) for i in range(data.GetNumberOfPoints())]
    )
    np.testing.assert_allclose(actual_points, frame["points"], rtol=1e-6, atol=0)
    for center, actual_data in [
        ("point_data", data.GetPointData()),
        ("cell_data", data.GetCellData()),
    ]:
        assert actual_data.GetNumberOfArrays() == len(frame[center])
        for name, field in frame[center].items():
            values = np.array(field["values"], dtype=field["dtype"])
            if values.dtype.kind == "f" and float_dtype != "preserve":
                values = values.astype(float_dtype)
            actual = vtk_to_numpy(actual_data.GetArray(name))
            # Compare every tuple, not just extrema or rendered appearance.
            np.testing.assert_array_equal(actual, values)
            assert actual.dtype.kind == values.dtype.kind
            assert actual.dtype.itemsize == values.dtype.itemsize
Delete(reader)
print(
    "PASS: Xdmf3ReaderT coordinates, fields, components, types and time steps",
    flush=True,
)
