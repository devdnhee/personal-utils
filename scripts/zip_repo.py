#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fire",
#   "rich",
# ]
# ///
"""Zip all git-tracked files in the repo into a zip archive."""

import subprocess
import zipfile
from pathlib import Path

import fire
from rich.console import Console

console = Console()


def main(output: str) -> None:
    """Zip git-tracked repo content.

    Args:
        output: Output zip file path.
    """
    output_path = Path(output)
    if not output_path.suffix:
        output_path = output_path.with_suffix(".zip")

    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    files = [f for f in result.stdout.splitlines() if f]

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            path = Path(file)
            if path.exists():
                zf.write(path, file)

    console.log(f"Zipped {len(files)} files to {output_path}")


if __name__ == "__main__":
    fire.Fire(main)
