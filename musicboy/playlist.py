from __future__ import annotations

import random
import typing
from functools import wraps
from pathlib import Path
from typing import NotRequired, TypedDict

from asyncer import asyncify

from musicboy.constants import DEFAULT_DATA_DIR
from musicboy.sources.youtube.youtube import (
    SongMetadata,
    fetch_metadata,
    spawn_audio_download,
)


def get_song_path(song_id: str, base_dir: str = DEFAULT_DATA_DIR) -> Path | None:
    try:
        path = next(Path(base_dir).glob(f"{song_id}.*"))
    except StopIteration:
        return None

    return path


def cache_song(song: SongMetadata, path: Path):
    return spawn_audio_download(song["url"], str(path))


cache_song_async = asyncify(cache_song)


if typing.TYPE_CHECKING:
    from musicboy.database import Database


async def cache_next_songs(playlist: Playlist, db: Database, data_dir=DEFAULT_DATA_DIR):
    for url in playlist.playlist[playlist.idx + 1 : playlist.idx + 4]:
        meta = await asyncify(db.get_metadata)(url=url)
        if meta is None:
            meta = await fetch_metadata(url)

        if get_song_path(meta["video_id"]) is None:
            await cache_song_async(meta, Path(data_dir) / meta["video_id"])


def write_state_after(func):
    @wraps(func)
    def wrapper(self: Playlist, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.write_state()
        return result

    return wrapper


class PlaylistExhausted(Exception):
    pass


class PlaylistState(TypedDict):
    guild_id: int
    playlist: NotRequired[list[str]]
    idx: int
    volume: float


class Playlist:
    playlist: list[str]
    idx: int

    def __init__(
        self,
        guild_id: int,
        db: Database,
        playlist: list[str] = [],
        idx: int = 0,
        loop=False,
        volume=0.05,
    ):
        self.db = db
        self.idx = idx
        self.playlist = playlist or []
        self.loop = loop
        self.guild_id = guild_id
        self._volume = volume

    def init_state(self):
        self._load_state(self.db.get_state(self.guild_id))

    @property
    def volume(self):
        return self._volume

    @volume.setter
    @write_state_after
    def volume(self, value: float):
        self._volume = value

    def _load_state(self, state: PlaylistState):
        self.playlist = state.get("playlist", [])
        self.idx = state["idx"]
        self.guild_id = state["guild_id"]
        self.volume = state["volume"] if state["volume"] >= 1 else state["volume"] * 100

    @classmethod
    def from_state(cls: type[Playlist], state: PlaylistState, db: Database):
        self = cls(
            state["guild_id"],
            playlist=state.get("playlist", []),
            idx=state["idx"],
            volume=state["volume"],
            db=db,
        )

        return self

    def write_state(self):
        self.db.write_state({**self.state, "volume": self.volume})
        self.db.write_playlist(self.guild_id, self.playlist)

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
    def move_song(self, current_idx: int, new_pos: int):
        new_idx = new_pos - 1
        if 0 > new_idx > len(self.playlist) - 1:
            raise ValueError("Position out of range")

        current_idx = current_idx - 1
        if 0 > current_idx > len(self.playlist) - 1:
            raise ValueError("Position out of range")

        self.playlist.insert(new_idx, self.playlist.pop(current_idx))

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
        self.db.write_playlist(self.guild_id, self.playlist)

    @write_state_after
    def remove_index(self, idx: int):
        self.playlist.pop(self.idx + idx - 1)
        self.db.write_playlist(self.guild_id, self.playlist)

    @write_state_after
    def remove_song(self, url: str, all=False):
        if all:
            self.playlist = [u for u in self.playlist if u != url]
        else:
            self.playlist.remove(url)

        self.db.write_playlist(self.guild_id, self.playlist)
