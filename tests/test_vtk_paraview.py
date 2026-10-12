"""Optional actual ParaView round trips for new geometry families."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.vtk_fixtures import KINDS, make_dataset, write_dataset
from vtk2h5.converter import convert_vtk_to_hdf5
from vtk2h5.mesh import normalize_dataset

PVPYTHON = os.environ.get("VTK2H5_PVPYTHON")
pytestmark = pytest.mark.skipif(
    not PVPYTHON, reason="Set VTK2H5_PVPYTHON to test an installed ParaView"
)


@pytest.mark.parametrize("kind", [*KINDS, "mixed_cells"])
@pytest.mark.parametrize(
    "dims",
    [
        (4, 3, 2),
        (4, 3, 1),
        (4, 1, 3),
        (1, 4, 3),
        (4, 1, 1),
        (1, 4, 1),
        (1, 1, 4),
        (1, 1, 1),
    ],
)
def test_geometry_roundtrip(tmp_path, kind, dims):
    inputs, expected = [], []
    for step in (0, 10):
        dataset = make_dataset(kind, step, dims)
        data = normalize_dataset(dataset, "fixture")
        inputs.append(
            write_dataset(dataset, tmp_path / f"step{step}.{KINDS.get(kind, 'vtu')}")
        )
        record = {
            "time": step,
            "first_field": "scalar",
            "points": data["points"].tolist(),
        }
        if "dimensions" in data:
            record["dimensions"] = data["dimensions"]
        else:
            record["cells"] = decode_topology(data["topology"])
        record.update(
            {
                center: {
                    name: {"values": values.tolist(), "dtype": str(values.dtype)}
                    for name, values in data[center].items()
                }
                for center in ("point_data", "cell_data")
            }
        )
        expected.append(record)
    h5, xmf = tmp_path / "out.h5", tmp_path / "out.xdmf"
    convert_vtk_to_hdf5(inputs, h5, xmf, jobs=1, silent=True, first_fields=["scalar"])
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps(expected))
    probe = Path(__file__).with_name("paraview_probe.py")
    result = subprocess.run(
        [
            PVPYTHON,
            "--no-mpi",
            "--disable-registry",
            str(probe),
            str(xmf),
            str(expected_path),
            "preserve",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS:" in result.stdout


def decode_topology(topology):
    """Independent decoding of XDMF expectations for ParaView's cell model."""
    cells, offset = [], 0
    types = {1: 2, 2: 4, 3: 7, 4: 5, 5: 9, 6: 10, 7: 14, 8: 13, 9: 12}
    sizes = {4: 3, 5: 4, 6: 4, 7: 5, 8: 6, 9: 8}
    while offset < len(topology):
        code = int(topology[offset])
        offset += 1
        if code in (1, 2, 3):
            size = int(topology[offset])
            offset += 1
        else:
            size = sizes[code]
        cells.append(
            {"type": types[code], "ids": topology[offset : offset + size].tolist()}
        )
        offset += size
    return cells
