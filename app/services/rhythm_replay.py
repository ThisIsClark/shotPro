"""Small, silent replay kept under the same ownership and lifetime as the report."""
import logging
import subprocess


def write_rhythm_replay(source, destination, start, end):
    try:
        subprocess.run([
            "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{start:.3f}",
            "-i", str(source), "-t", f"{end-start:.3f}", "-an", "-sn", "-dn",
            "-vf", "scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
            "-c:v", "libx264", "-threads", "1", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(destination),
        ], check=True, capture_output=True, timeout=25)
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        logging.getLogger(__name__).warning("Rhythm replay unavailable (%s)", type(exc).__name__)
        destination.unlink(missing_ok=True)
        return False
