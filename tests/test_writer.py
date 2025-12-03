"""Tests for HDF5 writer."""

import pytest
from pathlib import Path
import tempfile


class TestHDF5Writer:
    """Test cases for HDF5Writer."""

    def test_writer_context_manager(self):
        """Test writer context manager."""
        from vts2h5.writer import HDF5Writer
        
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with HDF5Writer(tmp_path) as writer:
                assert writer.file is not None
            
            # File should exist
            assert Path(tmp_path).exists()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # Add more tests when needed
