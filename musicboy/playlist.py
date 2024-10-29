import random
from dataclasses import dataclass


@dataclass
class SongMetadata:
    title: str
    duration: int
    url: str


class Playlist:
    playlist: list[str]

    def __init__(self, playlist: list[str] = []):
        self.playlist = playlist
        self.metadata = {}
        self.discarded = []
        self.idx = 0

    def _trim_past_songs(self, to_idx: int):
        self.discarded.extend(self.playlist[:to_idx])
        self.playlist = self.playlist[to_idx:]
        self.idx = 0

    def shuffle(self):
        np, *rest = self.playlist
        random.shuffle(rest)
        self.playlist = [np, *rest]

    def move_song_id_to_position(self, url: str, position: int):
        if position > len(self.playlist) - 1:
            raise ValueError("Position out of range")

        if url not in self.playlist:
            raise ValueError("URL not in playlist")

        self.playlist.insert(position, self.playlist.pop(self.playlist.index(url)))

    @property
    def current(self) -> SongMetadata:
        if self.idx < 0:
            self.idx = 0
        url = self.playlist[self.idx]

        return self.metadata[url]

    def goto(self, idx: int):
        if 0 > idx > len(self.playlist) - 1:
            raise ValueError("Index out of range")

        self._trim_past_songs(idx)

        return self.current

    def next(self):
        new_idx = self.idx + 1
        if new_idx > len(self.playlist) - 1:
            self.playlist = list(reversed(self.discarded))

        self._trim_past_songs(new_idx)

        return self.current

    def prev(self):
        new_idx = self.idx - 1
        if new_idx < 0 and len(self.discarded) > 0:
            self.playlist.insert(0, self.discarded.pop(-1))

        self.idx = new_idx if new_idx >= 0 else 0
        return self.current
