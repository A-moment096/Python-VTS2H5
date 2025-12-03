"""Tests for XDMF generator."""

import pytest


class TestXDMFGenerator:
    """Test cases for XDMFGenerator."""

    def test_generator_init(self):
        """Test generator initialization."""
        from vts2h5.xdmf import XDMFGenerator
        
        gen = XDMFGenerator("test.h5")
        assert gen.hdf5_filepath.name == "test.h5"

    # Add more tests when needed
