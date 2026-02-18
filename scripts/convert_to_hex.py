# /// script
# dependencies = [
#  "Pillow",
#  "fire",
# ]
# requires-python = ">=3.8"
# ///
from PIL import Image
import fire
import json


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def convert_to_color(
    input_path,
    output_path,
    from_color_hex="#000000",
    to_color_hex="#FFFFFF",
    tolerance=30,
    color_map: dict = None,
):
    """
    Converts pixels of specified colors in an image.

    Can either convert a single 'from' color to a 'to' color, or apply multiple
    transformations using a color map.

    :param input_path: Path to the input PNG file.
    :param output_path: Path to save the output PNG file.
    :param from_color_hex: Hexadecimal color code of the color to change (e.g., '#000000' for black).
                           Used if color_map is not provided.
    :param to_color_hex: Hexadecimal color code of the target color (e.g., '#FF5733').
                         Used if color_map is not provided.
    :param tolerance: Integer specifying the color matching tolerance (0-255).
    :param color_map: A JSON string representing a dictionary of hex color codes to
                      hex color codes (e.g., '{"#000000": "#FF0000", "#FFFFFF": "#0000FF"}').
                      If provided, overrides from_color_hex and to_color_hex.
    """
    try:
        img = Image.open(input_path).convert("RGBA")

        color_transformations = []
        if color_map:
            # color_map_dict = json.loads(color_map)
            color_map_dict = color_map
            for from_hex, to_hex in color_map_dict.items():
                color_transformations.append(
                    (_hex_to_rgb(from_hex), _hex_to_rgb(to_hex))
                )
        else:
            from_color_rgb = _hex_to_rgb(from_color_hex)
            to_color_rgb = _hex_to_rgb(to_color_hex)
            color_transformations.append((from_color_rgb, to_color_rgb))

        new_img = Image.new("RGBA", img.size, (0, 0, 0, 0))

        pixels = img.load()
        new_pixels = new_img.load()
        for y in range(img.size[1]):
            for x in range(img.size[0]):
                r, g, b, a = pixels[x, y]
                current_pixel_rgb = (r, g, b)

                transformed = False
                for from_rgb, to_rgb in color_transformations:
                    if (
                        abs(r - from_rgb[0]) < tolerance
                        and abs(g - from_rgb[1]) < tolerance
                        and abs(b - from_rgb[2]) < tolerance
                    ):

                        new_pixels[x, y] = (*to_rgb, a)
                        transformed = True
                        break  # Apply only the first matching transformation

                if not transformed:
                    new_pixels[x, y] = (r, g, b, a)

        new_img.save(output_path, format="PNG")
        print(f"Image successfully saved to {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")


# Example usage
if __name__ == "__main__":
    fire.Fire(convert_to_color)

