"""VTS2H5 - Convert VTK Structured Grid files to HDF5 with XDMF2 descriptors."""

__version__ = "0.1.0"

from .reader import VTSReader
from .writer import HDF5Writer
from .xdmf import XDMFGenerator

__all__ = ["VTSReader", "HDF5Writer", "XDMFGenerator"]
