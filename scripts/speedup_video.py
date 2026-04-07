# /// script
# dependencies = [
#   "fire",
#   "rich>=13.0.0",
# ]
# ///

import logging
import os
import shutil
import subprocess

import fire
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
log = logging.getLogger(__name__)


def speedup_video(
    input: str,
    output: str,
    factor: float = 2.0,
):
    """
    Speeds up a video file by the given factor using FFmpeg.
    Both video and audio streams are adjusted to match the new speed.

    Args:
        input (str): Path to the input video file.
        output (str): Path to the output video file.
        factor (float): Speed multiplier. Defaults to 2.0 (2x speed).
    """
    if not os.path.isfile(input):
        raise FileNotFoundError(f"Input file not found: {input}")
    if factor <= 0:
        raise ValueError(f"Speed factor must be positive, got {factor}")
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError(
            "FFmpeg not found. Ensure it is installed and available in PATH."
        )

    output_dir = os.path.dirname(output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # atempo filter is limited to [0.5, 100.0]; chain multiple filters for extreme factors
    audio_filters = _build_atempo_chain(factor)
    video_filter = f"setpts={1.0 / factor}*PTS"

    command = [
        "ffmpeg",
        "-i", input,
        "-filter:v", video_filter,
        "-filter:a", audio_filters,
        "-y",
        output,
    ]

    log.info(f"Speeding up '{input}' by {factor}x  →  '{output}'")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        log.info("Done.")
    except subprocess.CalledProcessError as e:
        log.error(f"FFmpeg failed (exit code {e.returncode}):\n{e.stderr}")
        raise


def _build_atempo_chain(factor: float) -> str:
    """Build a chained atempo filter string for factors outside [0.5, 100.0]."""
    filters = []
    remaining = factor
    # atempo only accepts values in [0.5, 100.0]
    while remaining > 100.0:
        filters.append("atempo=100.0")
        remaining /= 100.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining}")
    return ",".join(filters)


if __name__ == "__main__":
    fire.Fire(speedup_video)
