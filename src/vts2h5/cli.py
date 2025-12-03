"""Command-line interface for vts2h5."""

import argparse
import sys
from pathlib import Path
from typing import List
import re
from tqdm import tqdm

from .reader import VTSReader
from .writer import HDF5Writer
from .xdmf import XDMFGenerator


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

  # Silent mode (no progress bar, minimal output)
  vts2h5 data/test1 -s

  # Verbose mode (show grid info and detailed stats)
  vts2h5 data/test1 -v

  # Custom output name
  vts2h5 data/test1 --output-name simulation

  # Combine custom name with output folder
  vts2h5 data/test1 --output-name simulation -o results/

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
        "--info",
        action="store_true",
        help="Display folder information without conversion",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser.parse_args()


def find_vts_files(folder: Path) -> List[Path]:
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
        match = re.search(r'step[_\s]*(\d+)', filepath.stem)
        return int(match.group(1)) if match else 0
    
    files.sort(key=get_step_number)
    return files


def display_folder_info(folder: Path) -> None:
    """Display information about VTS files in a folder."""
    files = find_vts_files(folder)
    
    print(f"\nFolder: {folder}")
    print(f"VTS files found: {len(files)}")
    print()

    for filepath in files:
        try:
            reader = VTSReader(str(filepath))
            info = reader.get_info()

            print(f"  {filepath.name}:")
            print(f"    Dimensions: {info['dimensions']}")
            print(f"    Points: {info['num_points']:,}, Cells: {info['num_cells']:,}")
            print(f"    Point arrays: {', '.join(info['point_arrays'][:3])}" + 
                  (f" ... ({len(info['point_arrays'])} total)" if len(info['point_arrays']) > 3 else ""))
            print()

        except Exception as e:
            print(f"  Error reading {filepath.name}: {e}", file=sys.stderr)


def convert_folder(
    input_files: List[Path],
    output_file: Path,
    xdmf_output: Path,
    compression: str,
    compression_level: int,
    silent: bool,
    verbose: bool,
) -> None:
    """Convert all VTS files in a folder to HDF5 as a time series."""
    try:
        comp = None if compression == "none" else compression
        writer = HDF5Writer(str(output_file), compression=comp, compression_opts=compression_level)

        total_original_size = 0
        first_grid_data = None
        first_grid_info = None
        
        # Extract time steps from filenames
        time_steps = []
        for i, f in enumerate(input_files):
            match = re.search(r'step[_\s]*(\d+)', f.stem)
            if match:
                time_steps.append(int(match.group(1)))
            else:
                # Use file index if no step number found
                time_steps.append(i)

        # Process files with progress bar
        iterator = input_files if silent else tqdm(input_files, desc="Converting files", unit="file")
        
        for i, input_file in enumerate(iterator):
            reader = VTSReader(str(input_file))
            grid_data = reader.read()

            if i == 0:
                first_grid_data = grid_data
                if verbose:
                    first_grid_info = reader.get_info()

            writer.write(grid_data, time_step=time_steps[i])
            total_original_size += input_file.stat().st_size

        writer.close()

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

        # Report file sizes
        converted_size = output_file.stat().st_size
        ratio = (1 - converted_size / total_original_size) * 100

        if silent:
            print(f"H5:     {output_file}")
            print(f"XDMF:   {xdmf_output}")
        elif verbose:
            print(f"\n✓ Conversion complete!")
            if first_grid_info:
                print(f"\nGrid Information:")
                print(f"  Dimensions:    {first_grid_info['dimensions']}")
                print(f"  Points:        {first_grid_info['num_points']:,}")
                print(f"  Cells:         {first_grid_info['num_cells']:,}")
                print(f"  Point arrays:  {', '.join(first_grid_info['point_arrays'])}")
                if first_grid_info['cell_arrays']:
                    print(f"  Cell arrays:   {', '.join(first_grid_info['cell_arrays'])}")
            print(f"\nOutput:")
            print(f"  H5 file:       {output_file}")
            print(f"  XDMF file:     {xdmf_output}")
            print(f"  Files:         {len(input_files)} files")
            print(f"  Original size: {total_original_size:,} bytes")
            print(f"  Converted:     {converted_size:,} bytes")
            print(f"  Reduction:     {ratio:.1f}%")
        else:
            print(f"\nH5:     {output_file}")
            print(f"XDMF:   {xdmf_output}")

    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)


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
    )


if __name__ == "__main__":
    main()
