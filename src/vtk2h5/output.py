"""Publish an HDF5/descriptor pair with rollback on replacement failure."""

import shutil
import tempfile
from pathlib import Path


def temporary_sibling(target: Path) -> Path:
    """Reserve a temporary path on the target filesystem."""
    with tempfile.NamedTemporaryFile(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False
    ) as file:
        return Path(file.name)


def publish_pair(
    temporary_h5: Path, temporary_xdmf: Path, output_h5: Path, output_xdmf: Path
) -> None:
    """Replace both targets, restoring the previous state on any failure.

    This is rollback-safe for ordinary exceptions, not crash-atomic across
    the two filesystem replacements. Backups are retained if rollback fails.
    """
    backups = {}
    installed = []
    recoverable = True
    try:
        for target in (output_h5, output_xdmf):
            if target.exists():
                backup = temporary_sibling(target)
                backups[target] = backup
                shutil.copy2(target, backup)
        for temporary, target in (
            (temporary_h5, output_h5),
            (temporary_xdmf, output_xdmf),
        ):
            temporary.replace(target)
            installed.append(target)
    except BaseException:
        recoverable = False
        for target in reversed(installed):
            if target in backups:
                # copy2 leaves a recovery backup available if restoration fails.
                shutil.copy2(backups[target], target)
            else:
                target.unlink(missing_ok=True)
        recoverable = True
        raise
    finally:
        # Only remove backups when targets have been restored or installed.
        # A failed restoration exits before this success flag can be set.
        if recoverable:
            for backup in backups.values():
                backup.unlink(missing_ok=True)
