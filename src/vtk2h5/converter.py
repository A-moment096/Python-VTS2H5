"""Convert serial VTK datasets into fixed-mesh HDF5/XDMF3 series."""

import re
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any

from lxml import etree

from vtk2h5.output import publish_pair, temporary_sibling
from vtk2h5.reader import VTKReader
from vtk2h5.writer import TIMESERIES_GROUP, HDF5Writer
from vtk2h5.xdmf import XDMFGenerator


def read_vtk_file_worker(filepath: str) -> tuple[dict, int]:
    try:
        return VTKReader(filepath).read(), Path(filepath).stat().st_size
    except Exception as exc:
        raise ValueError(f"Failed to read {Path(filepath).name}: {exc}") from exc


def read_vts_file_worker(filepath: str) -> tuple[dict, int]:
    """Compatibility entry point, including the historical XML diagnostic."""
    try:
        return read_vtk_file_worker(filepath)
    except ValueError as exc:
        # Only classify failed reads; valid raw-appended XML never reaches
        # this general-purpose parser.
        import xml.etree.ElementTree as ET

        try:
            ET.parse(filepath)
        except ET.ParseError as parse_error:
            raise ValueError(
                f"Corrupted XML in {Path(filepath).name}: {parse_error}"
            ) from exc
        raise


def extract_time_steps(input_files: list[Path]) -> list[int]:
    """
    Extract time step numbers from VTS filenames.

    Args:
        input_files: List of VTS file paths

    Returns:
        List of time step numbers
    """
    time_steps = []
    for i, f in enumerate(input_files):
        match = re.search(r"step[_\s]*(\d+)", f.stem)
        if match:
            time_steps.append(int(match.group(1)))
        else:
            # Use file index if no step number found
            time_steps.append(i)
    return time_steps


def convert_vtk_to_hdf5(
    input_files: list[Path],
    output_file: Path,
    xdmf_output: Path,
    compression: str = "gzip",
    compression_level: int = 4,
    jobs: int = 0,
    silent: bool = False,
    verbose: bool = False,
    float_dtype: str = "preserve",
    first_fields=None,
) -> dict[str, Any]:
    """Convert a fixed-mesh time series, preserving old outputs on failure."""
    from tqdm import tqdm

    temporaries = []
    try:
        inputs = [Path(path) for path in input_files]
        if not inputs:
            raise ValueError("Input files must be nonempty")
        output_file, xdmf_output = Path(output_file), Path(xdmf_output)
        if output_file.resolve() == xdmf_output.resolve():
            raise ValueError("HDF5 and XDMF destinations must differ")
        if any(
            target.resolve() == source.resolve()
            for target in (output_file, xdmf_output)
            for source in inputs
        ):
            raise ValueError("Output must not replace an input file")
        steps = extract_time_steps(inputs)
        if len(set(steps)) != len(steps):
            raise ValueError(
                "Duplicate time steps in input filenames; separate independent series"
            )
        if any(b <= a for a, b in zip(steps, steps[1:])):
            raise ValueError("Time steps must be strictly increasing")
        count = min(len(inputs), cpu_count() if jobs == 0 else max(1, jobs))
        total = sum(path.stat().st_size for path in inputs)
        first = VTKReader(str(inputs[0])).read()
        XDMFGenerator.validate_first_fields(first, first_fields)
        for target in (output_file, xdmf_output):
            temporaries.append(temporary_sibling(target))
        temporary_h5, temporary_xmf = temporaries
        comp = None if compression == "none" else compression
        writer = HDF5Writer(
            str(temporary_h5),
            compression=comp,
            compression_opts=compression_level,
            group=TIMESERIES_GROUP,
            float_dtype=float_dtype,
        )

        def write_frames(results):
            iterator = zip(steps, results)
            if not silent:
                iterator = tqdm(
                    iterator, total=len(inputs), desc="Converting files", unit="file"
                )
            for step, grid in iterator:
                writer.write(grid, time_step=step)

        try:
            if count > 1 and len(inputs) > 1:
                if not silent:
                    print(
                        f"Reading {len(inputs)} VTK files with {count} parallel workers..."
                    )
                with Pool(processes=count) as pool:
                    # Ordered imap keeps time order and streams results to the writer.
                    results = pool.imap(read_vtk_file_worker, map(str, inputs[1:]))
                    from itertools import chain

                    write_frames(chain([first], (result[0] for result in results)))
            else:
                from itertools import chain

                write_frames(
                    chain([first], (VTKReader(str(path)).read() for path in inputs[1:]))
                )
        finally:
            writer.close()
        XDMFGenerator.generate_temporal_collection(
            str(temporary_h5),
            str(temporary_xmf),
            steps,
            hdf5_group=TIMESERIES_GROUP,
            point_arrays=list(first["point_data"]),
            cell_arrays=list(first["cell_data"]),
            first_fields=first_fields,
            hdf5_reference=str(output_file),
        )
        etree.parse(str(temporary_xmf))
        size = temporary_h5.stat().st_size
        publish_pair(temporary_h5, temporary_xmf, output_file, xdmf_output)
        info = {
            key: first[key]
            for key in (
                "dataset_type",
                "geometry_type",
                "num_points",
                "num_cells",
                "bounds",
            )
        }
        if "dimensions" in first:
            info["dimensions"] = first["dimensions"]
        info.update(
            point_arrays=list(first["point_data"]), cell_arrays=list(first["cell_data"])
        )
        return {
            "total_original_size": total,
            "converted_size": size,
            "reduction_ratio": (1 - size / total) * 100,
            "num_files": len(inputs),
            "grid_info": info if verbose else None,
        }
    except Exception as exc:
        print(f"Error during conversion: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        for path in temporaries:
            path.unlink(missing_ok=True)


def convert_vts_to_hdf5(*args, **kwargs) -> dict[str, Any]:
    """Compatibility wrapper for the generic converter."""
    return convert_vtk_to_hdf5(*args, **kwargs)
