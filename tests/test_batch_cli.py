import shutil
import sys

import h5py
import pytest
from lxml import etree

from vts2h5.cli import main, parse_args
from vts2h5.writer import HDF5Writer
from vts2h5.xdmf import XDMFGenerator


@pytest.mark.parametrize("mode", ["cwd", "inside", "beside", "output"])
def test_multiple_folders_and_output_locations(
    sample_vts_file, tmp_path, monkeypatch, mode
):
    home = tmp_path / "home"
    home.mkdir()
    folders = [tmp_path / "project" / name for name in ["trial1", "trial2"]]
    for folder in folders:
        folder.mkdir(parents=True)
        shutil.copyfile(sample_vts_file, folder / "step_0.vts")
    monkeypatch.chdir(home)
    options = {
        "cwd": [],
        "inside": ["-i"],
        "beside": ["-n"],
        "output": ["-o", str(tmp_path / "results")],
    }[mode]
    monkeypatch.setattr(
        sys,
        "argv",
        ["vts2h5", *map(str, folders), *options, "-f", "TEMP", "-j", "1", "-s"],
    )
    main()
    for folder in folders:
        output = {
            "cwd": home,
            "inside": folder,
            "beside": folder.parent,
            "output": tmp_path / "results",
        }[mode]
        h5 = output / f"{folder.name}.h5"
        xmf = output / f"{folder.name}.xdmf"
        assert h5.exists()
        tree = etree.parse(str(xmf))
        assert tree.find(".//Attribute").get("Name") == "temperature"
        with h5py.File(h5) as data:
            assert "timeseries/step_0/point_data/temperature" in data


def test_collisions_rejected_before_writing(tmp_path, monkeypatch):
    folders = [tmp_path / parent / "trial" for parent in ["one", "two"]]
    for folder in folders:
        folder.mkdir(parents=True)
        (folder / "step_0.vts").touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["vts2h5", *map(str, folders), "-s"])
    with pytest.raises(SystemExit):
        main()
    assert not list(tmp_path.glob("*.h5"))


@pytest.mark.parametrize(
    "flags", [["-i", "-n"], ["-n", "-o", "results"], ["-i", "-o", "results"]]
)
def test_conflicting_locations_rejected(monkeypatch, flags):
    monkeypatch.setattr(sys, "argv", ["vts2h5", "data", *flags])
    with pytest.raises(SystemExit):
        parse_args()


@pytest.mark.parametrize(
    "preference, expected",
    [
        (["con"], ["Con_Nb_1", "Con_Nb_2", "parameter"]),
        (["CON_NB_2"], ["Con_Nb_2", "parameter", "Con_Nb_1"]),
        (["con_nb_2", "param"], ["Con_Nb_2", "parameter", "Con_Nb_1"]),
    ],
)
def test_field_priority_case_insensitive(
    tmp_path, sample_grid_data, preference, expected
):
    field = sample_grid_data["point_data"]["temperature"]
    sample_grid_data["point_data"] = {
        "parameter": field,
        "Con_Nb_1": field,
        "Con_Nb_2": field,
    }
    h5, xmf = tmp_path / "data.h5", tmp_path / "data.xdmf"
    with HDF5Writer(str(h5)) as writer:
        writer.write(sample_grid_data)
    XDMFGenerator(str(h5), sample_grid_data, first_fields=preference).generate(str(xmf))
    assert [
        a.get("Name") for a in etree.parse(str(xmf)).findall(".//Attribute")
    ] == expected


def test_unmatched_priority_rejected(tmp_path, sample_grid_data):
    h5, xmf = tmp_path / "data.h5", tmp_path / "data.xdmf"
    with HDF5Writer(str(h5)) as writer:
        writer.write(sample_grid_data)
    with pytest.raises(ValueError, match="missing"):
        XDMFGenerator(str(h5), sample_grid_data, first_fields=["missing"]).generate(
            str(xmf)
        )
    assert not xmf.exists()


def test_unmatched_cli_preference_preserves_existing_outputs(
    sample_vts_file, tmp_path, monkeypatch
):
    h5, xmf = tmp_path / "saved.h5", tmp_path / "saved.xdmf"
    h5.write_bytes(b"original HDF5")
    xmf.write_bytes(b"original descriptor")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vts2h5",
            str(sample_vts_file.parent),
            "-o",
            str(tmp_path),
            "--output-name",
            "saved",
            "-f",
            "missing",
            "-s",
            "-j",
            "1",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    assert h5.read_bytes() == b"original HDF5"
    assert xmf.read_bytes() == b"original descriptor"
