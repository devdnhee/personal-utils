# /// script
# dependencies = [
#   "numpy>=2.2.2",
#   "pillow>=11.1.0",
#   "fire>=0.7.0",
#   "rich>=13.0.0",
# ]
# ///

import logging
import os
from collections import Counter

import fire
import numpy as np
from PIL import Image
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
log = logging.getLogger(__name__)


def hex_to_rgb(hex_color):
    """Converts hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def change_background(input_path: str, hex_color: str, output_path: str = None, tolerance: int = 30):
    """
    Changes the background color of an image.
    The background is assumed to be the majority color at the edges.

    :param input_path: Path to the input image.
    :param hex_color: Target background color in hex (e.g., '#FF0000' or 'FFFFFF').
    :param output_path: Path to save the output image. If None, appends '_new_bg' to the input filename.
    :param tolerance: Color distance tolerance to match the background (0-255).
    """
    if not os.path.exists(input_path):
        log.error(f"File '{input_path}' not found.")
        return

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_new_bg.png" # Saving as PNG to preserve quality

    try:
        # Load image and convert to RGB
        img = Image.open(input_path).convert('RGB')
        data = np.array(img)
        height, width, _ = data.shape

        # Extract edge pixels to find the majority color
        top_edge = data[0, :, :]
        bottom_edge = data[-1, :, :]
        left_edge = data[:, 0, :]
        right_edge = data[:, -1, :]

        edges = np.concatenate([top_edge, bottom_edge, left_edge, right_edge])

        # Count occurrences of each RGB color
        # Convert to tuples for hashability in Counter
        edge_colors = [tuple(c) for c in edges]
        most_common_color, _ = Counter(edge_colors).most_common(1)[0]

        log.info(f"Detected background color (RGB): {most_common_color}")

        # Convert target hex to RGB
        target_rgb = hex_to_rgb(hex_color)
        log.info(f"Changing background to (RGB): {target_rgb}")

        # Create a mask for pixels that are within the tolerance of the detected background color
        # Using Euclidean distance for color similarity
        diff = data.astype(np.float32) - np.array(most_common_color, dtype=np.float32)
        dist = np.sqrt(np.sum(diff**2, axis=-1))

        mask = dist <= tolerance

        # Apply the new color to the masked areas
        new_data = data.copy()
        new_data[mask] = target_rgb

        # Save the result
        result_img = Image.fromarray(new_data)
        result_img.save(output_path)
        log.info(f"Saved modified image to: {output_path}")

    except Exception as e:
        log.exception(f"An error occurred: {e}")

if __name__ == "__main__":
    fire.Fire(change_background)
