"""Normalize VTK dataset geometry and encode supported XDMF Mixed cells."""

import numpy as np
import vtk
from vtkmodules.util.numpy_support import vtk_to_numpy

# VTK type: (XDMF code, fixed node count or minimum variable node count).
CELL_TYPES = {
    vtk.VTK_VERTEX: (1, 1),
    vtk.VTK_POLY_VERTEX: (1, None),
    vtk.VTK_LINE: (2, 2),
    vtk.VTK_POLY_LINE: (2, None),
    vtk.VTK_POLYGON: (3, None),
    vtk.VTK_TRIANGLE: (4, 3),
    vtk.VTK_QUAD: (5, 4),
    vtk.VTK_PIXEL: (5, 4),
    vtk.VTK_TETRA: (6, 4),
    vtk.VTK_PYRAMID: (7, 5),
    vtk.VTK_WEDGE: (8, 6),
    vtk.VTK_HEXAHEDRON: (9, 8),
    vtk.VTK_VOXEL: (9, 8),
}


def encode_cells(dataset, source: str):
    """Return an int64 Mixed stream and source-cell index per output cell."""
    topology, sources = [], []
    point_ids = vtk.vtkIdList()
    for index in range(dataset.GetNumberOfCells()):
        cell_type = dataset.GetCellType(index)
        dataset.GetCellPoints(index, point_ids)
        ids = [point_ids.GetId(i) for i in range(point_ids.GetNumberOfIds())]
        if any(i < 0 or i >= dataset.GetNumberOfPoints() for i in ids):
            raise ValueError(f"{source}: cell {index} contains an invalid node index")
        if cell_type == vtk.VTK_POLY_VERTEX:
            if not ids:
                raise ValueError(f"{source}: cell {index} has no nodes")
            # XDMF counts Polyvertex nodes as elements, whereas ParaView's
            # Mixed reader consumes grouped cells. One node per record
            # avoids mismatched element counts and preserves cell values.
            for node in ids:
                topology.extend([1, 1, node])
                sources.append(index)
            continue
        if cell_type == vtk.VTK_TRIANGLE_STRIP:
            if len(ids) < 3:
                raise ValueError(f"{source}: cell {index} strip needs at least 3 nodes")
            for j in range(len(ids) - 2):
                triangle = [ids[j], ids[j + 1], ids[j + 2]]
                if j % 2:
                    triangle[0], triangle[1] = triangle[1], triangle[0]
                topology.extend([4, *triangle])
                sources.append(index)
            continue
        if cell_type not in CELL_TYPES:
            raise ValueError(
                f"{source}: unsupported cell {index}, VTK cell type {cell_type}"
            )
        code, count = CELL_TYPES[cell_type]
        minimum = {1: 1, 2: 2, 3: 3}.get(code, count)
        if (count is not None and len(ids) != count) or len(ids) < minimum:
            raise ValueError(
                f"{source}: cell {index} has invalid node count {len(ids)}"
            )
        if cell_type == vtk.VTK_PIXEL:
            ids = [ids[i] for i in (0, 1, 3, 2)]
        elif cell_type == vtk.VTK_VOXEL:
            ids = [ids[i] for i in (0, 1, 3, 2, 4, 5, 7, 6)]
        topology.append(code)
        if code in (1, 2, 3):
            topology.append(len(ids))
        topology.extend(ids)
        sources.append(index)
    if not sources:
        # XDMF needs a topology even for a point cloud. No source cell fields
        # are invented: these vertices only make its points addressable.
        for i in range(dataset.GetNumberOfPoints()):
            topology.extend([1, 1, i])
        sources = [-1] * dataset.GetNumberOfPoints()
    return np.asarray(topology, dtype=np.int64), np.asarray(sources, dtype=np.int64)


def _fields(obj, count, source, center):
    fields = {}
    for i in range(obj.GetNumberOfArrays()):
        array = obj.GetAbstractArray(i)
        name = array.GetName()
        if not name or "/" in name or name in fields:
            raise ValueError(
                f"{source}: invalid or duplicate {center} field name {name!r}"
            )
        if not isinstance(array, vtk.vtkDataArray):
            raise ValueError(
                f"{source}: {center}/{name}: nonnumeric array is unsupported"
            )
        if array.GetNumberOfTuples() != count:
            raise ValueError(f"{source}: {center}/{name}: expected {count} tuples")
        fields[name] = vtk_to_numpy(array).copy()
    return fields


def normalize_dataset(dataset, source: str):
    """Extract independent NumPy arrays without resampling source data."""
    n, nc = dataset.GetNumberOfPoints(), dataset.GetNumberOfCells()
    if not n:
        raise ValueError(f"{source}: empty geometry")
    data = {
        "dataset_type": dataset.GetClassName(),
        "num_points": n,
        "num_cells": nc,
        "source_num_cells": nc,
        "bounds": list(dataset.GetBounds()),
        "point_data": _fields(dataset.GetPointData(), n, source, "point_data"),
        "cell_data": _fields(dataset.GetCellData(), nc, source, "cell_data"),
        "metadata": {"source_file": source},
    }
    if isinstance(
        dataset, (vtk.vtkStructuredGrid, vtk.vtkRectilinearGrid, vtk.vtkImageData)
    ):
        dims = [0, 0, 0]
        if isinstance(dataset, vtk.vtkRectilinearGrid):
            dims = list(dataset.GetDimensions())
        else:
            dataset.GetDimensions(dims)
        data["dimensions"] = dims
        if isinstance(dataset, vtk.vtkStructuredGrid):
            data["points"] = vtk_to_numpy(dataset.GetPoints().GetData()).copy()
            data["geometry_type"] = "structured"
        elif isinstance(dataset, vtk.vtkRectilinearGrid):
            axes = [
                vtk_to_numpy(a).copy()
                for a in (
                    dataset.GetXCoordinates(),
                    dataset.GetYCoordinates(),
                    dataset.GetZCoordinates(),
                )
            ]
            z, y, x = np.meshgrid(axes[2], axes[1], axes[0], indexing="ij")
            data["points"] = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
            data["axes"] = axes
            data["geometry_type"] = "rectilinear"
        else:
            extent = dataset.GetExtent()
            z, y, x = np.meshgrid(
                np.arange(extent[4], extent[5] + 1),
                np.arange(extent[2], extent[3] + 1),
                np.arange(extent[0], extent[1] + 1),
                indexing="ij",
            )
            indices = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
            direction = np.array(
                [
                    dataset.GetDirectionMatrix().GetElement(i, j)
                    for i in range(3)
                    for j in range(3)
                ]
            ).reshape(3, 3)
            data["points"] = (
                indices * dataset.GetSpacing()
            ) @ direction.T + dataset.GetOrigin()
            data["geometry_type"] = "structured"
    elif isinstance(dataset, (vtk.vtkUnstructuredGrid, vtk.vtkPolyData)):
        data["geometry_type"] = "unstructured"
        data["points"] = vtk_to_numpy(dataset.GetPoints().GetData()).copy()
        data["topology"], data["cell_sources"] = encode_cells(dataset, source)
        data["num_cells"] = len(data["cell_sources"])
        if nc:
            data["cell_data"] = {
                name: values[data["cell_sources"]]
                for name, values in data["cell_data"].items()
            }
        elif data["cell_data"]:
            raise ValueError(f"{source}: point-only dataset cannot contain cell fields")
    else:
        raise ValueError(f"{source}: unsupported dataset type {dataset.GetClassName()}")
    if not np.all(np.isfinite(data["points"])):
        raise ValueError(f"{source}: coordinates must be finite")
    data["metadata"].update(
        num_point_arrays=len(data["point_data"]), num_cell_arrays=len(data["cell_data"])
    )
    return data


def prepare_geometry(grid_data):
    """Return a validated storage family and shared geometry payload."""
    from vtk2h5.writer import uniform_geometry

    family = grid_data.get("geometry_type", "uniform")
    points = np.asarray(grid_data["points"])
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or not len(points)
        or not np.all(np.isfinite(points))
    ):
        raise ValueError("Grid must contain finite XYZ coordinates")
    if len(points) != grid_data.get("num_points", len(points)):
        raise ValueError("Point count disagrees with geometry")
    if family == "unstructured":
        topology = np.asarray(grid_data["topology"])
        if topology.ndim != 1 or topology.dtype.kind not in "iu" or not len(topology):
            raise ValueError("Invalid Mixed topology")
        validate_topology(topology, len(points), grid_data["num_cells"])
        return family, {
            "points": points.astype(np.float64),
            "topology": topology.astype(np.int64),
        }
    dims = np.asarray(grid_data["dimensions"])
    if (
        dims.shape != (3,)
        or dims.dtype.kind not in "iu"
        or np.any(dims < 1)
        or np.prod(dims) != len(points)
    ):
        raise ValueError(
            "Grid dimensions must be three positive integers matching points"
        )
    if family == "rectilinear":
        axes = [np.asarray(a, dtype=np.float64) for a in grid_data["axes"]]
        if len(axes) != 3 or any(
            a.shape != (int(d),) or not np.all(np.isfinite(a))
            for a, d in zip(axes, dims)
        ):
            raise ValueError("Invalid rectilinear geometry axes")
        if any(
            len(a) > 1 and not (np.all(np.diff(a) > 0) or np.all(np.diff(a) < 0))
            for a in axes
        ):
            raise ValueError("Rectilinear geometry axes must be strictly monotonic")
        return family, dict(zip(("x", "y", "z"), axes))
    if family not in ("structured", "uniform"):
        raise ValueError(f"Unknown geometry type {family!r}")
    try:
        _, origin, spacing = uniform_geometry(grid_data)
        return "uniform", {"origin": origin[::-1], "spacing": spacing[::-1]}
    except ValueError:
        if family == "uniform":
            raise
    return "structured", {
        "points": points.astype(np.float64).reshape(*reversed(dims), 3)
    }


def validate_topology(topology, num_points, num_cells):
    """Validate a Mixed stream before opening an output file."""
    fixed = {4: 3, 5: 4, 6: 4, 7: 5, 8: 6, 9: 8}
    offset, count = 0, 0
    while offset < len(topology):
        code = int(topology[offset])
        offset += 1
        if code in (1, 2, 3):
            if offset == len(topology):
                raise ValueError("Truncated topology node count")
            size = int(topology[offset])
            offset += 1
            if size < code:
                raise ValueError("Invalid topology node count")
        elif code in fixed:
            size = fixed[code]
        else:
            raise ValueError(f"Unsupported topology code {code}")
        ids = topology[offset : offset + size]
        if len(ids) != size or np.any(ids < 0) or np.any(ids >= num_points):
            raise ValueError("Invalid topology node indices")
        offset += size
        count += 1
    if count != num_cells:
        raise ValueError("Topology cell count disagrees with geometry")
