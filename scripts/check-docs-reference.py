"""Fail if docs/reference is out of date with the docstrings in src/seriousdb.

Used by both .github/workflows/docs.yml and the "docs-reference" hook in
.pre-commit-config.yaml, so the check is defined once. Run directly with:

    uv run --group docs python scripts/check_docs_reference.py
"""

from __future__ import annotations

import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPHINX_SRC = ROOT / "docs" / "_sphinx"
REFERENCE = ROOT / "docs" / "reference"

FIX_COMMAND = (
    "uv run --group docs sphinx-build -b markdown "
    "-d docs/_build/doctrees docs/_sphinx docs/reference"
)


def _diff(dcmp: filecmp.dircmp, rel: Path = Path()) -> list[str]:
    """Collect every path that differs or is missing on one side, recursively.

    Parameters
    ----------
    dcmp : filecmp.dircmp
        Comparison to walk.
    rel : pathlib.Path, optional
        Path prefix to report, used when recursing into subdirectories.

    Returns
    -------
    list of str
        One entry per differing or missing file, relative to the compared
        directories' roots.
    """
    mismatches = [
        str(rel / name)
        for name in (*dcmp.diff_files, *dcmp.left_only, *dcmp.right_only)
    ]
    for name, sub_dcmp in dcmp.subdirs.items():
        mismatches += _diff(sub_dcmp, rel / name)
    return mismatches


def main() -> int:
    """Build the reference into a scratch directory and diff it against docs/reference.

    Returns
    -------
    int
        Process exit code: 0 if docs/reference is up to date, non-zero
        otherwise (a Sphinx build failure or a content mismatch).
    """
    with tempfile.TemporaryDirectory() as scratch:
        built = Path(scratch) / "reference"
        doctrees = Path(scratch) / "doctrees"

        result = subprocess.run(
            [
                "sphinx-build",
                "-b",
                "markdown",
                "-W",
                "-d",
                str(doctrees),
                str(SPHINX_SRC),
                str(built),
            ],
            check=False,
        )

        if result.returncode != 0:
            return result.returncode

        mismatches = sorted(_diff(filecmp.dircmp(built, REFERENCE)))

    if mismatches:
        print(
            "\ndocs/reference is out of date with the docstrings in src/seriousdb.\n"
            "Differing or missing files:\n"
            + "\n".join(f"  - {path}" for path in mismatches)
            + f"\n\nRegenerate it and commit the result:\n\n  {FIX_COMMAND}\n",
            file=sys.stderr,
        )
        return 1

    print("docs/reference is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
