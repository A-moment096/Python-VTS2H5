"""Generic VTK readers preserve source geometry and all numeric fields."""

import numpy as np
import pytest
import vtk
from vtkmodules.util.numpy_support import vtk_to_numpy

from tests.vtk_fixtures import KINDS, make_dataset, write_dataset
from vtk2h5.reader import VTKReader, VTSReader
from vtk2h5.mesh import normalize_dataset


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("encoding", ["ascii", "binary", "appended", "raw"])
def test_xml_formats(tmp_path, kind, encoding):
    source = make_dataset(kind)
    path = write_dataset(source, tmp_path / f"step0.{KINDS[kind].upper()}", encoding)
    data = VTKReader(str(path)).read()
    assert data["num_points"] == source.GetNumberOfPoints()
    assert data["num_cells"] == source.GetNumberOfCells()
    np.testing.assert_allclose(
        data["points"], [source.GetPoint(i) for i in range(source.GetNumberOfPoints())]
    )
    for center, obj in [
        ("point_data", source.GetPointData()),
        ("cell_data", source.GetCellData()),
    ]:
        assert len(data[center]) == obj.GetNumberOfArrays()
        for name, array in data[center].items():
            np.testing.assert_array_equal(array, vtk_to_numpy(obj.GetArray(name)))
            assert array.dtype == vtk_to_numpy(obj.GetArray(name)).dtype
    info = VTKReader(str(path)).get_info()
    assert info["dataset_type"] == source.GetClassName()


@pytest.mark.parametrize(
    "kind", ["structured", "image", "rectilinear", "unstructured", "polydata"]
)
@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_legacy_all_fields(tmp_path, kind, encoding):
    source = make_dataset(kind)
    path = write_dataset(source, tmp_path / "step0.vtk", encoding)
    data = VTKReader(str(path)).read()
    assert set(data["point_data"]) == {
        "scalar",
        "other_scalar",
        "velocity",
        "tensor",
        "ids",
    }
    assert set(data["cell_data"]) == {"cell_ids", "flux"}


def test_failed_reads(tmp_path):
    with pytest.raises(FileNotFoundError):
        VTKReader(str(tmp_path / "missing.vtk"))
    for ext in ["vts", "vti", "vtr", "vtu", "vtp", "vtk", "vtd"]:
        path = tmp_path / f"invalid.{ext}"
        path.write_text("broken input")
        with pytest.raises(ValueError):
            VTKReader(str(path)).read()


def test_empty_geometry(tmp_path):
    path = write_dataset(vtk.vtkPolyData(), tmp_path / "empty.vtp")
    with pytest.raises(ValueError, match="empty"):
        VTKReader(str(path)).read()


def test_vts_compatibility_geometry(tmp_path):
    path = write_dataset(make_dataset("curved"), tmp_path / "curved.vts")
    assert VTSReader(str(path)).read()["geometry_type"] == "structured"


@pytest.mark.parametrize("problem", ["unnamed", "duplicate", "string", "tuples"])
def test_invalid_fields(problem):
    grid = make_dataset("structured")
    fields = grid.GetPointData()
    if problem == "string":
        array = vtk.vtkStringArray()
        array.SetName("text")
        array.SetNumberOfTuples(grid.GetNumberOfPoints())
        fields.AddArray(array)
    elif problem == "unnamed":
        fields.GetArray(0).SetName(None)
    elif problem == "duplicate":
        fields.GetArray(1).SetName(fields.GetArray(0).GetName())
    else:
        fields.GetArray(0).SetNumberOfTuples(1)
    with pytest.raises(ValueError):
        normalize_dataset(grid, "fixture")


def test_wrong_xml_type(tmp_path):
    path = write_dataset(make_dataset("image"), tmp_path / "image.vti")
    wrong = path.with_suffix(".vts")
    path.rename(wrong)
    with pytest.raises(ValueError, match="type"):
        VTKReader(str(wrong)).read()


@pytest.mark.parametrize(
    "extension,encoding",
    [("vtk", "ascii"), ("vtk", "binary"), ("vts", "ascii"), ("vts", "raw")],
)
def test_duplicate_names_in_file(tmp_path, extension, encoding):
    path = write_dataset(
        make_dataset("structured"), tmp_path / f"step0.{extension}", encoding
    )
    path.write_bytes(path.read_bytes().replace(b"other_scalar", b"scalar"))
    with pytest.raises(ValueError, match="duplicate"):
        VTKReader(str(path)).read()


def test_truncated_legacy(tmp_path):
    path = write_dataset(make_dataset("structured"), tmp_path / "step0.vtk", "ascii")
    path.write_text(path.read_text().rsplit(" ", 12)[0])
    with pytest.raises(ValueError):
        VTKReader(str(path)).read()


def test_incomplete_scalar_header(tmp_path):
    path = tmp_path / "step0.vtk"
    path.write_text(
        "# vtk DataFile Version 3.0\ntruncated\nASCII\nDATASET STRUCTURED_POINTS\nDIMENSIONS 2 1 1\nORIGIN 0 0 0\nSPACING 1 1 1\nPOINT_DATA 2\nSCALARS values float\n"
    )
    with pytest.raises(ValueError, match="truncated"):
        VTKReader(str(path)).read()


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_same_name_different_centers(tmp_path, encoding):
    dataset = make_dataset("structured")
    dataset.GetCellData().GetArray(0).SetName("scalar")
    path = write_dataset(dataset, tmp_path / "step0.vtk", encoding)
    data = VTKReader(str(path)).read()
    assert "scalar" in data["point_data"]
    assert "scalar" in data["cell_data"]


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
@pytest.mark.parametrize("metadata", [False, True])
def test_legacy_active_fields_and_metadata(tmp_path, encoding, metadata):
    dataset = make_dataset("structured")
    dataset.GetPointData().SetActiveScalars("scalar")
    dataset.GetPointData().SetActiveVectors("velocity")
    dataset.GetPointData().SetActiveTensors("tensor")
    if metadata:
        array = dataset.GetPointData().GetArray("velocity")
        array.SetComponentName(0, "x component")
        array.GetInformation().Set(vtk.vtkDataArray.L2_NORM_RANGE(), [0,1], 2)
        other = dataset.GetPointData().GetArray("other_scalar")
        other.SetComponentName(0, "other component")
    path = write_dataset(dataset, tmp_path / "step0.vtk", encoding)
    data = VTKReader(str(path)).read()
    assert set(data["point_data"]) == {"scalar", "other_scalar", "velocity", "tensor", "ids"}
    for name, values in data["point_data"].items():
        np.testing.assert_array_equal(values, vtk_to_numpy(dataset.GetPointData().GetArray(name)))
