from collections.abc import Mapping, MutableMapping

from discord.ext import commands

from musicboy.playlist import Playlist, cache_next_songs
from musicboy.progress import ProgressTracker


class MusicBot(commands.Bot):
    enabled_extensions = ["playback"]

    def __init__(self, *args, playlist: Playlist, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlist = playlist
        self.progress: MutableMapping[int, ProgressTracker] = {}

    async def setup_hook(self) -> None:
        for cmd in self.enabled_extensions:
            await self.load_extension(f"musicboy.commands.{cmd}")

        cache_next_songs(self.playlist)
