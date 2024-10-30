from __future__ import annotations

import json
import random
from collections.abc import MutableMapping
from functools import wraps
from pathlib import Path
from traceback import print_exc
from typing import TypedDict

from musicboy.sources.youtube.youtube import SongMetadata, download_audio, get_metadata
from musicboy.threads import run_in_thread


def get_song_path(song_id: str, base_dir: str = "musicboy/data") -> Path | None:
    try:
        path = next(Path(base_dir).glob(f"{song_id}.*"))
    except StopIteration:
        return None

    return path


def cache_song(song: SongMetadata, path: Path):
    return download_audio(song["url"], str(path))


def cache_next_songs(playlist: Playlist):
    for url in playlist.playlist[playlist.idx + 1 : playlist.idx + 4]:
        meta = playlist.metadata[url]
        if get_song_path(meta["id"]) is None:
            run_in_thread(
                lambda: download_audio(
                    meta["url"], str(Path(playlist.data_dir) / meta["id"])
                )
            )


def write_state_after(func):
    @wraps(func)
    def wrapper(self: Playlist, *args, **kwargs):
        result = func(self, *args, **kwargs)
        with self.state_path.open("w") as f:
            json.dump(self.state, f)
        return result

    return wrapper


class PlaylistExhausted(Exception):
    pass


class PlaylistState(TypedDict):
    channel_id: int
    playlist: list[str]
    idx: int
    metadata: MutableMapping[str, SongMetadata]


class Playlist:
    playlist: list[str]
    data_dir: str
    metadata: MutableMapping[str, SongMetadata]
    idx: int

    def __init__(
        self,
        channel_id: int,
        data_dir: str = "musicboy/data",
        playlist: list[str] = [],
        idx: int = 0,
        metadata: MutableMapping[str, SongMetadata] = {},
        loop=False,
    ):
        self.idx = idx
        self.data_dir = data_dir
        self.playlist = playlist
        self.metadata = metadata
        self.loop = loop
        self.channel_id = channel_id

        self.state_path = Path(data_dir) / f"state_{channel_id}.json"
        try:
            with self.state_path.open() as f:
                Playlist.from_state(json.load(f))
        except FileNotFoundError:
            with open(self.state_path, "w") as f:
                json.dump(self.state, f)
        except json.JSONDecodeError:
            pass
        else:
            print("Loaded state from ", self.state_path)

        self.find_missing_metadata()

    def find_missing_metadata(self):
        for url in self.playlist:
            if url not in self.metadata:
                print("Finding metadata for", url)
                self.metadata[url] = get_metadata(url)

    @classmethod
    def from_state(cls: type[Playlist], state: PlaylistState):
        self = cls(
            state["channel_id"],
            playlist=state["playlist"],
            idx=state["idx"],
            metadata=state["metadata"],
        )

        return self

    def _write_state(self):
        with self.state_path.open("w") as f:
            json.dump(self.state, f)

    @property
    def has_next_song(self):
        return self.idx + 1 < len(self.playlist) or self.loop

    @property
    def next_song(self):
        if not self.has_next_song:
            return None

        return self.metadata[
            self.playlist[self.idx + 1 if self.idx + 1 < len(self.playlist) else 0]
        ]

    @property
    def state(self) -> PlaylistState:
        return PlaylistState(
            playlist=self.playlist,
            idx=self.idx,
            metadata=self.metadata,
            channel_id=self.channel_id,
        )

    @property
    def current(self) -> SongMetadata:
        url = self.playlist[self.idx]
        return self.metadata[url]

    @write_state_after
    def shuffle(self):
        np, *rest = self.playlist
        random.shuffle(rest)
        self.playlist = [np, *rest]

    @write_state_after
    def move_song(self, song_position: int, new_pos: int):
        new_idx = self.idx + new_pos - 1
        if 0 > new_idx > len(self.playlist) - 1:
            raise ValueError("Position out of range")

        song_position = self.idx + song_position - 1
        if 0 > song_position > len(self.playlist) - 1:
            raise ValueError("Position out of range")

        self.playlist.insert(new_idx, self.playlist.pop(song_position))

    @write_state_after
    def prepend_song(self, url: str):
        self.playlist.insert(0 if len(self.playlist) == 0 else self.idx + 1, url)
        self.metadata[url] = get_metadata(url)

    @write_state_after
    def append_song(self, url: str):
        self.playlist.append(url)
        self.metadata[url] = get_metadata(url)

    @write_state_after
    def goto(self, idx: int):
        if 0 > idx > len(self.playlist) - 1:
            raise ValueError("Index out of range")

        self.idx = idx

        return self.current

    @write_state_after
    def next(self):
        new_idx = self.idx + 1
        if new_idx > len(self.playlist) - 1:
            if self.loop:
                new_idx = 0
            else:
                raise PlaylistExhausted("No more songs in playlist")

        self.idx = new_idx
        return self.current

    @write_state_after
    def prev(self):
        new_idx = self.idx - 1
        new_idx = new_idx if new_idx >= 0 else len(self.playlist) - 1
        self.idx = new_idx

        return self.current

    @write_state_after
    def clear(self):
        self.playlist = self.playlist[:1]
        self.idx = 0

    @write_state_after
    def remove_index(self, idx: int):
        self.playlist.pop(self.idx + idx - 1)

    @write_state_after
    def remove_song(self, url: str, all=False):
        if all:
            self.playlist = [u for u in self.playlist if u != url]
        else:
            self.playlist.remove(url)
