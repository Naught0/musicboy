from __future__ import annotations

import json
import random
from functools import wraps
from pathlib import Path
from typing import TypedDict

from asyncer import asyncify

from musicboy.database import Database
from musicboy.sources.youtube.youtube import SongMetadata, download_audio


def get_song_path(song_id: str, base_dir: str = "musicboy/data") -> Path | None:
    try:
        path = next(Path(base_dir).glob(f"{song_id}.*"))
    except StopIteration:
        return None

    return path


def cache_song(song: SongMetadata, path: Path):
    return download_audio(song["url"], str(path))


cache_song_async = asyncify(cache_song)


def _cache_next_songs(playlist: Playlist, db: Database):
    for url in playlist.playlist[playlist.idx + 1 : playlist.idx + 4]:
        meta = db.get_metadata(url)
        if meta is None:
            continue

        if get_song_path(meta["id"]) is None:
            download_audio(meta["url"], str(Path(playlist.data_dir) / meta["id"]))


cache_next_songs = asyncify(_cache_next_songs)


def write_state_after(func):
    @wraps(func)
    def wrapper(self: Playlist, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self._write_state()
        return result

    return wrapper


class PlaylistExhausted(Exception):
    pass


class PlaylistState(TypedDict):
    guild_id: int
    playlist: list[str]
    idx: int
    volume: float


class Playlist:
    playlist: list[str]
    data_dir: str
    idx: int

    def __init__(
        self,
        guild_id: int,
        db: Database,
        data_dir: str = "musicboy/data",
        playlist: list[str] = [],
        idx: int = 0,
        loop=False,
        volume=0.05,
    ):
        self.db = db
        self.idx = idx
        self.data_dir = data_dir
        self.playlist = playlist
        self.loop = loop
        self.guild_id = guild_id
        self._volume = volume

        self.state_path = Path(data_dir) / f"state_{guild_id}.json"
        try:
            with self.state_path.open() as f:
                self._load_state(json.load(f))
        except FileNotFoundError:
            with open(self.state_path, "w") as f:
                json.dump(self.state, f)
        except json.JSONDecodeError:
            pass
        else:
            print("Loaded state from ", self.state_path)

    @property
    def volume(self):
        return self._volume

    @volume.setter
    @write_state_after
    def volume(self, value: float):
        self._volume = value

    def _load_state(self, state: PlaylistState):
        self.playlist = state["playlist"]
        self.idx = state["idx"]
        self.guild_id = state["guild_id"]
        self.volume = state["volume"] if state["volume"] >= 1 else state["volume"] / 100

    @classmethod
    def from_state(cls: type[Playlist], state: PlaylistState, db: Database):
        self = cls(
            state["guild_id"],
            playlist=state["playlist"],
            idx=state["idx"],
            volume=state["volume"],
            db=db,
        )

        return self

    def _write_state(self):
        self.db.write_state({**self.state, "volume": self.volume * 100})

    @property
    def has_next_song(self):
        return self.idx + 1 < len(self.playlist) or self.loop

    @property
    def next_song(self):
        if not self.has_next_song:
            return None

        return self.playlist[self.idx + 1 if self.idx + 1 < len(self.playlist) else 0]

    @property
    def state(self) -> PlaylistState:
        return PlaylistState(
            playlist=self.playlist,
            idx=self.idx,
            guild_id=self.guild_id,
            volume=self.volume,
        )

    @property
    def current(self) -> str:
        return self.playlist[self.idx]

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

    @write_state_after
    def append_song(self, url: str):
        self.playlist.append(url)

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
        self.playlist = []
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
