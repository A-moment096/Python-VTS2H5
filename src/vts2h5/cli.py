"""Command-line interface for vts2h5."""

import argparse
import re
import sys
from pathlib import Path


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert VTK Structured Grid (VTS) files from a folder to HDF5 with XDMF2 descriptors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert data/test1 folder, output test1.h5 and test1.xdmf2 in current directory
  vts2h5 data/test1

  # Output in the same folder as input
  vts2h5 data/test1 -i

  # Output to a specific folder
  vts2h5 data/test1 -o results/

  # Use 4 parallel workers for faster conversion
  vts2h5 data/test1 -j 4

  # Use all available CPU cores
  vts2h5 data/test1 -j 0

  # Silent mode (no progress bar, minimal output)
  vts2h5 data/test1 -s

  # Verbose mode (show grid info and detailed stats)
  vts2h5 data/test1 -v

  # Custom output name with parallel processing
  vts2h5 data/test1 --output-name simulation -j 4

  # Show folder info without conversion
  vts2h5 data/test1 --info
        """,
    )

    parser.add_argument("input_folder", help="Input folder containing VTS files")

    parser.add_argument(
        "-i",
        "--input-folder",
        action="store_true",
        dest="use_input_folder",
        help="Output files in the same folder as input",
    )
    parser.add_argument(
        "-o",
        "--output-folder",
        help="Output folder path (default: current directory)",
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
        help="Number of parallel jobs for reading VTS files (default: 0 for auto, use 1 for sequential)",
    )

    parser.add_argument(
        "--info",
        action="store_true",
        help="Display folder information without conversion",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.2.0",
    )

    return parser.parse_args()


def find_vts_files(folder: Path) -> list[Path]:
    """
    Find all VTS files in a folder.

    Args:
        folder: Folder path to search

    Returns:
        Sorted list of Path objects
    """
    if not folder.exists():
        print(f"Error: Folder not found: {folder}", file=sys.stderr)
        sys.exit(1)

    if not folder.is_dir():
        print(f"Error: Not a folder: {folder}", file=sys.stderr)
        sys.exit(1)

    files = list(folder.glob("*.vts"))

    if not files:
        print(f"Error: No VTS files found in {folder}", file=sys.stderr)
        sys.exit(1)

    # Sort files numerically by step number
    def get_step_number(filepath: Path) -> int:
        match = re.search(r"step[_\s]*(\d+)", filepath.stem)
        return int(match.group(1)) if match else 0

    files.sort(key=get_step_number)
    return files


def display_folder_info(folder: Path) -> None:
    """Display information about VTS files in a folder as a time series."""
    from vts2h5.converter import extract_time_steps
    from vts2h5.reader import VTSReader

    files = find_vts_files(folder)

    print(f"\nFolder: {folder}")
    print(f"VTS files: {len(files)}")

    # Read first file to get grid information
    try:
        reader = VTSReader(str(files[0]))
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
) -> None:
    """Convert all VTS files in a folder to HDF5 as a time series."""
    from vts2h5.converter import convert_vts_to_hdf5

    # Call the converter
    stats = convert_vts_to_hdf5(
        input_files=input_files,
        output_file=output_file,
        xdmf_output=xdmf_output,
        compression=compression,
        compression_level=compression_level,
        jobs=jobs,
        silent=silent,
        verbose=verbose,
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

    input_folder = Path(args.input_folder)

    # Validate input folder
    if not input_folder.exists():
        print(f"Error: Folder not found: {input_folder}", file=sys.stderr)
        sys.exit(1)

    if not input_folder.is_dir():
        print(f"Error: Not a folder: {input_folder}", file=sys.stderr)
        sys.exit(1)

    # Info mode
    if args.info:
        display_folder_info(input_folder)
        return

    # Find all VTS files in the folder
    input_files = find_vts_files(input_folder)

    # Determine output name (default to input folder name)
    output_name = args.output_name if args.output_name else input_folder.name

    # Determine output folder
    if args.use_input_folder:
        # Output in the same folder as input
        output_folder = input_folder
    elif args.output_folder:
        # Output to specified folder
        output_folder = Path(args.output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    else:
        # Output to current working directory (default)
        output_folder = Path.cwd()

    # Build output file paths
    output_h5 = output_folder / f"{output_name}.h5"
    output_xdmf = output_folder / f"{output_name}.xdmf2"

    if not args.silent:
        print(f"Converting {len(input_files)} VTS files from {input_folder}")
        if args.verbose:
            print(f"H5:     {output_h5}")
            print(f"XDMF:   {output_xdmf}")
        print()

    # Convert all files as a time series
    convert_folder(
        input_files,
        output_h5,
        output_xdmf,
        args.compression,
        args.compression_level,
        args.silent,
        args.verbose,
        args.jobs,
    )


if __name__ == "__main__":
    main()
