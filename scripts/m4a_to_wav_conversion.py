import os
import subprocess
import shutil
import fire
from typing import Optional


def convert_m4a_directory_to_wav(
    input_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    ffmpeg_path: Optional[str] = "ffmpeg",
):
    """
    Recursively finds .m4a files in input_dir, converts them to .wav
    using FFmpeg, and places them in the corresponding structure
    within output_dir.

    This function can be used as a command-line tool via Python Fire.

    Args:
        input_dir (str): The root directory containing .m4a files (e.g., 'directory').
                         This becomes a required positional argument in the CLI.
        output_dir (str, optional): The root directory to save .wav files.
                                     If not provided (or None), saves .wav files
                                     alongside original .m4a files.
                                     Use --output_dir=path/to/output in the CLI.
                                     Defaults to None.
        ffmpeg_path (str): Path to the FFmpeg executable.
                           Use --ffmpeg_path=/path/to/ffmpeg in the CLI.
                           Defaults to 'ffmpeg', assuming it's in the system PATH.

    Raises:
        FileNotFoundError: If input_dir doesn't exist or ffmpeg_path is invalid.
        RuntimeError: If FFmpeg conversion fails.
    """
    # 1. Validate inputs
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    if not shutil.which(ffmpeg_path):
        if not os.path.exists(ffmpeg_path) or not os.path.isfile(ffmpeg_path):
            raise FileNotFoundError(
                f"FFmpeg executable not found at '{ffmpeg_path}'. "
                "Ensure FFmpeg is installed and in your PATH, or provide the full path."
            )

    if output_dir is None:
        output_dir = input_dir  # Convert in-place
        print(
            f"Output directory not specified. Saving .wav files alongside .m4a files in '{input_dir}'."
        )
    elif not os.path.exists(output_dir):
        print(f"Output directory '{output_dir}' does not exist. Creating it.")
        os.makedirs(output_dir)  # Create the root output directory

    # 2. Walk through the directory tree
    converted_count = 0
    failed_count = 0
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.lower().endswith(".m4a"):
                input_m4a_path = os.path.join(root, filename)
                relative_path = os.path.relpath(root, input_dir)
                current_output_dir = os.path.join(output_dir, relative_path)

                # Create the output subdirectory if it doesn't exist
                if not os.path.exists(current_output_dir):
                    os.makedirs(current_output_dir)

                # Create the full output wav path
                base_filename, _ = os.path.splitext(filename)
                output_wav_path = os.path.join(
                    current_output_dir, base_filename + ".wav"
                )

                print(f"Converting: {input_m4a_path}  ==>  {output_wav_path}")

                # 3. Construct and run the FFmpeg command
                command = [
                    ffmpeg_path,
                    "-i",
                    input_m4a_path,
                    "-acodec",
                    "pcm_s16le",  # Standard WAV codec
                    # You can add other options here if needed, e.g.:
                    # "-ar", "44100", # Sample rate
                    # "-ac", "1",     # Mono channel
                    "-y",  # Overwrite output without asking
                    output_wav_path,
                ]

                try:
                    # Use capture_output=True to hide ffmpeg's console noise
                    # Add check=True to raise CalledProcessError on failure
                    result = subprocess.run(
                        command, check=True, capture_output=True, text=True
                    )
                    # print(f"Successfully converted: {output_wav_path}") # Uncomment for more verbose success logs
                    # FFmpeg often prints info to stderr, even on success
                    # print("FFmpeg output (stderr):\n", result.stderr)
                    converted_count += 1
                except subprocess.CalledProcessError as e:
                    print(f"--- FAILED to convert: {input_m4a_path} ---")
                    print(f"Error Code: {e.returncode}")
                    print(f"FFmpeg Command: {' '.join(e.cmd)}")
                    print(f"FFmpeg stderr:\n{e.stderr}")
                    print(f"FFmpeg stdout:\n{e.stdout}")
                    failed_count += 1
                except Exception as e:
                    print(f"--- FAILED to convert: {input_m4a_path} ---")
                    print(f"An unexpected error occurred: {e}")
                    failed_count += 1

    print("\n--- Conversion Summary ---")
    print(f"Successfully converted: {converted_count} file(s)")
    print(f"Failed conversions:     {failed_count} file(s)")
    print(f"Output directory:       {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    fire.Fire(convert_m4a_directory_to_wav)
