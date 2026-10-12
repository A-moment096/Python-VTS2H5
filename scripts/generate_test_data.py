"""Generate reproducible datasets for manual VTK/XDMF testing."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.vtk_fixtures import KINDS, make_dataset, write_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    examples = {**KINDS, "mixed_cells": "vtu", "legacy_structured": "vtk"}
    for kind, ext in examples.items():
        for step in (0, 10):
            path = args.output_directory / kind / f"step_{step}.{ext}"
            if path.exists():
                parser.error(f"Refusing to overwrite {path}")
    for kind, ext in examples.items():
        for step in (0, 10):
            dataset = make_dataset(
                "structured" if kind == "legacy_structured" else kind, step
            )
            path = write_dataset(
                dataset,
                args.output_directory / kind / f"step_{step}.{ext}",
                "binary" if ext == "vtk" else "appended",
            )
            print(f"{dataset.GetClassName()}: {path}")


if __name__ == "__main__":
    main()
