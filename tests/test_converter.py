"""Tests for converter module."""

import re
from pathlib import Path

import h5py
import pytest

from vts2h5.converter import (
    convert_vts_to_hdf5,
    extract_time_steps,
    read_vts_file_worker,
)


class TestExtractTimeSteps:
    """Test cases for extract_time_steps function."""

    def test_extract_from_standard_format(self, temp_dir):
        """Test extracting time steps from standard filename format."""
        files = [
            temp_dir / "scalar_variables_step0.vts",
            temp_dir / "scalar_variables_step100.vts",
            temp_dir / "scalar_variables_step200.vts",
        ]

        # Create dummy files
        for f in files:
            f.touch()

        time_steps = extract_time_steps(files)

        assert time_steps == [0, 100, 200]

    def test_extract_with_underscores(self, temp_dir):
        """Test extracting from filenames with different formats."""
        files = [
            temp_dir / "step_10.vts",
            temp_dir / "step_20.vts",
            temp_dir / "step_30.vts",
        ]

        for f in files:
            f.touch()

        time_steps = extract_time_steps(files)

        assert time_steps == [10, 20, 30]

    def test_fallback_to_index(self, temp_dir):
        """Test fallback to file index when no step number found."""
        files = [
            temp_dir / "data1.vts",
            temp_dir / "data2.vts",
            temp_dir / "data3.vts",
        ]

        for f in files:
            f.touch()

        time_steps = extract_time_steps(files)

        assert time_steps == [0, 1, 2]

    def test_mixed_formats(self, temp_dir):
        """Test extraction with mixed filename formats."""
        files = [
            temp_dir / "step0.vts",
            temp_dir / "noformat.vts",
            temp_dir / "step100.vts",
        ]

        for f in files:
            f.touch()

        time_steps = extract_time_steps(files)

        # First has step 0, second falls back to index 1, third has step 100
        assert time_steps == [0, 1, 100]


class TestReadVTSFileWorker:
    """Test cases for read_vts_file_worker function."""

    def test_read_valid_file(self, sample_vts_file):
        """Test reading a valid VTS file."""
        grid_data, file_size = read_vts_file_worker(str(sample_vts_file))

        assert isinstance(grid_data, dict)
        assert "dimensions" in grid_data
        assert "point_data" in grid_data
        assert file_size > 0

    def test_read_corrupted_xml(self, invalid_vts_file):
        """Test reading corrupted XML file."""
        with pytest.raises(ValueError, match="Corrupted XML"):
            read_vts_file_worker(str(invalid_vts_file))

    def test_read_invalid_format(self, corrupted_vts_file):
        """Test reading file with invalid VTK format."""
        with pytest.raises(ValueError, match="Failed to read"):
            read_vts_file_worker(str(corrupted_vts_file))

    def test_file_size(self, sample_vts_file):
        """Test that file size is returned correctly."""
        _, file_size = read_vts_file_worker(str(sample_vts_file))

        actual_size = sample_vts_file.stat().st_size
        assert file_size == actual_size


class TestConvertVTSToHDF5:
    """Test cases for convert_vts_to_hdf5 function."""

    def test_convert_single_file(self, temp_dir, sample_vts_files):
        """Test converting a single VTS file."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        stats = convert_vts_to_hdf5(
            input_files=[sample_vts_files[0]],
            output_file=output_h5,
            xdmf_output=output_xdmf,
            silent=True,
        )

        assert output_h5.exists()
        assert output_xdmf.exists()
        assert stats["num_files"] == 1
        assert stats["converted_size"] > 0

    def test_convert_multiple_files(self, temp_dir, sample_vts_files):
        """Test converting multiple VTS files."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        stats = convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            silent=True,
        )

        assert output_h5.exists()
        assert output_xdmf.exists()
        assert stats["num_files"] == len(sample_vts_files)

    def test_hdf5_structure(self, temp_dir, sample_vts_files):
        """Test HDF5 file structure after conversion."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            silent=True,
        )

        with h5py.File(output_h5, "r") as f:
            # Check for origin and spacing
            assert "origin" in f
            assert "spacing" in f

            # Check for time steps
            assert "step_0" in f
            assert "step_100" in f
            assert "step_200" in f

            # Check for point data
            assert "temperature" in f["step_0/point_data"]

    def test_compression_gzip(self, temp_dir, sample_vts_files):
        """Test conversion with gzip compression."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            compression="gzip",
            compression_level=9,
            silent=True,
        )

        with h5py.File(output_h5, "r") as f:
            dataset = f["step_0/point_data/temperature"]
            assert dataset.compression == "gzip"
            assert dataset.compression_opts == 9

    def test_no_compression(self, temp_dir, sample_vts_files):
        """Test conversion without compression."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            compression="none",
            silent=True,
        )

        with h5py.File(output_h5, "r") as f:
            dataset = f["step_0/point_data/temperature"]
            assert dataset.compression is None

    def test_sequential_processing(self, temp_dir, sample_vts_files):
        """Test sequential processing (jobs=1)."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        stats = convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            jobs=1,
            silent=True,
        )

        assert output_h5.exists()
        assert stats["num_files"] == len(sample_vts_files)

    def test_parallel_processing(self, temp_dir, sample_vts_files):
        """Test parallel processing (jobs=2)."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        stats = convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            jobs=2,
            silent=True,
        )

        assert output_h5.exists()
        assert stats["num_files"] == len(sample_vts_files)

    def test_auto_jobs(self, temp_dir, sample_vts_files):
        """Test automatic job detection (jobs=0)."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        stats = convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            jobs=0,
            silent=True,
        )

        assert output_h5.exists()
        assert stats["num_files"] == len(sample_vts_files)

    def test_statistics(self, temp_dir, sample_vts_files):
        """Test conversion statistics."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        stats = convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            silent=True,
        )

        assert "total_original_size" in stats
        assert "converted_size" in stats
        assert "reduction_ratio" in stats
        assert "num_files" in stats

        assert stats["total_original_size"] > 0
        assert stats["converted_size"] > 0
        assert stats["num_files"] == len(sample_vts_files)

    def test_verbose_mode(self, temp_dir, sample_vts_files):
        """Test conversion with verbose mode."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        stats = convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            verbose=True,
            silent=False,
        )

        assert "grid_info" in stats
        if stats["grid_info"]:
            assert "dimensions" in stats["grid_info"]

    def test_xdmf_generation(self, temp_dir, sample_vts_files):
        """Test that XDMF file is generated correctly."""
        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        convert_vts_to_hdf5(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            silent=True,
        )

        assert output_xdmf.exists()

        # Parse and verify XDMF
        from lxml import etree
        tree = etree.parse(str(output_xdmf))
        root = tree.getroot()

        assert root.tag == "Xdmf"
        grids = tree.findall(".//Grid[@GridType='Uniform']")
        assert len(grids) == len(sample_vts_files)
