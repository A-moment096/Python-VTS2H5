"""VTS to HDF5 converter module."""

import re
import sys
import xml.etree.ElementTree as ET
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any


def read_vts_file_worker(filepath: str) -> tuple[dict, int]:
    """
    Worker function to read a VTS file in parallel with validation.

    Args:
        filepath: Path to VTS file

    Returns:
        Tuple of (grid_data, file_size)

    Raises:
        Exception with descriptive message if file is corrupted or invalid
    """
    from pathlib import Path

    from vts2h5.reader import VTSReader

    # Validate XML structure
    try:
        ET.parse(filepath)
    except ET.ParseError as e:
        raise ValueError(f"Corrupted XML in {Path(filepath).name}: {str(e)}") from e

    # Read VTS file
    try:
        reader = VTSReader(filepath)
        grid_data = reader.read()
        file_size = Path(filepath).stat().st_size
        return grid_data, file_size
    except Exception as e:
        raise ValueError(f"Failed to read {Path(filepath).name}: {str(e)}") from e


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


def convert_vts_to_hdf5(
    input_files: list[Path],
    output_file: Path,
    xdmf_output: Path,
    compression: str = "gzip",
    compression_level: int = 4,
    jobs: int = 0,
    silent: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Convert VTS files to HDF5 with XDMF2 descriptor.

    Args:
        input_files: List of VTS file paths
        output_file: Output HDF5 file path
        xdmf_output: Output XDMF2 file path
        compression: Compression algorithm (gzip, lzf, none)
        compression_level: Compression level for gzip (0-9)
        jobs: Number of parallel workers (0 for auto)
        silent: Suppress all output
        verbose: Show detailed information

    Returns:
        Dictionary with conversion statistics

    Raises:
        SystemExit on validation errors or conversion failures
    """
    from tqdm import tqdm

    from vts2h5.reader import VTSReader
    from vts2h5.writer import HDF5Writer
    from vts2h5.xdmf import XDMFGenerator

    try:
        comp = None if compression == "none" else compression
        comp_opts = None if compression == "none" else compression_level
        writer = HDF5Writer(
            str(output_file), compression=comp, compression_opts=comp_opts
        )

        total_original_size = 0
        first_grid_data = None
        first_grid_info = None

        # Extract time steps from filenames
        time_steps = extract_time_steps(input_files)

        # Determine number of processes
        if jobs == 0:
            num_jobs = cpu_count()
        else:
            num_jobs = max(1, jobs)

        use_multiprocessing = num_jobs > 1 and len(input_files) > 1

        if use_multiprocessing and not silent:
            print(
                f"Reading {len(input_files)} VTS files with {num_jobs} parallel workers..."
            )

        # Read VTS files (parallel if jobs > 1)
        if use_multiprocessing:
            file_paths = [str(f) for f in input_files]

            try:
                with Pool(processes=num_jobs) as pool:
                    if silent:
                        results = pool.map(read_vts_file_worker, file_paths)
                    else:
                        results = list(
                            tqdm(
                                pool.imap(read_vts_file_worker, file_paths),
                                total=len(file_paths),
                                desc="Reading files",
                                unit="file",
                            )
                        )
            except Exception as e:
                print(f"\n✗ Error reading files: {e}", file=sys.stderr)
                print("Conversion aborted. No files were written.", file=sys.stderr)
                sys.exit(1)

            # Unpack results and validate consistency
            grid_data_list = [r[0] for r in results]
            file_sizes = [r[1] for r in results]
            total_original_size = sum(file_sizes)

            first_grid_data = grid_data_list[0]
            reference_dims = first_grid_data["dimensions"]

            # Validate all files have same dimensions
            for i, grid_data in enumerate(grid_data_list[1:], 1):
                if grid_data["dimensions"] != reference_dims:
                    print(
                        f"\n✗ Dimension mismatch in {input_files[i].name}!",
                        file=sys.stderr,
                    )
                    print(
                        f"  Expected: {reference_dims}, Got: {grid_data['dimensions']}",
                        file=sys.stderr,
                    )
                    print("Conversion aborted. No files were written.", file=sys.stderr)
                    sys.exit(1)

            if verbose:
                reader = VTSReader(str(input_files[0]))
                first_grid_info = reader.get_info()

            # Write to HDF5 (sequential, HDF5 is not thread-safe)
            if not silent:
                print("Writing to HDF5...")

            iterator = enumerate(grid_data_list)
            if not silent:
                iterator = tqdm(
                    iterator,
                    total=len(grid_data_list),
                    desc="Writing to HDF5",
                    unit="file",
                )

            for i, grid_data in iterator:
                writer.write(grid_data, time_step=time_steps[i])

        else:
            # Sequential processing
            iterator = (
                input_files
                if silent
                else tqdm(input_files, desc="Converting files", unit="file")
            )
            reference_dims = None

            try:
                for i, input_file in enumerate(iterator):
                    reader = VTSReader(str(input_file))
                    grid_data = reader.read()

                    if i == 0:
                        first_grid_data = grid_data
                        reference_dims = grid_data["dimensions"]
                        if verbose:
                            first_grid_info = reader.get_info()
                    else:
                        # Validate dimensions consistency
                        if grid_data["dimensions"] != reference_dims:
                            print(
                                f"\n✗ Dimension mismatch in {input_file.name}!",
                                file=sys.stderr,
                            )
                            print(
                                f"  Expected: {reference_dims}, Got: {grid_data['dimensions']}",
                                file=sys.stderr,
                            )
                            print(
                                "Conversion aborted. Cleaning up partial output...",
                                file=sys.stderr,
                            )
                            writer.close()
                            if output_file.exists():
                                output_file.unlink(missing_ok=True)
                            sys.exit(1)

                    writer.write(grid_data, time_step=time_steps[i])
                    total_original_size += input_file.stat().st_size

            except Exception as e:
                print(f"\n✗ Error reading {input_file.name}: {e}", file=sys.stderr)
                print(
                    "Conversion aborted. Cleaning up partial output...", file=sys.stderr
                )
                writer.close()
                if output_file.exists():
                    output_file.unlink(missing_ok=True)
                sys.exit(1)

        writer.close()

        # Generate XDMF descriptor
        if first_grid_data:
            if not silent:
                print("Generating XDMF2 descriptor...")

            XDMFGenerator.generate_temporal_collection(
                str(output_file),
                str(xdmf_output),
                time_steps=time_steps,
                time_values=[float(s) for s in time_steps],
                dimensions=first_grid_data["dimensions"],
                point_arrays=list(first_grid_data["point_data"].keys()),
                cell_arrays=list(first_grid_data["cell_data"].keys()),
            )

        # Calculate statistics
        converted_size = output_file.stat().st_size
        ratio = (1 - converted_size / total_original_size) * 100

        return {
            "total_original_size": total_original_size,
            "converted_size": converted_size,
            "reduction_ratio": ratio,
            "num_files": len(input_files),
            "grid_info": first_grid_info,
        }

    except Exception as e:
        print(f"\nError during conversion: {e}", file=sys.stderr)
        sys.exit(1)
