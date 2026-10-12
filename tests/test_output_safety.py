"""Failed conversion and publication never destroy a previous output pair."""

import pytest

from tests.vtk_fixtures import make_dataset, write_dataset
from vtk2h5.converter import convert_vtk_to_hdf5
from vtk2h5.output import publish_pair
from vtk2h5.xdmf import XDMFGenerator


def test_descriptor_failure(tmp_path, monkeypatch):
    path = write_dataset(make_dataset("image"), tmp_path / "step0.vti")
    h5, xmf = tmp_path / "out.h5", tmp_path / "out.xdmf"
    h5.write_bytes(b"oldh5")
    xmf.write_bytes(b"oldxmf")

    def fail(*args, **kwargs):
        raise ValueError("descriptor failed")

    monkeypatch.setattr(XDMFGenerator, "generate_temporal_collection", fail)
    with pytest.raises(SystemExit):
        convert_vtk_to_hdf5([path], h5, xmf, jobs=1, silent=True)
    assert h5.read_bytes() == b"oldh5"
    assert xmf.read_bytes() == b"oldxmf"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "out.h5",
        "out.xdmf",
        "step0.vti",
    ]


@pytest.mark.parametrize("existing", [True, False])
def test_second_replace_failure(tmp_path, monkeypatch, existing):
    from pathlib import Path

    h5, xmf = tmp_path / "out.h5", tmp_path / "out.xdmf"
    first, second = tmp_path / "temp.h5", tmp_path / "temp.xdmf"
    if existing:
        h5.write_bytes(b"oldh5")
        xmf.write_bytes(b"oldxmf")
    first.write_bytes(b"newh5")
    second.write_bytes(b"newxmf")
    replace = Path.replace

    def fail(self, target):
        if self == second:
            raise OSError("injected replacement failure")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(OSError):
        publish_pair(first, second, h5, xmf)
    if existing:
        assert h5.read_bytes() == b"oldh5"
        assert xmf.read_bytes() == b"oldxmf"
    else:
        assert not h5.exists()
        assert not xmf.exists()


def test_successful_replace(tmp_path):
    paths = [tmp_path / name for name in ("temp.h5", "temp.xdmf", "out.h5", "out.xdmf")]
    for path, contents in zip(paths, [b"newh5", b"newxmf", b"oldh5", b"oldxmf"]):
        path.write_bytes(contents)
    publish_pair(*paths)
    assert paths[2].read_bytes() == b"newh5"
    assert paths[3].read_bytes() == b"newxmf"
    assert not paths[0].exists()
    assert not paths[1].exists()


@pytest.mark.parametrize("jobs", [1, 2])
def test_truncated_legacy_preserves_pair(tmp_path, jobs):
    first = write_dataset(make_dataset("structured"), tmp_path / "step0.vtk", "ascii")
    second = write_dataset(make_dataset("structured"), tmp_path / "step10.vtk", "ascii")
    second.write_text(second.read_text().rsplit(" ", 12)[0])
    h5, xmf = tmp_path / "out.h5", tmp_path / "out.xdmf"
    h5.write_bytes(b"oldh5")
    xmf.write_bytes(b"oldxmf")
    with pytest.raises(SystemExit):
        convert_vtk_to_hdf5([first, second], h5, xmf, jobs=jobs, silent=True)
    assert h5.read_bytes() == b"oldh5"
    assert xmf.read_bytes() == b"oldxmf"
