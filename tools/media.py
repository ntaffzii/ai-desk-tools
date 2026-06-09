"""Media and desktop interaction MCP tools."""

from __future__ import annotations

import subprocess
import time
import urllib.parse
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def register(mcp) -> None:
    """Register media tools."""

    @mcp.tool()
    def open_website(url: str) -> dict:
        """Open a website in the user's default browser."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return {"success": False, "error": "invalid_url", "url": url}
        webbrowser.open(url)
        return {"success": True, "url": url}

    @mcp.tool()
    def play_and_search_youtube(song_name: str) -> dict:
        """Open YouTube search for a song. GUI clicking is intentionally not automatic."""
        query = urllib.parse.quote(song_name)
        url = f"https://www.youtube.com/results?search_query={query}"
        webbrowser.open(url)
        return {"success": True, "url": url, "note": "Opened YouTube search results. User or GUI tool can choose a result."}

    @mcp.tool()
    def play_audio_background(song_name: str) -> dict:
        """Stream first YouTube audio result through mpv if yt-dlp and mpv are installed."""
        import shutil

        ytdlp = shutil.which("yt-dlp")
        mpv = shutil.which("mpv")
        if not ytdlp:
            return {"success": False, "error": "yt-dlp_not_found"}
        if not mpv:
            return {"success": False, "error": "mpv_not_found"}

        try:
            result = subprocess.run(
                [ytdlp, f"ytsearch1:{song_name}", "--get-url", "--format", "bestaudio"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            stream_url = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
            if not stream_url:
                return {"success": False, "error": "stream_not_found", "stderr": result.stderr}
            subprocess.Popen([mpv, "--no-video", stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "song_name": song_name}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    def press_system_media_key(action: str) -> dict:
        """Press a system media key using PyAutoGUI."""
        key_map = {
            "play_pause": "playpause",
            "next": "nexttrack",
            "previous": "prevtrack",
            "volume_up": "volumeup",
            "volume_down": "volumedown",
            "mute": "volumemute",
        }
        if action not in key_map:
            return {"success": False, "error": "invalid_action", "valid_actions": list(key_map)}
        try:
            import pyautogui

            pyautogui.press(key_map[action])
            return {"success": True, "action": action}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    def inspect_image(path: str) -> dict:
        """Return basic image metadata."""
        image_path = Path(path).expanduser().resolve()
        if not image_path.exists():
            return {"success": False, "error": "file_not_found", "path": str(image_path)}
        try:
            from PIL import Image
        except ImportError:
            return {"success": False, "error": "pillow_not_installed"}
        with Image.open(image_path) as image:
            return {"success": True, "path": str(image_path), "width": image.width, "height": image.height, "mode": image.mode, "format": image.format}

    @mcp.tool()
    def extract_video_frame(path: str, timestamp_seconds: float, output_path: str | None = None) -> dict:
        """Extract one frame from a video using OpenCV."""
        video_path = Path(path).expanduser().resolve()
        if not video_path.exists():
            return {"success": False, "error": "file_not_found", "path": str(video_path)}
        try:
            import cv2
        except ImportError:
            return {"success": False, "error": "opencv_not_installed"}

        target = Path(output_path).expanduser().resolve() if output_path else video_path.with_suffix(f".frame_{int(timestamp_seconds)}.jpg")
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(timestamp_seconds * fps))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return {"success": False, "error": "frame_not_read"}
        target.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(target), frame)
        return {"success": True, "output_path": str(target)}

    @mcp.tool()
    def create_thumbnail(path: str, output_path: str, max_size: int = 512) -> dict:
        """Create an image thumbnail."""
        image_path = Path(path).expanduser().resolve()
        target = Path(output_path).expanduser().resolve()
        try:
            from PIL import Image
        except ImportError:
            return {"success": False, "error": "pillow_not_installed"}
        with Image.open(image_path) as image:
            image.thumbnail((max_size, max_size))
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target)
        return {"success": True, "output_path": str(target)}

    @mcp.tool()
    def transcribe_audio(path: str) -> dict:
        """Placeholder for transcription integration."""
        return {"success": False, "error": "transcription_not_configured", "path": str(Path(path).expanduser().resolve())}
