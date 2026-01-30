"""Tests for CLI module."""

import sys
from pathlib import Path

import pytest

from vts2h5.cli import (
    display_folder_info,
    find_vts_files,
    parse_args,
)


class TestParseArgs:
    """Test cases for argument parsing."""

    def test_basic_input(self, monkeypatch):
        """Test parsing basic input folder."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1"])
        args = parse_args()

        assert args.input_folder == "data/test1"
        assert args.use_input_folder is False
        assert args.output_folder is None
        assert args.silent is False
        assert args.verbose is False

    def test_input_folder_flag(self, monkeypatch):
        """Test -i flag for output in input folder."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1", "-i"])
        args = parse_args()

        assert args.use_input_folder is True

    def test_output_folder(self, monkeypatch):
        """Test -o flag for custom output folder."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1", "-o", "results/"])
        args = parse_args()

        assert args.output_folder == "results/"

    def test_silent_flag(self, monkeypatch):
        """Test -s flag for silent mode."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1", "-s"])
        args = parse_args()

        assert args.silent is True

    def test_verbose_flag(self, monkeypatch):
        """Test -v flag for verbose mode."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1", "-v"])
        args = parse_args()

        assert args.verbose is True

    def test_output_name(self, monkeypatch):
        """Test --output-name flag."""
        monkeypatch.setattr(
            sys, "argv", ["vts2h5", "data/test1", "--output-name", "simulation"]
        )
        args = parse_args()

        assert args.output_name == "simulation"

    def test_compression_flag(self, monkeypatch):
        """Test --compression flag."""
        monkeypatch.setattr(
            sys, "argv", ["vts2h5", "data/test1", "--compression", "lzf"]
        )
        args = parse_args()

        assert args.compression == "lzf"

    def test_compression_level(self, monkeypatch):
        """Test --compression-level flag."""
        monkeypatch.setattr(
            sys, "argv", ["vts2h5", "data/test1", "--compression-level", "9"]
        )
        args = parse_args()

        assert args.compression_level == 9

    def test_jobs_flag(self, monkeypatch):
        """Test -j flag for parallel jobs."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1", "-j", "4"])
        args = parse_args()

        assert args.jobs == 4

    def test_info_flag(self, monkeypatch):
        """Test --info flag."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1", "--info"])
        args = parse_args()

        assert args.info is True

    def test_default_compression(self, monkeypatch):
        """Test default compression settings."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1"])
        args = parse_args()

        assert args.compression == "gzip"
        assert args.compression_level == 4

    def test_default_jobs(self, monkeypatch):
        """Test default jobs setting."""
        monkeypatch.setattr(sys, "argv", ["vts2h5", "data/test1"])
        args = parse_args()

        assert args.jobs == 0  # Auto-detect


class TestFindVTSFiles:
    """Test cases for find_vts_files function."""

    def test_find_files_in_folder(self, temp_dir):
        """Test finding VTS files in a folder."""
        # Create test VTS files
        (temp_dir / "step0.vts").touch()
        (temp_dir / "step100.vts").touch()
        (temp_dir / "step200.vts").touch()

        files = find_vts_files(temp_dir)

        assert len(files) == 3
        assert all(f.suffix == ".vts" for f in files)

    def test_files_sorted_by_step(self, temp_dir):
        """Test that files are sorted by step number."""
        # Create files in random order
        (temp_dir / "step200.vts").touch()
        (temp_dir / "step0.vts").touch()
        (temp_dir / "step100.vts").touch()

        files = find_vts_files(temp_dir)

        # Extract step numbers
        import re
        steps = []
        for f in files:
            match = re.search(r"step[_\s]*(\d+)", f.stem)
            if match:
                steps.append(int(match.group(1)))

        assert steps == sorted(steps)

    def test_nonexistent_folder(self):
        """Test handling of non-existent folder."""
        with pytest.raises(SystemExit):
            find_vts_files(Path("nonexistent"))

    def test_not_a_folder(self, temp_dir):
        """Test handling when path is not a folder."""
        file_path = temp_dir / "not_a_folder.txt"
        file_path.touch()

        with pytest.raises(SystemExit):
            find_vts_files(file_path)

    def test_no_vts_files(self, temp_dir):
        """Test handling when no VTS files found."""
        # Create non-VTS files
        (temp_dir / "data.txt").touch()
        (temp_dir / "info.dat").touch()

        with pytest.raises(SystemExit):
            find_vts_files(temp_dir)

    def test_mixed_files(self, temp_dir):
        """Test finding VTS files among other files."""
        # Create VTS and non-VTS files
        (temp_dir / "step0.vts").touch()
        (temp_dir / "step100.vts").touch()
        (temp_dir / "readme.txt").touch()
        (temp_dir / "data.csv").touch()

        files = find_vts_files(temp_dir)

        assert len(files) == 2
        assert all(f.suffix == ".vts" for f in files)


class TestDisplayFolderInfo:
    """Test cases for display_folder_info function."""

    def test_display_with_valid_files(self, sample_vts_files, capsys):
        """Test displaying folder information."""
        folder = sample_vts_files[0].parent

        # Should not raise an exception
        display_folder_info(folder)

        captured = capsys.readouterr()
        assert "Folder:" in captured.out
        assert "VTS files:" in captured.out
        assert "Time Series Information:" in captured.out
        assert "Grid Information:" in captured.out

    def test_display_shows_time_steps(self, sample_vts_files, capsys):
        """Test that time step information is displayed."""
        folder = sample_vts_files[0].parent

        display_folder_info(folder)

        captured = capsys.readouterr()
        assert "Time steps:" in captured.out
        assert "steps" in captured.out

    def test_display_shows_dimensions(self, sample_vts_files, capsys):
        """Test that grid dimensions are displayed."""
        folder = sample_vts_files[0].parent

        display_folder_info(folder)

        captured = capsys.readouterr()
        assert "Dimensions:" in captured.out

    def test_display_shows_arrays(self, sample_vts_files, capsys):
        """Test that point/cell arrays are displayed."""
        folder = sample_vts_files[0].parent

        display_folder_info(folder)

        captured = capsys.readouterr()
        assert "Point arrays:" in captured.out or "Cell arrays:" in captured.out


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def test_full_conversion_workflow(self, temp_dir, sample_vts_files):
        """Test complete conversion workflow."""
        from vts2h5.cli import convert_folder

        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        # Should complete without errors
        convert_folder(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            compression="gzip",
            compression_level=4,
            silent=True,
            verbose=False,
            jobs=1,
        )

        assert output_h5.exists()
        assert output_xdmf.exists()

    def test_conversion_with_verbose(self, temp_dir, sample_vts_files, capsys):
        """Test conversion with verbose output."""
        from vts2h5.cli import convert_folder

        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        convert_folder(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            compression="gzip",
            compression_level=4,
            silent=False,
            verbose=True,
            jobs=1,
        )

        captured = capsys.readouterr()
        assert "Grid Information:" in captured.out
        assert "Dimensions:" in captured.out

    def test_conversion_silent_mode(self, temp_dir, sample_vts_files, capsys):
        """Test conversion in silent mode."""
        from vts2h5.cli import convert_folder

        output_h5 = temp_dir / "output.h5"
        output_xdmf = temp_dir / "output.xdmf2"

        convert_folder(
            input_files=sample_vts_files,
            output_file=output_h5,
            xdmf_output=output_xdmf,
            compression="gzip",
            compression_level=4,
            silent=True,
            verbose=False,
            jobs=1,
        )

        captured = capsys.readouterr()
        # Should have minimal output in silent mode
        assert len(captured.out) == 0 or captured.out.strip() == ""
