"""XDMF2 file generator module."""

from pathlib import Path
from typing import Any, Optional

from lxml import etree


class XDMFGenerator:
    """Generator for XDMF2 descriptor files matching C++ MInDes-VTS2H5 implementation."""

    def __init__(self, hdf5_filepath: str, grid_data: Optional[dict[str, Any]] = None):
        """
        Initialize XDMF generator.

        Args:
            hdf5_filepath: Path to the HDF5 file
            grid_data: Optional grid data dictionary from VTSReader
        """
        self.hdf5_filepath = Path(hdf5_filepath)
        self.grid_data = grid_data

    def generate(
        self,
        output_filepath: str,
        time_steps: Optional[list[int]] = None,
        time_values: Optional[list[float]] = None,
    ) -> None:
        """
        Generate XDMF2 file using 3DRectMesh topology with ORIGIN_DXDYDZ geometry.

        Args:
            output_filepath: Path for the output XDMF file
            time_steps: Optional list of time step indices for time series
            time_values: Optional list of actual time values
        """
        output_path = Path(output_filepath)

        # Create XDMF structure
        xdmf = etree.Element("Xdmf", Version="3.0")
        domain = etree.SubElement(xdmf, "Domain")

        if time_steps is not None and len(time_steps) > 1:
            # Time series
            collection = etree.SubElement(
                domain,
                "Grid",
                Name="TimeSeries",
                GridType="Collection",
                CollectionType="Temporal",
            )

            for i, step in enumerate(time_steps):
                time_val = time_values[i] if time_values else float(step)
                self._add_grid_to_collection(collection, step, time_val)
        else:
            # Single time step
            step = time_steps[0] if time_steps else None
            self._add_single_grid(domain, step)

        # Write to file
        tree = etree.ElementTree(xdmf)
        tree.write(
            str(output_path),
            pretty_print=True,
            xml_declaration=True,
            encoding="utf-8",
        )

    def _add_single_grid(self, parent, time_step: Optional[int] = None) -> None:
        """Add a single grid using 3DRectMesh topology."""
        if self.grid_data is None:
            raise ValueError("Grid data is required for single grid generation")

        prefix = f"step_{time_step}/" if time_step is not None else ""

        grid = etree.SubElement(
            parent, "Grid", Name="StructuredGrid", GridType="Uniform"
        )

        # Add topology - always use 3DRectMesh
        dims = self.grid_data["dimensions"]
        nx, ny, nz = dims[0], dims[1], dims[2]
        etree.SubElement(
            grid,
            "Topology",
            TopologyType="3DRectMesh",
            Dimensions=f"{nz} {ny} {nx}",  # Z Y X order
        )

        # Add geometry with ORIGIN_DXDYDZ
        geometry = etree.SubElement(grid, "Geometry", GeometryType="ORIGIN_DXDYDZ")

        # Origin DataItem
        origin_item = etree.SubElement(
            geometry,
            "DataItem",
            Name="Origin",
            Dimensions="3",
            NumberType="Float",
            Precision="8",
            Format="HDF",
        )
        origin_item.text = f"{self.hdf5_filepath.name}:/origin"

        # Spacing DataItem
        spacing_item = etree.SubElement(
            geometry,
            "DataItem",
            Name="Spacing",
            Dimensions="3",
            NumberType="Float",
            Precision="8",
            Format="HDF",
        )
        spacing_item.text = f"{self.hdf5_filepath.name}:/spacing"

        # Add point data attributes
        for name, _ in self.grid_data["point_data"].items():
            self._add_point_attribute(grid, name, dims, prefix)

        # Add cell data attributes
        for name, _ in self.grid_data["cell_data"].items():
            self._add_cell_attribute(grid, name, dims, prefix)

    def _add_grid_to_collection(
        self, collection, time_step: int, time_value: float
    ) -> None:
        """Add a grid to a temporal collection using 3DRectMesh topology."""
        prefix = f"step_{time_step}/"

        grid = etree.SubElement(
            collection, "Grid", Name=f"Step_{time_step}", GridType="Uniform"
        )

        # Add time information
        etree.SubElement(grid, "Time", Value=str(int(time_value)))

        # Add topology - always use 3DRectMesh
        if self.grid_data:
            dims = self.grid_data["dimensions"]
            nx, ny, nz = dims[0], dims[1], dims[2]
            etree.SubElement(
                grid,
                "Topology",
                TopologyType="3DRectMesh",
                Dimensions=f"{nz} {ny} {nx}",  # Z Y X order
            )

            # Add geometry with ORIGIN_DXDYDZ
            geometry = etree.SubElement(grid, "Geometry", GeometryType="ORIGIN_DXDYDZ")

            # Origin DataItem
            origin_item = etree.SubElement(
                geometry,
                "DataItem",
                Name="Origin",
                Dimensions="3",
                NumberType="Float",
                Precision="8",
                Format="HDF",
            )
            origin_item.text = f"{self.hdf5_filepath.name}:/origin"

            # Spacing DataItem
            spacing_item = etree.SubElement(
                geometry,
                "DataItem",
                Name="Spacing",
                Dimensions="3",
                NumberType="Float",
                Precision="8",
                Format="HDF",
            )
            spacing_item.text = f"{self.hdf5_filepath.name}:/spacing"

            # Add attributes from grid_data if available
            for name in self.grid_data["point_data"].keys():
                self._add_point_attribute(grid, name, dims, prefix)

            for name in self.grid_data["cell_data"].keys():
                self._add_cell_attribute(grid, name, dims, prefix)

    def _add_point_attribute(
        self,
        grid,
        name: str,
        dimensions: tuple,
        prefix: str = "",
    ) -> None:
        """Add a point/node data attribute to the grid."""
        nx, ny, nz = dimensions[0], dimensions[1], dimensions[2]

        attribute = etree.SubElement(
            grid, "Attribute", Name=name, AttributeType="Scalar", Center="Node"
        )

        data_item = etree.SubElement(
            attribute,
            "DataItem",
            Dimensions=f"{nz} {ny} {nx}",  # Z Y X order
            NumberType="Float",
            Precision="8",
            Format="HDF",
        )
        data_item.text = f"{self.hdf5_filepath.name}:/{prefix}point_data/{name}"

    def _add_cell_attribute(
        self,
        grid,
        name: str,
        dimensions: tuple,
        prefix: str = "",
    ) -> None:
        """Add a cell data attribute to the grid."""
        nx, ny, nz = dimensions[0], dimensions[1], dimensions[2]
        # Cell dimensions are one less in each direction
        cell_nx = max(1, nx - 1)
        cell_ny = max(1, ny - 1)
        cell_nz = max(1, nz - 1)

        attribute = etree.SubElement(
            grid, "Attribute", Name=name, AttributeType="Scalar", Center="Cell"
        )

        data_item = etree.SubElement(
            attribute,
            "DataItem",
            Dimensions=f"{cell_nz} {cell_ny} {cell_nx}",  # Z Y X order
            NumberType="Float",
            Precision="8",
            Format="HDF",
        )
        data_item.text = f"{self.hdf5_filepath.name}:/{prefix}cell_data/{name}"

    @staticmethod
    def generate_temporal_collection(
        hdf5_filepath: str,
        output_filepath: str,
        time_steps: list[int],
        time_values: Optional[list[float]] = None,
        dimensions: tuple = (10, 10, 10),
        point_arrays: Optional[list[str]] = None,
        cell_arrays: Optional[list[str]] = None,
    ) -> None:
        """
        Generate XDMF for time series using 3DRectMesh topology.

        Args:
            hdf5_filepath: Path to HDF5 file
            output_filepath: Path for output XDMF file (should end in .xdmf2)
            time_steps: List of time step values
            time_values: Optional list of time values (defaults to time_steps)
            dimensions: Grid dimensions (nx, ny, nz)
            point_arrays: List of point array names
            cell_arrays: List of cell array names
        """
        hdf5_path = Path(hdf5_filepath)
        output_path = Path(output_filepath)

        point_arrays = point_arrays or []
        cell_arrays = cell_arrays or []
        time_values = time_values or [float(s) for s in time_steps]

        nx, ny, nz = dimensions[0], dimensions[1], dimensions[2]
        cell_nx = max(1, nx - 1)
        cell_ny = max(1, ny - 1)
        cell_nz = max(1, nz - 1)

        # Create XDMF structure
        xdmf = etree.Element("Xdmf", Version="3.0")
        domain = etree.SubElement(xdmf, "Domain")
        collection = etree.SubElement(
            domain,
            "Grid",
            Name="TimeSeries",
            GridType="Collection",
            CollectionType="Temporal",
        )

        for i, step in enumerate(time_steps):
            time_val = time_values[i] if i < len(time_values) else float(step)
            prefix = f"step_{step}/"

            grid = etree.SubElement(
                collection, "Grid", Name=f"Step_{step}", GridType="Uniform"
            )
            etree.SubElement(grid, "Time", Value=str(int(time_val)))

            # Topology - always use 3DRectMesh
            etree.SubElement(
                grid,
                "Topology",
                TopologyType="3DRectMesh",
                Dimensions=f"{nz} {ny} {nx}",  # Z Y X order
            )

            # Geometry with ORIGIN_DXDYDZ
            geometry = etree.SubElement(grid, "Geometry", GeometryType="ORIGIN_DXDYDZ")

            # Origin DataItem
            origin_item = etree.SubElement(
                geometry,
                "DataItem",
                Name="Origin",
                Dimensions="3",
                NumberType="Float",
                Precision="8",
                Format="HDF",
            )
            origin_item.text = f"{hdf5_path.name}:/origin"

            # Spacing DataItem
            spacing_item = etree.SubElement(
                geometry,
                "DataItem",
                Name="Spacing",
                Dimensions="3",
                NumberType="Float",
                Precision="8",
                Format="HDF",
            )
            spacing_item.text = f"{hdf5_path.name}:/spacing"

            # Point arrays
            for arr_name in point_arrays:
                attribute = etree.SubElement(
                    grid,
                    "Attribute",
                    Name=arr_name,
                    AttributeType="Scalar",
                    Center="Node",
                )
                data_item = etree.SubElement(
                    attribute,
                    "DataItem",
                    Dimensions=f"{nz} {ny} {nx}",  # Z Y X order
                    NumberType="Float",
                    Precision="8",
                    Format="HDF",
                )
                data_item.text = f"{hdf5_path.name}:/{prefix}point_data/{arr_name}"

            # Cell arrays
            for arr_name in cell_arrays:
                attribute = etree.SubElement(
                    grid,
                    "Attribute",
                    Name=arr_name,
                    AttributeType="Scalar",
                    Center="Cell",
                )
                data_item = etree.SubElement(
                    attribute,
                    "DataItem",
                    Dimensions=f"{cell_nz} {cell_ny} {cell_nx}",  # Z Y X order
                    NumberType="Float",
                    Precision="8",
                    Format="HDF",
                )
                data_item.text = f"{hdf5_path.name}:/{prefix}cell_data/{arr_name}"

        # Write to file
        tree = etree.ElementTree(xdmf)
        tree.write(
            str(output_path),
            pretty_print=True,
            xml_declaration=True,
            encoding="utf-8",
        )
