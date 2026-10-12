"""XDMF3 descriptors derived from the HDF5 datasets they describe."""

import math
import os
from pathlib import Path
from typing import Any, Optional, cast

import h5py
import numpy as np
from lxml import etree


class XDMFGenerator:
    """Describe stored mesh geometry and fields in ParaView XDMF3 ordering."""

    def __init__(
        self,
        hdf5_filepath: str,
        grid_data: Optional[dict[str, Any]] = None,
        hdf5_group: str = "",
        first_fields: Optional[list[str]] = None,
        hdf5_reference: Optional[str] = None,
    ):
        self.hdf5_filepath = Path(hdf5_filepath)
        self.hdf5_reference = Path(hdf5_reference or hdf5_filepath)
        self.grid_data = grid_data
        self.hdf5_group = hdf5_group.strip("/")
        self.first_fields = first_fields or []

    def generate(
        self,
        output_filepath: str,
        time_steps: Optional[list[int]] = None,
        time_values: Optional[list[float]] = None,
    ) -> None:
        """Write a static grid or temporal collection, including one-frame series."""
        self._generate(
            output_filepath,
            time_steps,
            time_values,
            self.grid_data.get("dimensions") if self.grid_data else None,
            list(self.grid_data["point_data"]) if self.grid_data else None,
            list(self.grid_data["cell_data"]) if self.grid_data else None,
        )

    def _step_prefix(self, time_step):
        base = f"{self.hdf5_group}/" if self.hdf5_group else ""
        return base if time_step is None else f"{base}step_{time_step}/"

    @staticmethod
    def validate_first_fields(grid_data, first_fields):
        """Validate preferences before a converter opens its output file."""
        names = [
            name.casefold()
            for center in ("point_data", "cell_data")
            for name in grid_data[center]
        ]
        for preferred in first_fields or []:
            if not preferred or not any(
                name.startswith(preferred.casefold()) for name in names
            ):
                raise ValueError(
                    f"No field matches preferred name or prefix {preferred!r}"
                )

    @staticmethod
    def _data_item(parent, dataset, reference, name=None):
        kind = dataset.dtype.kind
        number_type = {"f": "Float", "i": "Int", "u": "UInt"}.get(kind)
        if number_type is None or (
            kind == "f" and dataset.dtype.itemsize not in (4, 8)
        ):
            raise ValueError(f"Unsupported XDMF3 dtype: {dataset.dtype}")
        props = {
            "Dimensions": " ".join(map(str, dataset.shape)),
            "NumberType": number_type,
            "Precision": str(dataset.dtype.itemsize),
            "Format": "HDF",
        }
        if name is not None:
            props["Name"] = name
        item = etree.SubElement(parent, "DataItem", attrib=props)
        item.text = reference

    def _generate(
        self,
        output_filepath,
        time_steps,
        time_values,
        dimensions,
        point_arrays,
        cell_arrays,
    ):
        output = Path(output_filepath)
        if time_steps is not None:
            if not time_steps or len(set(time_steps)) != len(time_steps):
                raise ValueError("Time steps must be nonempty and unique")
            values = (
                [float(s) for s in time_steps] if time_values is None else time_values
            )
            if len(values) != len(time_steps) or not all(
                math.isfinite(v) for v in values
            ):
                raise ValueError("Provide one finite time value per time step")
            if any(b <= a for a, b in zip(values, values[1:])):
                raise ValueError("Time values must be strictly increasing")
        else:
            if time_values is not None:
                raise ValueError("time_values requires time_steps")
            values = [None]
        # References are relative to the descriptor, not the current directory.
        try:
            relative_h5 = os.path.relpath(
                self.hdf5_reference.resolve(), output.parent.resolve()
            )
        except ValueError:  # Different Windows drives require an absolute path.
            relative_h5 = str(self.hdf5_reference.resolve())
        reference = Path(relative_h5).as_posix()
        root = etree.Element("Xdmf", Version="3.0")
        domain = etree.SubElement(root, "Domain")
        parent = (
            domain
            if time_steps is None
            else etree.SubElement(
                domain,
                "Grid",
                Name="TimeSeries",
                GridType="Collection",
                CollectionType="Temporal",
            )
        )
        with h5py.File(self.hdf5_filepath, "r") as h5:
            if h5.attrs.get("coordinate_order") != "ZYX":
                raise ValueError(
                    "HDF5 geometry is not marked ZYX; reconvert the source VTK files"
                )
            family = h5.attrs.get("geometry_type", "uniform")
            dims = (
                tuple(map(int, np.asarray(h5.attrs["dimensions"])))
                if family != "unstructured"
                else None
            )
            if dimensions is not None and tuple(dimensions) != dims:
                raise ValueError("Descriptor dimensions disagree with HDF5 geometry")
            for step, time in zip([None] if time_steps is None else time_steps, values):
                grid = etree.SubElement(
                    parent,
                    "Grid",
                    Name="StructuredGrid" if step is None else f"Step_{step}",
                    GridType="Uniform",
                )
                if time is not None:
                    etree.SubElement(grid, "Time", Value=format(float(time), ".17g"))
                self._geometry(grid, h5, reference, family, dims)
                prefix = self._step_prefix(step)
                for center, group_name, selected in (
                    ("Node", "point_data", point_arrays),
                    ("Cell", "cell_data", cell_arrays),
                ):
                    group_path = prefix + group_name
                    names = (
                        list(cast(h5py.Group, h5[group_path]))
                        if selected is None and group_path in h5
                        else (selected or [])
                    )
                    expected_shape = (
                        (
                            int(
                                h5.attrs["num_points"]
                                if center == "Node"
                                else h5.attrs["num_cells"]
                            ),
                        )
                        if family == "unstructured"
                        else (
                            tuple(reversed(dims))
                            if center == "Node"
                            else tuple(max(1, d - 1) for d in reversed(dims))
                        )
                    )
                    rank = len(expected_shape)
                    for name in names:
                        dataset = cast(h5py.Dataset, h5[f"{group_path}/{name}"])
                        if (
                            dataset.ndim not in (rank, rank + 1)
                            or dataset.shape[:rank] != expected_shape
                        ):
                            raise ValueError(
                                f"Invalid field shape: {dataset.name}: {dataset.shape}"
                            )
                        components = (
                            dataset.shape[-1] if dataset.ndim == rank + 1 else 1
                        )
                        attribute_type = {
                            1: "Scalar",
                            3: "Vector",
                            6: "Tensor6",
                            9: "Tensor",
                        }.get(components)
                        if attribute_type is None:
                            raise ValueError(
                                f"Unsupported component count: {components}"
                            )
                        attr = etree.SubElement(
                            grid,
                            "Attribute",
                            Name=name,
                            AttributeType=attribute_type,
                            Center=center,
                        )
                        self._data_item(attr, dataset, f"{reference}:{dataset.name}")
                attributes = grid.findall("Attribute")
                ordered = []
                for preferred in self.first_fields:
                    key = preferred.casefold()
                    matches = [
                        a
                        for a in attributes
                        if cast(str, a.attrib["Name"]).casefold() == key
                    ]
                    if not matches:
                        matches = [
                            a
                            for a in attributes
                            if cast(str, a.attrib["Name"]).casefold().startswith(key)
                        ]
                    if not matches:
                        raise ValueError(
                            f"No field matches preferred name or prefix {preferred!r}"
                        )
                    ordered.extend(a for a in matches if a not in ordered)
                ordered.extend(a for a in attributes if a not in ordered)
                for attribute in ordered:
                    grid.remove(attribute)
                    grid.append(attribute)
        etree.ElementTree(root).write(
            str(output), pretty_print=True, xml_declaration=True, encoding="utf-8"
        )

    def _geometry(self, grid, h5, reference, family, dims):
        types = {
            "uniform": "3DCoRectMesh",
            "rectilinear": "3DRectMesh",
            "structured": "3DSMesh",
            "unstructured": "Mixed",
        }
        if family not in types:
            raise ValueError(f"Unsupported stored geometry type {family!r}")
        props = {"TopologyType": types[family]}
        if family == "unstructured":
            props["NumberOfElements"] = str(h5.attrs["num_cells"])
        else:
            props["Dimensions"] = " ".join(map(str, reversed(dims)))
        topology = etree.SubElement(grid, "Topology", **props)
        if family == "unstructured":
            self._data_item(topology, h5["topology"], f"{reference}:/topology")
        geometry = etree.SubElement(
            grid,
            "Geometry",
            GeometryType={
                "uniform": "ORIGIN_DXDYDZ",
                "rectilinear": "VXVYVZ",
                "structured": "XYZ",
                "unstructured": "XYZ",
            }[family],
        )
        names = {
            "uniform": ("origin", "spacing"),
            "rectilinear": ("x", "y", "z"),
            "structured": ("points",),
            "unstructured": ("points",),
        }[family]
        for name in names:
            self._data_item(
                geometry, h5[name], f"{reference}:/{name}", name.capitalize()
            )

    @staticmethod
    def generate_temporal_collection(
        hdf5_filepath: str,
        output_filepath: str,
        time_steps: list[int],
        time_values: Optional[list[float]] = None,
        dimensions: Optional[tuple] = None,
        point_arrays: Optional[list[str]] = None,
        cell_arrays: Optional[list[str]] = None,
        hdf5_group: str = "",
        first_fields: Optional[list[str]] = None,
        hdf5_reference: Optional[str] = None,
    ) -> None:
        """Describe actual stored types/shapes; retain the existing public API."""
        generator = XDMFGenerator(
            hdf5_filepath,
            hdf5_group=hdf5_group,
            first_fields=first_fields,
            hdf5_reference=hdf5_reference,
        )
        generator._generate(
            output_filepath,
            time_steps,
            time_values,
            dimensions,
            point_arrays,
            cell_arrays,
        )
