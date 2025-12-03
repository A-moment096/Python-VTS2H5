"""Tests for VTS reader."""

import pytest
from pathlib import Path


class TestVTSReader:
    """Test cases for VTSReader."""

    def test_reader_init(self):
        """Test reader initialization."""
        # This will fail if file doesn't exist, which is expected
        with pytest.raises(FileNotFoundError):
            from vts2h5.reader import VTSReader
            reader = VTSReader("nonexistent.vts")

    # Add more tests when sample data is available
