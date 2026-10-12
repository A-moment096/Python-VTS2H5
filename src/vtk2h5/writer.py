"""HDF5 storage for fixed VTK meshes and XDMF3 fields."""

import json
from pathlib import Path
from typing import Any, Optional

import h5py
import numpy as np

from vtk2h5.mesh import prepare_geometry

TIMESERIES_GROUP = "timeseries"
FLOAT_DTYPES = ("preserve", "float32", "float64")


def uniform_geometry(grid_data):
    """Validate actual VTS coordinates; return dimensions and XYZ geometry."""
    dims = np.asarray(grid_data["dimensions"])
    if dims.shape != (3,) or dims.dtype.kind not in "iu" or np.any(dims < 1):
        raise ValueError("Grid dimensions must be three positive integers")
    nx, ny, nz = map(int, dims)
    points = np.asarray(grid_data["points"])
    if points.shape != (nx * ny * nz, 3) or not np.all(np.isfinite(points)):
        raise ValueError("Grid must contain one finite XYZ coordinate per point")
    coords = points.reshape(nz, ny, nx, 3)
    origin = points[0].astype(np.float64)
    spacing = np.ones(3, dtype=np.float64)
    axes = (coords[0, 0, :, 0], coords[0, :, 0, 1], coords[:, 0, 0, 2])
    epsilon = np.finfo(points.dtype).eps if points.dtype.kind == "f" else 0
    for axis, (size, values) in enumerate(zip(dims, axes)):
        if size > 1:
            spacing[axis] = (float(values[-1]) - origin[axis]) / (size - 1)
            if spacing[axis] == 0:
                raise ValueError("A populated grid axis cannot have zero spacing")
        expected = origin[axis] + np.arange(size) * spacing[axis]
        # Local coordinate rounding only: another axis or the choice of units
        # must not permit flattening a physically nonuniform grid.
        spacing_scale = abs(spacing[axis]) if size > 1 else 0
        tolerance = 2 * epsilon * np.maximum(np.abs(expected), spacing_scale)
        shape = [1, 1, 1]
        shape[2 - axis] = size
        if not np.allclose(
            coords[..., axis],
            expected.reshape(shape),
            rtol=0,
            atol=tolerance.reshape(shape),
        ):
            raise ValueError(
                "Only axis-aligned uniformly spaced grids are supported; "
                "nonuniform or curvilinear coordinates cannot use 3DCoRectMesh"
            )
    return tuple(map(int, dims)), origin, spacing


class HDF5Writer:
    """Write ZYX geometry/fields; precision conversion affects float fields only."""

    def __init__(
        self,
        filepath: str,
        compression: Optional[str] = "gzip",
        compression_opts: Optional[int] = 4,
        mode: str = "w",
        group: Optional[str] = None,
        float_dtype: str = "preserve",
    ):
        if float_dtype not in FLOAT_DTYPES:
            raise ValueError(
                f"Unsupported floating-point storage {float_dtype!r}; "
                "use preserve, float32, or float64. "
            )
        if compression not in (None, "gzip", "lzf"):
            raise ValueError(f"Unsupported compression: {compression}")
        self.filepath = Path(filepath)
        self.compression = compression
        self.compression_opts = compression_opts if compression == "gzip" else None
        self.mode = mode
        self.group = (group or "").strip("/")
        self.float_dtype = float_dtype
        self.file: Optional[h5py.File] = None

    def __enter__(self):
        self.file = h5py.File(self.filepath, self.mode)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _prepare_fields(self, grid_data, dims):
        fields = {}
        for center in ("point_data", "cell_data"):
            shape = (
                (
                    (
                        grid_data["num_points"]
                        if center == "point_data"
                        else grid_data["num_cells"]
                    ),
                )
                if dims is None
                else (
                    tuple(reversed(dims))
                    if center == "point_data"
                    else tuple(max(1, d - 1) for d in reversed(dims))
                )
            )
            count = int(np.prod(shape))
            for name, values in grid_data[center].items():
                if not name or "/" in name:
                    raise ValueError(f"Invalid field name: {name!r}")
                array = np.asarray(values)
                if array.ndim not in (1, 2) or array.shape[0] != count:
                    raise ValueError(
                        f"{center}/{name}: expected {count} tuples, got {array.shape}"
                    )
                if array.dtype.kind == "b":
                    array = array.astype(np.uint8)
                if array.dtype.kind not in "fiu" or array.dtype.itemsize not in (
                    1,
                    2,
                    4,
                    8,
                ):
                    raise ValueError(
                        f"{center}/{name}: unsupported dtype {array.dtype}"
                    )
                if array.dtype.kind == "f":
                    if array.dtype.itemsize not in (4, 8):
                        raise ValueError(
                            f"{center}/{name}: float16 is unsupported by XDMF3"
                        )
                    if self.float_dtype != "preserve":
                        with np.errstate(over="ignore", invalid="ignore"):
                            converted = array.astype(self.float_dtype)
                        if np.any(np.isfinite(array) & ~np.isfinite(converted)):
                            raise ValueError(
                                f"{center}/{name}: {self.float_dtype} overflow"
                            )
                        array = converted
                components = 1 if array.ndim == 1 else array.shape[1]
                if components not in (1, 3, 6, 9):
                    raise ValueError(
                        f"{center}/{name}: supported component counts are 1, 3, 6, 9"
                    )
                fields[f"{center}/{name}"] = array.reshape(
                    shape if components == 1 else (*shape, components)
                )
        return fields

    def write(self, grid_data: dict[str, Any], time_step: Optional[int] = None) -> None:
        """Validate a frame before adding it; frames share geometry and schema."""
        try:
            family, geometry = prepare_geometry(grid_data)
            dims = (
                tuple(map(int, grid_data["dimensions"]))
                if family != "unstructured"
                else None
            )
            fields = self._prepare_fields(grid_data, dims)
            schema = json.dumps(
                {
                    name: [list(a.shape), a.dtype.str]
                    for name, a in sorted(fields.items())
                },
                sort_keys=True,
            )
            if self.file is None:
                self.file = h5py.File(self.filepath, self.mode)
            if "field_schema" in self.file.attrs:
                if self.file.attrs.get("coordinate_order") != "ZYX":
                    raise ValueError(
                        "Cannot append to an older XYZ-layout HDF5 file; reconvert it"
                    )
                stored_family = self.file.attrs.get("geometry_type", "uniform")
                stored_dims = (
                    tuple(self.file.attrs["dimensions"])
                    if "dimensions" in self.file.attrs
                    else None
                )
                if (
                    stored_family != family
                    or stored_dims != dims
                    or any(
                        name not in self.file
                        or not np.array_equal(self.file[name][:], values)
                        for name, values in geometry.items()
                    )
                ):
                    raise ValueError("Grid geometry changes between time steps")
                if self.file.attrs["field_schema"] != schema:
                    raise ValueError(
                        "Field names, shapes or storage types change between time steps"
                    )
            else:
                if len(self.file) or len(self.file.attrs):
                    raise ValueError(
                        "Cannot append to an unrecognized HDF5 geometry layout"
                    )
                self.file.attrs["coordinate_order"] = "ZYX"
                self.file.attrs["layout_version"] = 2
                self.file.attrs["geometry_type"] = family
                if dims is not None:
                    self.file.attrs["dimensions"] = dims
                self.file.attrs["num_points"] = len(grid_data["points"])
                self.file.attrs["num_cells"] = (
                    grid_data.get(
                        "num_cells", int(np.prod([max(1, d - 1) for d in dims]))
                    )
                    if dims is not None
                    else grid_data["num_cells"]
                )
                self.file.attrs["field_schema"] = schema
                self.file.attrs["float_dtype"] = self.float_dtype
                for name, data in geometry.items():
                    self.file.create_dataset(
                        name,
                        data=data,
                        compression=self.compression,
                        compression_opts=self.compression_opts,
                    )
            base = f"{self.group}/" if self.group else ""
            prefix = f"{base}step_{time_step}/" if time_step is not None else base
            if (time_step is not None and prefix.rstrip("/") in self.file) or any(
                prefix + name in self.file for name in fields
            ):
                raise ValueError(f"Frame already exists: {time_step}")
            if time_step is not None:
                self.file.create_group(prefix.rstrip("/"))
            for name, array in fields.items():
                self.file.create_dataset(
                    prefix + name,
                    data=array,
                    compression=self.compression,
                    compression_opts=self.compression_opts,
                )
        except Exception as e:
            raise RuntimeError(f"Failed to write HDF5 file: {e}") from e

    def close(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None

    def write_multiple(self, grid_data_list: list, start_index: int = 0) -> None:
        for i, grid_data in enumerate(grid_data_list):
            self.write(grid_data, time_step=start_index + i)

    def get_file_size(self) -> int:
        return self.filepath.stat().st_size if self.filepath.exists() else 0
