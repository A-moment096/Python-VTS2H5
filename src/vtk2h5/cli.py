"""Command-line interface for vtk2h5."""

import argparse
import re
import sys
from pathlib import Path

from vtk2h5 import __version__
from vtk2h5.reader import SUPPORTED_FORMATS


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert VTK datasets from one or more folders to HDF5 with XDMF3 descriptors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert multiple folders, output beside each, prioritize concentration fields
  vtk2h5 data/trial1 data/trial2 -n -f con

  # Convert folder `data`, output data.h5 and data.xdmf in current directory
  vtk2h5 data

  # Output in the same folder as input
  vtk2h5 data -i

  # Output to a specific folder
  vtk2h5 data -o results/

  # Use 4 parallel workers for faster conversion
  vtk2h5 data -j 4

  # Use all available CPU cores
  vtk2h5 data -j 0

  # Silent mode (no progress bar, minimal output)
  vtk2h5 data -s

  # Verbose mode (show grid info and detailed stats)
  vtk2h5 data -v

  # Custom output name with parallel processing
  vtk2h5 data --output-name simulation -j 4

  # Show folder info without conversion
  vtk2h5 data --info
        """,
    )

    parser.add_argument(
        "input_folders", nargs="+", help="Input folders containing VTK datasets"
    )
    location = parser.add_mutually_exclusive_group()

    location.add_argument(
        "-i",
        "--input-folder",
        action="store_true",
        dest="use_input_folder",
        help="Output files in the same folder as input",
    )
    location.add_argument(
        "-o",
        "--output-folder",
        help="Output folder path (default: current directory)",
    )
    location.add_argument(
        "-n",
        "--beside-input",
        action="store_true",
        help="Output next to each input folder, in its parent directory",
    )
    parser.add_argument(
        "-f",
        "--first-field",
        action="append",
        default=[],
        metavar="FIELD",
        help="Prioritize a field by case-insensitive name or prefix; repeat to set priority order",
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        help="Silent mode: no progress bar, minimal output",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose mode: show grid info and detailed statistics",
    )
    parser.add_argument(
        "--output-name",
        help="Custom name for output files (default: input folder name)",
    )

    parser.add_argument(
        "--compression",
        choices=["gzip", "lzf", "none"],
        default="gzip",
        help="Compression algorithm (default: gzip)",
    )
    parser.add_argument(
        "--compression-level",
        type=int,
        default=4,
        choices=range(0, 10),
        metavar="[0-9]",
        help="Compression level for gzip (default: 4)",
    )

    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=0,
        metavar="N",
        help="Number of parallel jobs for reading VTK files (default: 0 for auto, use 1 for sequential)",
    )

    parser.add_argument(
        "--info",
        action="store_true",
        help="Display folder information without conversion",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--float-dtype",
        choices=["preserve", "float32", "float64"],
        default="preserve",
        help="Floating-point field storage (default: preserve). Geometry stays float64; "
        "integers retain their type.",
    )
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        type=lambda value: value.lower().lstrip("."),
        choices=SUPPORTED_FORMATS,
        metavar="EXT",
        help="Select an input extension; repeat to include several (default: all supported formats)",
    )
    args = parser.parse_args()
    if args.output_name and len(args.input_folders) != 1:
        parser.error("--output-name requires exactly one input folder")
    if args.output_name and (
        args.output_name in (".", "..")
        or "/" in args.output_name
        or "\\" in args.output_name
    ):
        parser.error("--output-name must be a file stem, not a path")
    if any(not field.strip() for field in args.first_field):
        parser.error("--first-field must not be empty")
    # Preserve the previous parse_args attribute for single-folder callers.
    args.input_folder = args.input_folders[0] if len(args.input_folders) == 1 else None
    return args


def default_output_name(input_folder: Path) -> str:
    """
    Return the default output name derived from the input folder.

    ``Path(".").name`` is empty for the current directory, so resolve the
    folder first and fall back to its directory name.
    """
    name = input_folder.resolve().name
    return name or "output"


def find_vtk_files(folder: Path, formats=None) -> list[Path]:
    """Discover selected serial formats deterministically and without recursion."""
    if not folder.is_dir():
        print(f"Error: Folder not found or not a folder: {folder}", file=sys.stderr)
        raise SystemExit(1)
    selected = {value.lower().lstrip(".") for value in (formats or SUPPORTED_FORMATS)}
    if not selected.issubset(SUPPORTED_FORMATS):
        raise ValueError(f"Unsupported formats: {selected - set(SUPPORTED_FORMATS)}")
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower().lstrip(".") in selected
    ]
    if not files:
        print(f"Error: No supported VTK files found in {folder}", file=sys.stderr)
        raise SystemExit(1)

    def order(path):
        match = re.search(r"step[_\s]*(\d+)", path.stem)
        return (int(match.group(1)) if match else 0, path.name.casefold(), path.name)

    return sorted(files, key=order)


def find_vts_files(folder: Path) -> list[Path]:
    """Compatibility discovery function restricted to VTS."""
    return find_vtk_files(folder, ["vts"])


def display_folder_info(folder: Path, formats=None) -> None:
    """Display information about VTK files in a folder as a time series."""
    from vtk2h5.converter import extract_time_steps
    from vtk2h5.reader import VTKReader

    files = find_vtk_files(folder, formats)

    print(f"\nFolder: {folder}")
    print(
        f"{'VTS' if all(p.suffix.lower() == '.vts' for p in files) else 'VTK'} files: {len(files)}"
    )

    # Read first file to get grid information
    try:
        reader = VTKReader(str(files[0]))
        info = reader.get_info()

        # Extract time steps from filenames
        time_steps = extract_time_steps(files)

        # Calculate total original size
        total_size = sum(f.stat().st_size for f in files)

        print("\nTime Series Information:")
        print(
            f"  Time steps:    {len(time_steps)} steps (from {min(time_steps)} to {max(time_steps)})"
        )
        print(f"  Total size:    {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")

        print("\nGrid Information:")
        print(f"  Dataset type:  {info['dataset_type']}")
        if "dimensions" in info:
            print(f"  Dimensions:    {info['dimensions']}")
        print(f"  Points:        {info['num_points']:,}")
        print(f"  Cells:         {info['num_cells']:,}")

        if info["point_arrays"]:
            print(f"  Point arrays:  {', '.join(info['point_arrays'])}")
        if info["cell_arrays"]:
            print(f"  Cell arrays:   {', '.join(info['cell_arrays'])}")

        print()

    except Exception as e:
        print(f"Error reading files: {e}", file=sys.stderr)


def convert_folder(
    input_files: list[Path],
    output_file: Path,
    xdmf_output: Path,
    compression: str,
    compression_level: int,
    silent: bool,
    verbose: bool,
    jobs: int = 0,
    float_dtype: str = "preserve",
    first_fields=None,
) -> None:
    """Convert all VTK files in a folder to HDF5 as a time series."""
    from vtk2h5.converter import convert_vtk_to_hdf5

    # Call the converter
    stats = convert_vtk_to_hdf5(
        input_files=input_files,
        output_file=output_file,
        xdmf_output=xdmf_output,
        compression=compression,
        compression_level=compression_level,
        jobs=jobs,
        silent=silent,
        verbose=verbose,
        float_dtype=float_dtype,
        first_fields=first_fields,
    )

    # Display results
    if silent:
        return

    if not verbose:
        print(f"\nH5:     {output_file}")
        print(f"XDMF:   {xdmf_output}")
    else:
        print("\n✓ Conversion complete!")

        if stats["grid_info"]:
            grid_info = stats["grid_info"]
            print("\nGrid Information:")
            print(f"  Dataset type:  {grid_info['dataset_type']}")
            if "dimensions" in grid_info:
                print(f"  Dimensions:    {grid_info['dimensions']}")
            print(f"  Points:        {grid_info['num_points']:,}")
            print(f"  Cells:         {grid_info['num_cells']:,}")
            if grid_info["point_arrays"]:
                print(f"  Point arrays:  {', '.join(grid_info['point_arrays'])}")

        print("\nOutput:")
        print(f"  H5 file:       {output_file}")
        print(f"  XDMF file:     {xdmf_output}")
        print(f"  Files:         {stats['num_files']} files")
        print(f"  Original size: {stats['total_original_size']:,} bytes")
        print(f"  Converted:     {stats['converted_size']:,} bytes")
        print(f"  Reduction:     {stats['reduction_ratio']:.1f}%")


def main():
    """Main entry point for the CLI."""
    args = parse_args()

    folders = [Path(folder).expanduser().resolve() for folder in args.input_folders]
    # Plan every destination before converting, so a batch cannot overwrite itself.
    plans = []
    destinations = set()
    for folder in folders:
        input_files = find_vtk_files(folder, args.formats)
        if args.info:
            plans.append((folder, input_files, None, None))
            continue
        name = args.output_name or default_output_name(folder)
        if args.use_input_folder:
            output_folder = folder
        elif args.beside_input:
            output_folder = folder.parent
        elif args.output_folder:
            output_folder = Path(args.output_folder).expanduser().resolve()
        else:
            output_folder = Path.cwd()
        output_h5 = output_folder / f"{name}.h5"
        output_xdmf = output_folder / f"{name}.xdmf"
        for destination in (output_h5, output_xdmf):
            if destination in destinations:
                print(
                    f"Error: Multiple inputs target {destination}; use -i or -n to separate outputs",
                    file=sys.stderr,
                )
                sys.exit(1)
            destinations.add(destination)
        plans.append((folder, input_files, output_h5, output_xdmf))

    for folder, input_files, output_h5, output_xdmf in plans:
        if args.info:
            display_folder_info(folder, args.formats)
            continue
        output_h5.parent.mkdir(parents=True, exist_ok=True)
        if not args.silent:
            print(f"Converting {len(input_files)} VTK files from {folder}")
            if args.verbose:
                print(f"H5:     {output_h5}")
                print(f"XDMF:   {output_xdmf}")
            print()
        convert_folder(
            input_files,
            output_h5,
            output_xdmf,
            args.compression,
            args.compression_level,
            args.silent,
            args.verbose,
            args.jobs,
            args.float_dtype,
            args.first_field,
        )


if __name__ == "__main__":
    main()
