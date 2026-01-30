"""VTS file reader module."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import vtk
from vtkmodules.util import numpy_support


class VTSReader:
    """Reader for VTK Structured Grid (VTS) files."""

    def __init__(self, filepath: str):
        """
        Initialize VTS reader.

        Args:
            filepath: Path to the VTS file
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

    def validate_xml(self) -> tuple[bool, Optional[str]]:
        """
        Validate that the VTS file is well-formed XML.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            tree = ET.parse(str(self.filepath))
            root = tree.getroot()

            # Check if it's a VTK file
            if root.tag != "VTKFile":
                return False, "Not a valid VTK file (missing VTKFile root element)"

            # Check if it's a StructuredGrid
            if root.get("type") != "StructuredGrid":
                return False, f"Not a StructuredGrid file (type is {root.get('type')})"

            return True, None
        except ET.ParseError as e:
            return False, f"XML parse error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def read(self) -> dict[str, Any]:
        """
        Read VTS file and extract grid data.

        Returns:
            Dictionary containing:
                - dimensions: Grid dimensions (nx, ny, nz)
                - points: Point coordinates array
                - point_data: Dictionary of point data arrays
                - cell_data: Dictionary of cell data arrays
                - metadata: Additional metadata
        """
        # Read VTS file
        reader = vtk.vtkXMLStructuredGridReader()
        reader.SetFileName(str(self.filepath))
        reader.Update()

        output = reader.GetOutput()

        # Extract grid information
        dimensions = [0, 0, 0]
        output.GetDimensions(dimensions)
        num_points = output.GetNumberOfPoints()
        num_cells = output.GetNumberOfCells()

        # Extract points
        points_vtk = output.GetPoints()
        points = numpy_support.vtk_to_numpy(points_vtk.GetData())

        # Extract point data
        point_data = {}
        point_data_obj = output.GetPointData()
        for i in range(point_data_obj.GetNumberOfArrays()):
            array_name = point_data_obj.GetArrayName(i)
            array_vtk = point_data_obj.GetArray(i)
            array_numpy = numpy_support.vtk_to_numpy(array_vtk)
            point_data[array_name] = array_numpy

        # Extract cell data
        cell_data = {}
        cell_data_obj = output.GetCellData()
        for i in range(cell_data_obj.GetNumberOfArrays()):
            array_name = cell_data_obj.GetArrayName(i)
            array_vtk = cell_data_obj.GetArray(i)
            array_numpy = numpy_support.vtk_to_numpy(array_vtk)
            cell_data[array_name] = array_numpy

        # Get bounds and spacing if available
        bounds = list(output.GetBounds())

        result = {
            "dimensions": dimensions,
            "num_points": num_points,
            "num_cells": num_cells,
            "points": points,
            "point_data": point_data,
            "cell_data": cell_data,
            "bounds": bounds,
            "metadata": {
                "source_file": str(self.filepath),
                "num_point_arrays": len(point_data),
                "num_cell_arrays": len(cell_data),
            },
        }

        return result

    def get_info(self) -> dict[str, Any]:
        """
        Get basic information about the VTS file without loading all data.

        Returns:
            Dictionary with file information
        """
        reader = vtk.vtkXMLStructuredGridReader()
        reader.SetFileName(str(self.filepath))
        reader.Update()

        output = reader.GetOutput()
        point_data_obj = output.GetPointData()
        cell_data_obj = output.GetCellData()

        dimensions = [0, 0, 0]
        output.GetDimensions(dimensions)

        bounds = [0.0] * 6
        output.GetBounds(bounds)

        info = {
            "filepath": str(self.filepath),
            "dimensions": dimensions,
            "num_points": output.GetNumberOfPoints(),
            "num_cells": output.GetNumberOfCells(),
            "bounds": bounds,
            "point_arrays": [
                point_data_obj.GetArrayName(i)
                for i in range(point_data_obj.GetNumberOfArrays())
            ],
            "cell_arrays": [
                cell_data_obj.GetArrayName(i)
                for i in range(cell_data_obj.GetNumberOfArrays())
            ],
        }

        return info
