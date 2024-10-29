from __future__ import annotations

import json
import random
from pathlib import Path

from musicboy.sources.youtube.youtube import (SongMetadata, download_audio,
                                              get_metadata)


def get_song_path(song: SongMetadata, base_dir: str = "musicboy/data") -> Path | None:
    try:
        path = next(Path(base_dir).glob(f"{song['id']}.*"))
    except StopIteration:
        return None

    return path


def cache_song(song: SongMetadata, path: Path):
    return download_audio(song["url"], str(path))


def cache_next_songs(playlist: Playlist):
    for url in playlist.playlist[:3]:
        if get_song_path(meta := playlist.metadata[url]) is None:
            print("Caching song", meta["title"])
            cache_song(meta, Path(playlist.data_dir) / meta["id"])


class Playlist:
    playlist: list[str]

    def __init__(
        self,
        data_dir: str = "musicboy/data",
    ):
        self.idx = 0
        self.data_dir = data_dir
        self.playlist_path = f"{data_dir}/playlist.txt"
        self.metadata_path = f"{data_dir}/metadata.json"
        self.history_path = f"{data_dir}/history.txt"

        with open(self.metadata_path, "r") as meta_file:
            self.metadata = json.load(meta_file)
        with open(self.playlist_path, "r") as playlist_file:
            self.playlist = playlist_file.read().splitlines()
        with open(self.history_path, "r") as history_file:
            self.discarded = history_file.read().splitlines()

        self.find_missing_metadata()

    def _trim_past_songs(self, to_idx: int):
        self.discarded.extend(self.playlist[:to_idx])
        self.playlist = self.playlist[to_idx:]
        self.idx = 0

    def find_missing_metadata(self):
        for url in self.playlist:
            if url not in self.metadata:
                print("Finding metadata for", url)
                self.metadata[url] = get_metadata(url)

    def write_state(self):
        with open(self.playlist_path, "w") as playlist_file, open(
            self.history_path, "w"
        ) as history_file:
            playlist_file.write("\n".join(self.playlist))
            history_file.write("\n".join(self.discarded))

    def write_metadata(self):
        with open(self.metadata_path, "w") as meta_file:
            json.dump(self.metadata, meta_file)

    def shuffle(self):
        np, *rest = self.playlist
        random.shuffle(rest)
        self.playlist = [np, *rest]
        self.write_state()

    def move_song(self, url: str, position: int):
        if position > len(self.playlist) - 1:
            raise ValueError("Position out of range")

        if url not in self.playlist:
            raise ValueError("URL not in playlist")

        self.playlist.insert(position, self.playlist.pop(self.playlist.index(url)))

        self.write_state()

    @property
    def current(self) -> SongMetadata:
        if self.idx < 0:
            self.idx = 0
        url = self.playlist[self.idx]

        return self.metadata[url]

    def prepend_song(self, url: str):
        self.playlist.append(url)
        self.metadata[url] = get_metadata(url)
        self.playlist.insert(0 if len(self.playlist) == 0 else 1, url)

        self.write_state()
        self.write_metadata()

        return self.current

    def append_song(self, url: str):
        self.playlist.append(url)
        self.metadata[url] = get_metadata(url)

        self.write_state()
        self.write_metadata()

        return self.current

    def goto(self, idx: int):
        if 0 > idx > len(self.playlist) - 1:
            raise ValueError("Index out of range")

        self._trim_past_songs(idx)
        self.write_state()

        return self.current

    def next(self):
        new_idx = self.idx + 1
        if new_idx > len(self.playlist) - 1:
            self.playlist = list(reversed(self.discarded))

        self._trim_past_songs(new_idx)
        self.write_state()

        return self.current

    def prev(self):
        new_idx = self.idx - 1
        if new_idx < 0 and len(self.discarded) > 0:
            self.playlist.insert(0, self.discarded.pop(-1))

        self.idx = new_idx if new_idx >= 0 else 0
        self.write_state()

        return self.current

    def clear(self):
        self.discarded = self.playlist
        self.playlist = []
        self.write_state()
