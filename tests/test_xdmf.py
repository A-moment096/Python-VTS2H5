"""Tests for XDMFGenerator module."""

from pathlib import Path

import pytest
from lxml import etree

from vts2h5.writer import HDF5Writer
from vts2h5.xdmf import XDMFGenerator


class TestXDMFGenerator:
    """Test cases for XDMFGenerator class."""

    def test_init(self, temp_dir):
        """Test XDMFGenerator initialization."""
        h5_file = temp_dir / "test.h5"
        generator = XDMFGenerator(str(h5_file))

        assert generator.hdf5_filepath == h5_file
        assert generator.grid_data is None

    def test_init_with_grid_data(self, temp_dir, sample_grid_data):
        """Test initialization with grid data."""
        h5_file = temp_dir / "test.h5"
        generator = XDMFGenerator(str(h5_file), sample_grid_data)

        assert generator.grid_data is not None
        assert generator.grid_data == sample_grid_data

    def test_generate_single_grid(self, temp_dir, sample_grid_data):
        """Test generating XDMF for a single grid."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        # First write HDF5 data
        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        # Generate XDMF
        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file))

        assert xdmf_file.exists()

    def test_xdmf_structure(self, temp_dir, sample_grid_data):
        """Test basic XDMF XML structure."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file))

        tree = etree.parse(str(xdmf_file))
        root = tree.getroot()

        assert root.tag == "Xdmf"
        assert root.get("Version") == "3.0"

        domain = root.find("Domain")
        assert domain is not None

    def test_single_grid_topology(self, temp_dir, sample_grid_data):
        """Test topology in single grid."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file))

        tree = etree.parse(str(xdmf_file))
        topology = tree.find(".//Topology")

        assert topology is not None
        assert topology.get("TopologyType") == "3DRectMesh"

        # Check dimensions (should be Z Y X order)
        dims = sample_grid_data["dimensions"]
        expected_dims = f"{dims[2]} {dims[1]} {dims[0]}"
        assert topology.get("Dimensions") == expected_dims

    def test_single_grid_geometry(self, temp_dir, sample_grid_data):
        """Test geometry with ORIGIN_DXDYDZ."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file))

        tree = etree.parse(str(xdmf_file))
        geometry = tree.find(".//Geometry")

        assert geometry is not None
        assert geometry.get("GeometryType") == "ORIGIN_DXDYDZ"

        # Check for Origin and Spacing DataItems
        data_items = geometry.findall(".//DataItem")
        assert len(data_items) >= 2

        names = [item.get("Name") for item in data_items]
        assert "Origin" in names
        assert "Spacing" in names

    def test_point_attributes(self, temp_dir, sample_grid_data):
        """Test point data attributes."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file))

        tree = etree.parse(str(xdmf_file))
        attributes = tree.findall(".//Attribute")

        assert len(attributes) >= 2

        attr_names = [attr.get("Name") for attr in attributes]
        assert "temperature" in attr_names
        assert "pressure" in attr_names

        # Check that point attributes have Center="Node"
        for attr in attributes:
            if attr.get("Name") in ["temperature", "pressure"]:
                assert attr.get("Center") == "Node"

    def test_generate_temporal_collection(self, temp_dir, sample_grid_data):
        """Test generating temporal collection for time series."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"
        time_steps = [0, 100, 200]

        # Write HDF5 with multiple time steps
        with HDF5Writer(str(h5_file)) as writer:
            for step in time_steps:
                writer.write(sample_grid_data, time_step=step)

        # Generate XDMF for time series
        XDMFGenerator.generate_temporal_collection(
            str(h5_file),
            str(xdmf_file),
            time_steps=time_steps,
            dimensions=sample_grid_data["dimensions"],
            point_arrays=list(sample_grid_data["point_data"].keys()),
        )

        assert xdmf_file.exists()

    def test_temporal_collection_structure(self, temp_dir, sample_grid_data):
        """Test temporal collection XML structure."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"
        time_steps = [0, 100, 200]

        with HDF5Writer(str(h5_file)) as writer:
            for step in time_steps:
                writer.write(sample_grid_data, time_step=step)

        XDMFGenerator.generate_temporal_collection(
            str(h5_file),
            str(xdmf_file),
            time_steps=time_steps,
            dimensions=sample_grid_data["dimensions"],
            point_arrays=list(sample_grid_data["point_data"].keys()),
        )

        tree = etree.parse(str(xdmf_file))

        # Check for temporal collection
        collection = tree.find(".//Grid[@GridType='Collection']")
        assert collection is not None
        assert collection.get("CollectionType") == "Temporal"

        # Check for individual time step grids
        grids = tree.findall(".//Grid[@GridType='Uniform']")
        assert len(grids) == len(time_steps)

    def test_time_values(self, temp_dir, sample_grid_data):
        """Test time values in temporal collection."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"
        time_steps = [0, 100, 200]
        time_values = [0.0, 1.0, 2.0]

        with HDF5Writer(str(h5_file)) as writer:
            for step in time_steps:
                writer.write(sample_grid_data, time_step=step)

        XDMFGenerator.generate_temporal_collection(
            str(h5_file),
            str(xdmf_file),
            time_steps=time_steps,
            time_values=time_values,
            dimensions=sample_grid_data["dimensions"],
            point_arrays=list(sample_grid_data["point_data"].keys()),
        )

        tree = etree.parse(str(xdmf_file))
        time_elements = tree.findall(".//Time")

        assert len(time_elements) == len(time_steps)

        for i, time_elem in enumerate(time_elements):
            assert time_elem.get("Value") == str(int(time_values[i]))

    def test_hdf5_paths(self, temp_dir, sample_grid_data):
        """Test HDF5 file paths in DataItems."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file))

        tree = etree.parse(str(xdmf_file))
        data_items = tree.findall(".//DataItem[@Format='HDF']")

        assert len(data_items) > 0

        # Check that all paths reference the correct HDF5 file
        for item in data_items:
            assert h5_file.name in item.text

    def test_cell_attributes(self, temp_dir, sample_grid_data):
        """Test cell data attributes."""
        # Add cell data
        sample_grid_data["cell_data"] = {
            "cell_temp": [1.0] * sample_grid_data["num_cells"]
        }

        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        XDMFGenerator.generate_temporal_collection(
            str(h5_file),
            str(xdmf_file),
            time_steps=[0],
            dimensions=sample_grid_data["dimensions"],
            point_arrays=list(sample_grid_data["point_data"].keys()),
            cell_arrays=list(sample_grid_data["cell_data"].keys()),
        )

        tree = etree.parse(str(xdmf_file))

        # Find cell attribute
        cell_attrs = [
            attr for attr in tree.findall(".//Attribute")
            if attr.get("Center") == "Cell"
        ]

        assert len(cell_attrs) > 0
        assert any(attr.get("Name") == "cell_temp" for attr in cell_attrs)

    def test_generate_with_timestep_instance(self, temp_dir, sample_grid_data):
        """Test generate method with time steps."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"
        time_steps = [0, 100]

        with HDF5Writer(str(h5_file)) as writer:
            for step in time_steps:
                writer.write(sample_grid_data, time_step=step)

        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file), time_steps=time_steps)

        tree = etree.parse(str(xdmf_file))
        grids = tree.findall(".//Grid[@GridType='Uniform']")

        assert len(grids) == len(time_steps)

    def test_xml_validity(self, temp_dir, sample_grid_data):
        """Test that generated XML is valid and parseable."""
        h5_file = temp_dir / "test.h5"
        xdmf_file = temp_dir / "test.xdmf2"

        with HDF5Writer(str(h5_file)) as writer:
            writer.write(sample_grid_data)

        generator = XDMFGenerator(str(h5_file), sample_grid_data)
        generator.generate(str(xdmf_file))

        # Should parse without errors
        tree = etree.parse(str(xdmf_file))
        assert tree is not None

        # Check XML declaration
        content = xdmf_file.read_text()
        assert '<?xml version=' in content
