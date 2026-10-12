"""Generic discovery and format selection preserve existing CLI options."""

import sys

import pytest

from tests.vtk_fixtures import make_dataset, write_dataset
from vtk2h5.cli import find_vtk_files, main


def test_discovery(tmp_path):
    for name in ["step10.VTU", "step0.vti", "step2.vtk", "ignored.vtd"]:
        (tmp_path / name).touch()
    assert [p.name for p in find_vtk_files(tmp_path)] == [
        "step0.vti",
        "step2.vtk",
        "step10.VTU",
    ]
    assert [p.name for p in find_vtk_files(tmp_path, [".VTU"])] == ["step10.VTU"]


def test_filter_and_info(tmp_path, monkeypatch, capsys):
    write_dataset(make_dataset("unstructured"), tmp_path / "step0.vtu")
    write_dataset(make_dataset("image"), tmp_path / "step0.vti")
    monkeypatch.setattr(
        sys, "argv", ["vtk2h5", str(tmp_path), "--format", "VTU", "--info"]
    )
    main()
    assert "vtkUnstructuredGrid" in capsys.readouterr().out
    monkeypatch.setattr(
        sys,
        "argv",
        ["vtk2h5", str(tmp_path), "--format", ".VTU", "-i", "-s", "-j", "1"],
    )
    main()
    assert (tmp_path / f"{tmp_path.name}.h5").exists()


def test_unsupported_format(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["vtk2h5", str(tmp_path), "--format", "vtd"])
    with pytest.raises(SystemExit):
        main()
