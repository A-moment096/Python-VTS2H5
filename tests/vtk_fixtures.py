"""Small deterministic VTK datasets shared by tests and the sample generator."""

from pathlib import Path

import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

KINDS = {
    "structured": "vts",
    "curved": "vts",
    "image": "vti",
    "rotated_image": "vti",
    "rectilinear": "vtr",
    "unstructured": "vtu",
    "polydata": "vtp",
}


def make_dataset(kind, step=0, dims=(4, 3, 2)):
    if kind in ("structured", "curved"):
        grid = vtk.vtkStructuredGrid()
        grid.SetDimensions(*dims)
        z, y, x = np.indices(tuple(reversed(dims)))
        xyz = np.column_stack((x.ravel(), y.ravel(), z.ravel())).astype(float)
        xyz = xyz * [2, 3, 4] + [3, 7, 11]
        if kind == "curved":
            xyz[:, 2] += 0.125 * xyz[:, 0] * xyz[:, 1]
        points = vtk.vtkPoints()
        points.SetData(numpy_to_vtk(xyz, deep=True))
        grid.SetPoints(points)
    elif kind in ("image", "rotated_image"):
        grid = vtk.vtkImageData()
        grid.SetExtent(2, dims[0] + 1, -1, dims[1] - 2, 3, dims[2] + 2)
        grid.SetOrigin(3, 7, 11)
        grid.SetSpacing(-2, 3, 4)
        if kind == "rotated_image":
            grid.SetDirectionMatrix(0, -1, 0, 1, 0, 0, 0, 0, 1)
    elif kind == "rectilinear":
        grid = vtk.vtkRectilinearGrid()
        grid.SetDimensions(*dims)
        for axis, setter in enumerate(
            (grid.SetXCoordinates, grid.SetYCoordinates, grid.SetZCoordinates)
        ):
            setter(
                numpy_to_vtk(
                    np.arange(dims[axis], dtype=float) ** 2 + axis * 5, deep=True
                )
            )
    elif kind in ("unstructured", "polydata", "mixed_cells"):
        points = vtk.vtkPoints()
        points.SetData(
            numpy_to_vtk(
                np.array(
                    [
                        [0, 0, 0],
                        [1, 0, 0],
                        [1, 1, 0],
                        [0, 1, 0],
                        [0, 0, 1],
                        [1, 0, 1],
                        [1, 1, 1],
                        [0, 1, 1],
                    ],
                    dtype=float,
                ),
                deep=True,
            )
        )
        grid = vtk.vtkUnstructuredGrid() if kind != "polydata" else vtk.vtkPolyData()
        grid.SetPoints(points)
        grid.Allocate(3)
        cells = (
            [(vtk.VTK_TETRA, [0, 1, 3, 4]), (vtk.VTK_HEXAHEDRON, list(range(8)))]
            if kind != "polydata"
            else [
                (vtk.VTK_VERTEX, [4]),
                (vtk.VTK_LINE, [0, 1]),
                (vtk.VTK_TRIANGLE, [0, 1, 2]),
            ]
        )
        if kind == "mixed_cells":
            cells = [
                (vtk.VTK_VERTEX, [0]),
                (vtk.VTK_POLY_VERTEX, [0, 2]),
                (vtk.VTK_LINE, [0, 1]),
                (vtk.VTK_POLY_LINE, [0, 1, 2]),
                (vtk.VTK_TRIANGLE, [0, 1, 2]),
                (vtk.VTK_QUAD, [0, 1, 2, 3]),
                (vtk.VTK_PIXEL, [0, 1, 3, 2]),
                (vtk.VTK_POLYGON, [0, 1, 2, 3, 4]),
                (vtk.VTK_TETRA, [0, 1, 3, 4]),
                (vtk.VTK_PYRAMID, [0, 1, 2, 3, 4]),
                (vtk.VTK_WEDGE, [0, 1, 2, 4, 5, 6]),
                (vtk.VTK_HEXAHEDRON, list(range(8))),
                (vtk.VTK_VOXEL, [0, 1, 3, 2, 4, 5, 7, 6]),
                (vtk.VTK_TRIANGLE_STRIP, [0, 1, 3, 2, 6]),
            ]
        for cell_type, ids in cells:
            cell = vtk.vtkIdList()
            for index in ids:
                cell.InsertNextId(index)
            grid.InsertNextCell(cell_type, cell)
    else:
        raise ValueError(kind)
    n, nc = grid.GetNumberOfPoints(), grid.GetNumberOfCells()
    for data, arrays in (
        (
            grid.GetPointData(),
            {
                "scalar": np.arange(n, dtype=np.float64) + step * 0.25,
                "other_scalar": np.arange(n, dtype=np.float64) + 100,
                "velocity": np.arange(n * 3, dtype=np.float32).reshape(n, 3),
                "tensor": np.arange(n * 9, dtype=np.float64).reshape(n, 9),
                "ids": np.arange(n, dtype=np.int32),
            },
        ),
        (
            grid.GetCellData(),
            {
                "cell_ids": np.arange(nc, dtype=np.int32),
                "flux": np.arange(nc * 3, dtype=np.float64).reshape(nc, 3) + step,
            },
        ),
    ):
        for name, values in arrays.items():
            array = numpy_to_vtk(values, deep=True)
            array.SetName(name)
            data.AddArray(array)
    return grid


def write_dataset(dataset, path: Path, encoding="appended"):
    writers = {
        ".vts": vtk.vtkXMLStructuredGridWriter,
        ".vti": vtk.vtkXMLImageDataWriter,
        ".vtr": vtk.vtkXMLRectilinearGridWriter,
        ".vtu": vtk.vtkXMLUnstructuredGridWriter,
        ".vtp": vtk.vtkXMLPolyDataWriter,
        ".vtk": vtk.vtkDataSetWriter,
    }
    writer = writers[path.suffix.lower()]()
    if path.suffix.lower() == ".vtk":
        if encoding == "binary":
            writer.SetFileTypeToBinary()
        else:
            writer.SetFileTypeToASCII()
    else:
        if encoding == "ascii":
            writer.SetDataModeToAscii()
        elif encoding == "binary":
            writer.SetDataModeToBinary()
        else:
            writer.SetDataModeToAppended()
            if encoding == "raw":
                writer.EncodeAppendedDataOff()
    path.parent.mkdir(parents=True, exist_ok=True)
    writer.SetFileName(str(path))
    writer.SetInputData(dataset)
    if not writer.Write():
        raise RuntimeError(f"Cannot write fixture {path}")
    return path
