"""Tests for HDF5Writer module."""

from pathlib import Path

import h5py
import numpy as np
import pytest

from vts2h5.writer import HDF5Writer


class TestHDF5Writer:
    """Test cases for HDF5Writer class."""

    def test_init(self, temp_dir):
        """Test HDF5Writer initialization."""
        output_file = temp_dir / "test.h5"
        writer = HDF5Writer(str(output_file))

        assert writer.filepath == output_file
        assert writer.compression == "gzip"
        assert writer.compression_opts == 4
        assert writer.mode == "w"
        assert writer.file is None

    def test_init_custom_compression(self, temp_dir):
        """Test initialization with custom compression settings."""
        output_file = temp_dir / "test.h5"
        writer = HDF5Writer(str(output_file), compression="lzf", compression_opts=1)

        assert writer.compression == "lzf"
        assert writer.compression_opts == 1

    def test_context_manager(self, temp_dir):
        """Test HDF5Writer as context manager."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file)) as writer:
            assert writer.file is not None
            assert isinstance(writer.file, h5py.File)

        # File should be closed after context
        assert output_file.exists()

    def test_write_single_timestep(self, temp_dir, sample_grid_data):
        """Test writing a single time step."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file)) as writer:
            writer.write(sample_grid_data)

        # Verify file was created and contains data
        assert output_file.exists()

        with h5py.File(output_file, "r") as f:
            assert "origin" in f
            assert "spacing" in f
            assert "point_data" in f
            assert "temperature" in f["point_data"]
            assert "pressure" in f["point_data"]

    def test_write_with_timestep(self, temp_dir, sample_grid_data):
        """Test writing with explicit time step."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file)) as writer:
            writer.write(sample_grid_data, time_step=100)

        with h5py.File(output_file, "r") as f:
            assert "step_100" in f
            assert "point_data" in f["step_100"]
            assert "temperature" in f["step_100/point_data"]

    def test_write_multiple_timesteps(self, temp_dir, sample_grid_data):
        """Test writing multiple time steps."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file)) as writer:
            for step in [0, 100, 200]:
                writer.write(sample_grid_data, time_step=step)

        with h5py.File(output_file, "r") as f:
            assert "step_0" in f
            assert "step_100" in f
            assert "step_200" in f

    def test_write_multiple_method(self, temp_dir, sample_grid_data):
        """Test write_multiple method."""
        output_file = temp_dir / "test.h5"
        grid_list = [sample_grid_data, sample_grid_data, sample_grid_data]

        with HDF5Writer(str(output_file)) as writer:
            writer.write_multiple(grid_list, start_index=0)

        with h5py.File(output_file, "r") as f:
            assert "step_0" in f
            assert "step_1" in f
            assert "step_2" in f

    def test_origin_and_spacing(self, temp_dir, sample_grid_data):
        """Test that origin and spacing are calculated correctly."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file)) as writer:
            writer.write(sample_grid_data)

        with h5py.File(output_file, "r") as f:
            origin = f["origin"][:]
            spacing = f["spacing"][:]

            assert len(origin) == 3
            assert len(spacing) == 3
            assert all(isinstance(x, (float, np.floating)) for x in origin)
            assert all(isinstance(x, (float, np.floating)) for x in spacing)

    def test_data_reshaping(self, temp_dir, sample_grid_data):
        """Test that data is reshaped correctly for XDMF."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file)) as writer:
            writer.write(sample_grid_data, time_step=0)

        with h5py.File(output_file, "r") as f:
            temp_data = f["step_0/point_data/temperature"]
            dims = sample_grid_data["dimensions"]

            # Should be reshaped to (nz, ny, nx)
            expected_shape = (dims[2], dims[1], dims[0])
            assert temp_data.shape == expected_shape

    def test_compression_applied(self, temp_dir, sample_grid_data):
        """Test that compression is applied to datasets."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file), compression="gzip", compression_opts=9) as writer:
            writer.write(sample_grid_data)

        with h5py.File(output_file, "r") as f:
            dataset = f["point_data/temperature"]
            assert dataset.compression == "gzip"
            assert dataset.compression_opts == 9

    def test_no_compression(self, temp_dir, sample_grid_data):
        """Test writing without compression."""
        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file), compression=None) as writer:
            writer.write(sample_grid_data)

        with h5py.File(output_file, "r") as f:
            dataset = f["point_data/temperature"]
            assert dataset.compression is None

    def test_close_method(self, temp_dir):
        """Test explicit close method."""
        output_file = temp_dir / "test.h5"
        writer = HDF5Writer(str(output_file))
        writer.file = h5py.File(output_file, "w")

        assert writer.file is not None
        writer.close()
        assert writer.file is None

    def test_get_file_size(self, temp_dir, sample_grid_data):
        """Test getting file size."""
        output_file = temp_dir / "test.h5"
        writer = HDF5Writer(str(output_file))

        # Before writing
        assert writer.get_file_size() == 0

        # After writing
        with writer:
            writer.write(sample_grid_data)

        size = writer.get_file_size()
        assert size > 0
        assert isinstance(size, int)

    def test_append_mode(self, temp_dir, sample_grid_data):
        """Test append mode."""
        output_file = temp_dir / "test.h5"

        # Write first time step
        with HDF5Writer(str(output_file), mode="w") as writer:
            writer.write(sample_grid_data, time_step=0)

        # Append second time step
        with HDF5Writer(str(output_file), mode="a") as writer:
            writer.write(sample_grid_data, time_step=100)

        with h5py.File(output_file, "r") as f:
            assert "step_0" in f
            assert "step_100" in f

    def test_cell_data(self, temp_dir, sample_grid_data):
        """Test writing cell data."""
        # Add cell data to sample
        sample_grid_data["cell_data"] = {
            "cell_temp": np.random.rand(
                sample_grid_data["num_cells"]
            ).astype(np.float64)
        }

        output_file = temp_dir / "test.h5"

        with HDF5Writer(str(output_file)) as writer:
            writer.write(sample_grid_data)

        with h5py.File(output_file, "r") as f:
            assert "cell_data" in f
            assert "cell_temp" in f["cell_data"]

    def test_write_error_handling(self, temp_dir):
        """Test error handling during write."""
        output_file = temp_dir / "test.h5"

        # Invalid grid data (missing required fields)
        invalid_data = {"dimensions": [10, 10, 10]}

        with HDF5Writer(str(output_file)) as writer:
            with pytest.raises(RuntimeError):
                writer.write(invalid_data)
