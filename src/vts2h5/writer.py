"""HDF5 file writer module."""

from pathlib import Path
from typing import Dict, Any, Optional
import h5py
import numpy as np


class HDF5Writer:
    """Writer for HDF5 files."""

    def __init__(
        self,
        filepath: str,
        compression: Optional[str] = "gzip",
        compression_opts: int = 4,
        mode: str = "w",
    ):
        """
        Initialize HDF5 writer.

        Args:
            filepath: Path to the output HDF5 file
            compression: Compression algorithm ('gzip', 'lzf', or None)
            compression_opts: Compression level (0-9 for gzip)
            mode: File mode ('w' for write, 'a' for append)
        """
        self.filepath = Path(filepath)
        self.compression = compression
        self.compression_opts = compression_opts
        self.mode = mode
        self.file: Optional[h5py.File] = None

    def __enter__(self):
        """Context manager entry."""
        self.file = h5py.File(self.filepath, self.mode)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.file:
            self.file.close()

    def write(self, grid_data: Dict[str, Any], time_step: Optional[int] = None) -> None:
        """
        Write grid data to HDF5 file.

        Args:
            grid_data: Dictionary containing grid data from VTSReader
            time_step: Optional time step index for time series data
        """
        if self.file is None:
            self.file = h5py.File(self.filepath, self.mode)

        try:
            # Write origin and spacing at root level (only once)
            if "origin" not in self.file and "bounds" in grid_data:
                bounds = grid_data["bounds"]
                dims = grid_data["dimensions"]
                
                # Calculate origin from bounds
                origin = np.array([bounds[0], bounds[2], bounds[4]], dtype=np.float64)
                self.file.create_dataset(
                    "origin",
                    data=origin,
                    compression=self.compression,
                    compression_opts=self.compression_opts,
                )
                
                # Calculate spacing from bounds and dimensions
                spacing = np.array([
                    (bounds[1] - bounds[0]) / max(1, dims[0] - 1),
                    (bounds[3] - bounds[2]) / max(1, dims[1] - 1),
                    (bounds[5] - bounds[4]) / max(1, dims[2] - 1) if dims[2] > 1 else 0.0
                ], dtype=np.float64)
                self.file.create_dataset(
                    "spacing",
                    data=spacing,
                    compression=self.compression,
                    compression_opts=self.compression_opts,
                )

            # Determine group prefix for time series
            prefix = f"step_{time_step}/" if time_step is not None else ""

            # Write point data
            if grid_data["point_data"]:
                point_data_group = self.file.require_group(f"{prefix}point_data")
                for name, array in grid_data["point_data"].items():
                    if name not in point_data_group:
                        # Reshape to 3D array in Z,Y,X order for XDMF compatibility
                        dims = grid_data["dimensions"]
                        nx, ny, nz = dims[0], dims[1], dims[2]
                        reshaped = array.reshape((nz, ny, nx))
                        point_data_group.create_dataset(
                            name,
                            data=reshaped,
                            compression=self.compression,
                            compression_opts=self.compression_opts,
                        )

            # Write cell data
            if grid_data["cell_data"]:
                cell_data_group = self.file.require_group(f"{prefix}cell_data")
                for name, array in grid_data["cell_data"].items():
                    if name not in cell_data_group:
                        cell_data_group.create_dataset(
                            name,
                            data=array,
                            compression=self.compression,
                            compression_opts=self.compression_opts,
                        )

        except Exception as e:
            raise RuntimeError(f"Failed to write HDF5 file: {e}")

    def close(self) -> None:
        """Close the HDF5 file."""
        if self.file:
            self.file.close()
            self.file = None

    def write_multiple(self, grid_data_list: list, start_index: int = 0) -> None:
        """
        Write multiple time steps to HDF5 file.

        Args:
            grid_data_list: List of grid data dictionaries
            start_index: Starting time step index
        """
        for i, grid_data in enumerate(grid_data_list):
            self.write(grid_data, time_step=start_index + i)

    def get_file_size(self) -> int:
        """
        Get the size of the HDF5 file in bytes.

        Returns:
            File size in bytes
        """
        if self.filepath.exists():
            return self.filepath.stat().st_size
        return 0
