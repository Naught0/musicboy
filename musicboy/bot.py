from collections.abc import MutableMapping

from discord.ext import commands

from musicboy.playlist import Playlist, cache_next_songs
from musicboy.progress import ProgressTracker


class MusicBoy(commands.Bot):
    enabled_extensions = ["playback"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlists: MutableMapping[int, Playlist] = {}
        self.progress: MutableMapping[int, ProgressTracker] = {}

    async def setup_hook(self) -> None:
        for cmd in self.enabled_extensions:
            await self.load_extension(f"musicboy.commands.{cmd}")

        for pl in self.playlists.values():
            cache_next_songs(pl)
