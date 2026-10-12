"""Descriptors faithfully describe every stored geometry and field."""

import h5py
import numpy as np
import pytest
from lxml import etree

from tests.vtk_fixtures import KINDS, make_dataset
from vtk2h5.mesh import normalize_dataset
from vtk2h5.writer import HDF5Writer
from vtk2h5.xdmf import XDMFGenerator


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("precision", ["preserve", "float32", "float64"])
def test_descriptors(tmp_path, kind, precision):
    data = normalize_dataset(make_dataset(kind), "fixture")
    h5path, xmf = tmp_path / "grid.h5", tmp_path / "descriptors/grid.xdmf"
    xmf.parent.mkdir()
    with HDF5Writer(str(h5path), float_dtype=precision, group="timeseries") as writer:
        writer.write(data, time_step=0)
        writer.write(data, time_step=10)
    XDMFGenerator.generate_temporal_collection(
        str(h5path), str(xmf), [0, 10], hdf5_group="timeseries", first_fields=["scalar"]
    )
    tree = etree.parse(str(xmf))
    with h5py.File(h5path) as h5:
        expected = {
            "uniform": "3DCoRectMesh",
            "rectilinear": "3DRectMesh",
            "structured": "3DSMesh",
            "unstructured": "Mixed",
        }[h5.attrs["geometry_type"]]
        for grid in tree.findall(".//Grid[@GridType='Uniform']"):
            assert grid.find("Topology").get("TopologyType") == expected
            assert grid.find("Attribute").get("Name") == "scalar"
            for item in grid.findall(".//DataItem"):
                filename, path = item.text.split(":", 1)
                assert filename == "../grid.h5"
                dataset = h5[path]
                assert item.get("Dimensions") == " ".join(map(str, dataset.shape))
                assert item.get("Precision") == str(dataset.dtype.itemsize)
                assert (
                    item.get("NumberType")
                    == {"f": "Float", "i": "Int", "u": "UInt"}[dataset.dtype.kind]
                )
            assert grid.find("Attribute[@Name='cell_ids']").get("Center") == "Cell"


def test_static_unstructured(tmp_path):
    data = normalize_dataset(make_dataset("polydata"), "fixture")
    h5path, xmf = tmp_path / "grid.h5", tmp_path / "grid.xdmf"
    with HDF5Writer(str(h5path)) as writer:
        writer.write(data)
    XDMFGenerator(str(h5path), data).generate(str(xmf))
    tree = etree.parse(str(xmf))
    assert tree.find(".//Topology").get("NumberOfElements") == str(data["num_cells"])


def test_final_reference(tmp_path):
    data = normalize_dataset(make_dataset("structured"), "fixture")
    temporary = tmp_path / "temporary.h5"
    with HDF5Writer(str(temporary)) as writer:
        writer.write(data)
    XDMFGenerator(
        str(temporary), data, hdf5_reference=str(tmp_path / "final.h5")
    ).generate(str(tmp_path / "final.xdmf"))
    assert "temporary.h5" not in (tmp_path / "final.xdmf").read_text()
    assert "final.h5:/origin" in (tmp_path / "final.xdmf").read_text()
