"""XDMF Mixed connectivity and normalization retain cell-field association."""

import numpy as np
import pytest
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from vtk2h5.mesh import encode_cells, normalize_dataset


def cell_grid(cell_type, ids):
    grid = vtk.vtkUnstructuredGrid()
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.arange(60, dtype=float).reshape(20, 3), deep=True))
    grid.SetPoints(points)
    cell = vtk.vtkIdList()
    for index in ids:
        cell.InsertNextId(index)
    grid.InsertNextCell(cell_type, cell)
    return grid


@pytest.mark.parametrize(
    "vtk_type,ids,expected",
    [
        (vtk.VTK_VERTEX, [0], [1, 1, 0]),
        (vtk.VTK_POLY_VERTEX, [0, 2], [1, 1, 0, 1, 1, 2]),
        (vtk.VTK_LINE, [0, 1], [2, 2, 0, 1]),
        (vtk.VTK_POLY_LINE, [0, 1, 2], [2, 3, 0, 1, 2]),
        (vtk.VTK_TRIANGLE, [0, 1, 2], [4, 0, 1, 2]),
        (vtk.VTK_QUAD, [0, 1, 2, 3], [5, 0, 1, 2, 3]),
        (vtk.VTK_POLYGON, [0, 1, 2, 3, 4], [3, 5, 0, 1, 2, 3, 4]),
        (vtk.VTK_TETRA, [0, 1, 2, 3], [6, 0, 1, 2, 3]),
        (vtk.VTK_PYRAMID, [0, 1, 2, 3, 4], [7, 0, 1, 2, 3, 4]),
        (vtk.VTK_WEDGE, [0, 1, 2, 3, 4, 5], [8, 0, 1, 2, 3, 4, 5]),
        (vtk.VTK_HEXAHEDRON, list(range(8)), [9, *range(8)]),
        (vtk.VTK_PIXEL, list(range(4)), [5, 0, 1, 3, 2]),
        (vtk.VTK_VOXEL, list(range(8)), [9, 0, 1, 3, 2, 4, 5, 7, 6]),
        (vtk.VTK_TRIANGLE_STRIP, list(range(5)), [4, 0, 1, 2, 4, 2, 1, 3, 4, 2, 3, 4]),
    ],
)
def test_cell_encoding(vtk_type, ids, expected):
    topology, sources = encode_cells(cell_grid(vtk_type, ids), "fixture")
    np.testing.assert_array_equal(topology, expected)
    np.testing.assert_array_equal(
        sources,
        np.zeros(
            (
                3
                if vtk_type == vtk.VTK_TRIANGLE_STRIP
                else 2 if vtk_type == vtk.VTK_POLY_VERTEX else 1
            ),
            dtype=int,
        ),
    )
    assert topology.dtype == np.int64


def test_strip_fields():
    grid = cell_grid(vtk.VTK_TRIANGLE_STRIP, list(range(5)))
    field = numpy_to_vtk(np.array([19], dtype=np.int32), deep=True)
    field.SetName("label")
    grid.GetCellData().AddArray(field)
    data = normalize_dataset(grid, "fixture")
    np.testing.assert_array_equal(data["cell_data"]["label"], [19, 19, 19])
    assert data["num_cells"] == 3
    assert data["source_num_cells"] == 1


def test_unsupported_cell():
    with pytest.raises(ValueError, match="fixture.*cell.*23"):
        encode_cells(cell_grid(vtk.VTK_QUADRATIC_QUAD, list(range(8))), "fixture")


def test_invalid_node():
    with pytest.raises(ValueError, match="node"):
        encode_cells(cell_grid(vtk.VTK_LINE, [0, 30]), "fixture")


def test_point_cloud():
    grid = cell_grid(vtk.VTK_VERTEX, [0])
    grid = vtk.vtkPolyData()
    points = vtk.vtkPoints()
    points.InsertNextPoint(1, 2, 3)
    grid.SetPoints(points)
    data = normalize_dataset(grid, "cloud")
    np.testing.assert_array_equal(data["topology"], [1, 1, 0])
    assert data["cell_data"] == {}
