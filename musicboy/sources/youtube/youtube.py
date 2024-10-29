from pathlib import Path

import yt_dlp


def download_audio(url: str, filename: Path) -> Path:
    """Download best audio from YouTube URL to specified filename."""
    opts = {
        "format": "bestaudio",
        "outtmpl": filename,
        "quiet": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }
        ],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return filename
