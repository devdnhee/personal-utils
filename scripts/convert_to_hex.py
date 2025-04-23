from PIL import Image
import fire

def convert_to_color(input_path, output_path, color_hex="#FFFFFF"):
    """
    Converts the black areas of a pencil drawing to a specified color.

    :param input_path: Path to the input PNG file.
    :param output_path: Path to save the output PNG file.
    :param color_hex: Hexadecimal color code (e.g., '#FF5733'), default is white (#FFFFFF).
    """
    try:
        # Open the image
        img = Image.open(input_path).convert('RGBA')
        
        # Parse the hex color code into RGB
        color_hex = color_hex.lstrip('#')
        new_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        
        # Create a new image to hold the modified pixels
        new_img = Image.new('RGBA', img.size, (255, 255, 255, 0))

        # Iterate through each pixel and replace black with the new color
        pixels = img.load()
        new_pixels = new_img.load()
        for y in range(img.size[1]):
            for x in range(img.size[0]):
                r, g, b, a = pixels[x, y]
                # Check for black pixels (tolerance for grayscale drawings)
                if r < 230 and g < 230 and b < 230:  # Assuming black areas
                    new_pixels[x, y] = (*new_color, a)  # Apply new color
                else:
                    new_pixels[x, y] = (r, g, b, a)  # Preserve other areas

        # Save the new image
        new_img.save(output_path, format='PNG')
        print(f"Image successfully saved to {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
if __name__ == "__main__":
    fire.Fire(convert_to_color)
