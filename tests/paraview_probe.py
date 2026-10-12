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
    if "dimensions" in frame:
        if data.IsA("vtkStructuredGrid"):
            dimensions = [0, 0, 0]
            data.GetDimensions(dimensions)
        else:
            dimensions = data.GetDimensions()
        assert tuple(dimensions) == tuple(frame["dimensions"])
    assert data.GetPointData().GetScalars().GetName() == frame["first_field"]
    actual_points = np.array(
        [data.GetPoint(i) for i in range(data.GetNumberOfPoints())]
    )
    np.testing.assert_allclose(actual_points, frame["points"], rtol=1e-6, atol=0)
    if "cells" in frame:
        assert data.GetNumberOfCells() == len(frame["cells"])
        for index, expected_cell in enumerate(frame["cells"]):
            cell = data.GetCell(index)
            actual_type = cell.GetCellType()
            expected_type = expected_cell["type"]
            # Mixed XDMF represents a vertex as a one-node Polyvertex,
            # and a line as a two-node Polyline. Connectivity is identical.
            assert actual_type == expected_type or (expected_type, actual_type) in [
                (1, 2),
                (3, 4),
            ], (index, expected_type, actual_type)
            assert [
                cell.GetPointId(i) for i in range(cell.GetNumberOfPoints())
            ] == expected_cell["ids"]
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
