"""Pytest fixtures for vts2h5 tests."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
import vtk
from vtk.util import numpy_support


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_vts_file(temp_dir):
    """Create a sample VTS file for testing."""
    # Create a simple structured grid
    nx, ny, nz = 10, 10, 10

    # Create points
    points = vtk.vtkPoints()
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                x = float(i) * 0.1
                y = float(j) * 0.1
                z = float(k) * 0.1
                points.InsertNextPoint(x, y, z)

    # Create structured grid
    grid = vtk.vtkStructuredGrid()
    grid.SetDimensions(nx, ny, nz)
    grid.SetPoints(points)

    # Add point data
    temperature = np.random.rand(nx * ny * nz).astype(np.float64)
    temp_array = numpy_support.numpy_to_vtk(temperature)
    temp_array.SetName("temperature")
    grid.GetPointData().AddArray(temp_array)

    pressure = np.random.rand(nx * ny * nz).astype(np.float64) * 100
    pres_array = numpy_support.numpy_to_vtk(pressure)
    pres_array.SetName("pressure")
    grid.GetPointData().AddArray(pres_array)

    # Write to file
    output_file = temp_dir / "test_sample.vts"
    writer = vtk.vtkXMLStructuredGridWriter()
    writer.SetFileName(str(output_file))
    writer.SetInputData(grid)
    writer.Write()

    return output_file


@pytest.fixture
def sample_vts_files(temp_dir):
    """Create multiple VTS files for time series testing."""
    files = []
    nx, ny, nz = 10, 10, 10

    for step in [0, 100, 200]:
        # Create points
        points = vtk.vtkPoints()
        for k in range(nz):
            for j in range(ny):
                for i in range(nx):
                    x = float(i) * 0.1
                    y = float(j) * 0.1
                    z = float(k) * 0.1
                    points.InsertNextPoint(x, y, z)

        # Create structured grid
        grid = vtk.vtkStructuredGrid()
        grid.SetDimensions(nx, ny, nz)
        grid.SetPoints(points)

        # Add point data (values change with time step)
        temperature = (np.random.rand(nx * ny * nz) + step * 0.01).astype(np.float64)
        temp_array = numpy_support.numpy_to_vtk(temperature)
        temp_array.SetName("temperature")
        grid.GetPointData().AddArray(temp_array)

        # Write to file
        output_file = temp_dir / f"scalar_variables_step{step}.vts"
        writer = vtk.vtkXMLStructuredGridWriter()
        writer.SetFileName(str(output_file))
        writer.SetInputData(grid)
        writer.Write()

        files.append(output_file)

    return files


@pytest.fixture
def invalid_vts_file(temp_dir):
    """Create an invalid VTS file for error testing."""
    invalid_file = temp_dir / "invalid.vts"
    invalid_file.write_text("This is not valid XML")
    return invalid_file


@pytest.fixture
def corrupted_vts_file(temp_dir):
    """Create a corrupted VTS file (valid XML but not VTK format)."""
    corrupted_file = temp_dir / "corrupted.vts"
    corrupted_file.write_text('<?xml version="1.0"?>\n<NotVTK><Data>test</Data></NotVTK>')
    return corrupted_file


@pytest.fixture
def sample_grid_data():
    """Create sample grid data dictionary for testing."""
    nx, ny, nz = 10, 10, 10
    num_points = nx * ny * nz

    return {
        "dimensions": [nx, ny, nz],
        "num_points": num_points,
        "num_cells": (nx - 1) * (ny - 1) * (nz - 1),
        "points": np.random.rand(num_points, 3).astype(np.float64),
        "point_data": {
            "temperature": np.random.rand(num_points).astype(np.float64),
            "pressure": np.random.rand(num_points).astype(np.float64) * 100,
        },
        "cell_data": {},
        "bounds": [0.0, 0.9, 0.0, 0.9, 0.0, 0.9],
        "metadata": {
            "source_file": "test.vts",
            "num_point_arrays": 2,
            "num_cell_arrays": 0,
        },
    }
