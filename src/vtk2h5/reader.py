"""Serial VTK dataset readers."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import vtk

from vtk2h5.declarations import validate_legacy_declarations, validate_xml_declarations
from vtk2h5.mesh import normalize_dataset

READERS = {
    ".vts": (vtk.vtkXMLStructuredGridReader, "vtkStructuredGrid"),
    ".vti": (vtk.vtkXMLImageDataReader, "vtkImageData"),
    ".vtr": (vtk.vtkXMLRectilinearGridReader, "vtkRectilinearGrid"),
    ".vtu": (vtk.vtkXMLUnstructuredGridReader, "vtkUnstructuredGrid"),
    ".vtp": (vtk.vtkXMLPolyDataReader, "vtkPolyData"),
    ".vtk": (vtk.vtkDataSetReader, None),
}
SUPPORTED_FORMATS = tuple(ext.lstrip(".") for ext in READERS)


class VTKReader:
    """Read common serial VTK formats through VTK's native readers."""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        if not self.filepath.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")
        if self.filepath.suffix.lower() not in READERS:
            raise ValueError(f"Unsupported VTK extension: {self.filepath.suffix}")

    def read(self) -> dict[str, Any]:
        if self.filepath.suffix.lower() == ".vtk":
            validate_legacy_declarations(self.filepath)
        else:
            validate_xml_declarations(self.filepath)
        constructor, expected = READERS[self.filepath.suffix.lower()]
        reader = constructor()
        errors = []

        @vtk.calldata_type(vtk.VTK_STRING)
        def on_error(obj, event, message):
            errors.append(str(message))

        reader.AddObserver(vtk.vtkCommand.ErrorEvent, on_error)
        reader.AddObserver(vtk.vtkCommand.WarningEvent, on_error)
        reader.SetFileName(str(self.filepath))
        if isinstance(reader, vtk.vtkDataSetReader):
            for category in (
                "Scalars",
                "Vectors",
                "Normals",
                "Tensors",
                "TCoords",
                "Fields",
                "ColorScalars",
            ):
                getattr(reader, f"ReadAll{category}On")()
        elif not reader.CanReadFile(str(self.filepath)):
            raise ValueError(
                f"Failed to read {self.filepath.name}: wrong or invalid VTK XML type"
            )
        reader.Update()
        if errors or reader.GetErrorCode():
            raise ValueError(
                f"Failed to read {self.filepath.name}: {'; '.join(errors) or reader.GetErrorCode()}"
            )
        output = reader.GetOutput()
        if output is None or (expected and output.GetClassName() != expected):
            raise ValueError(
                f"Failed to read {self.filepath.name}: incorrect dataset type"
            )
        return normalize_dataset(output, str(self.filepath))

    def get_info(self) -> dict[str, Any]:
        data = self.read()
        info = {
            key: data[key]
            for key in (
                "dataset_type",
                "geometry_type",
                "num_points",
                "num_cells",
                "bounds",
            )
        }
        if "dimensions" in data:
            info["dimensions"] = data["dimensions"]
        info.update(
            filepath=str(self.filepath),
            point_arrays=list(data["point_data"]),
            cell_arrays=list(data["cell_data"]),
        )
        return info


class VTSReader(VTKReader):
    """Reader for VTK Structured Grid (VTS) files."""

    def __init__(self, filepath: str):
        super().__init__(filepath)
        if self.filepath.suffix.lower() != ".vts":
            raise ValueError("VTSReader requires a .vts StructuredGrid file")

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
