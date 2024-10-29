from typing import TypedDict

import yt_dlp


class SongMetadata(TypedDict):
    id: str
    title: str
    duration: int
    url: str


def get_metadata(url: str, base_dir: str = "musicboy/data") -> SongMetadata:
    """Get metadata from YouTube URL."""
    with yt_dlp.YoutubeDL(params={"quiet": True}) as ydl:
        meta = ydl.extract_info(url, download=False, process=False)
        if meta is None:
            raise ValueError("Could not get metadata from YouTube URL")

        return SongMetadata(
            id=meta["id"],
            title=meta["title"],
            duration=meta["duration"],
            url=url,
        )


def download_audio(url: str, filename: str) -> str:
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
