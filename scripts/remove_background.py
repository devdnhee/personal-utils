# /// script
# dependencies = [
#   "opencv-python>=4.13.0.90",
#   "pillow>=11.2.1",
# ]
# ///

import cv2
import numpy as np
from PIL import Image
import fire
import os

def remove_background(input_path: str, output_path: str = None):
    """
    Removes the background from an image using OpenCV's GrabCut algorithm and Pillow.

    :param input_path: Path to the input image file.
    :param output_path: Path to save the output PNG file. If not provided, 
                        it saves as [input_filename]_no_bg.png in the same directory.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_no_bg.png"

    try:
        print(f"Processing image: {input_path}...")
        
        # Load image with OpenCV
        img = cv2.imread(input_path)
        if img is None:
            print(f"Error: Could not read image '{input_path}'.")
            return

        # Initialize mask, background and foreground models
        mask = np.zeros(img.shape[:2], np.uint8)
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)

        # Define a rectangle for GrabCut (assuming the object is centered)
        # We take a 5% margin from each side to define the probable foreground
        height, width = img.shape[:2]
        margin_h = int(height * 0.05)
        margin_w = int(width * 0.05)
        rect = (margin_w, margin_h, width - 2 * margin_w, height - 2 * margin_h)

        # Run GrabCut
        # Iterating 5 times is usually a good balance between speed and quality
        cv2.grabCut(img, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)

        # Create a mask where background is 0 (BGD/PR_BGD) and foreground is 1 (FGD/PR_FGD)
        # GrabCut labels: 0=BGD, 1=FGD, 2=PR_BGD, 3=PR_FGD
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

        # Convert to RGBA (with transparency)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Create an RGBA image
        # We use Pillow directly for easier RGBA construction from numpy array
        rgba_data = np.zeros((height, width, 4), dtype=np.uint8)
        rgba_data[:, :, :3] = img_rgb
        rgba_data[:, :, 3] = mask2 * 255

        # Convert to Pillow for saving
        output_image = Image.fromarray(rgba_data, 'RGBA')
        output_image.save(output_path)
        
        print(f"Background removed successfully. Saved to: {output_path}")

    except Exception as e:
        print(f"An error occurred during background removal: {e}")

if __name__ == "__main__":
    fire.Fire(remove_background)


