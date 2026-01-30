"""Tests for VTSReader module."""

from pathlib import Path

import numpy as np
import pytest

from vts2h5.reader import VTSReader


class TestVTSReader:
    """Test cases for VTSReader class."""

    def test_init_with_valid_file(self, sample_vts_file):
        """Test initialization with a valid VTS file."""
        reader = VTSReader(str(sample_vts_file))
        assert reader.filepath == sample_vts_file
        assert reader.filepath.exists()

    def test_init_with_nonexistent_file(self):
        """Test initialization with a non-existent file."""
        with pytest.raises(FileNotFoundError):
            VTSReader("nonexistent.vts")

    def test_validate_xml_valid_file(self, sample_vts_file):
        """Test XML validation with a valid VTS file."""
        reader = VTSReader(str(sample_vts_file))
        is_valid, error = reader.validate_xml()
        assert is_valid is True
        assert error is None

    def test_validate_xml_invalid_xml(self, invalid_vts_file):
        """Test XML validation with invalid XML."""
        reader = VTSReader(str(invalid_vts_file))
        is_valid, error = reader.validate_xml()
        assert is_valid is False
        assert "XML parse error" in error

    def test_validate_xml_wrong_format(self, corrupted_vts_file):
        """Test XML validation with wrong VTK format."""
        reader = VTSReader(str(corrupted_vts_file))
        is_valid, error = reader.validate_xml()
        assert is_valid is False
        assert "Not a valid VTK file" in error

    def test_read_basic_structure(self, sample_vts_file):
        """Test reading basic structure from VTS file."""
        reader = VTSReader(str(sample_vts_file))
        data = reader.read()

        assert "dimensions" in data
        assert "num_points" in data
        assert "num_cells" in data
        assert "points" in data
        assert "point_data" in data
        assert "cell_data" in data
        assert "bounds" in data
        assert "metadata" in data

    def test_read_dimensions(self, sample_vts_file):
        """Test reading grid dimensions."""
        reader = VTSReader(str(sample_vts_file))
        data = reader.read()

        dims = data["dimensions"]
        assert len(dims) == 3
        assert all(isinstance(d, int) for d in dims)
        assert all(d > 0 for d in dims)

    def test_read_points(self, sample_vts_file):
        """Test reading point coordinates."""
        reader = VTSReader(str(sample_vts_file))
        data = reader.read()

        points = data["points"]
        assert isinstance(points, np.ndarray)
        assert points.ndim == 2
        assert points.shape[1] == 3  # x, y, z coordinates
        assert points.shape[0] == data["num_points"]

    def test_read_point_data(self, sample_vts_file):
        """Test reading point data arrays."""
        reader = VTSReader(str(sample_vts_file))
        data = reader.read()

        point_data = data["point_data"]
        assert isinstance(point_data, dict)
        assert "temperature" in point_data
        assert "pressure" in point_data

        for _ , array in point_data.items():
            assert isinstance(array, np.ndarray)
            assert len(array) == data["num_points"]

    def test_get_info(self, sample_vts_file):
        """Test getting file information without loading all data."""
        reader = VTSReader(str(sample_vts_file))
        info = reader.get_info()

        assert "filepath" in info
        assert "dimensions" in info
        assert "num_points" in info
        assert "num_cells" in info
        assert "bounds" in info
        assert "point_arrays" in info
        assert "cell_arrays" in info

        assert isinstance(info["point_arrays"], list)
        assert len(info["point_arrays"]) > 0

    def test_get_info_array_names(self, sample_vts_file):
        """Test that get_info returns correct array names."""
        reader = VTSReader(str(sample_vts_file))
        info = reader.get_info()

        assert "temperature" in info["point_arrays"]
        assert "pressure" in info["point_arrays"]

    def test_read_consistency(self, sample_vts_file):
        """Test that multiple reads return consistent data."""
        reader = VTSReader(str(sample_vts_file))
        data1 = reader.read()
        data2 = reader.read()

        assert data1["dimensions"] == data2["dimensions"]
        assert data1["num_points"] == data2["num_points"]
        assert np.allclose(data1["points"], data2["points"])

    def test_bounds_format(self, sample_vts_file):
        """Test that bounds are in correct format."""
        reader = VTSReader(str(sample_vts_file))
        data = reader.read()

        bounds = data["bounds"]
        assert len(bounds) == 6  # xmin, xmax, ymin, ymax, zmin, zmax
        assert all(isinstance(b, float) for b in bounds)

    def test_metadata(self, sample_vts_file):
        """Test metadata content."""
        reader = VTSReader(str(sample_vts_file))
        data = reader.read()

        metadata = data["metadata"]
        assert "source_file" in metadata
        assert "num_point_arrays" in metadata
        assert "num_cell_arrays" in metadata
        assert metadata["num_point_arrays"] >= 0
        assert metadata["num_cell_arrays"] >= 0

    def test_multiple_files(self, sample_vts_files):
        """Test reading multiple VTS files."""
        for vts_file in sample_vts_files:
            reader = VTSReader(str(vts_file))
            data = reader.read()
            assert data["num_points"] > 0
            assert len(data["point_data"]) > 0
