from typing import NotRequired, TypedDict

import yt_dlp
from asyncer import asyncify


class SongMetadata(TypedDict):
    id: NotRequired[int]
    video_id: str
    title: str
    duration: int
    url: str


def _fetch_metadata(url: str) -> SongMetadata:
    """Get metadata from YouTube URL."""
    with yt_dlp.YoutubeDL(params={"quiet": True}) as ydl:
        meta = ydl.extract_info(url, download=False, process=False)
        if meta is None:
            raise ValueError("Could not get metadata from YouTube URL")

        return SongMetadata(
            video_id=meta["id"],
            title=meta["title"],
            duration=meta["duration"],
            url=url,
        )


fetch_metadata = asyncify(_fetch_metadata)


def download_audio(url: str, filename: str) -> str:
    """Download best audio from YouTube URL to specified filename."""
    print(f"Downloading audio for {url} to {filename}")
    opts = {
        "format": "m4a/bestaudio/best",
        "outtmpl": filename,
        "quiet": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            }
        ],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return filename
